package org.preceptoros.mvp;

import android.content.Context;
import android.content.SharedPreferences;

/** Shared durable per-node counter. A failed POST consumes its reserved sequence. */
final class HeartbeatSequence {
    private static final Object LOCK = new Object();
    private HeartbeatSequence() {}

    static long reserve(Context context, String node) {
        synchronized (LOCK) {
            SharedPreferences storage = context.getSharedPreferences(
                    "preceptoros.heartbeat.sequence", Context.MODE_PRIVATE);
            long next = storage.getLong(node, 0L);
            if (!HeartbeatOncePolicy.sequence(next) || next == 9007199254740991L)
                throw new IllegalStateException("sequence_invalid");
            if (!storage.edit().putLong(node, next + 1L).commit())
                throw new IllegalStateException("sequence_storage_unavailable");
            return next;
        }
    }
}
