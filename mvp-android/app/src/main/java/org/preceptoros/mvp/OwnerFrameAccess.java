package org.preceptoros.mvp;

/** Reject subframes and stale, foreign, or unverified main documents. */
final class OwnerFrameAccess {
    static final String DOMAIN = "preceptoros.mvp.local";
    static final String ORIGIN = "https://" + DOMAIN;
    static final String PAGE = ORIGIN + "/app.html";

    static boolean accepts(String origin, boolean mainFrame, boolean ready, String page) {
        return mainFrame && ready && ORIGIN.equals(origin) && PAGE.equals(page);
    }

    private OwnerFrameAccess() {}
}
