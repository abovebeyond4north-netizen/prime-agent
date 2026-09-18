package net.abovebeyond.codieai.agent

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL

class OpenAiCompatiblePlanner(
    endpoint: String,
    private val model: String
) : Planner {
    private val endpoint = endpoint.trim().also { validateEndpoint(it) }

    override fun nextAction(goal: String, snapshot: String, step: Int): AgentAction {
        val body = JSONObject()
            .put("model", model)
            .put("temperature", 0.1)
            .put("max_tokens", 320)
            .put(
                "messages",
                JSONArray()
                    .put(JSONObject().put("role", "system").put("content", PlannerPrompt.system))
                    .put(
                        JSONObject()
                            .put("role", "user")
                            .put("content", PlannerPrompt.user(goal, snapshot, step))
                    )
            )

        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 15_000
            readTimeout = 90_000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }

        connection.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body.toString()) }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val payload = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        connection.disconnect()

        require(status in 200..299) { "Planner endpoint returned HTTP " + status + ": " + payload }

        val root = JSONObject(payload)
        val message = root
            .getJSONArray("choices")
            .getJSONObject(0)
            .getJSONObject("message")
        val rawContent = message.opt("content")
        val content = when (rawContent) {
            is String -> rawContent
            is JSONArray -> buildString {
                for (i in 0 until rawContent.length()) {
                    val part = rawContent.optJSONObject(i) ?: continue
                    append(part.optString("text", ""))
                }
            }
            else -> rawContent?.toString().orEmpty()
        }
        return AgentAction.parse(content)
    }

    private fun validateEndpoint(raw: String) {
        require(raw.isNotBlank()) { "Planner endpoint is blank" }
        val uri = URI(raw)
        val scheme = uri.scheme?.lowercase()
        require(scheme == "http" || scheme == "https") { "Planner endpoint must use HTTP or HTTPS" }
        require(!uri.host.isNullOrBlank()) { "Planner endpoint must include a host" }

        if (scheme == "http") {
            val host = uri.host.lowercase()
            require(isPrivateOrLocal(host)) {
                "Cleartext HTTP is restricted to localhost or private LAN addresses. Use HTTPS for remote endpoints."
            }
        }
    }

    private fun isPrivateOrLocal(host: String): Boolean {
        if (host == "localhost" || host == "::1" || host.endsWith(".local")) return true
        if (host.startsWith("127.") || host.startsWith("10.") || host.startsWith("192.168.")) return true
        val match = Regex("""^172\.(\d{1,3})\.""").find(host)
        val second = match?.groupValues?.getOrNull(1)?.toIntOrNull()
        return second != null && second in 16..31
    }
}
