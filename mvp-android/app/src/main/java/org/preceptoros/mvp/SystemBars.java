package org.preceptoros.mvp;

import android.os.Build;
import android.view.View;
import android.view.WindowInsets;

/**
 * Android 15 draws every targetSdk 35+ app edge to edge: without this, the status bar covered the page's
 * first line on Tank 3 (measured 2026-11-24: «PreceptorOS» and «OpenWorld visitor» under the clock).
 * The root view is padded by the system bars and the display cutout; older Android keeps its own frame.
 */
final class SystemBars {
    private SystemBars() {}

    static void pad(View root) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return;
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()
                    | WindowInsets.Type.ime());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return WindowInsets.CONSUMED;
        });
        root.requestApplyInsets();
    }
}
