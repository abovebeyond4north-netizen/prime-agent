package net.abovebeyond.codieai.tools

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import org.json.JSONObject

object ToolRegistry {
    private val catalog = listOf(
        "calculator(expression): safe arithmetic/functions; supports + - * / % ^, sqrt, sin, cos, log, min, max, pow",
        "web_search(query): search the public web without a paid API",
        "web_fetch(url): read a public HTTPS page; localhost/private LAN targets are blocked",
        "apps_list(): list launchable installed apps and package names",
        "memory_put(key,value): save explicit durable local tool memory",
        "memory_get(key): retrieve local tool memory",
        "memory_list(): list local memory keys",
        "memory_delete(key): delete a local memory key",
        "workspace_list(): list files in Codie AI's private tool workspace",
        "workspace_read(name,offset,max_chars): read a text workspace file chunk",
        "workspace_write(name,content): create/replace a text workspace file",
        "workspace_delete(name): delete a workspace file"
    )

    fun promptCatalog(): String = catalog.joinToString("\n- ", prefix = "- ")

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
                "workspace_read" -> {
                    val text = WorkspaceTools.read(context, args.requireString("name"))
                    val offset = args.optInt("offset", 0).coerceAtLeast(0)
                    val maxChars = args.optInt("max_chars", 3_000).coerceIn(200, 5_000)
                    if (offset >= text.length) {
                        "End of file."
                    } else {
                        val end = (offset + maxChars).coerceAtMost(text.length)
                        buildString {
                            append("Characters ").append(offset).append("..").append(end)
                                .append(" of ").append(text.length).append(":\n")
                            append(text.substring(offset, end))
                            if (end < text.length) {
                                append("\n[more available; next offset=").append(end).append("]")
                            }
                        }
                    }
                }
                "workspace_write" -> WorkspaceTools.write(
                    context,
                    args.requireString("name"),
                    args.requireString("content")
                )
                "workspace_delete" -> WorkspaceTools.delete(
                    context,
                    args.requireString("name")
                )

                else -> throw IllegalArgumentException(
                    "Unknown tool '" + tool + "'. Available tools: " +
                        catalog.joinToString("; ") { it.substringBefore('(') }
                )
            }

            ("TOOL_RESULT " + name + ":\n" + output).take(12_000)
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
