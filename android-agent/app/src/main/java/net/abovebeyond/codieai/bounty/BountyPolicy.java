package net.abovebeyond.codieai.bounty;

import java.net.URI;
import java.util.Locale;
import java.util.regex.Pattern;

/** Deterministic triage, not a prediction of payout or profitability. */
public final class BountyPolicy {
    private static final Pattern MONEY = Pattern.compile(
        "(?i)(?:\\$|USD\\s*|CAD\\s*|EUR\\s*)[0-9]+(?:[,.][0-9]+)*");
    private BountyPolicy() {}

    public static boolean validIssueUrl(String value) {
        try {
            URI uri = URI.create(value);
            return "https".equals(uri.getScheme()) && "github.com".equals(uri.getHost())
                && uri.getUserInfo() == null && uri.getPort() == -1
                && uri.getQuery() == null && uri.getFragment() == null
                && uri.getPath().matches("/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[1-9][0-9]*");
        } catch (IllegalArgumentException error) {
            return false;
        }
    }

    public static String amountMention(String text) {
        java.util.regex.Matcher match = MONEY.matcher(text);
        return match.find() ? match.group() : "No amount found";
    }

    public static int score(String title, String body, boolean assigned) {
        String text = (title + "\n" + body).toLowerCase(Locale.ROOT);
        int score = assigned ? 0 : 20;
        if (MONEY.matcher(text).find()) score += 20;
        if (text.contains("reproduce") || text.contains("expected behavior")) score += 15;
        if (text.contains("test") || text.contains("acceptance criteria")) score += 15;
        if (text.contains("documentation") || text.contains("typo")) score += 10;
        if (text.contains("python") || text.contains("kotlin") || text.contains("typescript")) score += 10;
        if (text.contains("deposit") || text.contains("upfront fee")) score -= 40;
        return Math.max(0, Math.min(100, score));
    }
}
