package org.preceptoros.mvp;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.SecureRandom;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * «Create my node» on the device: the same contracts as APP #416 (deployment-request/2, scoped plan,
 * cédula, latido-llave/1, latido/1) and Aduana's one building per admitted node. The owner seed and the
 * heartbeat key are born here, in the app's private directory, and never leave it; only public keys,
 * hashes and signatures travel. Approval is never produced here: it is the Sovereign's signed decision.
 * Pure Java (no Android API) so the whole flow runs on the JVM against a local Aduana.
 */
final class NodeOwner {
    interface Http { Reply post(String path, byte[] body, String heartbeatKey) throws Exception; }
    static final class Reply {
        final int status; final Map<String, Object> json;
        Reply(int status, Map<String, Object> json) { this.status = status; this.json = json; }
    }

    static final Pattern NODE = Pattern.compile("^nodo\\.[0-9]{1,6}\\.[a-z0-9][a-z0-9-]{0,30}$");
    static final Pattern ALIAS = Pattern.compile("^[a-z0-9][a-z0-9._-]{0,63}$");
    static final Pattern HEX64 = Pattern.compile("^[a-f0-9]{64}$");
    static final long BEAT_SECONDS = 240;
    private static final String STATE = "state.json", SEED = "owner.seed";

    private final File dir;
    private final Http http;
    private final SecureRandom random = new SecureRandom();

    NodeOwner(File dir, Http http) {
        this.dir = dir; this.http = http;
        if (!dir.isDirectory() && !dir.mkdirs()) throw new IllegalStateException("owner_directory_unavailable");
    }

    // ---- private storage ----
    private String randomHex(int bytes) { byte[] b = new byte[bytes]; random.nextBytes(b); return NodeCrypto.hex(b); }
    private void writePrivate(String name, byte[] data) throws Exception {
        File tmp = new File(dir, name + ".tmp");
        try (FileOutputStream out = new FileOutputStream(tmp)) { out.write(data); out.getFD().sync(); }
        tmp.setReadable(false, false); tmp.setReadable(true, true); tmp.setWritable(false, false); tmp.setWritable(true, true);
        if (!tmp.renameTo(new File(dir, name))) throw new IllegalStateException("private_write_failed");
    }
    private byte[] seed() throws Exception {
        File f = new File(dir, SEED);
        if (!f.exists()) writePrivate(SEED, randomHex(32).getBytes(StandardCharsets.US_ASCII));
        String hex = new String(Files.readAllBytes(f.toPath()), StandardCharsets.US_ASCII).trim();
        if (!HEX64.matcher(hex).matches()) throw new IllegalStateException("owner_seed_corrupt");
        return NodeCrypto.unhex(hex);
    }
    @SuppressWarnings("unchecked")
    Map<String, Object> state() {
        File f = new File(dir, STATE);
        if (!f.exists()) return new LinkedHashMap<>();
        try { return (Map<String, Object>) NodeCrypto.parse(new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8)); }
        catch (Exception e) { throw new IllegalStateException("node_state_corrupt"); }
    }
    private void save(Map<String, Object> s) throws Exception { writePrivate(STATE, NodeCrypto.canonicalBytes(s)); }

    private static Map<String, Object> obj(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }
    private Map<String, Object> result(String state, String step, String cause, Map<String, Object> s) {
        Map<String, Object> r = obj("state", state, "step", step, "cause", cause,
            "node", s.get("node"), "alias", s.get("alias"), "request_id", s.get("request_id"));
        Object b = s.get("building");
        if (b != null) r.put("building", b);
        Object hb = s.get("hb_hasta");
        if (hb != null) r.put("key_until", hb);
        if (s.get("last_beat") != null) r.put("last_beat", s.get("last_beat"));
        return r;
    }
    private static String iso(Instant t) { return t.truncatedTo(ChronoUnit.SECONDS).toString(); }
    private static String code(Reply r) {
        Object c = r.json == null ? null : (r.json.get("codigo") != null ? r.json.get("codigo") : r.json.get("causa"));
        if (c == null && r.json != null) c = r.json.get("cause");
        return c instanceof String && ((String) c).matches("[a-zA-Z0-9_()]{1,64}") ? (String) c : "http_" + r.status;
    }
    private Map<String, Object> signed(byte[] seed, Map<String, Object> body, String namespace) {
        Map<String, Object> out = new LinkedHashMap<>(body);
        out.put("firma_ssh", NodeCrypto.sshsig(seed, namespace, NodeCrypto.canonicalBytes(body)));
        return out;
    }

    /** What the screen shows: the next step, without touching the network. */
    Map<String, Object> status() {
        Map<String, Object> s = state();
        if (s.get("request_id") == null) return result("NO_DATA", "no_identity", "node_not_created", s);
        if (s.get("cedula_receipt") == null) return result("PENDING", "awaiting_approval", "awaiting_sovereign_approval", s);
        if (s.get("hb_key") == null) return result("PENDING", "awaiting_map_link", "alias_not_linked_yet", s);
        if (s.get("building") == null) return result("MEASURED", "ready_to_build", "cedula_verified", s);
        return result("MEASURED", "building_raised", "one_node_one_building", s);
    }

    /** Identity + owner key + deployment-request/2. Idempotent: a second press shows the same request. */
    Map<String, Object> create(String node, String alias, String deviceDigest) throws Exception {
        Map<String, Object> s = state();
        if (s.get("request_id") != null) return status();
        if (node == null || !NODE.matcher(node).matches() || alias == null || !ALIAS.matcher(alias).matches()
            || NODE.matcher(alias).matches() || deviceDigest == null || !HEX64.matcher(deviceDigest).matches())
            return result("NO_DATA", "no_identity", "invalid_node_or_alias", s);
        byte[] seed = seed();
        Map<String, Object> request = s.get("request") instanceof Map ? (Map<String, Object>) s.get("request") : null;
        if (request == null || !node.equals(request.get("node")) || !alias.equals(request.get("alias"))) {
            List<Object> roles = new ArrayList<>(); roles.add("APP_CLIENT");
            request = obj("schema", "preceptoros.deployment-request/2", "node", node, "nonce", randomHex(16),
                "device_sha256", deviceDigest, "consent", Boolean.TRUE, "owner_public_key", NodeCrypto.publicLine(seed),
                "alias", alias, "offer", obj("roles", roles));
            s = obj("node", node, "alias", alias, "request", request);
            save(s);   // the same body is resent after a network failure, so Aduana sees one request
        }
        byte[] body = NodeCrypto.canonicalBytes(request);
        String id = NodeCrypto.sha256Hex(body);
        Reply r = http.post("/api/v1/deployment-requests", body, null);
        Map<String, Object> j = r.json == null ? obj() : r.json;
        if (!DeploymentRequestPolicy.validReceipt(r.status, str(j.get("schema")), str(j.get("request_id")),
                str(j.get("state")), str(j.get("received_at")), str(j.get("authority")), str(j.get("credential")),
                str(j.get("live")), id) || !DeploymentRequestPolicy.validNotification(str(j.get("notification"))))
            return result("NO_DATA", "no_identity", r.status == 200 || r.status == 202 ? "intake_receipt_unverified" : code(r), s);
        s.put("request_id", id);
        save(s);
        return result("PENDING", "awaiting_approval", "awaiting_sovereign_approval", s);
    }
    private static String str(Object o) { return o instanceof String ? (String) o : ""; }

    /** After the Sovereign's APPROVED: cédula, then the heartbeat key born here, then one heartbeat. */
    Map<String, Object> advance(Instant now) throws Exception {
        Map<String, Object> s = state();
        if (s.get("request_id") == null) return status();
        byte[] seed = seed();
        String node = (String) s.get("node"), alias = (String) s.get("alias");
        if (s.get("cedula_receipt") == null) {
            String admin = NodeCrypto.sha256Hex(NodeCrypto.publicLine(seed).getBytes(StandardCharsets.US_ASCII));
            Map<String, Object> plan = signed(seed, obj("esquema", "preceptoros.plan-nodo/1", "accion", "crear_nodo",
                "id", node, "nodo", node, "admin_sha256", admin, "request_sha256", s.get("request_id")), "preceptoros-plan-nodo");
            plan.put("sha256", NodeCrypto.digest(plan));
            List<Object> devices = new ArrayList<>();
            devices.add(obj("clave", ((Map<?, ?>) s.get("request")).get("device_sha256"), "estado", "solicitado"));
            Map<String, Object> cedula = signed(seed, obj("esquema", "preceptoros.cedula-nodo/1", "nodo", node,
                "admin", admin, "plan_sha256", plan.get("sha256"), "dispositivos", devices), "preceptoros-cedula");
            cedula.put("sha256", NodeCrypto.digest(cedula));
            Reply r = http.post("/api/v1/cedulas", NodeCrypto.canonicalBytes(obj("cedula", cedula, "plan", plan)), null);
            if (r.status == 409) return result("PENDING", "awaiting_approval", "awaiting_sovereign_approval", s);
            Object recibo = r.json == null ? null : r.json.get("recibo");
            if ((r.status != 200 && r.status != 202) || !(recibo instanceof Map)
                || !"verificado".equals(((Map<?, ?>) recibo).get("estado")) || !cedula.get("sha256").equals(((Map<?, ?>) recibo).get("credential_sha256")))
                return result("NO_DATA", "awaiting_approval", code(r), s);
            s.put("cedula_receipt", ((Map<?, ?>) recibo).get("recibo_sha256"));
            save(s);
        }
        String until = (String) s.get("hb_hasta");
        if (s.get("hb_key") == null || until == null || Instant.parse(until).isBefore(now.plus(12, ChronoUnit.HOURS))) {
            String key = randomHex(32);
            Map<String, Object> record = signed(seed, obj("esquema", "preceptoros.latido-llave/1", "nodo", alias,
                "sha256", NodeCrypto.sha256Hex(key.getBytes(StandardCharsets.US_ASCII)),
                "desde", iso(now.minusSeconds(60)), "hasta", iso(now.plus(23 * 60 + 50, ChronoUnit.MINUTES))), "preceptoros-latido-llave");
            Reply r = http.post("/api/v1/latidos/llaves", NodeCrypto.canonicalBytes(record), null);
            if (r.status != 202 || r.json == null || !"registrada".equals(r.json.get("estado")) || !alias.equals(r.json.get("nodo"))) {
                if (s.get("hb_key") == null) return result("PENDING", "awaiting_map_link", code(r), s);
            } else {
                s.put("hb_key", key); s.put("hb_hasta", record.get("hasta"));
                save(s);
            }
        }
        return beat(now);
    }

    /** One heartbeat with the device's own key (preceptoros.latido/1, strictly increasing sequence). */
    Map<String, Object> beat(Instant now) throws Exception {
        Map<String, Object> s = state();
        if (s.get("hb_key") == null) return status();
        long last = s.get("seq") instanceof Long ? (Long) s.get("seq") : 0L;
        long seq = Math.max(last + 1, now.getEpochSecond());
        Map<String, Object> body = obj("esquema", "preceptoros.latido/1", "nodo", s.get("alias"), "secuencia", seq, "medido_en", iso(now));
        Reply r = http.post("/api/v1/latidos", NodeCrypto.canonicalBytes(body), (String) s.get("hb_key"));
        if (r.status != 202 && r.status != 200) return result("NO_DATA", (String) status().get("step"), code(r), s);
        s.put("seq", seq); s.put("last_beat", iso(now));
        save(s);
        return status();
    }

    /** One node, one building: «casa-<alias>». Pressing again recognises it and never asks for a second one. */
    Map<String, Object> build(Instant now) throws Exception {
        Map<String, Object> s = state();
        if (s.get("hb_key") == null) return status();
        String id = "casa-" + s.get("alias");
        Reply r = http.post("/api/v1/edificios", NodeCrypto.canonicalBytes(
            obj("esquema", "preceptoros.edificio-declaracion/1", "edificio", id)), (String) s.get("hb_key"));
        boolean ok = (r.status == 200 || r.status == 202) && r.json != null && id.equals(r.json.get("edificio"));
        boolean exists = r.status == 409 && "edificio_ya_asignado".equals(code(r));
        if (!ok && !exists) return result("NO_DATA", "ready_to_build", code(r), s);
        s.put("building", id);
        if (ok) s.put("building_receipt", r.json.get("recibo_sha256"));
        save(s);
        return status();
    }
}
