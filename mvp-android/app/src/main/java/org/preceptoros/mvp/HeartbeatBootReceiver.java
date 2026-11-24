package org.preceptoros.mvp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.Manifest;
import android.os.Build;

/**
 * After a restart: only when the owner separately enabled auto-resume in the consent dialog.
 * After an APP update: whenever the owner's consent is still active — installing a new version kills the process,
 * and an update must not silently withdraw a running, unrevoked consent (measured on Tank 3, 2026-11-24 18:03Z:
 * the service stayed dead after install -r and the node would have dropped at 300 s).
 */
public final class HeartbeatBootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        String action = intent == null ? null : intent.getAction();
        boolean boot = Intent.ACTION_BOOT_COMPLETED.equals(action) && HeartbeatCredentialStore.autoResume(context);
        boolean updated = Intent.ACTION_MY_PACKAGE_REPLACED.equals(action) && HeartbeatCredentialStore.consentActive(context);
        if (!boot && !updated) return;
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
