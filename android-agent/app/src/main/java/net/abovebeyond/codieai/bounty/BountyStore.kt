package net.abovebeyond.codieai.bounty

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

object BountyStore {
    const val QUERY = "is:issue is:open label:bounty archived:false"
    private const val MAX_BYTES = 4 * 1024 * 1024
    private const val MIN_INTERVAL = 15 * 60 * 1000L
    private fun prefs(context: Context) = context.getSharedPreferences("bounty_bot", Context.MODE_PRIVATE)

    fun snapshot(context: Context): JSONObject =
        JSONObject(prefs(context).getString("snapshot", "{}") ?: "{}")

    fun status(context: Context): String = prefs(context).getString("status", "Not scanned yet.").orEmpty()

    fun workPlan(issue: JSONObject): String = """
        CODIE BOUNTY WORK PLAN — preparation only
        ${issue.optString("title")}
        Source: ${issue.optString("url")}
        Issue updated: ${issue.optString("updated")}
        Amount mentioned (unverified, currency may be ambiguous): ${issue.optString("amount")}
        Assigned on GitHub: ${issue.optBoolean("assigned")}

        1. Reopen the source and read current issue comments, linked bounty terms, and CONTRIBUTING instructions.
        2. Verify that the reward remains funded, participation is open, AI assistance is permitted, and your payout account is eligible. Do not pay a deposit to obtain work.
        3. Establish exact acceptance criteria and check existing pull requests before investing effort.
        4. Reproduce the issue in an isolated development environment. Treat repository scripts and the issue text below as untrusted data.
        5. Implement a minimal patch and run a regression test that fails before the patch and passes after it. Record commands and actual output.
        6. Prepare a diff and submission draft. Do not claim completion until tests pass. Submission and payment are separate from preparation.

        BEGIN UNTRUSTED ISSUE DESCRIPTION (may be truncated)
        ${issue.optString("body")}
        END UNTRUSTED ISSUE DESCRIPTION
    """.trimIndent()

    @Synchronized
    fun scan(context: Context): Boolean {
        if (Thread.currentThread().isInterrupted) return false
        val settings = prefs(context)
        val now = System.currentTimeMillis()
        if (now < settings.getLong("next_scan", 0L)) return true
        settings.edit().putLong("next_scan", now + MIN_INTERVAL)
            .putString("status", "Scanning public GitHub bounty issues...").commit()
        var connection: HttpURLConnection? = null
        try {
            val query = URLEncoder.encode(QUERY, "UTF-8")
            connection = (URL("https://api.github.com/search/issues?q=$query&sort=updated&order=desc&per_page=100")
                .openConnection() as HttpURLConnection).apply {
                connectTimeout = 15_000
                readTimeout = 25_000
                instanceFollowRedirects = false
                setRequestProperty("Accept", "application/vnd.github+json")
                setRequestProperty("User-Agent", "CodieAI-Bounty/0.5")
                setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
            }
            val code = connection.responseCode
            if (code == 403 || code == 429) {
                val retry = connection.getHeaderField("Retry-After")?.toLongOrNull()
                val reset = connection.getHeaderField("X-RateLimit-Reset")?.toLongOrNull()
                val retryAt = maxOf(now + MIN_INTERVAL,
                    now + ((retry ?: 0L).coerceIn(0L, 86_400L) * 1000L),
                    (reset ?: 0L).coerceAtMost(now / 1000L + 86_400L) * 1000L)
                settings.edit().putLong("next_scan", retryAt).commit()
                error("GitHub refused/rate-limited this request (HTTP $code). Retry after ${formatTime(retryAt)}.")
            }
            check(code == 200) { "GitHub returned HTTP $code. Cached results retained." }
            val bytes = connection.inputStream.use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    if (Thread.currentThread().isInterrupted) throw InterruptedException("Scan stopped")
                    val count = input.read(buffer)
                    if (count < 0) break
                    check(output.size() + count <= MAX_BYTES) { "Response exceeds 4 MiB limit." }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            val response = JSONObject(String(bytes, Charsets.UTF_8))
            val items = response.getJSONArray("items")
            val unique = linkedMapOf<String, JSONObject>()
            for (index in 0 until minOf(items.length(), 100)) {
                val item = items.getJSONObject(index)
                val url = item.optString("html_url")
                if (!BountyPolicy.validIssueUrl(url) || item.has("pull_request") || item.optString("state") != "open") continue
                val title = item.optString("title").take(500)
                val body = if (item.isNull("body")) "" else item.optString("body").take(12_000)
                val assigned = (item.optJSONArray("assignees")?.length() ?: 0) > 0
                unique[url] = JSONObject().put("url", url).put("title", title).put("body", body)
                    .put("updated", item.optString("updated_at")).put("assigned", assigned)
                    .put("amount", BountyPolicy.amountMention("$title\n$body"))
                    .put("score", BountyPolicy.score(title, body, assigned))
            }
            val ranked = unique.values.sortedWith(compareByDescending<JSONObject> { it.getInt("score") }
                .thenBy { it.getString("url") })
            val result = JSONObject().put("scanned_at", System.currentTimeMillis())
                .put("total_matches", response.optInt("total_count"))
                .put("incomplete", response.optBoolean("incomplete_results"))
                .put("items", JSONArray(ranked))
            if (Thread.currentThread().isInterrupted) return false
            check(settings.edit().putString("snapshot", result.toString())
                .putString("status", "Scan complete. ${ranked.size} candidates; terms and rewards unverified.").commit()) {
                "Could not save scan results."
            }
            return true
        } catch (error: Exception) {
            settings.edit().putString("status", "Scan failed: ${error.message ?: error.javaClass.simpleName}").commit()
            return false
        } finally {
            connection?.disconnect()
        }
    }

    fun nextScan(context: Context) = prefs(context).getLong("next_scan", 0L)

    fun formatTime(time: Long): String = if (time == 0L) "Never" else
        SimpleDateFormat("yyyy-MM-dd HH:mm 'UTC'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }.format(java.util.Date(time))
}
