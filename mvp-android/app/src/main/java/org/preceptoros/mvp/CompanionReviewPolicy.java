package org.preceptoros.mvp;

import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;

/**
 * Strict, public-data-only Android handoff for the EXISTING Companion intake.
 * No authorization, submission, delivery receipt or node registration is implied.
 *
 * This class has no Android dependencies, so the same policy can be tested with javac.
 */
public final class CompanionReviewPolicy {
    private static final String HOST = "github.com";
    private static final String PATH = "/piskyRpapalo/preceptoros-companion/issues/new";
    private static final String TITLE_PREFIX = "Companion admission request · ";
    private static final String BODY_PREFIX = "@piskyRpapalo · Architect review requested for one building.\n"
            + "Companion slug: ";
    private static final String BODY_SUFFIX = "\n"
            + "Declaration PR: NO_DATA(declaration_pr_not_linked)\n"
            + "Public knowledge/defense docs: NO_DATA(not_submitted)\n"
            + "Approval: pending review; no publication, grant or registration requested automatically.";

    private CompanionReviewPolicy() {}

    public static boolean accepts(String rawUrl) {
        if (rawUrl == null || rawUrl.length() > 2048 || rawUrl.length() < 80) return false;
        try {
            URI uri = new URI(rawUrl);
            if (!"https".equals(uri.getScheme()) || !HOST.equals(uri.getHost())
                    || uri.getPort() != -1 || uri.getUserInfo() != null
                    || uri.getRawFragment() != null || !PATH.equals(uri.getRawPath())) {
                return false;
            }
            String rawQuery = uri.getRawQuery();
            if (rawQuery == null) return false;
            String[] params = rawQuery.split("&", -1);
            if (params.length != 2 || !params[0].startsWith("title=")
                    || !params[1].startsWith("body=")) return false;
            String title = decode(params[0].substring("title=".length()));
            String body = decode(params[1].substring("body=".length()));
            if (!title.startsWith(TITLE_PREFIX)) return false;
            String slug = title.substring(TITLE_PREFIX.length());
            if (!slug.matches("[a-z0-9][a-z0-9-]{0,23}")) return false;
            return (BODY_PREFIX + slug + BODY_SUFFIX).equals(body);
        } catch (Exception invalidUrl) {
            return false;
        }
    }

    private static String decode(String raw) {
        return URLDecoder.decode(raw, StandardCharsets.UTF_8);
    }
}
