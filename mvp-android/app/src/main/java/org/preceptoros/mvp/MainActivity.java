package org.preceptoros.mvp;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebChromeClient;
import android.webkit.ValueCallback;
import android.webkit.WebViewClient;
import android.widget.Toast;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicBoolean;

import org.json.JSONException;
import org.json.JSONObject;

import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;

import androidx.webkit.WebViewAssetLoader;

/**
 * PreceptorOS MVP. The app's panels run from the APK under a secure local origin,
 * https://preceptoros.mvp.local/, served by WebViewAssetLoader. Root-relative paths
 * (/app.js, /app.css) therefore resolve, and nothing is loaded from the network.
 */
public class MainActivity extends Activity {
    static final String DOMAIN = OwnerFrameAccess.DOMAIN;
    static final String START = OwnerFrameAccess.PAGE;

    private WebViewAssetLoader loader;
    private volatile boolean ownPageReady = false;
    boolean ownPageVerified() { return ownPageReady; }
    private long lastReviewRequest;
    private long lastOpenWorldRequest;
    private final AtomicBoolean miniBusy = new AtomicBoolean();
    private long lastMiniAsk = 0L;
    // Owner-selected JSON through Android's system SAF picker. Never broad storage access.
    private static final int MINI_RECOVERY_PICKER = 3114;
    private ValueCallback<Uri[]> pendingMiniRecoveryFile;
    private HeartbeatOnceBridge heartbeatBridge;
    private HeartbeatServiceBridge heartbeatServiceBridge;
    private NodeOwnerBridge nodeBridge;
    private RackModelsBridge modelsBridge;
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == HeartbeatOnceBridge.PICKER_REQUEST) {
            if (heartbeatBridge != null) heartbeatBridge.onCredentialSelected(resultCode,data);
            return;
        }
        if (requestCode == HeartbeatServiceBridge.PICKER_REQUEST) {
            if (heartbeatServiceBridge != null) heartbeatServiceBridge.onCredentialSelected(resultCode, data);
            return;
        }
        if (requestCode != MINI_RECOVERY_PICKER) return;
        ValueCallback<Uri[]> callback = pendingMiniRecoveryFile;
        pendingMiniRecoveryFile = null;
        if (callback == null) return;
        Uri selected = (resultCode == RESULT_OK && data != null) ? data.getData() : null;
        callback.onReceiveValue(selected == null ? null : new Uri[]{selected});
    }
    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == HeartbeatServiceBridge.NOTIFICATION_PERMISSION_REQUEST && heartbeatServiceBridge != null)
            heartbeatServiceBridge.onNotificationPermissionResult(grantResults);
    }
    private static final String MINI_MODEL_SHA256 =
            "ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747";

    private void evaluateBundledScript(WebView view, String name) throws IOException {
        // Scripts are loaded exclusively from APK assets, not from an external URL.
        try (InputStream in = getAssets().open(name)) {
            view.evaluateJavascript(readScript(in), null);
        }
    }

    private static String readScript(InputStream in) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] block = new byte[2048];
        int n;
        while ((n = in.read(block)) != -1) bytes.write(block, 0, n);
        return new String(bytes.toByteArray(), StandardCharsets.UTF_8);
    }

    /**
     * Restricted Android handoff. Only opens the public GitHub issue composer;
     * never sends a message, submits an issue, or reads private node data.
     * A compromised frame still cannot pass arbitrary destinations or content.
     */
    private boolean openReview(String url) {
        if (!CompanionReviewPolicy.accepts(url)) return false;
        long now = SystemClock.elapsedRealtime();
        if (lastReviewRequest != 0 && now - lastReviewRequest < 3000) return false;
        lastReviewRequest = now;
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.addCategory(Intent.CATEGORY_BROWSABLE);
            startActivity(intent);
            return true;
        } catch (ActivityNotFoundException error) {
            Toast.makeText(this, "NO_DATA: no browser available. Nothing submitted.",
                Toast.LENGTH_LONG).show();
            return false;
        }
    }

    /** User initiated handoff to the existing public visitor game only. */
    private boolean openWorld(String url) {
        if (!OpenWorldVisitorPolicy.accepts(url) || !ownPageReady) return false;
        long now = SystemClock.elapsedRealtime();
        if (lastOpenWorldRequest != 0 && now - lastOpenWorldRequest < 3000) return false;
        lastOpenWorldRequest = now;
        try {
            Intent intent = new Intent(this, OpenWorldActivity.class);
            startActivity(intent);
            return true;
        } catch (RuntimeException error) {
            Toast.makeText(this, "NO_DATA(openworld_viewer_unavailable)", Toast.LENGTH_LONG).show();
            return false;
        }
    }

    /** The message port authenticates the frame before parsing or dispatch. */
    private void installLocalBridge(WebView web) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)
                || !WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) return;
        String script;
        try (InputStream in = getResources().openRawResource(R.raw.local_bridge)) {
            String version = "v" + BuildConfig.VERSION_CODE + " · " + BuildConfig.VERSION_NAME;
            script = "(" + readScript(in) + ")(" + JSONObject.quote(version) + ");";
        } catch (IOException unavailable) {
            return;
        }
        WebViewCompat.addWebMessageListener(web, "PreceptorLocalNative",
                Collections.singleton(OwnerFrameAccess.ORIGIN), (view, message, origin, main, reply) -> {
                    if (!OwnerFrameAccess.accepts(origin == null ? null : origin.toString(),
                            main, ownPageVerified(), view.getUrl())) return;
                    handleLocalMessage(message.getData(), reply);
                });
        WebViewCompat.addDocumentStartJavaScript(web, script,
                Collections.singleton(OwnerFrameAccess.ORIGIN));
    }

    private void handleLocalMessage(String raw, JavaScriptReplyProxy reply) {
        if (raw == null || raw.length() > 4096) return;
        try {
            JSONObject request = new JSONObject(raw);
            int id = request.getInt("id");
            String value = request.getString("value");
            switch (request.getString("operation")) {
                case "review":
                    replyLocal(reply, id, openReview(value));
                    break;
                case "openworld":
                    replyLocal(reply, id, openWorld(value));
                    break;
                case "mini":
                    if (value.isEmpty() || value.length() > 600) {
                        replyLocal(reply, id, "NO_DATA(mini_input_out_of_range)");
                    } else if (!miniBusy.compareAndSet(false, true)) {
                        replyLocal(reply, id, "NO_DATA(mini_busy)");
                    } else {
                        new Thread(() -> {
                            try {
                                String result = generateMini(value);
                                runOnUiThread(() -> replyLocal(reply, id, result));
                            } finally {
                                miniBusy.set(false);
                            }
                        }, "preceptor-local-mini").start();
                    }
                    break;
                default:
                    replyLocal(reply, id, "NO_DATA(local_operation_unknown)");
            }
        } catch (JSONException invalid) {
            // The caller's deadline applies to malformed requests without a usable id.
        }
    }

    private static void replyLocal(JavaScriptReplyProxy reply, int id, Object value) {
        try {
            reply.postMessage(new JSONObject().put("id", id).put("value", value).toString());
        } catch (JSONException | IllegalStateException expired) {
            // The document may have gone away while generation was in flight.
        }
    }

    /** Mini uses only the bundled model and explicit user input. */
    private String generateMini(String prompt) {
        if (!MiniNative.available()) return "NO_DATA(mini_native_runtime_not_packaged)";
        long now = SystemClock.elapsedRealtime();
        if (lastMiniAsk > 0 && now - lastMiniAsk < 800) return "NO_DATA(mini_rate_limited)";
        lastMiniAsk = now;
        try {
            File model = installVerifiedMiniModel();
            if (model == null) return "NO_DATA(mini_model_asset_missing_or_invalid)";
            String result = MiniNative.generate(model.getAbsolutePath(), prompt);
            return result == null || result.isEmpty() ? "NO_DATA(mini_native_empty_result)" : result;
        } catch (Exception | LinkageError error) {
            return "NO_DATA(mini_native_generation_failed)";
        }
    }

    private File installVerifiedMiniModel() {
        // The model is a bundled, public, Apache-2.0 135M GGUF. Copy only to
        // private app storage, verify SHA-256 and atomically replace.
        File model = new File(getFilesDir(), "mini-135m.gguf");
        File temp = new File(getFilesDir(), "mini-135m.gguf.tmp");
        try {
            if (model.isFile() && MINI_MODEL_SHA256.equals(sha256Of(model))) return model;
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = getAssets().open("offline-mini.gguf");
                 FileOutputStream output = new FileOutputStream(temp)) {
                byte[] buf = new byte[65536];
                int n;
                while ((n = input.read(buf)) != -1) {
                    output.write(buf, 0, n);
                    digest.update(buf, 0, n);
                }
                output.getFD().sync();
            }
            if (!MINI_MODEL_SHA256.equals(hex(digest.digest()))) return null;
            if (!temp.renameTo(model)) return null;
            return model;
        } catch (Exception failure) {
            return null;
        } finally {
            if (temp.exists()) temp.delete();
        }
    }

    private static String sha256Of(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new java.io.FileInputStream(file)) {
            byte[] b = new byte[65536]; int n;
            while ((n = input.read(b)) != -1) digest.update(b, 0, n);
        }
        return hex(digest.digest());
    }
    private static String hex(byte[] raw) {
        StringBuilder result = new StringBuilder(raw.length * 2);
        final char[] chars = "0123456789abcdef".toCharArray();
        for (byte b : raw) {
            result.append(chars[(b >>> 4) & 15]);
            result.append(chars[b & 15]);
        }
        return result.toString();
    }

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        loader = new WebViewAssetLoader.Builder()
                .setDomain(DOMAIN)
                .addPathHandler("/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        // Debug builds only: lets the test harness read the WebView's storage. Release builds never enable it.
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        WebView web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true); // SAF URI grant only; filesystem access remains false.
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                // Only our packaged first-party page may open the picker. No automatic
                // scan, no filesystem permissions; Android grants exactly one JSON URI
                // after an explicit user gesture. File bytes stay in this WebView.
                if (callback == null) return true;
                if (!ownPageReady || !START.equals(view.getUrl()) ||
                    pendingMiniRecoveryFile != null) {
                    callback.onReceiveValue(null);
                    return true;
                }
                pendingMiniRecoveryFile = callback;
                Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                picker.addCategory(Intent.CATEGORY_OPENABLE);
                picker.setType("application/json");
                picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                try {
                    startActivityForResult(picker, MINI_RECOVERY_PICKER);
                } catch (ActivityNotFoundException error) {
                    pendingMiniRecoveryFile = null;
                    callback.onReceiveValue(null);
                    Toast.makeText(MainActivity.this,
                        "NO_DATA(mini_recovery_picker_unavailable)", Toast.LENGTH_LONG).show();
                }
                return true;
            }
        });
        installLocalBridge(web);
        // All native messages require a verified local main frame.
        final boolean joinAvailable = DeploymentJoinBridge.install(this, web);
        heartbeatServiceBridge = HeartbeatServiceBridge.create(this, web);
        heartbeatBridge = HeartbeatOnceBridge.install(this,web,heartbeatServiceBridge);
        nodeBridge = NodeOwnerBridge.install(this, web);
        modelsBridge = RackModelsBridge.install(this, web);
        if ("OWNER".equals(BuildConfig.APP_DISTRIBUTION_PROFILE)) {
            PrivateTalkBridge.install(this, web);
        }
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                ownPageReady = false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                ownPageReady = START.equals(url) && START.equals(view.getUrl());
                if (ownPageReady) {
                    // The APK's JS is read as a local asset, not fetched through a
                    // service worker (which may be offline or have stale caches).
                    try {
                        evaluateBundledScript(view, "android_review_bridge.js");
                        evaluateBundledScript(view, "android_openworld_bridge.js");
                        evaluateBundledScript(view, "offline_mini.js");
                        if (joinAvailable) evaluateBundledScript(view, "android_join_bridge.js");
                        if (heartbeatBridge != null) evaluateBundledScript(view, "android_heartbeat_bridge.js");
                        if (heartbeatServiceBridge != null) evaluateBundledScript(view, "android_heartbeat_service_bridge.js");
                        if (nodeBridge != null) evaluateBundledScript(view, "android_node_bridge.js");
                        if (modelsBridge != null) evaluateBundledScript(view, "android_models_bridge.js");
                    } catch (IOException unavailable) {
                        ownPageReady = false;
                        Toast.makeText(MainActivity.this,
                            "NO_DATA: Android offline capability unavailable.",
                            Toast.LENGTH_LONG).show();
                    }
                }
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                // This build has no app server. An /api/ request is not answered here: it fails without
                // network, so the panel reports that the server cannot be reached, never a made-up reading.
                String path = request.getUrl().getPath();
                if (path != null && path.startsWith("/api/")) return null;
                return loader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                // Navigation stays inside the bundle; external pages are opened ONLY
                // by the review bridge after strict validation and an explicit tap.
                return !"https".equals(request.getUrl().getScheme()) || !DOMAIN.equals(request.getUrl().getHost());
            }
        });
        setContentView(web);
        SystemBars.pad(web);
        web.loadUrl(START);
    }

    @Override
    public void onTrimMemory(int level) {
        super.onTrimMemory(level);
        if (modelsBridge != null) modelsBridge.onTrimMemory(level);
    }

    @Override
    protected void onDestroy() {
        if (nodeBridge != null) nodeBridge.close();
        if (modelsBridge != null) modelsBridge.close();
        super.onDestroy();
    }
}
