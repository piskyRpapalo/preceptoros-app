package org.preceptoros.mvp;

import java.io.ByteArrayOutputStream;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Pure-Java pieces of the node owner (no Android APIs, so they are testable on the JVM):
 * Ed25519 (RFC 8032), OpenSSH SSHSIG signatures, and the canonical JSON Aduana hashes
 * (sorted keys, compact separators, ASCII escapes: Python json.dumps(sort_keys, ensure_ascii)).
 * The private seed is passed in by the caller and never leaves the device.
 */
final class NodeCrypto {
    private NodeCrypto() {}

    // ---- Ed25519, RFC 8032 section 5.1 (reference arithmetic; a few signatures per day) ----
    private static final BigInteger P = BigInteger.ONE.shiftLeft(255).subtract(BigInteger.valueOf(19));
    private static final BigInteger L = BigInteger.ONE.shiftLeft(252).add(new BigInteger("27742317777372353535851937790883648493"));
    private static final BigInteger D = BigInteger.valueOf(-121665).multiply(BigInteger.valueOf(121666).modInverse(P)).mod(P);
    private static final BigInteger SQRT_M1 = BigInteger.valueOf(2).modPow(P.subtract(BigInteger.ONE).shiftRight(2), P);
    private static final BigInteger[] G;
    static {
        BigInteger gy = BigInteger.valueOf(4).multiply(BigInteger.valueOf(5).modInverse(P)).mod(P);
        BigInteger gx = recoverX(gy, 0);
        G = new BigInteger[]{gx, gy, BigInteger.ONE, gx.multiply(gy).mod(P)};
    }

    static byte[] sha512(byte[]... parts) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-512");
            for (byte[] p : parts) md.update(p);
            return md.digest();
        } catch (Exception e) { throw new IllegalStateException("sha512_unavailable"); }
    }
    static String sha256Hex(byte[] data) {
        try { return hex(MessageDigest.getInstance("SHA-256").digest(data)); }
        catch (Exception e) { throw new IllegalStateException("sha256_unavailable"); }
    }
    static String hex(byte[] b) {
        StringBuilder s = new StringBuilder(b.length * 2);
        for (byte x : b) s.append(Character.forDigit((x >> 4) & 15, 16)).append(Character.forDigit(x & 15, 16));
        return s.toString();
    }
    static byte[] unhex(String h) {
        byte[] out = new byte[h.length() / 2];
        for (int i = 0; i < out.length; i++) out[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
        return out;
    }
    private static BigInteger le(byte[] b) {
        byte[] r = new byte[b.length + 1];
        for (int i = 0; i < b.length; i++) r[b.length - i] = b[i];
        return new BigInteger(r);
    }
    private static byte[] le32(BigInteger v) {
        byte[] big = v.toByteArray(), out = new byte[32];
        for (int i = 0; i < 32 && i < big.length; i++) out[i] = big[big.length - 1 - i];
        return out;
    }
    private static BigInteger recoverX(BigInteger y, int sign) {
        BigInteger y2 = y.multiply(y);
        BigInteger x2 = y2.subtract(BigInteger.ONE).multiply(D.multiply(y2).add(BigInteger.ONE).modInverse(P)).mod(P);
        if (x2.signum() == 0) { if (sign == 1) throw new IllegalArgumentException("bad_point"); return BigInteger.ZERO; }
        BigInteger x = x2.modPow(P.add(BigInteger.valueOf(3)).shiftRight(3), P);
        if (!x.multiply(x).subtract(x2).mod(P).equals(BigInteger.ZERO)) x = x.multiply(SQRT_M1).mod(P);
        if (!x.multiply(x).subtract(x2).mod(P).equals(BigInteger.ZERO)) throw new IllegalArgumentException("bad_point");
        if (x.testBit(0) != (sign == 1)) x = P.subtract(x);
        return x;
    }
    private static BigInteger[] add(BigInteger[] a, BigInteger[] b) {
        BigInteger A = a[1].subtract(a[0]).multiply(b[1].subtract(b[0])).mod(P);
        BigInteger B = a[1].add(a[0]).multiply(b[1].add(b[0])).mod(P);
        BigInteger C = a[3].multiply(BigInteger.valueOf(2)).multiply(D).multiply(b[3]).mod(P);
        BigInteger Dd = a[2].multiply(BigInteger.valueOf(2)).multiply(b[2]).mod(P);
        BigInteger E = B.subtract(A), F = Dd.subtract(C), Gg = Dd.add(C), H = B.add(A);
        return new BigInteger[]{E.multiply(F).mod(P), Gg.multiply(H).mod(P), F.multiply(Gg).mod(P), E.multiply(H).mod(P)};
    }
    private static BigInteger[] mul(BigInteger s, BigInteger[] p) {
        BigInteger[] q = {BigInteger.ZERO, BigInteger.ONE, BigInteger.ONE, BigInteger.ZERO};
        while (s.signum() > 0) {
            if (s.testBit(0)) q = add(q, p);
            p = add(p, p);
            s = s.shiftRight(1);
        }
        return q;
    }
    private static byte[] compress(BigInteger[] p) {
        BigInteger zi = p[2].modInverse(P);
        BigInteger x = p[0].multiply(zi).mod(P), y = p[1].multiply(zi).mod(P);
        byte[] out = le32(y);
        if (x.testBit(0)) out[31] |= (byte) 0x80;
        return out;
    }
    private static BigInteger secretScalar(byte[] h) {
        byte[] a = Arrays.copyOf(h, 32);
        a[0] &= (byte) 248; a[31] &= 127; a[31] |= 64;
        return le(a);
    }
    static byte[] publicKey(byte[] seed) {
        if (seed.length != 32) throw new IllegalArgumentException("seed_32_bytes");
        return compress(mul(secretScalar(sha512(seed)), G));
    }
    static byte[] sign(byte[] seed, byte[] message) {
        byte[] h = sha512(seed);
        BigInteger a = secretScalar(h);
        byte[] pub = compress(mul(a, G));
        byte[] prefix = Arrays.copyOfRange(h, 32, 64);
        BigInteger r = le(sha512(prefix, message)).mod(L);
        byte[] rs = compress(mul(r, G));
        BigInteger k = le(sha512(rs, pub, message)).mod(L);
        BigInteger s = r.add(k.multiply(a)).mod(L);
        byte[] out = new byte[64];
        System.arraycopy(rs, 0, out, 0, 32);
        System.arraycopy(le32(s), 0, out, 32, 32);
        return out;
    }

    // ---- OpenSSH: public key line and SSHSIG armored signature (PROTOCOL.sshsig) ----
    private static void string(ByteArrayOutputStream o, byte[] b) {
        o.write((b.length >>> 24) & 255); o.write((b.length >>> 16) & 255); o.write((b.length >>> 8) & 255); o.write(b.length & 255);
        o.write(b, 0, b.length);
    }
    private static byte[] ascii(String s) { return s.getBytes(StandardCharsets.US_ASCII); }
    static byte[] publicBlob(byte[] pub) {
        ByteArrayOutputStream o = new ByteArrayOutputStream();
        string(o, ascii("ssh-ed25519")); string(o, pub);
        return o.toByteArray();
    }
    /** `ssh-ed25519 <base64>`: the exact form deployment-request/2 accepts. */
    static String publicLine(byte[] seed) {
        return "ssh-ed25519 " + Base64.getEncoder().encodeToString(publicBlob(publicKey(seed)));
    }
    static String sshsig(byte[] seed, String namespace, byte[] message) {
        byte[] blob = publicBlob(publicKey(seed));
        ByteArrayOutputStream signed = new ByteArrayOutputStream();
        signed.write(ascii("SSHSIG"), 0, 6);
        string(signed, ascii(namespace)); string(signed, new byte[0]); string(signed, ascii("sha512"));
        string(signed, sha512(message));
        ByteArrayOutputStream sigBlob = new ByteArrayOutputStream();
        string(sigBlob, ascii("ssh-ed25519")); string(sigBlob, sign(seed, signed.toByteArray()));
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(ascii("SSHSIG"), 0, 6);
        out.write(0); out.write(0); out.write(0); out.write(1);
        string(out, blob); string(out, ascii(namespace)); string(out, new byte[0]); string(out, ascii("sha512"));
        string(out, sigBlob.toByteArray());
        String b64 = Base64.getEncoder().encodeToString(out.toByteArray());
        StringBuilder armored = new StringBuilder("-----BEGIN SSH SIGNATURE-----\n");
        for (int i = 0; i < b64.length(); i += 70) armored.append(b64, i, Math.min(b64.length(), i + 70)).append('\n');
        return armored.append("-----END SSH SIGNATURE-----\n").toString();
    }

    // ---- Canonical JSON (Map, List, String, Long/Integer, Boolean, null) ----
    static String canonical(Object v) {
        StringBuilder s = new StringBuilder();
        write(s, v);
        return s.toString();
    }
    static byte[] canonicalBytes(Object v) { return ascii(canonical(v)); }
    static String digest(Object v) { return sha256Hex(canonicalBytes(v)); }
    @SuppressWarnings("unchecked")
    private static void write(StringBuilder s, Object v) {
        if (v == null) { s.append("null"); return; }
        if (v instanceof String) { quote(s, (String) v); return; }
        if (v instanceof Boolean) { s.append(((Boolean) v) ? "true" : "false"); return; }
        if (v instanceof Integer || v instanceof Long) { s.append(v.toString()); return; }
        if (v instanceof Map) {
            TreeMap<String, Object> sorted = new TreeMap<>((Map<String, Object>) v);
            s.append('{');
            boolean first = true;
            for (Map.Entry<String, Object> e : sorted.entrySet()) {
                if (!first) s.append(',');
                first = false;
                quote(s, e.getKey()); s.append(':'); write(s, e.getValue());
            }
            s.append('}');
            return;
        }
        if (v instanceof List) {
            s.append('[');
            boolean first = true;
            for (Object x : (List<Object>) v) { if (!first) s.append(','); first = false; write(s, x); }
            s.append(']');
            return;
        }
        throw new IllegalArgumentException("not_canonical_json");
    }
    // ---- Strict JSON reader for Aduana replies: Map (insertion order), List, String, Long, Double, Boolean, null ----
    static Object parse(String text) {
        int[] at = {0};
        Object v = value(text, at);
        skip(text, at);
        if (at[0] != text.length()) throw new IllegalArgumentException("json_trailing_data");
        return v;
    }
    private static void skip(String t, int[] at) {
        while (at[0] < t.length() && " \t\r\n".indexOf(t.charAt(at[0])) >= 0) at[0]++;
    }
    private static Object value(String t, int[] at) {
        skip(t, at);
        if (at[0] >= t.length()) throw new IllegalArgumentException("json_truncated");
        char c = t.charAt(at[0]);
        if (c == '{') {
            at[0]++;
            Map<String, Object> m = new java.util.LinkedHashMap<>();
            skip(t, at);
            if (t.charAt(at[0]) == '}') { at[0]++; return m; }
            while (true) {
                skip(t, at);
                Object k = value(t, at);
                if (!(k instanceof String)) throw new IllegalArgumentException("json_key");
                skip(t, at);
                if (t.charAt(at[0]++) != ':') throw new IllegalArgumentException("json_colon");
                if (m.put((String) k, value(t, at)) != null || m.size() > 512) throw new IllegalArgumentException("json_duplicate_key");
                skip(t, at);
                char n = t.charAt(at[0]++);
                if (n == '}') return m;
                if (n != ',') throw new IllegalArgumentException("json_object");
            }
        }
        if (c == '[') {
            at[0]++;
            List<Object> l = new java.util.ArrayList<>();
            skip(t, at);
            if (t.charAt(at[0]) == ']') { at[0]++; return l; }
            while (true) {
                l.add(value(t, at));
                skip(t, at);
                char n = t.charAt(at[0]++);
                if (n == ']') return l;
                if (n != ',') throw new IllegalArgumentException("json_array");
            }
        }
        if (c == '"') {
            StringBuilder s = new StringBuilder();
            at[0]++;
            while (true) {
                char x = t.charAt(at[0]++);
                if (x == '"') return s.toString();
                if (x != '\\') { s.append(x); continue; }
                char e = t.charAt(at[0]++);
                switch (e) {
                    case 'n': s.append('\n'); break; case 'r': s.append('\r'); break; case 't': s.append('\t'); break;
                    case 'b': s.append('\b'); break; case 'f': s.append('\f'); break;
                    case 'u': s.append((char) Integer.parseInt(t.substring(at[0], at[0] + 4), 16)); at[0] += 4; break;
                    default: s.append(e);
                }
            }
        }
        if (t.startsWith("true", at[0])) { at[0] += 4; return Boolean.TRUE; }
        if (t.startsWith("false", at[0])) { at[0] += 5; return Boolean.FALSE; }
        if (t.startsWith("null", at[0])) { at[0] += 4; return null; }
        int start = at[0];
        while (at[0] < t.length() && "+-0123456789.eE".indexOf(t.charAt(at[0])) >= 0) at[0]++;
        String num = t.substring(start, at[0]);
        if (num.isEmpty()) throw new IllegalArgumentException("json_value");
        return num.matches("-?[0-9]+") ? (Object) Long.parseLong(num) : (Object) Double.parseDouble(num);
    }

    private static void quote(StringBuilder s, String v) {
        s.append('"');
        for (int i = 0; i < v.length(); i++) {
            char c = v.charAt(i);
            switch (c) {
                case '"': s.append("\\\""); break;
                case '\\': s.append("\\\\"); break;
                case '\n': s.append("\\n"); break;
                case '\r': s.append("\\r"); break;
                case '\t': s.append("\\t"); break;
                case '\b': s.append("\\b"); break;
                case '\f': s.append("\\f"); break;
                default:
                    if (c < 0x20 || c > 0x7e && c != 0x7f) s.append(String.format("\\u%04x", (int) c));
                    else s.append(c);
            }
        }
        s.append('"');
    }
}
