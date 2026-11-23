package org.preceptoros.mvp;

import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.text.InputType;
import android.webkit.WebView;
import android.widget.EditText;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;
import javax.net.ssl.HttpsURLConnection;

/**
 * The existing model picker's link to the rack: the catalog and one streamed turn through the owner's own
 * APP gateway (the same Tailscale Serve origin PrivateTalkBridge stores), plus Android's own TextToSpeech.
 * The gateway decides who is the owner (Serve identity); a message from this page never grants itself OWNER.
 * Every state the page shows comes from an event here: request sent, first token, tokens, done, error,
 * cancel, speech start, speech end. Nothing is timed or simulated.
 */
final class RackModelsBridge {
    private static final int MAX_CATALOG = 262144;
    private final MainActivity activity;
    private final SharedPreferences settings;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final AtomicReference<HttpsURLConnection> current = new AtomicReference<>();
    private TextToSpeech tts;
    private boolean ttsReady;
    private JavaScriptReplyProxy speechReply;

    private RackModelsBridge(MainActivity activity) {
        this.activity = activity;
        settings = activity.getSharedPreferences("preceptoros.private_talk", Context.MODE_PRIVATE);
    }

    static RackModelsBridge install(MainActivity activity, WebView web) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return null;
        RackModelsBridge bridge = new RackModelsBridge(activity);
        WebViewCompat.addWebMessageListener(web, "PreceptorModelsNative", Collections.singleton(OwnerFrameAccess.ORIGIN),
            (view, message, origin, main, reply) -> {
                if (!OwnerFrameAccess.accepts(origin == null ? null : origin.toString(), main,
                        activity.ownPageVerified(), view.getUrl())) return;
                String raw = message.getData();
                if (raw == null || raw.length() > 70000) return;
                bridge.handle(raw, reply);
            });
        return bridge;
    }

    void close() {
        cancel();
        worker.shutdownNow();
        if (tts != null) tts.shutdown();
    }

    private String origin() { return settings.getString("serve_origin", ""); }

    private void post(JavaScriptReplyProxy reply, String id, JSONObject body) {
        try { body.put("id", id); } catch (JSONException ignored) { return; }
        String text = body.toString();
        activity.runOnUiThread(() -> reply.postMessage(text));
    }
    private static JSONObject obj(Object... kv) {
        JSONObject o = new JSONObject();
        try { for (int i = 0; i < kv.length; i += 2) o.put((String) kv[i], kv[i + 1]); } catch (JSONException ignored) { }
        return o;
    }
    private static JSONObject event(String e, Object... kv) {
        JSONObject o = obj(kv);
        try { o.put("e", e); } catch (JSONException ignored) { }
        return obj("ev", o);
    }

    private void handle(String raw, JavaScriptReplyProxy reply) {
        String id = "";
        try {
            JSONObject m = new JSONObject(raw);
            id = m.optString("id");
            if (!id.matches("[a-f0-9]{32}")) return;
            final String rid = id;
            switch (m.optString("op")) {
                case "status":
                    post(reply, rid, obj("configured", PrivateTalkBridge.validOrigin(origin()), "tts", ttsState()));
                    return;
                case "configure": activity.runOnUiThread(() -> configure(reply, rid)); return;
                case "list": worker.execute(() -> list(reply, rid)); return;
                case "chat": {
                    String model = m.optString("modelo");
                    JSONArray msgs = m.optJSONArray("mensajes");
                    if (model.isEmpty() || model.length() > 140 || msgs == null || msgs.length() == 0) {
                        post(reply, rid, event("error", "cause", "request_invalid"));
                        return;
                    }
                    byte[] body = obj("modelo", model, "mensajes", msgs).toString().getBytes(StandardCharsets.UTF_8);
                    worker.execute(() -> chat(reply, rid, body));
                    return;
                }
                case "cancel": cancel(); post(reply, rid, obj("cancel_requested", true)); return;
                case "speak": activity.runOnUiThread(() -> speak(reply, rid, m.optString("texto"))); return;
                case "stop_speech":
                    activity.runOnUiThread(() -> { if (tts != null) tts.stop(); post(reply, rid, event("speak_stopped")); });
                    return;
                default: post(reply, rid, event("error", "cause", "request_invalid"));
            }
        } catch (JSONException invalid) {
            if (!id.isEmpty()) post(reply, id, event("error", "cause", "request_invalid"));
        }
    }

    private void configure(JavaScriptReplyProxy reply, String id) {
        EditText input = new EditText(activity);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setSingleLine(true);
        input.setText(origin());
        new AlertDialog.Builder(activity)
            .setTitle("Rack models")
            .setMessage("Enter the HTTPS Tailscale Serve origin of your own PreceptorOS APP. Your questions are sent only there; it decides whether you are the owner.")
            .setView(input)
            .setPositiveButton("Save", (d, w) -> {
                String value = input.getText().toString().trim();
                boolean ok = PrivateTalkBridge.validOrigin(value) && settings.edit().putString("serve_origin", value).commit();
                post(reply, id, obj("configured", ok, "cause", ok ? "configured" : "serve_origin_invalid"));
            })
            .setNegativeButton("Cancel", (d, w) -> post(reply, id, obj("configured", PrivateTalkBridge.validOrigin(origin()), "cause", "owner_cancelled")))
            .show();
    }

    private HttpsURLConnection open(String base, String path, String method) throws IOException {
        HttpsURLConnection c = (HttpsURLConnection) new URL(base + path).openConnection();
        c.setInstanceFollowRedirects(false);
        c.setUseCaches(false);
        c.setConnectTimeout(8000);
        c.setRequestMethod(method);
        c.setRequestProperty("Origin", base);
        return c;
    }

    private void list(JavaScriptReplyProxy reply, String id) {
        String base = origin();
        if (!PrivateTalkBridge.validOrigin(base)) { post(reply, id, obj("ok", false, "cause", "serve_not_configured")); return; }
        HttpsURLConnection c = null;
        try {
            c = open(base, "/api/modelos", "GET");
            c.setReadTimeout(30000);
            c.setRequestProperty("Accept", "application/json");
            int code = c.getResponseCode();
            InputStream in = code == 200 ? c.getInputStream() : c.getErrorStream();
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            if (in != null) try (InputStream input = in) {
                byte[] block = new byte[4096]; int n;
                while ((n = input.read(block)) != -1) {
                    if (bytes.size() + n > MAX_CATALOG) throw new IOException("catalog_too_large");
                    bytes.write(block, 0, n);
                }
            }
            JSONObject body = new JSONObject(bytes.toString("UTF-8"));
            if (code != 200) {
                String cause = body.optString("causa", "http_" + code);
                post(reply, id, obj("ok", false, "cause", cause.matches("[a-z0-9_]{1,96}") ? cause : "http_" + code));
                return;
            }
            post(reply, id, obj("ok", true, "catalog", body));
        } catch (IOException | JSONException e) {
            post(reply, id, obj("ok", false, "cause", "gateway_unreachable"));
        } finally { if (c != null) c.disconnect(); }
    }

    private void chat(JavaScriptReplyProxy reply, String id, byte[] body) {
        String base = origin();
        if (!PrivateTalkBridge.validOrigin(base)) { post(reply, id, event("error", "cause", "serve_not_configured")); return; }
        HttpsURLConnection c = null;
        boolean ended = false;
        try {
            c = open(base, "/api/modelos/charla", "POST");
            current.set(c);
            c.setReadTimeout(200000);
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            c.setRequestProperty("Accept", "application/x-ndjson");
            c.setFixedLengthStreamingMode(body.length);
            post(reply, id, event("sent"));
            try (OutputStream out = c.getOutputStream()) { out.write(body); }
            int code = c.getResponseCode();
            if (code != 200) {
                String cause = "http_" + code;
                InputStream err = c.getErrorStream();
                if (err != null) try (InputStream e = err) {
                    byte[] b = new byte[2048]; int n = e.read(b);
                    if (n > 0) cause = new JSONObject(new String(b, 0, n, StandardCharsets.UTF_8)).optString("causa", cause);
                } catch (JSONException | IOException ignored) { }
                post(reply, id, event("error", "cause", cause.matches("[a-z0-9_]{1,96}") ? cause : "http_" + code));
                ended = true;
                return;
            }
            try (BufferedReader lines = new BufferedReader(new InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = lines.readLine()) != null) {
                    if (line.length() > 65536) break;
                    JSONObject ev = new JSONObject(line);
                    String e = ev.optString("e");
                    if (!e.matches("loading|token|done|error")) continue;
                    post(reply, id, obj("ev", ev));
                    if (e.equals("done") || e.equals("error")) { ended = true; return; }
                }
            }
        } catch (IOException | JSONException e) {
            if (current.get() == null) { post(reply, id, event("cancelled")); ended = true; return; }
        } finally {
            if (c != null) c.disconnect();
            boolean wasCancelled = current.getAndSet(null) == null;
            if (!ended) post(reply, id, wasCancelled ? event("cancelled") : event("error", "cause", "gateway_stream_interrupted"));
        }
    }

    private void cancel() {
        HttpsURLConnection c = current.getAndSet(null);
        if (c != null) new Thread(c::disconnect, "preceptoros-rack-cancel").start();
    }

    private String ttsState() { return tts == null ? "NOT_STARTED" : ttsReady ? "READY" : "NO_DATA"; }

    private void speak(JavaScriptReplyProxy reply, String id, String text) {
        if (text == null || text.trim().isEmpty() || text.length() > 3900) { post(reply, id, event("speak_error", "cause", "speech_text_invalid")); return; }
        speechReply = reply;
        Runnable say = () -> {
            tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override public void onStart(String u) { post(speechReply, u, event("speak_start")); }
                @Override public void onDone(String u) { post(speechReply, u, event("speak_done")); }
                @Override public void onError(String u) { post(speechReply, u, event("speak_error", "cause", "tts_engine_error")); }
                @Override public void onStop(String u, boolean interrupted) { post(speechReply, u, event("speak_stopped")); }
            });
            int r = tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, id);
            if (r != TextToSpeech.SUCCESS) post(reply, id, event("speak_error", "cause", "tts_rejected"));
        };
        if (tts != null && ttsReady) { say.run(); return; }
        if (tts != null) { post(reply, id, event("speak_error", "cause", "tts_not_ready")); return; }
        tts = new TextToSpeech(activity, status -> {
            ttsReady = status == TextToSpeech.SUCCESS;
            if (!ttsReady) { post(reply, id, event("speak_error", "cause", "tts_unavailable")); return; }
            Locale es = new Locale("es", "ES");
            if (tts.isLanguageAvailable(es) >= TextToSpeech.LANG_AVAILABLE) tts.setLanguage(es);
            say.run();
        });
    }
}
