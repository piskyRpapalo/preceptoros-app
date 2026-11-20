package org.preceptoros.mvp;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.regex.Pattern;

/** Wire contract for Aduana's EXISTING latido receiver. This never grants node authority. */
final class HeartbeatOncePolicy {
    static final String ENDPOINT = "https://api.preceptoros.org/api/v1/latidos";
    static final String SCHEMA = "preceptoros.latido/1";
    static final String RECEIPT = "preceptoros.recibo-latido/1";
    static final String KEY_FILE = "preceptoros.heartbeat-key-local/1"; // local transport only
    private static final Pattern NODE = Pattern.compile("^nodo\\.[0-9]{1,6}\\.[a-z0-9][a-z0-9-]{0,30}$");
    private static final Pattern KEY = Pattern.compile("^[a-f0-9]{64}$");
    private static final Pattern UTC = Pattern.compile("^\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d(?:\\.\\d{1,3})?Z$");
    private static final long MAX_SEQUENCE = 9007199254740991L;
    private HeartbeatOncePolicy() {}

    static boolean node(String value) { return value != null && NODE.matcher(value).matches(); }
    static boolean key(String value) { return value != null && KEY.matcher(value).matches(); }
    static boolean sequence(long value) { return value >= 0 && value <= MAX_SEQUENCE; }
    static boolean utc(String value) {
        if (value == null || !UTC.matcher(value).matches()) return false;
        try { Instant.parse(value); return true; } catch (Exception ex) { return false; }
    }
    static String body(String node, long sequence, String measured) {
        if (!node(node) || !sequence(sequence) || !utc(measured))
            throw new IllegalArgumentException("heartbeat_shape_invalid");
        // ASCII-only and sorted keys, exactly as Aduana canonicalJson(body,true).
        String s = "{\"esquema\":\"" + SCHEMA + "\",\"medido_en\":\"" + measured
            + "\",\"nodo\":\"" + node + "\",\"secuencia\":" + sequence + "}";
        if (s.getBytes(StandardCharsets.UTF_8).length > 1024)
            throw new IllegalArgumentException("heartbeat_oversized");
        return s;
    }
    static String digest(String text) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder s = new StringBuilder(64);
            for (byte b : hash) s.append(Character.forDigit((b >>> 4) & 15, 16))
                                 .append(Character.forDigit(b & 15, 16));
            return s.toString();
        } catch (Exception ex) { throw new IllegalStateException("sha256_unavailable"); }
    }
    private static boolean eq(String supplied, String expected) {
        return supplied != null && KEY.matcher(supplied).matches() &&
            MessageDigest.isEqual(supplied.getBytes(StandardCharsets.US_ASCII),
                                  expected.getBytes(StandardCharsets.US_ASCII));
    }
    static boolean receipt(int status, String node, long sequence, String measured,
                           String received, String payloadDigest, String receiptDigest) {
        if ((status != 202 && status != 200) || !node(node) || !sequence(sequence) ||
            !utc(measured) || !utc(received)) return false;
        String payload = digest(body(node,sequence,measured));
        if (!eq(payloadDigest,payload)) return false;
        String canonical = "{\"esquema\":\"" + RECEIPT + "\",\"medido_en\":\"" + measured +
            "\",\"nodo\":\"" + node + "\",\"payload_sha256\":\"" + payload +
            "\",\"recibido\":\"" + received + "\",\"secuencia\":" + sequence + "}";
        return eq(receiptDigest,digest(canonical));
    }
}
