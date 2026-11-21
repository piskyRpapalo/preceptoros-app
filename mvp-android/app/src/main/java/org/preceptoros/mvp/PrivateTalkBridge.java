package org.preceptoros.mvp;

import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.text.InputType;
import android.webkit.WebView;
import android.widget.EditText;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.net.ssl.HttpsURLConnection;

/** The installed OWNER app's link to the existing private Talk route. */
final class PrivateTalkBridge {
    private static final String APP_ORIGIN = OwnerFrameAccess.ORIGIN;
    private static final String PREF_ORIGIN = "serve_origin";
    private static final int MAX_BYTES = 1023;
    private final MainActivity activity;
    private final SharedPreferences settings;
    private final AtomicBoolean sending = new AtomicBoolean();
    private boolean configuring;

    private PrivateTalkBridge(MainActivity activity) {
        this.activity = activity;
        settings = activity.getSharedPreferences("preceptoros.private_talk", Context.MODE_PRIVATE);
    }

    static void install(MainActivity activity, WebView web) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return;
        PrivateTalkBridge bridge = new PrivateTalkBridge(activity);
        WebViewCompat.addWebMessageListener(web, "PreceptorPrivateTalkNative",
                Collections.singleton(APP_ORIGIN), (view, message, origin, main, reply) -> {
                    if (!OwnerFrameAccess.accepts(origin == null ? null : origin.toString(),
                            main, activity.ownPageVerified(), view.getUrl())) return;
                    bridge.handle(message.getData(), reply);
                });
    }

    static boolean validOrigin(String origin) {
        return origin != null && origin.length() <= 253
                && origin.matches("https://(?:[a-z0-9-]+\\.){2,}ts\\.net");
    }

    private String savedOrigin() {
        return settings.getString(PREF_ORIGIN, "");
    }

    private void handle(String raw, JavaScriptReplyProxy reply) {
        if (raw == null || raw.length() > 2048) return;
        String id = "";
        try {
            JSONObject message = new JSONObject(raw);
            id = message.optString("id");
            if (!id.matches("[a-f0-9]{32}")) return;
            String operation = message.optString("op");
            if ("configure".equals(operation) && message.length() == 2) {
                configure(reply, id);
            } else if ("status".equals(operation) && message.length() == 2) {
                if (validOrigin(savedOrigin())) {
                    emit(reply, id, unavailable("authentication", "private_talk_auth_unverified"));
                } else {
                    emit(reply, id, unavailable("connection", "private_talk_serve_not_configured"));
                }
            } else if ("send".equals(operation) && message.length() == 3
                    && message.opt("texto") instanceof String) {
                String text = message.getString("texto");
                byte[] body = new JSONObject().put("texto", text)
                        .toString().getBytes(StandardCharsets.UTF_8);
                if (text.trim().isEmpty() || text.codePointCount(0, text.length()) > 600
                        || body.length > MAX_BYTES) {
                    emit(reply, id, unavailable("request", "request_invalid"));
                } else {
                    send(reply, id, body);
                }
            } else {
                emit(reply, id, unavailable("request", "request_invalid"));
            }
        } catch (JSONException invalid) {
            if (!id.isEmpty()) emit(reply, id, unavailable("request", "request_invalid"));
        }
    }

    private void configure(JavaScriptReplyProxy reply, String id) {
        if (configuring || sending.get()) {
            emit(reply, id, unavailable("request", "private_talk_busy"));
            return;
        }
        configuring = true;
        EditText input = new EditText(activity);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setSingleLine(true);
        input.setText(savedOrigin());
        AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle("Private Hexelion Talk")
                .setMessage("Enter the HTTPS Tailscale Serve origin you control. Private Talk messages will be sent to this address.")
                .setView(input)
                .setPositiveButton("Save", (ignored, which) -> {
                    String origin = input.getText().toString().trim();
                    if (!validOrigin(origin)) {
                        emit(reply, id, unavailable("connection", "private_talk_origin_invalid"));
                    } else if (settings.edit().putString(PREF_ORIGIN, origin).commit()) {
                        emit(reply, id, unavailable("authentication", "private_talk_auth_unverified"));
                    } else {
                        emit(reply, id, unavailable("connection", "private_talk_settings_unavailable"));
                    }
                })
                .setNeutralButton("Forget", (ignored, which) -> {
                    boolean removed = settings.edit().remove(PREF_ORIGIN).commit();
                    emit(reply, id, unavailable("connection", removed
                            ? "private_talk_serve_not_configured" : "private_talk_settings_unavailable"));
                })
                .setNegativeButton("Cancel", (ignored, which) ->
                        emit(reply, id, unavailable("request", "owner_cancelled")))
                .create();
        dialog.setOnCancelListener(ignored ->
                emit(reply, id, unavailable("request", "owner_cancelled")));
        dialog.setOnDismissListener(ignored -> configuring = false);
        dialog.show();
    }

    private void send(JavaScriptReplyProxy reply, String id, byte[] body) {
        String origin = savedOrigin();
        if (!validOrigin(origin)) {
            emit(reply, id, unavailable("connection", "private_talk_serve_not_configured"));
            return;
        }
        if (configuring || !sending.compareAndSet(false, true)) {
            emit(reply, id, unavailable("request", "private_talk_busy"));
            return;
        }
        new Thread(() -> {
            JSONObject result;
            try {
                result = request(origin, body);
            } catch (IOException unavailable) {
                result = unavailable("connection", "private_talk_network_unavailable");
            } catch (JSONException invalid) {
                result = unavailable("model", "private_talk_reply_invalid");
            } finally {
                sending.set(false);
            }
            emit(reply, id, result);
        }, "preceptoros-private-talk").start();
    }

    private static JSONObject request(String origin, byte[] body) throws IOException, JSONException {
        URL url = new URL(origin + "/api/hexelion/chat");
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(6000);
        connection.setReadTimeout(135000);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setUseCaches(false);
        connection.setRequestProperty("Origin", origin);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("Content-Type", "application/json");
        connection.setFixedLengthStreamingMode(body.length);
        try {
            try (OutputStream out = connection.getOutputStream()) { out.write(body); }
            int code = connection.getResponseCode();
            if (code >= 300 && code < 400)
                return unavailable("connection", "private_talk_redirect_refused");
            String type = connection.getContentType();
            if (type == null || !type.split(";", 2)[0].trim().equalsIgnoreCase("application/json")) {
                if (code == 401 || code == 403)
                    return unavailable("authentication", "private_talk_owner_auth_required");
                return unavailable("connection", "private_talk_endpoint_unverified");
            }
            try (InputStream in = code == 200 ? connection.getInputStream() : connection.getErrorStream()) {
                if (in == null) return unavailable("connection", "private_talk_endpoint_unverified");
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                byte[] block = new byte[512];
                int size;
                while ((size = in.read(block)) != -1) {
                    if (bytes.size() + size > MAX_BYTES)
                        return unavailable("model", "private_talk_reply_invalid");
                    bytes.write(block, 0, size);
                }
                JSONObject result = new JSONObject(bytes.toString(StandardCharsets.UTF_8.name()));
                String cause = result.optString("causa");
                String stage = result.optString("stage");
                if ((code == 401 || code == 403) && !"authentication".equals(stage))
                    return unavailable("authentication", "private_talk_owner_auth_required");
                if (code != 200 && "NO_DATA".equals(result.optString("estado"))
                        && cause.matches("[a-z0-9_]{1,96}")) {
                    if (!stage.matches("authentication|connection|model|context"))
                        stage = "request";
                    return unavailable(stage, cause);
                }
                JSONObject answer = result.optJSONObject("respuesta");
                JSONObject measurement = answer == null ? null : answer.optJSONObject("maquina");
                if (code == 200 && "MEASURED".equals(result.optString("estado")) && answer != null
                        && "MEASURED".equals(answer.optString("estado"))
                        && "hexelion".equals(answer.optString("voz"))
                        && answer.optJSONArray("fuentes") != null
                        && answer.optJSONArray("fuentes").length() > 0
                        && measurement != null && "hexelion:latest".equals(measurement.optString("modelo"))
                        && measurement.optDouble("ms", 0) > 0
                        && !answer.optString("texto").trim().isEmpty()) return result;
                return unavailable("model", "private_talk_reply_invalid");
            }
        } finally {
            connection.disconnect();
        }
    }

    private void emit(JavaScriptReplyProxy reply, String id, JSONObject result) {
        activity.runOnUiThread(() -> {
            if (!activity.ownPageVerified()) return;
            try {
                reply.postMessage(new JSONObject().put("id", id).put("result", result).toString());
            } catch (JSONException | IllegalStateException expired) {
                // The page may have gone away while the network call was in flight.
            }
        });
    }

    private static JSONObject unavailable(String stage, String cause) {
        try {
            return new JSONObject().put("estado", "NO_DATA").put("stage", stage).put("causa", cause);
        } catch (JSONException impossible) {
            throw new AssertionError(impossible);
        }
    }
}
