package org.preceptoros.mvp;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

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
        web.setWebViewClient(new WebViewClient() {
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
                // Navigation stays inside the bundle; every other link is refused, not opened.
                return !"https".equals(request.getUrl().getScheme()) || !DOMAIN.equals(request.getUrl().getHost());
            }
        });
        setContentView(web);
        web.loadUrl(START);
    }
}
