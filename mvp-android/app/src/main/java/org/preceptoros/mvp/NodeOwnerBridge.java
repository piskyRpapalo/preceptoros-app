package org.preceptoros.mvp;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.webkit.WebView;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import javax.net.ssl.HttpsURLConnection;

/**
 * «Create my node» from the installed APP. Origin + main frame verified like DeploymentJoinBridge.
 * The owner seed and heartbeat key live in getFilesDir()/node-owner and never reach JavaScript;
 * JS only receives the public state. Creating the identity and raising the building each need a
 * second, native confirmation. While the APP is open it finishes the admission once the Sovereign
 * has approved; periodic heartbeats belong to the owner-consented HeartbeatPresenceService.
 */
final class NodeOwnerBridge {
    private static final String API = "https://api.preceptoros.org";
    private static final Set<String> PATHS = Set.of("/api/v1/deployment-requests", "/api/v1/cedulas",
        "/api/v1/latidos/llaves", "/api/v1/latidos", "/api/v1/edificios");
    private static final int MAX_REPLY = 8192;
    private final MainActivity activity;
    private final NodeOwner owner;
    private final ScheduledExecutorService worker = Executors.newSingleThreadScheduledExecutor();

    private NodeOwnerBridge(MainActivity activity) {
        this.activity = activity;
        this.owner = owner(activity);
    }

    static NodeOwnerBridge install(MainActivity activity, WebView web) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return null;
        NodeOwnerBridge bridge = new NodeOwnerBridge(activity);
        WebViewCompat.addWebMessageListener(web, "PreceptorNodeNative", Collections.singleton(OwnerFrameAccess.ORIGIN),
            (view, message, origin, isMainFrame, reply) -> {
                if (!OwnerFrameAccess.accepts(origin == null ? null : origin.toString(), isMainFrame,
                        activity.ownPageVerified(), view.getUrl())) {
                    bridge.reply(reply, "", Map.of("state", "NO_DATA", "cause", "origin_or_page_unverified"));
                    return;
                }
                String raw = message.getData();
                if (raw == null || raw.length() > 600) { bridge.reply(reply, "", Map.of("state", "NO_DATA", "cause", "message_out_of_range")); return; }
                activity.runOnUiThread(() -> bridge.handle(raw, reply));
            });
        // Finish the admission after approval (one first beat), while the APP is open. Never before a request exists.
        bridge.worker.scheduleWithFixedDelay(bridge::tick, 20, 120, TimeUnit.SECONDS);
        return bridge;
    }

    void close() { worker.shutdownNow(); }

    private void tick() {
        try {
            Map<String, Object> s = owner.status();
            String step = (String) s.get("step");
            // One emitter per identity: while the owner's presence service beats for this node, the APP does not.
            boolean serviceBeats = HeartbeatCredentialStore.deviceNode(activity);
            // The owner's consent is active but the service may have died (update, OEM kill): the open APP brings it back.
            if (serviceBeats) {
                try {
                    android.content.Intent service = new android.content.Intent(activity, HeartbeatPresenceService.class)
                        .setAction(HeartbeatPresenceService.ACTION_START);
                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) activity.startForegroundService(service);
                    else activity.startService(service);
                } catch (RuntimeException notAllowedNow) { /* background start refused: the next foreground tick retries */ }
            }
            // Only the admission steps advance here. Periodic beats belong to the owner-consented service alone: after
            // «Revoke and stop» an open APP must not become the old foreground emitter again (Sovereign, 2026-11-24).
            synchronized (NodeOwner.LOCK) {
                if ("awaiting_approval".equals(step) || "awaiting_map_link".equals(step)) owner.advance(Instant.now());
            }
        } catch (Exception ignored) { /* NO_DATA is shown on the next status read; never a false LIVE */ }
    }

    private void reply(JavaScriptReplyProxy target, String id, Map<String, Object> result) {
        try {
            java.util.LinkedHashMap<String, Object> out = new java.util.LinkedHashMap<>(result);
            out.put("id", id);
            String text = NodeCrypto.canonical(out);
            activity.runOnUiThread(() -> target.postMessage(text));
        } catch (Exception ignored) { /* the page times out to NO_DATA */ }
    }

    private void handle(String raw, JavaScriptReplyProxy reply) {
        String id = "";
        try {
            Object parsed = NodeCrypto.parse(raw);
            if (!(parsed instanceof Map)) throw new IllegalArgumentException();
            Map<?, ?> m = (Map<?, ?>) parsed;
            id = m.get("id") instanceof String ? (String) m.get("id") : "";
            String action = m.get("action") instanceof String ? (String) m.get("action") : "";
            if (!id.matches("[a-f0-9]{32}")) { reply(reply, "", Map.of("state", "NO_DATA", "cause", "invalid_message")); return; }
            final String rid = id;
            switch (action) {
                case "status": background(rid, reply, () -> withSuggestion(owner.status())); return;
                case "advance": background(rid, reply, () -> { synchronized (NodeOwner.LOCK) { return owner.advance(Instant.now()); } }); return;
                case "create": {
                    String node = m.get("node") instanceof String ? (String) m.get("node") : "";
                    String alias = m.get("alias") instanceof String ? (String) m.get("alias") : "";
                    if (!Boolean.TRUE.equals(m.get("consent")) || !NodeOwner.NODE.matcher(node).matches()
                            || !NodeOwner.ALIAS.matcher(alias).matches()) {
                        reply(reply, rid, Map.of("state", "NO_DATA", "cause", "invalid_or_unconsented_request")); return;
                    }
                    confirm("Create my node?",
                        "Identity: " + node + "\nPublic map name: " + alias + "\n\nThis phone creates its own owner key, which "
                        + "never leaves it, and sends a request to api.preceptoros.org. Nothing is published until the "
                        + "Sovereign approves it with the Sovereign's own signature.",
                        "Create my node", rid, reply, () -> owner.create(node, alias, deviceDigest()));
                    return;
                }
                case "build":
                    confirm("Raise my building?",
                        "One node has exactly one public building in OpenWorld. If it already exists, it is recognised, "
                        + "never duplicated. Your node must stay approved and alive for it to be shown.",
                        "Raise my building", rid, reply, () -> owner.build(Instant.now()));
                    return;
                default: reply(reply, rid, Map.of("state", "NO_DATA", "cause", "unknown_action"));
            }
        } catch (Exception malformed) {
            reply(reply, id, Map.of("state", "NO_DATA", "cause", "invalid_json_request"));
        }
    }

    /** A first-press suggestion from this device's model (e.g. TANK_3 -> tank-3); always editable on screen. */
    private static Map<String, Object> withSuggestion(Map<String, Object> status) {
        java.util.LinkedHashMap<String, Object> out = new java.util.LinkedHashMap<>(status);
        String slug = android.os.Build.MODEL == null ? "" : android.os.Build.MODEL.toLowerCase(java.util.Locale.ROOT)
            .replaceAll("[^a-z0-9]+", "-").replaceAll("^-+|-+$", "");
        if (slug.length() > 30) slug = slug.substring(0, 30).replaceAll("-+$", "");
        if (NodeOwner.ALIAS.matcher(slug).matches()) out.put("suggested_alias", slug);
        return out;
    }

    private interface Step { Map<String, Object> run() throws Exception; }
    private void background(String id, JavaScriptReplyProxy reply, Step step) {
        worker.execute(() -> {
            try { reply(reply, id, step.run()); }
            catch (Exception e) { reply(reply, id, Map.of("state", "NO_DATA", "cause", "aduana_unavailable")); }
        });
    }
    private void confirm(String title, String text, String yes, String id, JavaScriptReplyProxy reply, Step step) {
        new AlertDialog.Builder(activity).setTitle(title).setMessage(text)
            .setNegativeButton("Cancel", (d, w) -> reply(reply, id, Map.of("state", "NO_DATA", "cause", "owner_cancelled")))
            .setOnCancelListener(d -> reply(reply, id, Map.of("state", "NO_DATA", "cause", "owner_cancelled")))
            .setPositiveButton(yes, (d, w) -> {
                if (!activity.ownPageVerified()) { reply(reply, id, Map.of("state", "NO_DATA", "cause", "page_not_verified")); return; }
                background(id, reply, step);
            }).show();
    }

    /** The same installation digest the existing review request uses (one device, one claim). */
    private String deviceDigest() {
        SharedPreferences prefs = activity.getSharedPreferences("preceptoros.join.install", Activity.MODE_PRIVATE);
        String seed = prefs.getString("installation_seed", null);
        if (seed == null || !seed.matches("[a-f0-9]{64}")) {
            byte[] b = new byte[32];
            new SecureRandom().nextBytes(b);
            seed = NodeCrypto.hex(b);
            if (!prefs.edit().putString("installation_seed", seed).commit()) throw new IllegalStateException("local_identity_storage_unavailable");
        }
        return DeploymentRequestPolicy.sha256(seed);
    }

    @SuppressWarnings("unchecked")
    static NodeOwner owner(android.content.Context context) {
        return new NodeOwner(new File(context.getFilesDir(), "node-owner"), NodeOwnerBridge::post);
    }

    static NodeOwner.Reply post(String path, byte[] body, String heartbeatKey) throws Exception {
        if (!PATHS.contains(path)) throw new IllegalStateException("destination_not_authorized");
        URL url = new URL(API + path);
        HttpsURLConnection c = (HttpsURLConnection) url.openConnection();
        c.setInstanceFollowRedirects(false);
        c.setConnectTimeout(8000); c.setReadTimeout(10000);
        c.setRequestMethod("POST"); c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        c.setRequestProperty("Accept", "application/json");
        if (heartbeatKey != null) c.setRequestProperty("x-heartbeat-key", heartbeatKey);
        try {
            try (OutputStream out = c.getOutputStream()) { out.write(body); }
            int code = c.getResponseCode();
            InputStream in = code < 400 ? c.getInputStream() : c.getErrorStream();
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            if (in != null) try (InputStream input = in) {
                byte[] block = new byte[1024]; int n;
                while ((n = input.read(block)) != -1) {
                    if (bytes.size() + n > MAX_REPLY) throw new IllegalStateException("reply_too_large");
                    bytes.write(block, 0, n);
                }
            }
            String text = bytes.toString("UTF-8");
            Object json = text.isEmpty() ? null : NodeCrypto.parse(text);
            return new NodeOwner.Reply(code, json instanceof Map ? (Map<String, Object>) json : null);
        } finally { c.disconnect(); }
    }
}
