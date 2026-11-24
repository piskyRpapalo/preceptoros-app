package org.preceptoros.mvp;

/** Deterministic policy vectors; does not start a service or send a request. */
public final class HeartbeatServicePolicyTest {
    public static void main(String[] args) {
        int passed = 0;
        if (HeartbeatServicePolicy.safeInterval(HeartbeatServicePolicy.INTERVAL_MILLIS)) passed++;
        if (!HeartbeatServicePolicy.safeInterval(0)) passed++;
        if (!HeartbeatServicePolicy.safeInterval(HeartbeatServicePolicy.LIVE_WINDOW_MILLIS)) passed++;
        if (HeartbeatServicePolicy.maySend(true, true, false)) passed++;
        if (!HeartbeatServicePolicy.maySend(false, true, false)) passed++;
        if (!HeartbeatServicePolicy.maySend(true, false, false)) passed++;
        if (!HeartbeatServicePolicy.maySend(true, true, true)) passed++;
        if (passed != 7) throw new AssertionError("service policy vectors failed: " + passed + "/7");
        System.out.println("PASS " + passed + "/7");
    }
}
