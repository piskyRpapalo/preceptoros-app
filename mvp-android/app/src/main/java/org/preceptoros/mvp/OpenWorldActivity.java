package org.preceptoros.mvp;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Unprivileged, route-limited renderer for the existing public visitor game. */
public final class OpenWorldActivity extends Activity {
    private WebView game;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setBackgroundColor(Color.rgb(21, 44, 56));
        TextView label = new TextView(this);
        label.setText("OpenWorld visitor · public game · no node admission");
        label.setTextColor(Color.WHITE);
        label.setPadding(16, 12, 16, 12);
        page.addView(label, new LinearLayout.LayoutParams(-1, -2));
        game = new WebView(this);
        WebSettings settings = game.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);
        game.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !OpenWorldVisitorPolicy.allowsNavigation(request.getUrl().toString());
            }

            @SuppressWarnings("deprecation")
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return !OpenWorldVisitorPolicy.allowsNavigation(url);
            }

            @Override public void onReceivedSslError(WebView view, android.webkit.SslErrorHandler handler,
                                                       android.net.http.SslError error) {
                handler.cancel();
            }

            @Override public void onSafeBrowsingHit(WebView view, WebResourceRequest request,
                    int threatType, android.webkit.SafeBrowsingResponse response) {
                response.backToSafety(true);
                showUnavailable();
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request,
                                                   WebResourceError error) {
                if (request.isForMainFrame()) showUnavailable();
            }

            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request,
                                                       WebResourceResponse response) {
                if (request.isForMainFrame() && response.getStatusCode() >= 400) showUnavailable();
            }
        });
        Button back = new Button(this);
        back.setText("Back to PreceptorOS");
        back.setOnClickListener(v -> finish());
        page.addView(back, new LinearLayout.LayoutParams(-1, -2));
        page.addView(game, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(page, new ViewGroup.LayoutParams(-1, -1));
        game.loadUrl(OpenWorldVisitorPolicy.URL);
    }

    private void showUnavailable() {
        if (game != null) game.post(() -> game.loadDataWithBaseURL(null,
                "<!doctype html><meta name='viewport' content='width=device-width'><h2>NO_DATA(openworld_unavailable)</h2><p>Connection or HTTPS validation failed. No LIVE state was recorded.</p>",
                "text/html", "UTF-8", null));
    }

    @Override protected void onDestroy() {
        if (game != null) {
            game.stopLoading();
            game.removeAllViews();
            game.destroy();
            game = null;
        }
        super.onDestroy();
    }
}
