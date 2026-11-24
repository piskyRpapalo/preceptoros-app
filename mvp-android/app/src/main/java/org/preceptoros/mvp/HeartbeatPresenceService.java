package org.preceptoros.mvp;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Visible, owner-consented sender for the existing node heartbeat contract. */
public final class HeartbeatPresenceService extends Service {
    static final String ACTION_START = "org.preceptoros.mvp.HEARTBEAT_START";
    static final String ACTION_REVOKE = "org.preceptoros.mvp.HEARTBEAT_REVOKE";
    static final String ACTION_BOOT_RESUME = "org.preceptoros.mvp.HEARTBEAT_BOOT_RESUME";
    private static final String CHANNEL = "node-presence-heartbeat";
    private static final int NOTIFICATION_ID = 4315;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService sender = Executors.newSingleThreadExecutor();
    private volatile boolean inFlight;
    private String visibleStatus = "Waiting for first Aduana receipt; public LIVE is not checked.";
    private final Runnable tick = this::sendTick;

    @Override public void onCreate() {
        super.onCreate();
        createChannel();
        // Android requires foreground promotion immediately after a user-started start.
        promote("Starting owner-approved node presence.");
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? null : intent.getAction();
        if (ACTION_REVOKE.equals(action)) {
            revokeAndStop();
            return START_NOT_STICKY;
        }
        if (!HeartbeatCredentialStore.consentActive(this)) {
            stopSelf(startId);
            return START_NOT_STICKY;
        }
        try {
            if (HeartbeatCredentialStore.deviceNode(this)) {
                String alias = NodeOwnerBridge.owner(this).beatingAlias();
                if (alias == null || !alias.equals(HeartbeatCredentialStore.deviceAlias(this)))
                    throw new IllegalStateException("device_node_unavailable");
                visibleStatus = "Node " + alias + ": service active; public LIVE is not checked.";
                updateNotification();
                handler.removeCallbacks(tick);
                handler.post(tick);
                return START_STICKY;
            }
            HeartbeatCredentialStore.Credential credential = HeartbeatCredentialStore.load(this);
            if (credential == null || !HeartbeatOncePolicy.node(credential.node) ||
                    !HeartbeatOncePolicy.key(credential.key)) {
                visibleStatus = "NO_DATA(credential_unavailable); no heartbeat sent.";
                updateNotification();
                stopSelf(startId);
                return START_NOT_STICKY;
            }
        } catch (Exception failure) {
            visibleStatus = "NO_DATA(credential_unavailable); no heartbeat sent.";
            updateNotification();
            stopSelf(startId);
            return START_NOT_STICKY;
        }
        visibleStatus = "Connected service active; public LIVE is not checked.";
        updateNotification();
        handler.removeCallbacks(tick);
        handler.post(tick);
        return START_STICKY;
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    @Override public void onDestroy() {
        handler.removeCallbacks(tick);
        sender.shutdownNow();
        super.onDestroy();
    }

    private void sendTick() {
        if (!HeartbeatServicePolicy.maySend(HeartbeatCredentialStore.consentActive(this),
                true, inFlight)) {
            if (!HeartbeatCredentialStore.consentActive(this)) stopSelf();
            return;
        }
        inFlight = true;
        sender.execute(() -> {
            String next;
            try {
                if (!HeartbeatCredentialStore.consentActive(this))
                    throw new IllegalStateException("consent_revoked");
                if (HeartbeatCredentialStore.deviceNode(this)) {
                    // The phone's own node: NodeOwner renews its key 12 h before expiry and keeps the
                    // sequence strictly increasing (max(last+1, epoch seconds)), the same chain Aduana already holds.
                    java.util.Map<String, Object> r;
                    synchronized (NodeOwner.LOCK) { r = NodeOwnerBridge.owner(this).advance(java.time.Instant.now()); }
                    String cause = String.valueOf(r.get("cause"));
                    next = "MEASURED".equals(r.get("state"))
                            ? "Node " + r.get("alias") + ": Aduana accepted the heartbeat; public LIVE is unverified."
                            : "Reconnecting; " + cause + ". Public LIVE is unverified.";
                    String status = next;
                    handler.post(() -> { inFlight = false; if (!HeartbeatCredentialStore.consentActive(this)) { stopSelf(); return; }
                        visibleStatus = status; updateNotification(); handler.postDelayed(tick, HeartbeatServicePolicy.INTERVAL_MILLIS); });
                    return;
                }
                HeartbeatCredentialStore.Credential credential = HeartbeatCredentialStore.load(this);
                if (credential == null) throw new IllegalStateException("credential_unavailable");
                JSONObject receipt = HeartbeatSender.send(this, credential.node, credential.key);
                next = "Aduana receipt " + receipt.optLong("sequence") +
                        " acknowledged; public LIVE is unverified.";
            } catch (Exception failure) {
                next = "Reconnecting; " + HeartbeatSender.safeCause(failure) +
                        ". Public LIVE is unverified.";
            }
            String status = next;
            handler.post(() -> {
                inFlight = false;
                if (!HeartbeatCredentialStore.consentActive(this)) {
                    stopSelf();
                    return;
                }
                visibleStatus = status;
                updateNotification();
                handler.postDelayed(tick, HeartbeatServicePolicy.INTERVAL_MILLIS);
            });
        });
    }

    private void revokeAndStop() {
        handler.removeCallbacks(tick);
        HeartbeatCredentialStore.revoke(this);
        visibleStatus = "Stopped; saved heartbeat credential revoked.";
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(CHANNEL,
                "Node presence", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Visible status and immediate revocation for owner-approved node heartbeats.");
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) manager.createNotificationChannel(channel);
    }

    private void promote(String text) {
        Notification notification = notification(text);
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private void updateNotification() {
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) manager.notify(NOTIFICATION_ID, notification(visibleStatus));
    }

    private Notification notification(String text) {
        Intent revoke = new Intent(this, HeartbeatPresenceService.class).setAction(ACTION_REVOKE);
        PendingIntent stop = PendingIntent.getService(this, 4316, revoke,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        builder.setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("PreceptorOS node presence")
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .addAction(android.R.drawable.ic_menu_close_clear_cancel,
                        "Revoke and stop", stop);
        return builder.build();
    }
}
