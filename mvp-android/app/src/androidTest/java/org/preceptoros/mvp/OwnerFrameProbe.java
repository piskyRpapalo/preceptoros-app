package org.preceptoros.mvp;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.ViewGroup;
import android.webkit.WebView;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.json.JSONObject;
import org.json.JSONTokener;

/** Exercises the production Activity in an isolated OWNER emulator. No request uses real inputs. */
public final class OwnerFrameProbe extends Instrumentation {
    @Override public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        start();
    }

    @Override public void onStart() {
        Bundle result = new Bundle();
        Activity activity = null;
        try {
            activity = startActivitySync(new Intent(getTargetContext(), MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            WebView web = (WebView) ((ViewGroup) activity.findViewById(android.R.id.content)).getChildAt(0);
            awaitValue(web, "document.readyState==='complete' && !!window.PreceptorAndroidMiniModel", "true");
            evaluate(web, """
                (async () => {
                  const request = (port, data) => new Promise(resolve => {
                    port.onmessage = event => resolve(JSON.parse(event.data));
                    port.postMessage(data);
                  });
                  const results = await Promise.all([
                    PreceptorAndroidMiniModel.generate(''),
                    PreceptorAndroidReview.openReview('invalid'),
                    request(PreceptorJoinNative, ' '.repeat(1101)),
                    request(PreceptorHeartbeatNative, ' '.repeat(129)),
                    request(PreceptorPrivateTalkNative, '{"id":"00000000000000000000000000000000","op":"status"}')
                  ]);
                  window.frameProbePositive = JSON.stringify({
                    version: PreceptorAndroidMiniModel.version(), mini: results[0], review: results[1],
                    join: results[2].cause, heartbeat: results[3].cause, privateState: results[4].result.estado
                  });
                })();
                """);
            JSONObject positive = awaitJson(web, "window.frameProbePositive");
            require(positive.getString("version").startsWith("v8 · "), "native version");
            require("NO_DATA(mini_input_out_of_range)".equals(positive.getString("mini")), "Mini dispatch");
            require(!positive.getBoolean("review"), "Review input policy");
            require("message_out_of_range".equals(positive.getString("join")), "join dispatch");
            require("heartbeat_message_out_of_range".equals(positive.getString("heartbeat")), "heartbeat dispatch");
            require("NO_DATA".equals(positive.getString("privateState")), "Talk status dispatch");

            evaluate(web, """
                (() => {
                  const frame = document.createElement('iframe');
                  frame.sandbox = 'allow-scripts';
                  window.addEventListener('message', event => {
                    if (event.source === frame.contentWindow && event.origin === 'null' && event.data?.probe) {
                      window.frameProbeNegative = JSON.stringify(event.data);
                    }
                  });
                  frame.srcdoc = `<script>
                    const operations = [
                      ['PreceptorAndroidMiniModel', 'version'], ['PreceptorAndroidMiniModel', 'generate'],
                      ['PreceptorAndroidReview', 'openReview'], ['PreceptorLocalNative', 'postMessage'],
                      ['PreceptorJoinNative', 'postMessage'], ['PreceptorHeartbeatNative', 'postMessage'],
                      ['PreceptorPrivateTalkNative', 'postMessage']
                    ];
                    const denied = operations.map(([name, method]) => {
                      try { window[name][method]('frame-policy-probe'); return false; }
                      catch (_) { return typeof window[name] === 'undefined'; }
                    });
                    const parentDenied = operations.every(([name]) => {
                      try { return typeof parent[name] === 'undefined'; } catch (e) { return e.name === 'SecurityError'; }
                    });
                    parent.postMessage({probe: true, denied, parentDenied}, '*');
                    </script>`;
                  document.body.append(frame);
                })();
                """);
            JSONObject negative = awaitJson(web, "window.frameProbeNegative");
            require(negative.getBoolean("parentDenied"), "parent capability isolation");
            require(negative.getJSONArray("denied").length() == 7, "all entry points tried");
            for (int i = 0; i < 7; i++) {
                require(negative.getJSONArray("denied").getBoolean(i), "foreign frame entry point " + i);
            }
            result.putString("stream", "\nOWNER main frame 5/5; foreign iframe 7/7 rejected; parent access denied\n");
            finish(Activity.RESULT_OK, result);
        } catch (Throwable failure) {
            result.putString("stream", "\nFAIL " + failure + "\n");
            finish(Activity.RESULT_CANCELED, result);
        } finally {
            if (activity != null) activity.finish();
        }
    }

    private String evaluate(WebView web, String script) throws Exception {
        CompletableFuture<String> value = new CompletableFuture<>();
        runOnMainSync(() -> web.evaluateJavascript(script, value::complete));
        return value.get(5, TimeUnit.SECONDS);
    }

    private void awaitValue(WebView web, String script, String expected) throws Exception {
        long deadline = SystemClock.elapsedRealtime() + 12000;
        do {
            if (expected.equals(evaluate(web, script))) return;
            SystemClock.sleep(100);
        } while (SystemClock.elapsedRealtime() < deadline);
        throw new AssertionError("Timed out: " + script);
    }

    private JSONObject awaitJson(WebView web, String script) throws Exception {
        awaitValue(web, "typeof " + script + " === 'string'", "true");
        return new JSONObject((String) new JSONTokener(evaluate(web, script)).nextValue());
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
