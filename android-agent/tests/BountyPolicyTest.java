import net.abovebeyond.codieai.bounty.BountyPolicy;

public class BountyPolicyTest {
    private static int checks;
    private static void check(boolean value) {
        checks++;
        if (!value) throw new AssertionError("Check " + checks + " failed");
    }
    public static void main(String[] args) {
        check(BountyPolicy.validIssueUrl("https://github.com/owner/repo/issues/12"));
        for (String url : new String[] {
            "https://github.com.evil.test/a/b/issues/1", "http://github.com/a/b/issues/1",
            "https://github.com@evil.test/a/b/issues/1", "https://github.com/a/b/pull/1",
            "https://github.com/a/b/issues/1?redirect=evil", "https://github.com:444/a/b/issues/1",
            "javascript:alert(1)", "https://github.com/a/b/issues/0", "not a url"
        }) check(!BountyPolicy.validIssueUrl(url));
        check(BountyPolicy.amountMention("Bounty USD 125.50").equals("USD 125.50"));
        check(BountyPolicy.amountMention("$1,250 reward").equals("$1,250"));
        check(BountyPolicy.amountMention("No payment promised").equals("No amount found"));
        check(BountyPolicy.score("Fix", "", false) > BountyPolicy.score("Fix", "", true));
        check(BountyPolicy.score("Python tests $100", "reproduce", false) == 80);
        check(BountyPolicy.score("Python tests $100", "reproduce upfront fee", false) == 40);
        check(BountyPolicy.score("deposit", "", true) == 0);
        System.out.println("BountyPolicy: " + checks + " checks passed");
    }
}
