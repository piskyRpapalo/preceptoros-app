package org.preceptoros.mvp;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.concurrent.atomic.AtomicLong;

import androidx.webkit.WebViewAssetLoader;

/**
 * PreceptorOS MVP. The app's panels run from the APK under a secure local origin,
 * https://preceptoros.mvp.local/, served by WebViewAssetLoader. Root-relative paths
 * (/app.js, /app.css) therefore resolve, and nothing is loaded from the network.
 */
public class MainActivity extends Activity {
    static final String DOMAIN = "preceptoros.mvp.local";
    static final String START = "https://" + DOMAIN + "/app.html";

    private WebViewAssetLoader loader;
    private volatile boolean ownPageReady = false;
    boolean ownPageVerified() { return ownPageReady; }
    private final AtomicLong lastReviewRequest = new AtomicLong(0L);
    private final Object miniModelLock = new Object();
    private long lastMiniAsk = 0L;
    private static final String MINI_MODEL_SHA256 =
            "ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747";

    private void evaluateBundledScript(WebView view, String name) throws IOException {
        // Scripts are loaded exclusively from APK assets, not from an external URL.
        try (InputStream in = getAssets().open(name)) {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            byte[] block = new byte[2048];
            int n;
            while ((n = in.read(block)) != -1) bytes.write(block, 0, n);
            view.evaluateJavascript(new String(bytes.toByteArray(), StandardCharsets.UTF_8), null);
        }
    }

    /**
     * Restricted Android handoff. Only opens the public GitHub issue composer;
     * never sends a message, submits an issue, or reads private node data.
     * A compromised frame still cannot pass arbitrary destinations or content.
     */
    private final class ReviewHandoff {
        @JavascriptInterface
        public boolean openReview(String url) {
            if (!ownPageReady || !CompanionReviewPolicy.accepts(url)) return false;
            long now = SystemClock.elapsedRealtime();
            long previous = lastReviewRequest.get();
            if (previous != 0 && now - previous < 3000) return false;
            if (!lastReviewRequest.compareAndSet(previous, now)) return false;
            runOnUiThread(() -> {
                if (!ownPageReady) return;
                try {
                    Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    intent.addCategory(Intent.CATEGORY_BROWSABLE);
                    startActivity(intent);
                } catch (ActivityNotFoundException error) {
                    Toast.makeText(MainActivity.this,
                        "NO_DATA: no browser available. Nothing submitted.",
                        Toast.LENGTH_LONG).show();
                }
            });
            return true; // Dispatch requested, NOT proof that a browser opened or issue was sent.
        }
    }

    /** No model files, memory, tools or grants are accessible to JavaScript. */
    private final class OfflineModelBridge {
        @JavascriptInterface
        public String generate(String prompt) {
            if (!ownPageReady) return "NO_DATA(mini_page_not_verified)";
            if (prompt == null || prompt.isEmpty() || prompt.length() > 600)
                return "NO_DATA(mini_input_out_of_range)";
            if (!MiniNative.available()) return "NO_DATA(mini_native_runtime_not_packaged)";
            synchronized (miniModelLock) {
                long now = SystemClock.elapsedRealtime();
                if (lastMiniAsk > 0 && now - lastMiniAsk < 800)
                    return "NO_DATA(mini_rate_limited)";
                lastMiniAsk = now;
                try {
                    File model = installVerifiedMiniModel();
                    if (model == null) return "NO_DATA(mini_model_asset_missing_or_invalid)";
                    String result = MiniNative.generate(model.getAbsolutePath(), prompt);
                    return result == null || result.isEmpty() ?
                            "NO_DATA(mini_native_empty_result)" : result;
                } catch (Exception error) {
                    return "NO_DATA(mini_native_generation_failed)";
                }
            }
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
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.addJavascriptInterface(new ReviewHandoff(), "PreceptorAndroidReview");
        web.addJavascriptInterface(new OfflineModelBridge(), "PreceptorAndroidMiniModel");
        // No addJavascriptInterface for network/identity: only origin/main-frame checked listener.
        final boolean joinAvailable = DeploymentJoinBridge.install(this, web);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                ownPageReady = START.equals(url);
                if (ownPageReady) {
                    // The APK's JS is read as a local asset, not fetched through a
                    // service worker (which may be offline or have stale caches).
                    try {
                        evaluateBundledScript(view, "android_review_bridge.js");
                        evaluateBundledScript(view, "offline_mini.js");
                        if (joinAvailable) evaluateBundledScript(view, "android_join_bridge.js");
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
        web.loadUrl(START);
    }
}
