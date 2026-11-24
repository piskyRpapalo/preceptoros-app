package org.preceptoros.mvp;

/** Scheduling invariants for the owner-consented Android presence service. */
final class HeartbeatServicePolicy {
    static final long INTERVAL_MILLIS = 120_000L;
    static final long LIVE_WINDOW_MILLIS = 300_000L;
    private HeartbeatServicePolicy() {}

    static boolean safeInterval(long interval) {
        return interval > 0 && interval < LIVE_WINDOW_MILLIS;
    }

    static boolean maySend(boolean consentActive, boolean credentialAvailable,
                           boolean requestInFlight) {
        return consentActive && credentialAvailable && !requestInFlight;
    }
}
