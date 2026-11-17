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
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
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
    private final AtomicLong lastReviewRequest = new AtomicLong(0L);

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
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                ownPageReady = START.equals(url);
                if (ownPageReady) {
                    // The APK's JS is read as a local asset, not fetched through a
                    // service worker (which may be offline or have stale caches).
                    try (InputStream in = getAssets().open("android_review_bridge.js")) {
                        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                        byte[] block = new byte[2048];
                        int n;
                        while ((n = in.read(block)) != -1) bytes.write(block, 0, n);
                        view.evaluateJavascript(
                            new String(bytes.toByteArray(), StandardCharsets.UTF_8), null);
                    } catch (IOException unavailable) {
                        ownPageReady = false;
                        Toast.makeText(MainActivity.this,
                            "NO_DATA: Android review bridge unavailable.",
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
