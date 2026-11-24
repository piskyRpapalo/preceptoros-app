package org.preceptoros.mvp;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import javax.net.ssl.HttpsURLConnection;

/**
 * What the public OpenWorld says about THIS phone's node, for Acho in the APP (Sovereign 2026-11-24):
 * state, cause, source and age, read natively from the gateway's world-state (one fixed HTTPS GET,
 * no cookies, nothing sent about the owner). Absence is never OFFLINE: today the gateway lists only
 * LIVE nodes, so a node it does not list is NO_DATA(node_not_in_public_feed).
 */
final class PublicNodeState {
    static final String SOURCE = "https://preceptoros.org/api/world-state";
    private static final int MAX = 256 * 1024;

    private PublicNodeState() {}

    /** Pure: classify(worldState, alias, checkedAt) → {state, cause, source, checked_at, node?, since?}. */
    @SuppressWarnings("unchecked")
    static Map<String, Object> classify(Object world, String alias, Instant checkedAt) {
        if (alias == null) return reply("NO_DATA", "no_beating_node_on_this_phone", checkedAt);
        if (!(world instanceof Map)) return reply("NO_DATA", "world_state_unreadable", checkedAt);
        Object colonia = ((Map<String, Object>) world).get("colonia");
        Object nodes = colonia instanceof Map ? ((Map<String, Object>) colonia).get("nodes") : null;
        if (!(nodes instanceof List)) return reply("NO_DATA", "world_state_without_nodes", checkedAt);
        for (Object n : (List<Object>) nodes) {
            if (!(n instanceof Map)) continue;
            Map<String, Object> node = (Map<String, Object>) n;
            if (!alias.equals(node.get("id"))) continue;
            Object seal = node.get("seal");
            if (!"LIVE".equals(seal) && !"STALE".equals(seal) && !"OFFLINE".equals(seal))
                return reply("NO_DATA", "seal_not_recognised", checkedAt);
            Map<String, Object> out = reply((String) seal, "", checkedAt);
            out.put("node", alias);
            if (node.get("since") instanceof String) out.put("since", node.get("since"));
            return out;
        }
        Map<String, Object> out = reply("NO_DATA", "node_not_in_public_feed", checkedAt);
        out.put("node", alias);
        return out;
    }

    private static Map<String, Object> reply(String state, String cause, Instant checkedAt) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("kind", "public_state");
        m.put("state", state);
        m.put("cause", cause);
        m.put("source", SOURCE);
        m.put("checked_at", checkedAt.truncatedTo(ChronoUnit.SECONDS).toString());
        return m;
    }

    /** One read of the public feed for this alias; any failure is NO_DATA with its cause, never a guess. */
    static Map<String, Object> read(String alias) {
        Instant now = Instant.now();
        if (alias == null) return classify(null, null, now);
        try {
            HttpsURLConnection c = (HttpsURLConnection) new URL(SOURCE).openConnection();
            c.setInstanceFollowRedirects(false);
            c.setConnectTimeout(8000); c.setReadTimeout(10000);
            c.setUseCaches(false);
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("Cache-Control", "no-cache");
            c.setRequestProperty("User-Agent", "PreceptorOS-Android");
            try {
                int code = c.getResponseCode();
                if (code != 200) return reply("NO_DATA", "world_state_http_" + code, now);
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (InputStream in = c.getInputStream()) {
                    byte[] block = new byte[2048]; int n;
                    while ((n = in.read(block)) != -1) {
                        if (bytes.size() + n > MAX) return reply("NO_DATA", "world_state_too_large", now);
                        bytes.write(block, 0, n);
                    }
                }
                return classify(NodeCrypto.parse(bytes.toString("UTF-8")), alias, now);
            } finally { c.disconnect(); }
        } catch (Exception e) {
            return reply("NO_DATA", "world_state_unreachable", now);
        }
    }
}
