package net.abovebeyond.codieai.tools

import android.content.Context
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
    private const val MAX_TOOLS = 40

    fun importManifest(context: Context, raw: String): String {
        val json = JSONObject(raw)
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
        WebTools.validatePublicHttpsEndpoint(endpoint)

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
        if (authType == "api_key") {
            val header = authHeader.ifBlank { "X-API-Key" }
            require(header.matches(Regex("""[A-Za-z0-9-]{1,64}"""))) {
                "Invalid API key header name"
            }
        }

        val current = list(context).toMutableList()
        current.removeAll { it.name == name }
        require(current.size < MAX_TOOLS) { "Maximum custom tools reached" }

        current.add(
            CustomTool(
                name = name,
                description = description,
                endpoint = endpoint,
                method = method,
                authType = authType,
                secretAlias = secretAlias,
                authHeader = if (authType == "api_key") {
                    authHeader.ifBlank { "X-API-Key" }
                } else ""
            )
        )
        write(context, current)

        return "Installed custom tool '" + name + "'" +
            if (authType == "none") "" else " using encrypted secret alias '" + secretAlias + "'"
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

        val headers = authenticatedHeaders(context, tool)
        return when (tool.method.uppercase()) {
            "GET" -> WebTools.getJsonPublic(tool.endpoint, argumentsJson, headers)
            "POST" -> WebTools.postJsonPublic(tool.endpoint, argumentsJson, headers)
            else -> throw IllegalStateException("Unsupported method: " + tool.method)
        }
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

    private fun write(context: Context, tools: List<CustomTool>) {
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
