package org.preceptoros.mvp;

import android.content.Context;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import javax.net.ssl.HttpsURLConnection;

/** One shared HTTPS implementation for both explicitly initiated and service heartbeats. */
final class HeartbeatSender {
    private static final int MAX_RESPONSE = 2048;
    private HeartbeatSender() {}

    static JSONObject send(Context context, String node, String key) throws Exception {
        long sequence = HeartbeatSequence.reserve(context, node);
        String measured = Instant.now().minusSeconds(NodeOwner.CLOCK_MARGIN_SECONDS).truncatedTo(ChronoUnit.SECONDS).toString(); // medicion_futura guard
        String body = HeartbeatOncePolicy.body(node, sequence, measured);
        URL url = new URL(HeartbeatOncePolicy.ENDPOINT);
        if (!"https".equals(url.getProtocol()) ||
                !"api.preceptoros.org".equals(url.getHost()) || url.getPort() != -1)
            throw new IllegalStateException("destination_not_authorized");
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(6000);
        connection.setReadTimeout(7000);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(body.getBytes(StandardCharsets.UTF_8).length);
        connection.setRequestProperty("Content-Type", "application/json");
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("Cache-Control", "no-store");
        connection.setRequestProperty("x-heartbeat-key", key);
        try {
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body.getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
            int status = connection.getResponseCode();
            if (status != 200 && status != 202)
                throw new IllegalStateException("heartbeat_http_" + status);
            String contentType = connection.getContentType();
            if (contentType == null || !contentType.toLowerCase().startsWith("application/json"))
                throw new IllegalStateException("receipt_content_type_invalid");
            if (connection.getContentLengthLong() > MAX_RESPONSE)
                throw new IllegalStateException("receipt_too_large");
            ByteArrayOutputStream response = new ByteArrayOutputStream();
            try (InputStream input = connection.getInputStream()) {
                byte[] block = new byte[256];
                int count;
                while ((count = input.read(block)) != -1) {
                    if (response.size() + count > MAX_RESPONSE)
                        throw new IllegalStateException("receipt_too_large");
                    response.write(block, 0, count);
                }
            }
            JSONObject reply = new JSONObject(response.toString(StandardCharsets.UTF_8.name()));
            JSONObject receipt = reply.optJSONObject("recibo");
            if (reply.length() != 2 || !"recibido".equals(reply.optString("estado")) ||
                    receipt == null || receipt.length() != 7 ||
                    !HeartbeatOncePolicy.RECEIPT.equals(receipt.optString("esquema")) ||
                    !node.equals(receipt.optString("nodo")) ||
                    !(receipt.opt("secuencia") instanceof Number) ||
                    receipt.getLong("secuencia") != sequence ||
                    !measured.equals(receipt.optString("medido_en")) ||
                    !HeartbeatOncePolicy.receipt(status, node, sequence, measured,
                            receipt.optString("recibido"), receipt.optString("payload_sha256"),
                            receipt.optString("recibo_sha256")))
                throw new IllegalStateException("receipt_unverified");
            JSONObject state = new JSONObject();
            state.put("node", node);
            state.put("sequence", sequence);
            state.put("state", "RECEIVED");
            state.put("receiptSha256", receipt.getString("recibo_sha256"));
            state.put("authority", "NONE");
            state.put("live", false);
            state.put("publicProof", "NO_DATA(public_live_not_independently_verified)");
            return state;
        } finally {
            connection.disconnect();
        }
    }

    static String safeCause(Exception error) {
        String message = error.getMessage();
        if (message != null && message.matches(
                "heartbeat_http_[0-9]{3}|receipt_unverified|receipt_content_type_invalid|" +
                        "receipt_too_large|sequence_invalid|sequence_storage_unavailable|destination_not_authorized"))
            return message;
        return "heartbeat_network_or_runtime_unavailable";
    }
}
