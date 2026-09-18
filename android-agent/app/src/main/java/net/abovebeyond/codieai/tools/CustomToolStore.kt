package net.abovebeyond.codieai.tools

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject

data class CustomTool(
    val name: String,
    val description: String,
    val endpoint: String,
    val method: String,
    val authType: String = "none",
    val secretAlias: String = "",
    val authHeader: String = ""
)

object CustomToolStore {
    private const val PREFS = "codie_ai_custom_tools"
    private const val KEY_TOOLS = "tools"
    private const val MAX_TOOLS = 60
    private val placeholderRegex = Regex("""\{([A-Za-z][A-Za-z0-9_]{0,40})\}""")

    fun importManifest(context: Context, raw: String): String {
        val incoming = parseBundle(raw)
        require(incoming.length() > 0) { "Tool bundle is empty" }

        val parsed = ArrayList<CustomTool>()
        for (i in 0 until incoming.length()) {
            parsed.add(parseTool(context, incoming.getJSONObject(i)))
        }

        val current = list(context).associateBy { it.name }.toMutableMap()
        parsed.forEach { current[it.name] = it }
        require(current.size <= MAX_TOOLS) { "Maximum custom tools reached" }
        write(context, current.values.sortedBy { it.name })

        return if (parsed.size == 1) {
            "Installed custom tool '" + parsed.first().name + "'"
        } else {
            "Installed " + parsed.size + " custom tools: " +
                parsed.joinToString(", ") { it.name }
        }
    }

    fun list(context: Context): List<CustomTool> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_TOOLS, "[]")
            .orEmpty()

        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    add(
                        CustomTool(
                            name = obj.getString("name"),
                            description = obj.getString("description"),
                            endpoint = obj.getString("endpoint"),
                            method = obj.optString("method", "POST"),
                            authType = obj.optString("auth_type", "none"),
                            secretAlias = obj.optString("secret_alias", ""),
                            authHeader = obj.optString("auth_header", "")
                        )
                    )
                }
            }
        }.getOrElse { emptyList() }
    }

    fun remove(context: Context, name: String): String {
        val current = list(context)
        val filtered = current.filterNot { it.name == name.trim().lowercase() }
        require(filtered.size != current.size) { "Custom tool not found: " + name }
        write(context, filtered)
        return "Removed custom tool '" + name + "'"
    }

    fun find(context: Context, name: String): CustomTool? =
        list(context).firstOrNull { it.name == name.trim().lowercase() }

    fun call(context: Context, name: String, argumentsJson: String): String {
        val tool = find(context, name)
            ?: throw IllegalArgumentException("Custom tool not found: " + name)

        val original = JSONObject(argumentsJson.ifBlank { "{}" })
        val resolved = resolveEndpoint(tool.endpoint, original)
        val remaining = JSONObject()
        val consumed = placeholderRegex.findAll(tool.endpoint)
            .map { it.groupValues[1] }
            .toSet()

        val keys = original.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            if (key !in consumed) remaining.put(key, original.get(key))
        }

        val headers = authenticatedHeaders(context, tool)
        return when (tool.method.uppercase()) {
            "GET" -> WebTools.getJsonPublic(resolved, remaining.toString(), headers)
            "POST" -> WebTools.postJsonPublic(resolved, remaining.toString(), headers)
            else -> throw IllegalStateException("Unsupported method: " + tool.method)
        }
    }

    private fun parseBundle(raw: String): JSONArray {
        val trimmed = raw.trim()
        require(trimmed.length <= 200_000) { "Connector bundle is too large" }

        return when {
            trimmed.startsWith("[") -> JSONArray(trimmed)
            else -> {
                val root = JSONObject(trimmed)
                if (root.has("tools")) root.getJSONArray("tools")
                else JSONArray().put(root)
            }
        }
    }

    private fun parseTool(context: Context, json: JSONObject): CustomTool {
        val name = json.getString("name").trim().lowercase()
        val description = json.getString("description").trim()
        val endpoint = json.getString("endpoint").trim()
        val method = json.optString("method", "POST").trim().uppercase()

        require(name.matches(Regex("""[a-z][a-z0-9_]{1,40}"""))) {
            "Tool name must match [a-z][a-z0-9_]{1,40}"
        }
        require(description.isNotBlank() && description.length <= 500) {
            "Tool description must be 1..500 characters"
        }
        require(method == "POST" || method == "GET") {
            "Custom tools support GET or POST"
        }

        validateEndpointTemplate(endpoint)

        val auth = json.optJSONObject("auth")
        val authType = auth?.optString("type", "none")?.trim()?.lowercase() ?: "none"
        val secretAlias = auth?.optString("secret_alias", "")?.trim()?.lowercase().orEmpty()
        val authHeader = auth?.optString("header", "")?.trim().orEmpty()

        require(authType in setOf("none", "bearer", "api_key")) {
            "auth.type must be none, bearer, or api_key"
        }
        if (authType != "none") {
            require(secretAlias.isNotBlank()) {
                "Authenticated tools require auth.secret_alias"
            }
            require(SecretStore.exists(context, secretAlias)) {
                "Secret alias '" + secretAlias + "' is not stored yet"
            }
        }

        val header = if (authType == "api_key") {
            authHeader.ifBlank { "X-API-Key" }.also {
                require(it.matches(Regex("""[A-Za-z0-9-]{1,64}"""))) {
                    "Invalid API key header name"
                }
            }
        } else ""

        return CustomTool(
            name = name,
            description = description,
            endpoint = endpoint,
            method = method,
            authType = authType,
            secretAlias = secretAlias,
            authHeader = header
        )
    }

    private fun validateEndpointTemplate(endpoint: String) {
        require(endpoint.startsWith("https://", ignoreCase = true)) {
            "Connector endpoints must use public HTTPS"
        }

        val authorityStart = endpoint.indexOf("://") + 3
        val pathStart = endpoint.indexOf('/', authorityStart)
        val authority = if (pathStart < 0) {
            endpoint.substring(authorityStart)
        } else {
            endpoint.substring(authorityStart, pathStart)
        }

        require(!authority.contains('{') && !authority.contains('}')) {
            "Endpoint templates may not change the host"
        }

        val placeholders = placeholderRegex.findAll(endpoint).toList()
        require(placeholders.size <= 12) { "Too many endpoint placeholders" }

        val normalized = placeholderRegex.replace(endpoint, "placeholder")
        WebTools.validatePublicHttpsEndpoint(normalized)
    }

    private fun resolveEndpoint(endpoint: String, arguments: JSONObject): String {
        var resolved = endpoint
        placeholderRegex.findAll(endpoint).forEach { match ->
            val key = match.groupValues[1]
            require(arguments.has(key)) {
                "Missing path argument '" + key + "' for connector endpoint"
            }
            val raw = arguments.get(key)
            require(
                raw is String || raw is Number || raw is Boolean
            ) {
                "Path argument '" + key + "' must be a scalar value"
            }
            resolved = resolved.replace(
                match.value,
                Uri.encode(raw.toString())
            )
        }

        WebTools.validatePublicHttpsEndpoint(resolved)
        return resolved
    }

    private fun authenticatedHeaders(
        context: Context,
        tool: CustomTool
    ): Map<String, String> {
        if (tool.authType == "none") return emptyMap()
        val secret = SecretStore.resolve(context, tool.secretAlias)

        return when (tool.authType) {
            "bearer" -> mapOf("Authorization" to ("Bearer " + secret))
            "api_key" -> mapOf(
                tool.authHeader.ifBlank { "X-API-Key" } to secret
            )
            else -> throw IllegalStateException("Unsupported auth type")
        }
    }

    private fun write(context: Context, tools: Collection<CustomTool>) {
        val array = JSONArray()
        tools.forEach { tool ->
            array.put(
                JSONObject()
                    .put("name", tool.name)
                    .put("description", tool.description)
                    .put("endpoint", tool.endpoint)
                    .put("method", tool.method)
                    .put("auth_type", tool.authType)
                    .put("secret_alias", tool.secretAlias)
                    .put("auth_header", tool.authHeader)
            )
        }

        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_TOOLS, array.toString())
            .apply()
    }
}
