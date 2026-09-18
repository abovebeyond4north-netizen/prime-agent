package net.abovebeyond.codieai.tools

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicLong

object McpClient {
    private const val PROTOCOL_VERSION = "2026-07-28"
    private const val MAX_RESPONSE_BYTES = 768_000
    private const val MAX_RESULT_CHARS = 20_000
    private val nextId = AtomicLong(1000)

    fun listTools(
        context: Context,
        server: McpServerDefinition
    ): List<McpToolDefinition> {
        val tools = ArrayList<McpToolDefinition>()
        var cursor: String? = null

        repeat(5) {
            val params = baseParams()
            if (!cursor.isNullOrBlank()) params.put("cursor", cursor)

            val result = completeResult(
                request(context, server, "tools/list", params, null)
            )
            val array = result.optJSONArray("tools") ?: JSONArray()
            for (i in 0 until array.length()) {
                val tool = array.getJSONObject(i)
                tools.add(
                    McpToolDefinition(
                        name = tool.getString("name"),
                        description = tool.optString("description", ""),
                        inputSchema = tool.optJSONObject("inputSchema")?.toString() ?: "{}"
                    )
                )
            }

            cursor = result.optString("nextCursor", "").ifBlank { null }
            if (cursor == null) return tools
        }

        return tools
    }

    fun callTool(
        context: Context,
        server: McpServerDefinition,
        toolName: String,
        argumentsJson: String
    ): String {
        val params = baseParams()
            .put("name", toolName)
            .put("arguments", JSONObject(argumentsJson.ifBlank { "{}" }))

        val result = completeResult(
            request(context, server, "tools/call", params, toolName)
        )
        return renderToolResult(result).take(MAX_RESULT_CHARS)
    }

    fun listResources(
        context: Context,
        server: McpServerDefinition
    ): String {
        val results = ArrayList<String>()
        var cursor: String? = null

        repeat(5) {
            val params = baseParams()
            if (!cursor.isNullOrBlank()) params.put("cursor", cursor)

            val result = completeResult(
                request(context, server, "resources/list", params, null)
            )
            val array = result.optJSONArray("resources") ?: JSONArray()
            for (i in 0 until array.length()) {
                val resource = array.getJSONObject(i)
                results.add(
                    buildString {
                        append(resource.optString("name", resource.optString("uri", "resource")))
                        append(" | uri=").append(resource.optString("uri", ""))
                        resource.optString("mimeType", "").takeIf { it.isNotBlank() }?.let {
                            append(" | mime=").append(it)
                        }
                        resource.optString("description", "").takeIf { it.isNotBlank() }?.let {
                            append(" | ").append(it.take(500))
                        }
                    }
                )
                if (results.size >= 100) return@repeat
            }

            cursor = result.optString("nextCursor", "").ifBlank { null }
            if (cursor == null || results.size >= 100) {
                return if (results.isEmpty()) {
                    "MCP server exposes no direct resources."
                } else {
                    "MCP resources:\n" + results.joinToString("\n") { "- " + it }
                }
            }
        }

        return if (results.isEmpty()) {
            "MCP server exposes no direct resources."
        } else {
            "MCP resources:\n" + results.joinToString("\n") { "- " + it }
        }
    }

    fun readResource(
        context: Context,
        server: McpServerDefinition,
        uri: String
    ): String {
        val params = baseParams().put("uri", uri)
        val result = completeResult(
            request(context, server, "resources/read", params, null)
        )
        val contents = result.optJSONArray("contents") ?: JSONArray()

        if (contents.length() == 0) return "MCP resource returned no content."

        return buildString {
            append("MCP resource ").append(uri).append(":")
            for (i in 0 until contents.length()) {
                val item = contents.optJSONObject(i) ?: continue
                append("\n\n")
                append(item.optString("uri", uri))
                item.optString("mimeType", "").takeIf { it.isNotBlank() }?.let {
                    append(" [").append(it).append("]")
                }

                when {
                    item.has("text") -> {
                        append("\n").append(item.optString("text", "").take(18_000))
                    }
                    item.has("blob") -> {
                        val blob = item.optString("blob", "")
                        append("\n[binary resource, base64_chars=")
                            .append(blob.length)
                            .append("]")
                    }
                    else -> append("\n").append(item.toString().take(4_000))
                }
            }
        }.take(MAX_RESULT_CHARS)
    }

    fun listPrompts(
        context: Context,
        server: McpServerDefinition
    ): String {
        val results = ArrayList<String>()
        var cursor: String? = null

        repeat(5) {
            val params = baseParams()
            if (!cursor.isNullOrBlank()) params.put("cursor", cursor)

            val result = completeResult(
                request(context, server, "prompts/list", params, null)
            )
            val array = result.optJSONArray("prompts") ?: JSONArray()

            for (i in 0 until array.length()) {
                val prompt = array.getJSONObject(i)
                val args = prompt.optJSONArray("arguments")
                results.add(
                    buildString {
                        append(prompt.getString("name"))
                        prompt.optString("description", "").takeIf { it.isNotBlank() }?.let {
                            append(" — ").append(it.take(500))
                        }
                        if (args != null && args.length() > 0) {
                            append(" | args=")
                            val names = ArrayList<String>()
                            for (j in 0 until args.length()) {
                                val arg = args.optJSONObject(j) ?: continue
                                names.add(
                                    arg.optString("name", "arg") +
                                        if (arg.optBoolean("required", false)) "*" else ""
                                )
                            }
                            append(names.joinToString(","))
                        }
                    }
                )
                if (results.size >= 100) return@repeat
            }

            cursor = result.optString("nextCursor", "").ifBlank { null }
            if (cursor == null || results.size >= 100) {
                return if (results.isEmpty()) {
                    "MCP server exposes no prompts."
                } else {
                    "MCP prompts:\n" + results.joinToString("\n") { "- " + it }
                }
            }
        }

        return if (results.isEmpty()) "MCP server exposes no prompts."
        else "MCP prompts:\n" + results.joinToString("\n") { "- " + it }
    }

    fun getPrompt(
        context: Context,
        server: McpServerDefinition,
        name: String,
        argumentsJson: String
    ): String {
        val params = baseParams()
            .put("name", name)
            .put("arguments", JSONObject(argumentsJson.ifBlank { "{}" }))

        val result = completeResult(
            request(context, server, "prompts/get", params, null)
        )

        return buildString {
            result.optString("description", "").takeIf { it.isNotBlank() }?.let {
                append("Prompt description: ").append(it).append("\n")
            }

            val messages = result.optJSONArray("messages") ?: JSONArray()
            for (i in 0 until messages.length()) {
                val message = messages.optJSONObject(i) ?: continue
                append("\n").append(message.optString("role", "user")).append(": ")
                append(renderContent(message.opt("content")))
            }
        }.take(MAX_RESULT_CHARS)
    }

    private fun request(
        context: Context,
        server: McpServerDefinition,
        method: String,
        params: JSONObject,
        targetName: String?
    ): JSONObject {
        WebTools.validatePublicHttpsEndpoint(server.endpoint)
        val requestId = nextId.incrementAndGet()

        val body = JSONObject()
            .put("jsonrpc", "2.0")
            .put("id", requestId)
            .put("method", method)
            .put("params", params)
            .toString()

        val connection = (URL(server.endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 15_000
            readTimeout = 45_000
            doOutput = true
            instanceFollowRedirects = false
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", "application/json, text/event-stream")
            setRequestProperty("MCP-Protocol-Version", PROTOCOL_VERSION)
            setRequestProperty("Mcp-Method", method)
            if (!targetName.isNullOrBlank()) {
                setRequestProperty("Mcp-Name", targetName)
            }
            setRequestProperty("User-Agent", "CodieAI/1.6 MCP client")
            authHeaders(context, server).forEach { (header, value) ->
                setRequestProperty(header, value)
            }
        }

        val bytes = body.toByteArray(Charsets.UTF_8)
        require(bytes.size <= 256_000) { "MCP request is too large" }
        connection.outputStream.use { it.write(bytes) }

        val status = connection.responseCode
        require(status !in 300..399) {
            "MCP redirects are blocked; configure the final HTTPS endpoint."
        }

        val contentType = connection.contentType.orEmpty().lowercase()
        val stream = if (status in 200..299) {
            connection.inputStream
        } else {
            connection.errorStream
        }

        val raw = readLimited(stream)
        connection.disconnect()

        require(status in 200..299) {
            "MCP server returned HTTP " + status + ": " + raw.take(2_000)
        }

        val response = if (contentType.contains("text/event-stream")) {
            parseSseForResponse(raw, requestId)
        } else {
            JSONObject(raw)
        }

        if (response.has("error")) {
            val error = response.getJSONObject("error")
            throw IllegalStateException(
                "MCP error " + error.optInt("code") + ": " +
                    error.optString("message", "unknown error")
            )
        }

        require(response.optLong("id", Long.MIN_VALUE) == requestId) {
            "MCP response id did not match request"
        }
        require(response.has("result")) { "MCP response did not contain a result" }
        return response
    }

    private fun completeResult(response: JSONObject): JSONObject {
        val result = response.getJSONObject("result")
        if (result.optString("resultType", "complete") == "input_required") {
            throw IllegalStateException(
                "MCP server requires an additional user/model input round trip; " +
                    "automatic elicitation is not enabled for this request."
            )
        }
        return result
    }

    private fun baseParams(): JSONObject =
        JSONObject().put("_meta", requestMeta())

    private fun requestMeta(): JSONObject =
        JSONObject()
            .put("io.modelcontextprotocol/protocolVersion", PROTOCOL_VERSION)
            .put(
                "io.modelcontextprotocol/clientCapabilities",
                JSONObject()
                    .put("tools", JSONObject())
                    .put("resources", JSONObject())
                    .put("prompts", JSONObject())
            )
            .put(
                "io.modelcontextprotocol/clientInfo",
                JSONObject()
                    .put("name", "codie-ai-android")
                    .put("version", "1.6.0")
            )

    private fun authHeaders(
        context: Context,
        server: McpServerDefinition
    ): Map<String, String> {
        if (server.authType == "none") return emptyMap()
        val secret = SecretStore.resolve(context, server.secretAlias)
        return when (server.authType) {
            "bearer" -> mapOf("Authorization" to ("Bearer " + secret))
            "api_key" -> mapOf(
                server.authHeader.ifBlank { "X-API-Key" } to secret
            )
            else -> throw IllegalStateException("Unsupported MCP auth type")
        }
    }

    private fun readLimited(input: java.io.InputStream?): String {
        if (input == null) return ""
        return input.use { stream ->
            val output = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            var total = 0
            while (true) {
                val count = stream.read(buffer)
                if (count < 0) break
                total += count
                require(total <= MAX_RESPONSE_BYTES) {
                    "MCP response exceeds " + MAX_RESPONSE_BYTES + " bytes"
                }
                output.write(buffer, 0, count)
            }
            output.toByteArray().toString(Charsets.UTF_8)
        }
    }

    private fun parseSseForResponse(raw: String, requestId: Long): JSONObject {
        val events = ArrayList<String>()
        val data = StringBuilder()

        fun finishEvent() {
            if (data.isNotEmpty()) {
                events.add(data.toString())
                data.setLength(0)
            }
        }

        raw.lineSequence().forEach { line ->
            if (line.isBlank()) {
                finishEvent()
            } else if (line.startsWith("data:")) {
                if (data.isNotEmpty()) data.append('\n')
                data.append(line.removePrefix("data:").trimStart())
            }
        }
        finishEvent()

        val parsed = events.mapNotNull { event ->
            runCatching { JSONObject(event) }.getOrNull()
        }

        return parsed.lastOrNull {
            it.optLong("id", Long.MIN_VALUE) == requestId &&
                (it.has("result") || it.has("error"))
        } ?: throw IllegalStateException(
            "MCP SSE stream ended without a final response for request " + requestId
        )
    }

    private fun renderContent(content: Any?): String =
        when (content) {
            null, JSONObject.NULL -> ""
            is JSONObject -> {
                when (content.optString("type")) {
                    "text" -> content.optString("text", "")
                    "resource" -> content.optJSONObject("resource")?.let { resource ->
                        resource.optString("text", "").ifBlank {
                            "[embedded resource " + resource.optString("uri", "") + "]"
                        }
                    } ?: content.toString()
                    else -> content.toString()
                }
            }
            is JSONArray -> {
                val parts = ArrayList<String>()
                for (i in 0 until content.length()) {
                    parts.add(renderContent(content.opt(i)))
                }
                parts.joinToString("\n")
            }
            else -> content.toString()
        }

    private fun renderToolResult(result: JSONObject): String {
        val textParts = ArrayList<String>()
        val content = result.optJSONArray("content") ?: JSONArray()

        for (i in 0 until content.length()) {
            val item = content.optJSONObject(i) ?: continue
            when (item.optString("type")) {
                "text" -> {
                    val text = item.optString("text", "")
                    if (text.isNotBlank()) textParts.add(text)
                }
                "image" -> textParts.add(
                    "[MCP image content: " +
                        item.optString("mimeType", "unknown type") + "]"
                )
                "audio" -> textParts.add(
                    "[MCP audio content: " +
                        item.optString("mimeType", "unknown type") + "]"
                )
                "resource" -> textParts.add(renderContent(item))
                "resource_link" -> textParts.add(
                    "[MCP resource link: " + item.optString("uri", "") + "]"
                )
                else -> textParts.add(item.toString())
            }
        }

        result.opt("structuredContent")?.let {
            if (it != JSONObject.NULL) {
                textParts.add("structuredContent=" + it.toString())
            }
        }

        if (result.optBoolean("isError", false)) {
            throw IllegalStateException(
                "MCP tool reported an error: " +
                    textParts.joinToString("\n").take(4_000)
            )
        }

        return if (textParts.isEmpty()) result.toString()
        else textParts.joinToString("\n")
    }
}
