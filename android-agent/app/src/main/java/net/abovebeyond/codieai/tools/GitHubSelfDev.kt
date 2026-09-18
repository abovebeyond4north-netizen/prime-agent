package net.abovebeyond.codieai.tools

import android.content.Context
import android.net.Uri
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.ZipInputStream

object GitHubSelfDev {
    private const val API = "https://api.github.com"
    private const val OWNER = "abovebeyond4north-netizen"
    private const val REPO = "prime-agent"
    private const val BASE_BRANCH = "feature/android-agent"
    private const val BRANCH_PREFIX = "codie-selfdev/"
    private const val TOKEN_ALIAS = "github_token"
    private const val PREFS = "codie_ai_selfdev"
    private const val KEY_ACTIVE_BRANCH = "active_branch"
    private const val MAX_SOURCE_BYTES = 500_000
    private const val MAX_PATCH_FILES = 10
    private const val MAX_LOG_CHARS = 80_000
    private const val MAX_ARTIFACT_BYTES = 160_000_000L
    private const val MAX_APK_BYTES = 320_000_000L

    fun status(context: Context): String {
        val token = SecretStore.exists(context, TOKEN_ALIAS)
        val branch = activeBranch(context).ifBlank { "(none)" }
        return "Self-development: repo=" + OWNER + "/" + REPO +
            " base=" + BASE_BRANCH +
            " active_branch=" + branch +
            " github_token_stored=" + token +
            "\nWrites are restricted to android-agent/** on codie-selfdev/** branches. " +
            "This subsystem cannot merge to main."
    }

    fun begin(context: Context, goal: String): String {
        requireToken(context)
        val cleanedGoal = goal.trim()
        require(cleanedGoal.isNotBlank()) { "Self-development goal is blank" }

        val baseSha = refSha(context, BASE_BRANCH)
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        val slug = cleanedGoal
            .lowercase(Locale.US)
            .replace(Regex("[^a-z0-9]+"), "-")
            .trim('-')
            .take(36)
            .ifBlank { "improvement" }

        val branch = BRANCH_PREFIX + stamp + "-" + slug
        val body = JSONObject()
            .put("ref", "refs/heads/" + branch)
            .put("sha", baseSha)

        apiJson(context, "POST", repoPath("/git/refs"), body, authRequired = true)
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ACTIVE_BRANCH, branch)
            .apply()

        return "Created self-development branch " + branch +
            " from " + BASE_BRANCH + " at " + baseSha +
            ". Inspect source, make bounded changes, then verify CI. Do not merge."
    }

    fun activeBranch(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_ACTIVE_BRANCH, "")
            .orEmpty()

    fun tree(context: Context, branchArg: String = ""): String {
        val branch = branch(context, branchArg, allowBase = true)
        val commitSha = refSha(context, branch)
        val commit = apiJson(
            context,
            "GET",
            repoPath("/git/commits/" + encode(commitSha)),
            null,
            authRequired = false
        )
        val treeSha = commit.getJSONObject("tree").getString("sha")
        val tree = apiJson(
            context,
            "GET",
            repoPath("/git/trees/" + encode(treeSha)) + "?recursive=1",
            null,
            authRequired = false
        ).optJSONArray("tree") ?: JSONArray()

        val paths = ArrayList<String>()
        for (i in 0 until tree.length()) {
            val item = tree.optJSONObject(i) ?: continue
            val path = item.optString("path", "")
            if (
                item.optString("type") == "blob" &&
                path.startsWith("android-agent/")
            ) {
                paths.add(path)
            }
        }

        return buildString {
            append("android-agent source tree @ ").append(branch)
            paths.sorted().take(500).forEach {
                append("\n- ").append(it)
            }
            if (paths.size > 500) append("\n... ").append(paths.size - 500).append(" more")
        }
    }

    fun read(
        context: Context,
        pathArg: String,
        branchArg: String = "",
        offset: Int = 0,
        maxChars: Int = 6000
    ): String {
        val path = sourcePath(pathArg)
        val branch = branch(context, branchArg, allowBase = true)
        val content = readFile(context, path, branch)
        val start = offset.coerceIn(0, content.length)
        val end = (start + maxChars.coerceIn(500, 12_000)).coerceAtMost(content.length)

        return buildString {
            append(path).append(" @ ").append(branch)
                .append(" chars ").append(start).append("..").append(end)
                .append("/").append(content.length).append(":\n")
            append(content.substring(start, end))
            if (end < content.length) {
                append("\n[more available; next offset=").append(end).append("]")
            }
        }
    }

    fun find(
        context: Context,
        pathArg: String,
        query: String,
        branchArg: String = ""
    ): String {
        val path = sourcePath(pathArg)
        val branch = branch(context, branchArg, allowBase = true)
        val needle = query.trim()
        require(needle.isNotBlank()) { "Find query is blank" }

        val lines = readFile(context, path, branch).lines()
        val hits = ArrayList<String>()
        lines.forEachIndexed { index, line ->
            if (line.contains(needle, ignoreCase = true)) {
                val from = (index - 2).coerceAtLeast(0)
                val to = (index + 3).coerceAtMost(lines.size)
                hits.add(
                    buildString {
                        append("lines ").append(from + 1).append("..").append(to)
                        for (i in from until to) {
                            append("\n").append(i + 1).append(": ").append(lines[i])
                        }
                    }
                )
            }
        }

        return if (hits.isEmpty()) {
            "No matches in " + path + " for: " + needle
        } else {
            hits.take(20).joinToString(
                separator = "\n\n",
                prefix = "Matches in " + path + " @ " + branch + ":\n"
            )
        }.take(20_000)
    }

    fun patch(
        context: Context,
        branchArg: String,
        message: String,
        changesJson: String
    ): String {
        requireToken(context)
        val branch = branch(context, branchArg, allowBase = false)
        val commitMessage = message.trim()
        require(commitMessage.length in 5..180) {
            "Commit message must be 5..180 characters"
        }

        val changes = JSONArray(changesJson)
        require(changes.length() in 1..MAX_PATCH_FILES) {
            "A self-development commit must change 1.." + MAX_PATCH_FILES + " files"
        }

        val parentSha = refSha(context, branch)
        val parent = apiJson(
            context,
            "GET",
            repoPath("/git/commits/" + encode(parentSha)),
            null,
            authRequired = true
        )
        val baseTree = parent.getJSONObject("tree").getString("sha")
        val treeItems = JSONArray()
        val changedPaths = ArrayList<String>()

        for (i in 0 until changes.length()) {
            val change = changes.getJSONObject(i)
            val path = sourcePath(change.getString("path"))
            val updated = when {
                change.has("content") -> change.getString("content")
                change.has("old") && change.has("new") -> {
                    val current = readFile(context, path, branch)
                    val old = change.getString("old")
                    require(old.isNotEmpty()) { "Exact replacement old text is empty for " + path }
                    val occurrences = countOccurrences(current, old)
                    require(occurrences == 1) {
                        "Exact replacement for " + path + " matched " + occurrences +
                            " times; expected exactly 1"
                    }
                    current.replace(old, change.getString("new"))
                }
                else -> throw IllegalArgumentException(
                    "Each change requires either content or old+new: " + path
                )
            }

            val bytes = updated.toByteArray(Charsets.UTF_8)
            require(bytes.size <= MAX_SOURCE_BYTES) {
                "Generated source file is too large: " + path
            }

            val blob = apiJson(
                context,
                "POST",
                repoPath("/git/blobs"),
                JSONObject()
                    .put("content", updated)
                    .put("encoding", "utf-8"),
                authRequired = true
            )

            treeItems.put(
                JSONObject()
                    .put("path", path)
                    .put("mode", "100644")
                    .put("type", "blob")
                    .put("sha", blob.getString("sha"))
            )
            changedPaths.add(path)
        }

        val tree = apiJson(
            context,
            "POST",
            repoPath("/git/trees"),
            JSONObject()
                .put("base_tree", baseTree)
                .put("tree", treeItems),
            authRequired = true
        )

        val commit = apiJson(
            context,
            "POST",
            repoPath("/git/commits"),
            JSONObject()
                .put("message", commitMessage)
                .put("tree", tree.getString("sha"))
                .put("parents", JSONArray().put(parentSha)),
            authRequired = true
        )
        val commitSha = commit.getString("sha")

        apiJson(
            context,
            "PATCH",
            repoPath("/git/refs/heads/" + encodeRef(branch)),
            JSONObject()
                .put("sha", commitSha)
                .put("force", false),
            authRequired = true
        )

        return "Committed " + changedPaths.size + " file(s) to " + branch +
            " at " + commitSha +
            ":\n" + changedPaths.joinToString("\n") { "- " + it } +
            "\nGitHub Actions should start automatically for this self-development branch."
    }

    fun review(context: Context, branchArg: String = ""): String {
        val branch = branch(context, branchArg, allowBase = false)
        val compare = apiJson(
            context,
            "GET",
            repoPath(
                "/compare/" + encode(BASE_BRANCH) + "..." + encode(branch)
            ),
            null,
            authRequired = false
        )
        val files = compare.optJSONArray("files") ?: JSONArray()

        return buildString {
            append("Self-development review ").append(BASE_BRANCH)
                .append("...").append(branch)
            append("\nstatus=").append(compare.optString("status", "unknown"))
            append(" ahead_by=").append(compare.optInt("ahead_by", 0))
            append(" behind_by=").append(compare.optInt("behind_by", 0))
            append(" files=").append(files.length())

            for (i in 0 until files.length().coerceAtMost(30)) {
                val file = files.getJSONObject(i)
                append("\n\n").append(file.optString("filename"))
                    .append(" [").append(file.optString("status")).append("]")
                    .append(" +").append(file.optInt("additions"))
                    .append(" -").append(file.optInt("deletions"))
                file.optString("patch", "").takeIf { it.isNotBlank() }?.let {
                    append("\n").append(it.take(2500))
                }
            }
        }.take(30_000)
    }

    fun ci(context: Context, branchArg: String = ""): String {
        val branch = branch(context, branchArg, allowBase = false)
        val query = "?branch=" + query(branch) + "&per_page=5"
        val runs = apiJson(
            context,
            "GET",
            repoPath("/actions/workflows/android-agent.yml/runs") + query,
            null,
            authRequired = false
        ).optJSONArray("workflow_runs") ?: JSONArray()

        if (runs.length() == 0) {
            return "No Android Agent workflow run found yet for " + branch
        }

        val run = runs.getJSONObject(0)
        val runId = run.getLong("id")
        val jobs = apiJson(
            context,
            "GET",
            repoPath("/actions/runs/" + runId + "/jobs?per_page=100"),
            null,
            authRequired = false
        ).optJSONArray("jobs") ?: JSONArray()

        return buildString {
            append("CI branch=").append(branch)
            append(" run_id=").append(runId)
            append(" status=").append(run.optString("status"))
            append(" conclusion=").append(run.optString("conclusion", ""))
            append(" head_sha=").append(run.optString("head_sha", ""))
            append(" url=").append(run.optString("html_url", ""))

            for (i in 0 until jobs.length()) {
                val job = jobs.getJSONObject(i)
                append("\njob_id=").append(job.optLong("id"))
                    .append(" ").append(job.optString("name"))
                    .append(" status=").append(job.optString("status"))
                    .append(" conclusion=").append(job.optString("conclusion", ""))
                val steps = job.optJSONArray("steps") ?: JSONArray()
                for (j in 0 until steps.length()) {
                    val step = steps.getJSONObject(j)
                    append("\n  - ").append(step.optString("name"))
                        .append(": ").append(step.optString("status"))
                        .append("/").append(step.optString("conclusion", ""))
                }
            }
        }.take(24_000)
    }

    fun logs(context: Context, runId: Long): String {
        require(runId > 0) { "Invalid CI run id" }
        val jobs = apiJson(
            context,
            "GET",
            repoPath("/actions/runs/" + runId + "/jobs?per_page=100"),
            null,
            authRequired = false
        ).optJSONArray("jobs") ?: JSONArray()

        val selected = ArrayList<Long>()
        for (i in 0 until jobs.length()) {
            val job = jobs.getJSONObject(i)
            if (job.optString("conclusion") == "failure") {
                selected.add(job.getLong("id"))
            }
        }
        if (selected.isEmpty() && jobs.length() > 0) {
            selected.add(jobs.getJSONObject(0).getLong("id"))
        }
        require(selected.isNotEmpty()) { "CI run has no jobs yet" }

        return buildString {
            append("CI logs for run ").append(runId)
            selected.take(3).forEach { jobId ->
                append("\n\n===== job ").append(jobId).append(" =====\n")
                append(downloadJobLog(context, jobId).take(MAX_LOG_CHARS / 3))
            }
        }.let(::redactLog).take(MAX_LOG_CHARS)
    }

    fun artifacts(context: Context, runId: Long): String {
        require(runId > 0) { "Invalid CI run id" }
        val artifacts = apiJson(
            context,
            "GET",
            repoPath("/actions/runs/" + runId + "/artifacts?per_page=100"),
            null,
            authRequired = false
        ).optJSONArray("artifacts") ?: JSONArray()

        if (artifacts.length() == 0) return "No artifacts available for run " + runId

        return buildString {
            append("Artifacts for run ").append(runId).append(":")
            for (i in 0 until artifacts.length()) {
                val artifact = artifacts.getJSONObject(i)
                append("\n- id=").append(artifact.optLong("id"))
                    .append(" name=").append(artifact.optString("name"))
                    .append(" size=").append(artifact.optLong("size_in_bytes"))
                    .append(" expired=").append(artifact.optBoolean("expired"))
            }
        }
    }

    fun fetchApk(context: Context, runId: Long): String {
        requireToken(context)
        require(runId > 0) { "Invalid CI run id" }

        val artifacts = apiJson(
            context,
            "GET",
            repoPath("/actions/runs/" + runId + "/artifacts?per_page=100"),
            null,
            authRequired = true
        ).optJSONArray("artifacts") ?: JSONArray()

        var artifactId = -1L
        for (i in 0 until artifacts.length()) {
            val item = artifacts.getJSONObject(i)
            if (
                item.optString("name") == "codie-ai-debug-apk" &&
                !item.optBoolean("expired", false)
            ) {
                artifactId = item.getLong("id")
                break
            }
        }
        require(artifactId > 0) {
            "No non-expired codie-ai-debug-apk artifact found for run " + runId
        }

        val zip = File(context.cacheDir, "selfdev-" + runId + ".zip")
        downloadArtifactZip(context, artifactId, zip)

        var apkBytes = 0L
        var outputName = ""
        ZipInputStream(zip.inputStream().buffered()).use { zin ->
            while (true) {
                val entry = zin.nextEntry ?: break
                if (!entry.isDirectory && entry.name.lowercase(Locale.US).endsWith(".apk")) {
                    val safeName = "codie-selfdev-" + runId + ".apk"
                    val out = WorkspaceTools.file(context, safeName)
                    FileOutputStream(out).use { output ->
                        val buffer = ByteArray(1024 * 1024)
                        while (true) {
                            val count = zin.read(buffer)
                            if (count < 0) break
                            apkBytes += count
                            require(apkBytes <= MAX_APK_BYTES) {
                                "Downloaded APK exceeds allowed size"
                            }
                            output.write(buffer, 0, count)
                        }
                    }
                    outputName = out.name
                    break
                }
                zin.closeEntry()
            }
        }
        zip.delete()
        require(outputName.isNotBlank()) { "Artifact ZIP did not contain an APK" }

        return "Downloaded verified CI artifact to private workspace file " +
            outputName + " (" + apkBytes + " bytes). " +
            "Installation still requires the Android package-installer/user approval boundary."
    }

    private fun refSha(context: Context, branch: String): String {
        val ref = apiJson(
            context,
            "GET",
            repoPath("/git/ref/heads/" + encodeRef(branch)),
            null,
            authRequired = false
        )
        return ref.getJSONObject("object").getString("sha")
    }

    private fun readFile(context: Context, path: String, branch: String): String {
        val response = apiJson(
            context,
            "GET",
            repoPath("/contents/" + encodePath(path)) + "?ref=" + query(branch),
            null,
            authRequired = false
        )
        require(response.optString("type") == "file") { "Not a file: " + path }
        val encoded = response.optString("content", "").replace("\n", "")
        require(encoded.isNotBlank()) { "GitHub did not return inline content for " + path }
        val bytes = Base64.decode(encoded, Base64.DEFAULT)
        require(bytes.size <= MAX_SOURCE_BYTES) { "Source file is too large: " + path }
        return bytes.toString(Charsets.UTF_8)
    }

    private fun sourcePath(raw: String): String {
        val path = raw.trim().removePrefix("/")
        require(path.startsWith("android-agent/")) {
            "Self-development writes/reads are restricted to android-agent/**"
        }
        require(!path.contains("..") && !path.contains('\\')) {
            "Invalid self-development source path"
        }
        return path
    }

    private fun branch(
        context: Context,
        requested: String,
        allowBase: Boolean
    ): String {
        val value = requested.trim().ifBlank { activeBranch(context) }
        require(value.isNotBlank()) { "No active self-development branch. Run selfdev_begin first." }

        if (allowBase && value == BASE_BRANCH) return value
        require(value.startsWith(BRANCH_PREFIX)) {
            "Self-development may only modify codie-selfdev/** branches"
        }
        return value
    }

    private fun requireToken(context: Context) {
        require(SecretStore.exists(context, TOKEN_ALIAS)) {
            "Store a GitHub fine-grained token in the encrypted vault under alias '" +
                TOKEN_ALIAS + "'. It needs Contents read/write and Actions read for this repository."
        }
    }

    private fun apiJson(
        context: Context,
        method: String,
        pathAndQuery: String,
        body: JSONObject?,
        authRequired: Boolean
    ): JSONObject {
        val response = apiText(context, method, pathAndQuery, body, authRequired)
        return JSONObject(response)
    }

    private fun apiText(
        context: Context,
        method: String,
        pathAndQuery: String,
        body: JSONObject?,
        authRequired: Boolean
    ): String {
        val token = if (SecretStore.exists(context, TOKEN_ALIAS)) {
            SecretStore.resolve(context, TOKEN_ALIAS)
        } else {
            require(!authRequired) { "GitHub token is required for this operation" }
            ""
        }

        val connection = (URL(API + pathAndQuery).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 15_000
            readTimeout = 45_000
            instanceFollowRedirects = false
            setRequestProperty("Accept", "application/vnd.github+json")
            setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
            setRequestProperty("User-Agent", "CodieAI-SelfDev/1.8")
            if (token.isNotBlank()) {
                setRequestProperty("Authorization", "Bearer " + token)
            }
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
        }

        if (body != null) {
            connection.outputStream.use {
                it.write(body.toString().toByteArray(Charsets.UTF_8))
            }
        }

        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        connection.disconnect()

        require(status in 200..299) {
            "GitHub API " + method + " " + pathAndQuery.substringBefore('?') +
                " returned HTTP " + status + ": " + text.take(2500)
        }
        return text
    }

    private fun downloadJobLog(context: Context, jobId: Long): String {
        requireToken(context)
        val token = SecretStore.resolve(context, TOKEN_ALIAS)
        val first = (URL(API + repoPath("/actions/jobs/" + jobId + "/logs"))
            .openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 15_000
            readTimeout = 30_000
            instanceFollowRedirects = false
            setRequestProperty("Accept", "application/vnd.github+json")
            setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
            setRequestProperty("Authorization", "Bearer " + token)
            setRequestProperty("User-Agent", "CodieAI-SelfDev/1.8")
        }

        val status = first.responseCode
        val location = first.getHeaderField("Location")
        if (status in 300..399 && !location.isNullOrBlank()) {
            first.disconnect()
            val redirected = URL(location)
            require(redirected.protocol.equals("https", true)) {
                "GitHub log redirect was not HTTPS"
            }
            val second = redirected.openConnection() as HttpURLConnection
            second.connectTimeout = 15_000
            second.readTimeout = 45_000
            second.instanceFollowRedirects = true
            second.setRequestProperty("User-Agent", "CodieAI-SelfDev/1.8")
            return second.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
                val out = StringBuilder()
                val buffer = CharArray(8192)
                while (out.length < MAX_LOG_CHARS) {
                    val count = reader.read(buffer)
                    if (count < 0) break
                    out.append(buffer, 0, count.coerceAtMost(MAX_LOG_CHARS - out.length))
                }
                out.toString()
            }.also { second.disconnect() }
        }

        val stream = if (status in 200..299) first.inputStream else first.errorStream
        val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        first.disconnect()
        require(status in 200..299) {
            "GitHub job logs returned HTTP " + status + ": " + text.take(1200)
        }
        return text.take(MAX_LOG_CHARS)
    }

    private fun downloadArtifactZip(context: Context, artifactId: Long, destination: File) {
        val token = SecretStore.resolve(context, TOKEN_ALIAS)
        val first = (URL(API + repoPath("/actions/artifacts/" + artifactId + "/zip"))
            .openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 15_000
            readTimeout = 45_000
            instanceFollowRedirects = false
            setRequestProperty("Accept", "application/vnd.github+json")
            setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
            setRequestProperty("Authorization", "Bearer " + token)
            setRequestProperty("User-Agent", "CodieAI-SelfDev/1.8")
        }

        val status = first.responseCode
        val location = first.getHeaderField("Location")
        require(status in 300..399 && !location.isNullOrBlank()) {
            "GitHub artifact download did not return a redirect; HTTP " + status
        }
        first.disconnect()

        val redirected = URL(location)
        require(redirected.protocol.equals("https", true)) {
            "GitHub artifact redirect was not HTTPS"
        }
        val second = redirected.openConnection() as HttpURLConnection
        second.connectTimeout = 20_000
        second.readTimeout = 120_000
        second.instanceFollowRedirects = true
        second.setRequestProperty("User-Agent", "CodieAI-SelfDev/1.8")

        var total = 0L
        destination.outputStream().buffered(1024 * 1024).use { output ->
            second.inputStream.buffered(1024 * 1024).use { input ->
                val buffer = ByteArray(1024 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    require(total <= MAX_ARTIFACT_BYTES) {
                        "GitHub artifact ZIP exceeds allowed size"
                    }
                    output.write(buffer, 0, count)
                }
            }
        }
        second.disconnect()
    }

    private fun redactLog(raw: String): String =
        raw
            .replace(Regex("github_pat_[A-Za-z0-9_]{20,}"), "[REDACTED_GITHUB_TOKEN]")
            .replace(Regex("gh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]")
            .replace(Regex("(?i)Authorization:\\s*Bearer\\s+\\S+"), "Authorization: Bearer [REDACTED]")

    private fun countOccurrences(text: String, needle: String): Int {
        var count = 0
        var from = 0
        while (true) {
            val index = text.indexOf(needle, from)
            if (index < 0) return count
            count++
            from = index + needle.length
        }
    }

    private fun repoPath(suffix: String): String =
        "/repos/" + OWNER + "/" + REPO + suffix

    private fun encode(value: String): String = Uri.encode(value)
    private fun encodeRef(value: String): String = Uri.encode(value, "/")
    private fun encodePath(value: String): String =
        value.split('/').joinToString("/") { Uri.encode(it) }

    private fun query(value: String): String =
        URLEncoder.encode(value, Charsets.UTF_8.name())
}
