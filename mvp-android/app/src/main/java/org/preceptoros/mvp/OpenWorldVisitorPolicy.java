package org.preceptoros.mvp;

import java.net.URI;

/** Exact public game entry point. This grants visitor access only; it never creates identity. */
public final class OpenWorldVisitorPolicy {
    public static final String URL = "https://preceptoros.org/openworld/";

    public static boolean accepts(String value) {
        return URL.equals(value) && allowsNavigation(value);
    }

    /** Same-origin OpenWorld documents only; HTTPS redirects elsewhere are blocked. */
    public static boolean allowsNavigation(String value) {
        if (value == null || value.length() > 2048) return false;
        try {
            URI uri = new URI(value);
            String path = uri.getRawPath();
            return "https".equals(uri.getScheme())
                    && "preceptoros.org".equals(uri.getHost())
                    && uri.getPort() == -1 && uri.getUserInfo() == null
                    && path != null && !path.contains("%")
                    && ("/openworld".equals(uri.normalize().getRawPath())
                        || uri.normalize().getRawPath().startsWith("/openworld/"));
        } catch (Exception invalid) {
            return false;
        }
    }

    private OpenWorldVisitorPolicy() {}
}
