package org.preceptoros.mvp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.Manifest;
import android.os.Build;

/** Restarts only after the owner separately enabled auto-resume in the consent dialog. */
public final class HeartbeatBootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction()) ||
                !HeartbeatCredentialStore.autoResume(context)) return;
        if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) return;
        Intent service = new Intent(context, HeartbeatPresenceService.class)
                .setAction(HeartbeatPresenceService.ACTION_BOOT_RESUME);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(service);
            else context.startService(service);
        } catch (RuntimeException ignored) {
            // Platform restrictions fail closed: the owner can start it again from the APP.
        }
    }
}
