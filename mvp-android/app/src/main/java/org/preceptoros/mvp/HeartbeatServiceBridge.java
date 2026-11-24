package org.preceptoros.mvp;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.webkit.WebView;
import androidx.webkit.JavaScriptReplyProxy;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/** Owner-only UI bridge for starting, inspecting, and revoking recurring presence. */
final class HeartbeatServiceBridge {
    static final int PICKER_REQUEST = 3116;
    static final int NOTIFICATION_PERMISSION_REQUEST = 4317;
    private static final int MAX_CREDENTIAL = 512;
    private final MainActivity activity;
    private final WebView web;
    private JavaScriptReplyProxy pendingReply;
    private String pendingId;

    private HeartbeatServiceBridge(MainActivity activity, WebView web) {
        this.activity = activity;
        this.web = web;
    }

    static HeartbeatServiceBridge create(MainActivity activity, WebView web) {
        return new HeartbeatServiceBridge(activity, web);
    }

    void onCredentialSelected(int resultCode, Intent data) {
        if (pendingReply == null) return;
        Uri selected = data == null ? null : data.getData();
        if (resultCode != Activity.RESULT_OK || selected == null) {
            finish(false, "owner_cancelled", null);
            return;
        }
        if (!"content".equals(selected.getScheme()) || !safePage()) {
            finish(false, "selected_credential_or_page_invalid", null);
            return;
        }
        new Thread(() -> {
            try {
                HeartbeatCredentialStore.Credential credential = readCredential(selected);
                activity.runOnUiThread(() -> confirmStart(credential));
            } catch (Exception failure) {
                activity.runOnUiThread(() -> finish(false, "credential_invalid_or_unreadable", null));
            }
        }, "preceptor-heartbeat-service-key-read").start();
    }

    void onNotificationPermissionResult(int[] grantResults) {
        if (pendingReply == null) return;
        if (grantResults == null || grantResults.length == 0 ||
                grantResults[0] != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            finish(false, "notification_permission_required", null);
            return;
        }
        chooseSource();
    }

    private boolean safePage() {
        return activity.ownPageVerified() && MainActivity.START.equals(web.getUrl());
    }

    void handle(String raw, JavaScriptReplyProxy reply) {
        String id = "";
        try {
            JSONObject request = new JSONObject(raw);
            id = request.optString("id", "");
            String action = request.optString("action", "");
            if (request.length() != 2 || !request.has("id") || !request.has("action") ||
                    !id.matches("[a-f0-9]{32}") || !safePage()) {
                reply(reply, id, false, safePage() ? "invalid_heartbeat_service_request" : "page_not_verified", null);
                return;
            }
            if ("heartbeat_service_status".equals(action)) {
                boolean active = HeartbeatCredentialStore.consentActive(activity);
                JSONObject result = new JSONObject();
                result.put("state", active ? "ACTIVE" : "STOPPED");
                result.put("autoResume", active && HeartbeatCredentialStore.autoResume(activity));
                result.put("publicProof", "NO_DATA(public_live_not_independently_verified)");
                reply(reply, id, true, null, result);
                return;
            }
            if ("heartbeat_service_start".equals(action)) {
                if (pendingReply != null) {
                    reply(reply, id, false, "heartbeat_service_request_in_flight", null);
                    return;
                }
                if (HeartbeatCredentialStore.consentActive(activity)) {
                    reply(reply, id, false, "heartbeat_service_active", null);
                    return;
                }
                if (HeartbeatOnceBridge.isBusy()) {
                    reply(reply, id, false, "one_shot_heartbeat_in_flight", null);
                    return;
                }
                pendingReply = reply;
                pendingId = id;
                if (Build.VERSION.SDK_INT >= 33 && activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                        != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                    activity.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},
                            NOTIFICATION_PERMISSION_REQUEST);
                } else {
                    chooseSource();
                }
                return;
            }
            if ("heartbeat_service_revoke".equals(action)) {
                final String requestId = id;
                new AlertDialog.Builder(activity)
                        .setTitle("Revoke node presence consent?")
                        .setMessage("This stops recurring heartbeats and deletes the encrypted key copy from this app. Aduana may continue to show the last heartbeat until its normal expiry.")
                        .setNegativeButton("Keep active", (dialog, which) -> reply(reply, requestId, false, "owner_cancelled", null))
                        .setOnCancelListener(dialog -> reply(reply, requestId, false, "owner_cancelled", null))
                        .setPositiveButton("Revoke and stop", (dialog, which) -> {
                            HeartbeatCredentialStore.revoke(activity);
                            activity.stopService(new Intent(activity, HeartbeatPresenceService.class));
                            JSONObject result = new JSONObject();
                            try { result.put("state", "REVOKED"); }
                            catch (Exception ignored) {}
                            reply(reply, requestId, true, null, result);
                        }).show();
                return;
            }
            reply(reply, id, false, "heartbeat_service_action_unknown", null);
        } catch (Exception failure) {
            reply(reply, id, false, "heartbeat_service_request_invalid", null);
        }
    }

    /** The node born on this phone needs no imported file; any other node keeps the picker. */
    private void chooseSource() {
        String alias = null;
        try { alias = NodeOwnerBridge.owner(activity).beatingAlias(); } catch (Exception ignored) { /* no device node */ }
        if (alias == null) { openPicker(); return; }
        confirmDeviceNode(alias);
    }

    private void confirmDeviceNode(String alias) {
        if (!safePage()) { finish(false, "page_not_verified", null); return; }
        android.widget.CheckBox resume = new android.widget.CheckBox(activity);
        resume.setText("Resume automatically after device restart (still visible and revocable)");
        resume.setPadding(32, 12, 32, 8);
        new AlertDialog.Builder(activity)
                .setTitle("Keep this node online?")
                .setMessage("Node: " + alias + " (born on this phone)" +
                        "\n\nWhile the visible foreground service runs, the app sends this node's heartbeat to Aduana over HTTPS every 120 seconds, with the key that was born on this phone and never leaves it. It renews that key before it expires. A notification stays visible with a revoke action. This does not prove public LIVE.")
                .setView(resume)
                .setNegativeButton("Cancel", (dialog, which) -> finish(false, "owner_cancelled", null))
                .setOnCancelListener(dialog -> finish(false, "owner_cancelled", null))
                .setPositiveButton("Start visible service", (dialog, which) -> {
                    if (!safePage()) { finish(false, "page_not_verified", null); return; }
                    if (HeartbeatOnceBridge.isBusy()) { finish(false, "one_shot_heartbeat_in_flight", null); return; }
                    try {
                        HeartbeatCredentialStore.saveDeviceNode(activity, alias, resume.isChecked());
                        Intent service = new Intent(activity, HeartbeatPresenceService.class)
                                .setAction(HeartbeatPresenceService.ACTION_START);
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) activity.startForegroundService(service);
                        else activity.startService(service);
                        JSONObject result = new JSONObject();
                        result.put("state", "STARTING");
                        result.put("node", alias);
                        result.put("source", "device_node");
                        result.put("intervalSeconds", HeartbeatServicePolicy.INTERVAL_MILLIS / 1000);
                        result.put("autoResume", resume.isChecked());
                        result.put("publicProof", "NO_DATA(public_live_not_independently_verified)");
                        finish(true, null, result);
                    } catch (Exception failure) {
                        HeartbeatCredentialStore.revoke(activity);
                        finish(false, "heartbeat_service_start_failed", null);
                    }
                }).show();
    }

    private void openPicker() {
        if (pendingReply == null || !safePage()) {
            finish(false, "page_not_verified", null);
            return;
        }
        Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType("application/json");
        picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            activity.startActivityForResult(picker, PICKER_REQUEST);
        } catch (Exception failure) {
            finish(false, "native_picker_unavailable", null);
        }
    }

    private HeartbeatCredentialStore.Credential readCredential(Uri uri) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (InputStream stream = activity.getContentResolver().openInputStream(uri)) {
            if (stream == null) throw new IllegalArgumentException("missing_file");
            byte[] block = new byte[256];
            int count;
            while ((count = stream.read(block)) != -1) {
                if (bytes.size() + count > MAX_CREDENTIAL) throw new IllegalArgumentException("too_large");
                bytes.write(block, 0, count);
            }
        }
        JSONObject value = new JSONObject(bytes.toString(StandardCharsets.UTF_8.name()));
        if (value.length() != 3 || !value.has("schema") || !value.has("node") || !value.has("key") ||
                !HeartbeatOncePolicy.KEY_FILE.equals(value.optString("schema")) ||
                !HeartbeatOncePolicy.node(value.optString("node")) ||
                !HeartbeatOncePolicy.key(value.optString("key")))
            throw new IllegalArgumentException("credential_shape_invalid");
        return new HeartbeatCredentialStore.Credential(value.getString("node"), value.getString("key"));
    }

    private void confirmStart(HeartbeatCredentialStore.Credential credential) {
        if (!safePage()) { finish(false, "page_not_verified", null); return; }
        android.widget.CheckBox resume = new android.widget.CheckBox(activity);
        resume.setText("Resume automatically after device restart (still visible and revocable)");
        resume.setPadding(32, 12, 32, 8);
        new AlertDialog.Builder(activity)
                .setTitle("Keep this node online?")
                .setMessage("Node: " + credential.node +
                        "\n\nWhile the visible foreground service runs, the app sends this node ID, a sequence number and timestamp to Aduana over HTTPS every 120 seconds. The key is stored encrypted with Android Keystore. A notification stays visible with a revoke action. This does not sign identity or prove public LIVE.")
                .setView(resume)
                .setNegativeButton("Cancel", (dialog, which) -> finish(false, "owner_cancelled", null))
                .setOnCancelListener(dialog -> finish(false, "owner_cancelled", null))
                .setPositiveButton("Start visible service", (dialog, which) -> {
                    if (!safePage()) { finish(false, "page_not_verified", null); return; }
                    if (HeartbeatOnceBridge.isBusy()) { finish(false, "one_shot_heartbeat_in_flight", null); return; }
                    try {
                        HeartbeatCredentialStore.save(activity, credential.node, credential.key, resume.isChecked());
                        Intent service = new Intent(activity, HeartbeatPresenceService.class)
                                .setAction(HeartbeatPresenceService.ACTION_START);
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) activity.startForegroundService(service);
                        else activity.startService(service);
                        JSONObject result = new JSONObject();
                        result.put("state", "STARTING");
                        result.put("node", credential.node);
                        result.put("intervalSeconds", HeartbeatServicePolicy.INTERVAL_MILLIS / 1000);
                        result.put("autoResume", resume.isChecked());
                        result.put("publicProof", "NO_DATA(public_live_not_independently_verified)");
                        finish(true, null, result);
                    } catch (Exception failure) {
                        HeartbeatCredentialStore.revoke(activity);
                        finish(false, "heartbeat_service_start_failed", null);
                    }
                }).show();
    }

    private void reply(JavaScriptReplyProxy target, String id, boolean ok, String cause, JSONObject result) {
        try {
            JSONObject out = new JSONObject();
            out.put("id", id);
            out.put("ok", ok);
            if (ok && result != null) out.put("result", result);
            if (!ok) out.put("cause", cause);
            activity.runOnUiThread(() -> target.postMessage(out.toString()));
        } catch (Exception ignored) { /* UI bridge timeout remains fail closed. */ }
    }

    private void finish(boolean ok, String cause, JSONObject result) {
        JavaScriptReplyProxy target = pendingReply;
        String id = pendingId == null ? "" : pendingId;
        pendingReply = null;
        pendingId = null;
        if (target != null) reply(target, id, ok, cause, result);
    }
}
