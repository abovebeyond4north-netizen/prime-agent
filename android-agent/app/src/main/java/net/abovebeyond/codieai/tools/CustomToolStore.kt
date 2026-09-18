package net.abovebeyond.codieai.tools

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

data class CustomTool(
    val name: String,
    val description: String,
    val endpoint: String,
    val method: String
)

object CustomToolStore {
    private const val PREFS = "codie_ai_custom_tools"
    private const val KEY_TOOLS = "tools"
    private const val MAX_TOOLS = 25

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
        require(method == "POST") { "Custom tools currently support POST only" }
        WebTools.validatePublicHttpsEndpoint(endpoint)

        val current = list(context).toMutableList()
        current.removeAll { it.name == name }
        require(current.size < MAX_TOOLS) { "Maximum custom tools reached" }
        current.add(CustomTool(name, description, endpoint, method))
        write(context, current)
        return "Installed custom tool '" + name + "'"
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
                            method = obj.optString("method", "POST")
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
        return WebTools.postJsonPublic(tool.endpoint, argumentsJson)
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
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_TOOLS, array.toString())
            .apply()
    }
}
