package org.preceptoros.mvp;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.webkit.WebView;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicBoolean;

/** One owner-selected, explicitly approved POST to the EXISTING Aduana receiver.
 * No background service, key retention, cédula sign, or self-attested LIVE.
 */
final class HeartbeatOnceBridge {
    static final int PICKER_REQUEST = 3115;
    private static final String ORIGIN = OwnerFrameAccess.ORIGIN;
    private static final int MAX_CREDENTIAL = 512, MAX_RESPONSE = 2048;
    private final MainActivity activity;
    private final WebView web;
    private final AtomicBoolean busy = new AtomicBoolean(false);
    private JavaScriptReplyProxy pendingReply;
    private String pendingId;

    private HeartbeatOnceBridge(MainActivity activity, WebView web) {
        this.activity = activity; this.web = web;
    }
    static HeartbeatOnceBridge install(MainActivity activity, WebView web) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return null;
        HeartbeatOnceBridge bridge = new HeartbeatOnceBridge(activity,web);
        WebViewCompat.addWebMessageListener(web,"PreceptorHeartbeatNative",
            Collections.singleton(ORIGIN), (view,message,origin,isMainFrame,reply) -> {
                if (!OwnerFrameAccess.accepts(origin == null ? null : origin.toString(),
                    isMainFrame, activity.ownPageVerified(), view.getUrl())) {
                    bridge.reply(reply,"",false,"origin_or_page_unverified",null); return;
                }
                String raw = message.getData();
                if (raw == null || raw.length() > 128) {
                    bridge.reply(reply,"",false,"heartbeat_message_out_of_range",null); return;
                }
                activity.runOnUiThread(() -> {
                    if (!bridge.safePage())
                        bridge.reply(reply,"",false,"origin_or_page_unverified",null);
                    else bridge.choose(raw,reply);
                });
            });
        return bridge;
    }
    private boolean safePage() {
        return activity.ownPageVerified() && MainActivity.START.equals(web.getUrl());
    }
    private void reply(JavaScriptReplyProxy target,String id,boolean ok,String cause,JSONObject detail) {
        try {
            JSONObject out = new JSONObject();
            out.put("id",id); out.put("ok",ok);
            if (!ok) out.put("cause",cause);
            if (ok && detail != null) out.put("result",detail);
            activity.runOnUiThread(() -> target.postMessage(out.toString()));
        } catch (Exception ignored) { /* caller timeout must fail closed */ }
    }
    private void finish(boolean ok,String cause,JSONObject detail) {
        JavaScriptReplyProxy target = pendingReply;
        String id = pendingId == null ? "" : pendingId;
        pendingReply = null; pendingId = null;
        busy.set(false);
        if (target != null) reply(target,id,ok,cause,detail);
    }
    private void choose(String raw,JavaScriptReplyProxy reply) {
        String id = "";
        try {
            JSONObject request = new JSONObject(raw);
            id = request.optString("id","");
            if (request.length()!=2 || !request.has("id") || !request.has("action") ||
                !id.matches("[a-f0-9]{32}") ||
                !"heartbeat_once".equals(request.optString("action",""))) {
                reply(reply,id,false,"invalid_heartbeat_request",null); return;
            }
            if (!safePage()) {
                reply(reply,id,false,"page_not_verified",null); return;
            }
            if (!busy.compareAndSet(false,true)) {
                reply(reply,id,false,"heartbeat_in_flight",null); return;
            }
            pendingId = id; pendingReply = reply;
            Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            picker.addCategory(Intent.CATEGORY_OPENABLE);
            picker.setType("application/json");
            picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            try { activity.startActivityForResult(picker,PICKER_REQUEST); }
            catch (Exception ex) {
                finish(false,"native_picker_unavailable",null);
            }
        } catch (Exception ignored) {
            reply(reply,id,false,"heartbeat_request_not_json",null);
        }
    }
    void onCredentialSelected(int resultCode,Intent data) {
        if (!busy.get() || pendingReply == null) return;
        Uri selected = data == null ? null : data.getData();
        if (resultCode != Activity.RESULT_OK || selected == null) {
            finish(false,"owner_cancelled",null); return;
        }
        if (!"content".equals(selected.getScheme()) || !safePage()) {
            finish(false,"selected_credential_or_page_invalid",null); return;
        }
        // File is read in native code ONLY. No key or URI enters WebView, JS or logs.
        new Thread(() -> {
            try {
                Credential credential = readCredential(selected);
                activity.runOnUiThread(() -> confirm(credential));
            } catch (Exception ignored) {
                activity.runOnUiThread(() -> finish(false,"credential_invalid_or_unreadable",null));
            }
        },"preceptor-heartbeat-owner-file").start();
    }
    private static final class Credential {
        final String node, key;
        Credential(String node,String key) { this.node=node; this.key=key; }
    }
    private Credential readCredential(Uri uri) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (InputStream stream = activity.getContentResolver().openInputStream(uri)) {
            if (stream == null) throw new IllegalArgumentException("missing_file");
            byte[] buf = new byte[256]; int n;
            while ((n=stream.read(buf))!=-1) {
                if (bytes.size()+n>MAX_CREDENTIAL) throw new IllegalArgumentException("too_large");
                bytes.write(buf,0,n);
            }
        }
        JSONObject selected = new JSONObject(bytes.toString(StandardCharsets.UTF_8.name()));
        if (selected.length()!=3 || !selected.has("schema") || !selected.has("node") ||
            !selected.has("key") || !HeartbeatOncePolicy.KEY_FILE.equals(selected.optString("schema")) ||
            !HeartbeatOncePolicy.node(selected.optString("node")) ||
            !HeartbeatOncePolicy.key(selected.optString("key"))) {
            throw new IllegalArgumentException("credential_shape_invalid");
        }
        return new Credential(selected.getString("node"),selected.getString("key"));
    }
    private void confirm(Credential credential) {
        if (!safePage()) { finish(false,"page_not_verified",null); return; }
        new AlertDialog.Builder(activity)
            .setTitle("Send one authenticated heartbeat?")
            .setMessage("Node: "+credential.node+
                "\n\nThis sends one measurement and the selected secret to Aduana over HTTPS."+
                " The credential file is owner-controlled and is NOT proof of a signed cédula."+
                " Aduana must already have verified human admission and a matching temporary key."+
                " This does not grant identity, activate a model, or prove Open World LIVE.")
            .setNegativeButton("Cancel",(dialog,which) ->
                finish(false,"owner_cancelled",null))
            .setOnCancelListener(dialog ->
                finish(false,"owner_cancelled",null))
            .setPositiveButton("Send one heartbeat",(dialog,which) -> {
                if (!safePage()) { finish(false,"page_not_verified",null); return; }
                new Thread(() -> {
                    JSONObject receipt=null; String cause=null;
                    try { receipt=sendOnce(credential); }
                    catch (Exception error) { cause=normalized(error); }
                    final JSONObject result=receipt; final String failure=cause;
                    activity.runOnUiThread(() -> finish(result!=null,failure,result));
                },"preceptor-heartbeat-one-shot").start();
            }).show();
    }
    private JSONObject sendOnce(Credential credential) throws Exception {
        SharedPreferences storage = activity.getSharedPreferences(
            "preceptoros.heartbeat.sequence",Activity.MODE_PRIVATE);
        long next = storage.getLong(credential.node,0);
        if (!HeartbeatOncePolicy.sequence(next) || next==9007199254740991L)
            throw new IllegalStateException("sequence_invalid");
        // Reserve before send; crashes/retries never intentionally reuse a sequence
        // with new measurement bytes. A consumed number is not evidence of receipt.
        if (!storage.edit().putLong(credential.node,next+1).commit())
            throw new IllegalStateException("sequence_storage_unavailable");
        String measured = Instant.now().truncatedTo(ChronoUnit.SECONDS).toString();
        String body = HeartbeatOncePolicy.body(credential.node,next,measured);
        URL url = new URL(HeartbeatOncePolicy.ENDPOINT);
        if (!"https".equals(url.getProtocol()) ||
            !"api.preceptoros.org".equals(url.getHost()) || url.getPort()!=-1)
            throw new IllegalStateException("destination_not_authorized");
        HttpsURLConnection conn = (HttpsURLConnection)url.openConnection();
        conn.setInstanceFollowRedirects(false);
        conn.setConnectTimeout(6000); conn.setReadTimeout(7000);
        conn.setRequestMethod("POST"); conn.setDoOutput(true);
        conn.setFixedLengthStreamingMode(body.getBytes(StandardCharsets.UTF_8).length);
        conn.setRequestProperty("Content-Type","application/json");
        conn.setRequestProperty("Accept","application/json");
        conn.setRequestProperty("Cache-Control","no-store");
        conn.setRequestProperty("x-heartbeat-key",credential.key);
        try {
            try (OutputStream output = conn.getOutputStream()) {
                output.write(body.getBytes(StandardCharsets.UTF_8)); output.flush();
            }
            int status = conn.getResponseCode();
            if (status!=200 && status!=202)
                throw new IllegalStateException("heartbeat_http_"+status);
            String type = conn.getContentType();
            if (type==null || !type.toLowerCase().startsWith("application/json"))
                throw new IllegalStateException("receipt_content_type_invalid");
            if (conn.getContentLengthLong()>MAX_RESPONSE)
                throw new IllegalStateException("receipt_too_large");
            ByteArrayOutputStream response = new ByteArrayOutputStream();
            try (InputStream input = conn.getInputStream()) {
                byte[] block = new byte[256]; int n;
                while ((n=input.read(block))!=-1) {
                    if (response.size()+n>MAX_RESPONSE)
                        throw new IllegalStateException("receipt_too_large");
                    response.write(block,0,n);
                }
            }
            JSONObject reply = new JSONObject(response.toString(StandardCharsets.UTF_8.name()));
            JSONObject receipt = reply.optJSONObject("recibo");
            if (reply.length()!=2 || !"recibido".equals(reply.optString("estado")) ||
                receipt==null || receipt.length()!=7 ||
                !HeartbeatOncePolicy.RECEIPT.equals(receipt.optString("esquema")) ||
                !credential.node.equals(receipt.optString("nodo")) ||
                !(receipt.opt("secuencia") instanceof Number) ||
                receipt.getLong("secuencia")!=next ||
                !measured.equals(receipt.optString("medido_en")) ||
                !HeartbeatOncePolicy.receipt(status,credential.node,next,measured,
                    receipt.optString("recibido"),
                    receipt.optString("payload_sha256"),
                    receipt.optString("recibo_sha256")))
                throw new IllegalStateException("receipt_unverified");
            // RECEIVED only: an independent public GET is required for LIVE.
            JSONObject state = new JSONObject();
            state.put("node",credential.node);
            state.put("sequence",next);
            state.put("state","RECEIVED");
            state.put("receiptSha256",receipt.getString("recibo_sha256"));
            state.put("authority","NONE");
            state.put("live",false);
            state.put("publicProof","NO_DATA(public_live_not_independently_verified)");
            return state;
        } finally { conn.disconnect(); }
    }
    private static String normalized(Exception error) {
        String message = error.getMessage();
        if (message!=null && message.matches(
            "heartbeat_http_[0-9]{3}|receipt_unverified|receipt_content_type_invalid|"+
            "receipt_too_large|sequence_invalid|sequence_storage_unavailable|destination_not_authorized"))
            return message;
        return "heartbeat_network_or_runtime_unavailable";
    }
}
