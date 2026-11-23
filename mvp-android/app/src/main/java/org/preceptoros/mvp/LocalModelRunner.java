package org.preceptoros.mvp;

import android.app.ActivityManager;
import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Locale;

/**
 * Inference on THIS phone, inside the APP: the pinned llama.cpp fork's server, packaged in the APK as
 * libllama_server.so, runs a GGUF from the APP's own models folder. It starts only when the person sends a
 * message to a local model they picked; it listens on loopback with a fresh key per launch; it is stopped on
 * idle, on memory trim, on memory pressure and when the APP closes. A memory budget is checked BEFORE loading
 * and watched WHILE loading/generating: the phone's other apps come first.
 * Loopback is reached through a plain socket: the APP's cleartext policy stays off for every network.
 */
final class LocalModelRunner {
    interface Events { boolean emit(JSONObject event); }

    static final String DEVICE = "this-phone";
    private static final int PORT = 18431;
    private static final long HEADROOM_B = 2_500_000_000L;       // KV cache + compute buffers + room for the OS
    private static final long PRESSURE_MARGIN_B = 600_000_000L;  // stop above the system's own low-memory line
    private static final long LOAD_LIMIT_MS = 180_000;
    // One copy of the weights, file-backed (--no-repack + mmap): measured 2026-11-23 on Tank 3, the repacked
    // copy doubled RSS to 9.5 GB and lmkd killed 23 background apps. Never again without this flag.
    static final long IDLE_UNLOAD_MS = 300_000;

    private final Context ctx;
    private final SharedPreferences receipts;
    private Process proc;
    private File loaded;
    private String key;
    private volatile long lastUse;
    private volatile String lastStop = "";
    private final byte[] tail = new byte[4096];
    private int tailLen;

    LocalModelRunner(Context ctx) {
        this.ctx = ctx;
        receipts = ctx.getSharedPreferences("preceptoros.local_models", Context.MODE_PRIVATE);
    }

    File modelsDir() { return ctx.getExternalFilesDir("models"); }
    File runner() { return new File(ctx.getApplicationInfo().nativeLibraryDir, "libllama_server.so"); }
    synchronized boolean running() { return proc != null && proc.isAlive(); }
    long idleMs() { return System.currentTimeMillis() - lastUse; }

    private File[] models() {
        File dir = modelsDir();
        File[] all = dir == null ? null : dir.listFiles((d, n) -> n.endsWith(".gguf") && !n.startsWith("mmproj")
            && n.matches("[A-Za-z0-9._-]{1,120}"));
        if (all == null) return new File[0];
        Arrays.sort(all);
        return all;
    }

    File resolve(String name) {
        for (File f : models()) if (f.getName().equals(name)) return f;
        return null;
    }

    JSONObject catalog() throws JSONException {
        JSONArray out = new JSONArray();
        boolean packaged = runner().canExecute();
        ActivityManager.MemoryInfo mi = memory();
        for (File f : models()) {
            String state;
            synchronized (this) { state = running() && f.equals(loaded) ? "READY" : "AVAILABLE"; }
            long need = f.length() + HEADROOM_B;
            String receipt = receipts.getString(f.getName(), null);
            out.put(new JSONObject()
                .put("key", DEVICE + "/" + f.getName()).put("name", f.getName().replace(".gguf", ""))
                .put("device", DEVICE).put("where", "LOCAL_ANDROID").put("network", false)
                .put("size_gb", Math.round(f.length() / 1e8) / 10.0)
                .put("state", packaged ? state : "NO_DATA")
                .put("capabilities", "NO_DATA").put("chat", packaged)
                .put("memory", new JSONObject().put("needs_mb", need / 1_000_000).put("available_mb", mi.availMem / 1_000_000)
                    .put("fits_now", !mi.lowMemory && mi.availMem >= need))
                .put("runner", packaged ? "PACKAGED" : "NO_DATA(runner_not_packaged)")
                .put("voice", "ANDROID_TTS")
                .put("e2e", receipt == null ? JSONObject.NULL : new JSONObject(receipt)));
        }
        return new JSONObject().put("models", out).put("last_stop", lastStop);
    }

    private ActivityManager.MemoryInfo memory() {
        ActivityManager.MemoryInfo mi = new ActivityManager.MemoryInfo();
        ((ActivityManager) ctx.getSystemService(Context.ACTIVITY_SERVICE)).getMemoryInfo(mi);
        return mi;
    }

    /** null when memory is fine, else the cause. */
    private String pressure() {
        ActivityManager.MemoryInfo mi = memory();
        if (mi.lowMemory) return "memory_pressure_system_low";
        if (mi.availMem < mi.threshold + PRESSURE_MARGIN_B) return "memory_pressure_near_low_line";
        return null;
    }

    synchronized void stop(String why) {
        if (proc != null) {
            proc.destroy();
            try { if (!proc.waitFor(3, java.util.concurrent.TimeUnit.SECONDS)) proc.destroyForcibly(); }
            catch (InterruptedException e) { proc.destroyForcibly(); Thread.currentThread().interrupt(); }
        }
        if (proc != null) lastStop = why;
        proc = null;
        loaded = null;
        key = null;
    }

    /** Make `model` the loaded one. Returns null when READY, else a NO_DATA cause (already emitted). */
    String ensure(File model, Events ev) throws JSONException {
        synchronized (this) {
            if (running() && model.equals(loaded)) { lastUse = System.currentTimeMillis(); return null; }
        }
        stop("switch_model");
        if (!runner().canExecute()) return fail(ev, "runner_not_packaged");
        ActivityManager.MemoryInfo mi = memory();
        long need = model.length() + HEADROOM_B;
        if (mi.lowMemory || mi.availMem < need) {
            ev.emit(new JSONObject().put("e", "error").put("cause", "memory_budget_insufficient")
                .put("available_mb", mi.availMem / 1_000_000).put("needs_mb", need / 1_000_000));
            return "memory_budget_insufficient";
        }
        byte[] k = new byte[24];
        new SecureRandom().nextBytes(k);
        StringBuilder hex = new StringBuilder();
        for (byte b : k) hex.append(String.format(Locale.ROOT, "%02x", b));
        Process p;
        try {
            ProcessBuilder pb = new ProcessBuilder(runner().getAbsolutePath(),
                "-m", model.getAbsolutePath(), "--host", "127.0.0.1", "--port", String.valueOf(PORT),
                "--api-key", hex.toString(), "-c", "2048", "-t", "4", "-np", "1", "--no-webui", "--no-repack",
                "--jinja", "--reasoning-format", "deepseek", "-rea", "off", "-n", "768")
                .directory(ctx.getCacheDir()).redirectErrorStream(true);
            p = pb.start();
        } catch (IOException e) {
            return fail(ev, "runner_start_failed");
        }
        synchronized (this) { proc = p; loaded = model; key = hex.toString(); tailLen = 0; }
        Thread drain = new Thread(() -> drain(p), "preceptoros-local-runner-log");
        drain.setDaemon(true);
        drain.start();
        ev.emit(new JSONObject().put("e", "loading").put("model", model.getName()).put("where", "LOCAL_ANDROID")
            .put("available_mb", mi.availMem / 1_000_000).put("needs_mb", need / 1_000_000));
        long until = System.currentTimeMillis() + LOAD_LIMIT_MS;
        while (System.currentTimeMillis() < until) {
            if (!p.isAlive()) { stop("runner_exited"); return fail(ev, "runner_exited_while_loading"); }
            String press = pressure();
            if (press != null) { stop(press); return fail(ev, press); }
            try {
                Http h = Http.open("GET", "/health", key, null, 2000);
                int status = h.status;
                h.close();
                if (status == 200) { lastUse = System.currentTimeMillis(); return null; }
            } catch (IOException notYet) { /* still binding or loading */ }
            if (!ev.emit(new JSONObject().put("e", "loading_tick"))) { stop("cancelled_while_loading"); return "cancelled"; }
            try { Thread.sleep(300); } catch (InterruptedException e) { stop("interrupted"); return "cancelled"; }
        }
        stop("load_timeout");
        return fail(ev, "runner_load_timeout");
    }

    private String fail(Events ev, String cause) throws JSONException {
        ev.emit(new JSONObject().put("e", "error").put("cause", cause));
        return cause;
    }

    private void drain(Process p) {
        try (InputStream in = p.getInputStream()) {
            byte[] b = new byte[2048];
            int n;
            while ((n = in.read(b)) != -1) {
                synchronized (this) {
                    if (n >= tail.length) { System.arraycopy(b, n - tail.length, tail, 0, tail.length); tailLen = tail.length; }
                    else {
                        int keep = Math.min(tailLen, tail.length - n);
                        System.arraycopy(tail, tailLen - keep, tail, 0, keep);
                        System.arraycopy(b, 0, tail, keep, n);
                        tailLen = keep + n;
                    }
                }
            }
        } catch (IOException ignored) { }
    }

    /** One streamed turn on the loaded model. Returns the full answer text, or null (event already emitted). */
    String stream(JSONArray messages, Events ev, java.util.concurrent.atomic.AtomicReference<Http> current) throws JSONException {
        String k;
        File m;
        synchronized (this) { k = key; m = loaded; }
        if (k == null) return failNull(ev, "runner_not_loaded");
        JSONObject body = new JSONObject().put("messages", messages).put("stream", true).put("max_tokens", 768)
            .put("timings_per_token", false);
        long started = System.currentTimeMillis();
        long first = 0;
        int tokens = 0;
        StringBuilder text = new StringBuilder();
        Http h = null;
        Thread watch = null;
        final boolean[] pressured = {false};
        try {
            h = Http.open("POST", "/v1/chat/completions", k, body.toString().getBytes(StandardCharsets.UTF_8), 200_000);
            current.set(h);
            final Http hh = h;
            watch = new Thread(() -> {
                while (!Thread.currentThread().isInterrupted()) {
                    String press = pressure();
                    if (press != null) { pressured[0] = true; lastStop = press; hh.close(); stop(press); return; }
                    try { Thread.sleep(1000); } catch (InterruptedException e) { return; }
                }
            }, "preceptoros-local-memory-watch");
            watch.setDaemon(true);
            watch.start();
            if (h.status != 200) return failNull(ev, "runner_http_" + h.status);
            BufferedReader lines = new BufferedReader(new InputStreamReader(h.body, StandardCharsets.UTF_8));
            String line;
            JSONObject timings = null;
            while ((line = lines.readLine()) != null) {
                if (!line.startsWith("data: ")) continue;
                String data = line.substring(6).trim();
                if (data.equals("[DONE]")) break;
                JSONObject chunk = new JSONObject(data);
                if (chunk.has("timings")) timings = chunk.optJSONObject("timings");
                JSONArray choices = chunk.optJSONArray("choices");
                JSONObject delta = choices == null || choices.length() == 0 ? null : choices.getJSONObject(0).optJSONObject("delta");
                if (delta == null) continue;
                String piece = delta.optString("content", "");
                if (delta.isNull("content")) piece = "";
                String thought = delta.isNull("reasoning_content") ? "" : delta.optString("reasoning_content", "");
                if (!thought.isEmpty() && !ev.emit(new JSONObject().put("e", "thinking"))) return cancelled();
                if (!piece.isEmpty()) {
                    if (first == 0) first = System.currentTimeMillis();
                    tokens++;
                    text.append(piece);
                    if (!ev.emit(new JSONObject().put("e", "token").put("t", piece))) return cancelled();
                }
            }
            lastUse = System.currentTimeMillis();
            if (pressured[0]) return failNull(ev, lastStop);
            if (text.length() == 0) return failNull(ev, running() ? "engine_returned_no_text" : "runner_exited_while_answering");
            JSONObject done = new JSONObject().put("e", "done").put("state", "MEASURED").put("where", "LOCAL_ANDROID")
                .put("model", m == null ? "" : m.getName())
                .put("first_token_ms", first == 0 ? JSONObject.NULL : first - started)
                .put("total_ms", System.currentTimeMillis() - started)
                .put("tokens", timings != null ? timings.optInt("predicted_n", tokens) : tokens)
                .put("tokens_per_s", timings != null ? timings.optDouble("predicted_per_second", 0) : JSONObject.NULL)
                .put("at", java.time.Instant.now().toString());
            if (m != null) receipts.edit().putString(m.getName(), new JSONObject().put("at", done.get("at"))
                .put("tokens", done.get("tokens")).put("first_token_ms", done.get("first_token_ms")).toString()).apply();
            ev.emit(done);
            return text.toString();
        } catch (IOException e) {
            if (pressured[0]) return failNull(ev, lastStop);
            if (current.get() == null) return cancelled();
            if (!running()) return failNull(ev, "runner_exited_while_answering");
            return failNull(ev, "runner_stream_interrupted");
        } finally {
            if (watch != null) watch.interrupt();
            if (h != null) h.close();
            current.compareAndSet(h, null);
        }
    }

    private static String cancelled() { return null; }
    private String failNull(Events ev, String cause) throws JSONException { fail(ev, cause); return null; }

    /** Minimal HTTP/1.1 over a loopback socket (the cleartext policy stays off for real networks). */
    static final class Http {
        final Socket socket;
        final int status;
        final InputStream body;

        private Http(Socket socket, int status, InputStream body) { this.socket = socket; this.status = status; this.body = body; }

        static Http open(String method, String path, String key, byte[] payload, int readTimeoutMs) throws IOException {
            Socket s = new Socket(InetAddress.getByName("127.0.0.1"), PORT);
            s.setSoTimeout(readTimeoutMs);
            StringBuilder req = new StringBuilder()
                .append(method).append(' ').append(path).append(" HTTP/1.1\r\n")
                .append("Host: 127.0.0.1:").append(PORT).append("\r\n")
                .append("Authorization: Bearer ").append(key).append("\r\n")
                .append("Accept: text/event-stream, application/json\r\nConnection: close\r\n");
            if (payload != null) req.append("Content-Type: application/json\r\nContent-Length: ").append(payload.length).append("\r\n");
            req.append("\r\n");
            OutputStream out = s.getOutputStream();
            out.write(req.toString().getBytes(StandardCharsets.US_ASCII));
            if (payload != null) out.write(payload);
            out.flush();
            InputStream in = new java.io.BufferedInputStream(s.getInputStream());
            String statusLine = readLine(in);
            if (statusLine == null || !statusLine.startsWith("HTTP/1.")) { s.close(); throw new IOException("bad_status"); }
            int status = Integer.parseInt(statusLine.split(" ")[1]);
            boolean chunked = false;
            String h;
            while ((h = readLine(in)) != null && !h.isEmpty()) {
                if (h.toLowerCase(Locale.ROOT).startsWith("transfer-encoding:") && h.toLowerCase(Locale.ROOT).contains("chunked")) chunked = true;
            }
            return new Http(s, status, chunked ? new Chunked(in) : in);
        }

        void close() { try { socket.close(); } catch (IOException ignored) { } }

        static String readLine(InputStream in) throws IOException {
            ByteArrayOutputStream b = new ByteArrayOutputStream();
            int c;
            while ((c = in.read()) != -1) {
                if (c == '\n') break;
                if (c != '\r') b.write(c);
                if (b.size() > 8192) throw new IOException("line_too_long");
            }
            if (c == -1 && b.size() == 0) return null;
            return b.toString("ISO-8859-1");
        }
    }

    static final class Chunked extends InputStream {
        private final InputStream in;
        private int left;
        private boolean eof;
        Chunked(InputStream in) { this.in = in; }
        private boolean next() throws IOException {
            if (eof) return false;
            if (left == 0) {
                String size = Http.readLine(in);
                if (size != null && size.isEmpty()) size = Http.readLine(in);   // CRLF after the previous chunk
                if (size == null) { eof = true; return false; }
                int semi = size.indexOf(';');
                left = Integer.parseInt((semi >= 0 ? size.substring(0, semi) : size).trim(), 16);
                if (left == 0) { eof = true; return false; }
            }
            return true;
        }
        @Override public int read() throws IOException {
            if (!next()) return -1;
            int c = in.read();
            if (c == -1) { eof = true; return -1; }
            left--;
            return c;
        }
        @Override public int read(byte[] b, int off, int len) throws IOException {
            if (!next()) return -1;
            int n = in.read(b, off, Math.min(len, left));
            if (n == -1) { eof = true; return -1; }
            left -= n;
            return n;
        }
    }
}
