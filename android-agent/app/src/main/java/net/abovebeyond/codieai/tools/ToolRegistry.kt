package net.abovebeyond.codieai.tools

import android.content.Context
import android.content.Intent
import org.json.JSONObject

object ToolRegistry {
    private val builtins = listOf(
        "calculator(expression): safe arithmetic/functions",
        "web_search(query): search the public web without a paid API",
        "web_fetch(url): read a public HTTPS page; localhost/private LAN targets are blocked",
        "apps_list(): list launchable installed apps and package names",
        "memory_put(key,value): save explicit durable local tool memory",
        "memory_get(key): retrieve local tool memory",
        "memory_list(): list local memory keys",
        "memory_delete(key): delete a local memory key",
        "workspace_list(): list private workspace files",
        "workspace_read(name,offset,max_chars): read a workspace text chunk",
        "workspace_write(name,content): create/replace a workspace text file",
        "workspace_delete(name): delete a workspace file",
        "text_search(name,query): search lines inside a workspace text file",
        "csv_summary(name): summarize CSV columns and numeric statistics",
        "json_query(name,path): query a JSON workspace file with dot/index path",
        "file_sha256(name): calculate SHA-256 for a workspace file",
        "skill_save(name,instructions): save a reusable local skill/instruction recipe",
        "skill_get(name): retrieve a saved skill",
        "skill_list(): list saved skills",
        "skill_delete(name): delete a saved skill",
        "image_ocr(name): extract text from an imported workspace image on-device",
        "image_labels(name): identify general objects/places/activities in a workspace image on-device",
        "js_sandbox(code): execute pure sandboxed JavaScript for logic/data transformation; no Java/Android/network/filesystem access",
        "custom_tool_list(): list user-installed HTTPS tools"
    )

    fun promptCatalog(context: Context): String {
        val lines = ArrayList<String>()
        lines.addAll(builtins)
        CustomToolStore.list(context).forEach { tool ->
            lines.add(
                tool.name + "(arguments): USER-INSTALLED HTTPS TOOL — " + tool.description
            )
        }
        return lines.joinToString("\n- ", prefix = "- ")
    }

    fun execute(context: Context, tool: String, argumentsJson: String): Result<String> =
        runCatching {
            val name = tool.trim().lowercase()
            val args = JSONObject(argumentsJson.ifBlank { "{}" })

            val output = when (name) {
                "calculator" -> {
                    val expression = args.requireString("expression")
                    val value = MathExpression.evaluate(expression)
                    expression + " = " + formatNumber(value)
                }

                "web_search" -> WebTools.search(args.requireString("query"))
                "web_fetch" -> WebTools.fetch(args.requireString("url"))
                "apps_list" -> listApps(context)

                "memory_put" -> MemoryTools.put(
                    context,
                    args.requireString("key"),
                    args.requireString("value")
                )
                "memory_get" -> MemoryTools.get(context, args.requireString("key"))
                "memory_list" -> MemoryTools.list(context)
                "memory_delete" -> MemoryTools.delete(context, args.requireString("key"))

                "workspace_list" -> WorkspaceTools.list(context)
                "workspace_read" -> readWorkspaceChunk(context, args)
                "workspace_write" -> WorkspaceTools.write(
                    context,
                    args.requireString("name"),
                    args.requireString("content")
                )
                "workspace_delete" -> WorkspaceTools.delete(
                    context,
                    args.requireString("name")
                )

                "text_search" -> DataTools.textSearch(
                    context,
                    args.requireString("name"),
                    args.requireString("query")
                )
                "csv_summary" -> DataTools.csvSummary(
                    context,
                    args.requireString("name")
                )
                "json_query" -> DataTools.jsonQuery(
                    context,
                    args.requireString("name"),
                    args.optString("path", "")
                )
                "file_sha256" -> DataTools.sha256(
                    context,
                    args.requireString("name")
                )
                "image_ocr" -> VisualTools.ocr(
                    context,
                    args.requireString("name")
                )
                "image_labels" -> VisualTools.labels(
                    context,
                    args.requireString("name")
                )
                "js_sandbox" -> JavaScriptSandbox.execute(
                    args.requireString("code")
                )

                "skill_save" -> SkillStore.save(
                    context,
                    args.requireString("name"),
                    args.requireString("instructions")
                )
                "skill_get" -> SkillStore.get(context, args.requireString("name"))
                "skill_list" -> SkillStore.list(context)
                "skill_delete" -> SkillStore.delete(context, args.requireString("name"))

                "custom_tool_list" -> {
                    val tools = CustomToolStore.list(context)
                    if (tools.isEmpty()) "No custom tools installed."
                    else tools.joinToString("\n", "Custom tools:\n") {
                        "- " + it.name + ": " + it.description + " [" + it.endpoint + "]"
                    }
                }

                else -> {
                    if (CustomToolStore.find(context, name) != null) {
                        CustomToolStore.call(context, name, argumentsJson)
                    } else {
                        throw IllegalArgumentException("Unknown tool: " + tool)
                    }
                }
            }

            ("TOOL_RESULT " + name + ":\n" + output).take(12_000)
        }

    private fun readWorkspaceChunk(context: Context, args: JSONObject): String {
        val text = WorkspaceTools.read(context, args.requireString("name"))
        val offset = args.optInt("offset", 0).coerceAtLeast(0)
        val maxChars = args.optInt("max_chars", 3_000).coerceIn(200, 5_000)

        if (offset >= text.length) return "End of file."

        val end = (offset + maxChars).coerceAtMost(text.length)
        return buildString {
            append("Characters ").append(offset).append("..").append(end)
                .append(" of ").append(text.length).append(":\n")
            append(text.substring(offset, end))
            if (end < text.length) {
                append("\n[more available; next offset=").append(end).append("]")
            }
        }
    }

    private fun listApps(context: Context): String {
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = context.packageManager.queryIntentActivities(intent, 0)
            .map { info ->
                val label = info.loadLabel(context.packageManager).toString()
                label to info.activityInfo.packageName
            }
            .distinct()
            .sortedBy { it.first.lowercase() }
            .take(150)

        return buildString {
            append("Launchable apps:")
            apps.forEach { (label, packageName) ->
                append("\n- ").append(label).append(" [").append(packageName).append("]")
            }
        }
    }

    private fun JSONObject.requireString(name: String): String {
        val value = optString(name, "").trim()
        require(value.isNotBlank()) { "Missing tool argument: " + name }
        return value
    }

    private fun formatNumber(value: Double): String {
        val whole = value.toLong()
        return if (value == whole.toDouble()) whole.toString()
        else java.math.BigDecimal.valueOf(value).stripTrailingZeros().toPlainString()
    }
}
