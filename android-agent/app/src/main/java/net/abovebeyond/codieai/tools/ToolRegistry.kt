package net.abovebeyond.codieai.tools

import android.content.Context
import android.content.Intent
import net.abovebeyond.codieai.agent.DurableAgentService
import net.abovebeyond.codieai.agent.DurableTaskStore
import net.abovebeyond.codieai.agent.TaskPlanStore
import net.abovebeyond.codieai.privileged.ShizukuBridge
import org.json.JSONObject

object ToolRegistry {
    private val builtins = listOf(
        "calculator(expression): safe arithmetic/functions",
        "web_search(query): search the public web without a paid API",
        "web_fetch(url): read a public HTTPS page; localhost/private LAN targets are blocked",
        "apps_list(): list launchable installed apps and package names",
        "clipboard_read(): read clipboard text when Android permits access",
        "clipboard_write(text): write text to the clipboard",
        "device_sensors(): sample available motion/environment sensors and battery temperature",
        "shizuku_status(): report Shizuku availability/permission and privileged bridge status",
        "shizuku_list_packages(): list user-installed packages through the optional Shizuku bridge",
        "shizuku_package_info(package): inspect one Android package through Shizuku",
        "shizuku_force_stop(package): force-stop one package; only use when the user explicitly asks",
        "shizuku_battery_dump(): detailed Android battery diagnostics through Shizuku",
        "shizuku_meminfo(package): detailed memory diagnostics for one package through Shizuku",
        "shizuku_animation_scale(value): set all Android animation scales from 0 to 10; state-changing",
        "shizuku_stay_awake(enabled): keep screen awake while charging; state-changing",
        "mcp_servers(): list installed MCP Streamable HTTP servers and cached tool counts",
        "mcp_refresh(server): discover/refresh the current tools exposed by one MCP server",
        "mcp_resources(server): list direct resources exposed by one MCP server",
        "mcp_resource_read(server,uri): read one MCP resource as context",
        "mcp_prompts(server): list reusable prompts exposed by one MCP server",
        "mcp_prompt_get(server,name,arguments): retrieve one MCP prompt/template",
        "mcp_pending(): list pending MCP multi-round-trip requests that need more input",
        "mcp_continue(pending_id,input_responses): resume a pending MCP request with protocol inputResponses",
        "knowledge_reindex(): rebuild full-text index of text/code files in the private workspace",
        "knowledge_search(query,limit): search indexed workspace knowledge",
        "durable_enqueue(goal): queue a persistent autonomous goal in the foreground durable-agent service",
        "durable_tasks(): list persistent task state/checkpoints",
        "durable_cancel(id): cancel a queued/running durable task",
        "durable_resume(): resume any queued durable task when Android permits a foreground service start",
        "task_plan_create(goal,steps): create a dependency graph; steps is [{id,goal,depends_on:[ids]}]",
        "task_plan_run(id): dispatch all currently-ready plan nodes to the durable queue",
        "task_plan_status(id): inspect a plan and every dependency-linked node",
        "task_plan_cancel(id): cancel a plan and its queued/running nodes",
        "selfdev_status(): report Codie AI self-development repository/branch/token readiness",
        "selfdev_begin(goal): create an isolated codie-selfdev/** branch from the verified Android base",
        "selfdev_tree(branch): list Codie AI android-agent source files",
        "selfdev_read(path,branch,offset,max_chars): read Codie AI source from GitHub",
        "selfdev_find(path,query,branch): search one Codie AI source file with line context",
        "selfdev_patch(branch,message,changes): atomically commit bounded source changes; changes=[{path,old,new}|{path,content}]",
        "selfdev_review(branch): compare a self-development branch against feature/android-agent",
        "selfdev_ci(branch): inspect the latest Android CI run and job steps for a self-development branch",
        "selfdev_logs(run_id): retrieve redacted CI job logs for diagnosis",
        "selfdev_artifacts(run_id): list verified CI artifacts",
        "selfdev_fetch_apk(run_id): download a successful CI APK artifact into the private workspace",
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
        lines.addAll(McpServerStore.catalogLines(context))
        return lines.joinToString("\n- ", prefix = "- ")
    }

    fun execute(context: Context, tool: String, argumentsJson: String): Result<String> =
        runCatching {
            val requestedName = tool.trim()
            val name = requestedName.lowercase()
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
                "clipboard_read" -> DeviceTools.clipboardRead(context)
                "clipboard_write" -> DeviceTools.clipboardWrite(
                    context,
                    args.requireString("text")
                )
                "device_sensors" -> DeviceTools.sensorReport(context)
                "shizuku_status" -> ShizukuBridge.status()
                "shizuku_list_packages" ->
                    ShizukuBridge.listUserPackages(context).getOrThrow()
                "shizuku_package_info" ->
                    ShizukuBridge.packageInfo(
                        context,
                        args.requireString("package")
                    ).getOrThrow()
                "shizuku_force_stop" ->
                    ShizukuBridge.forceStop(
                        context,
                        args.requireString("package")
                    ).getOrThrow()
                "shizuku_battery_dump" ->
                    ShizukuBridge.batteryDump(context).getOrThrow()
                "shizuku_meminfo" ->
                    ShizukuBridge.memoryInfo(
                        context,
                        args.requireString("package")
                    ).getOrThrow()
                "shizuku_animation_scale" ->
                    ShizukuBridge.setAnimationScale(
                        context,
                        args.optDouble("value", 1.0).toFloat()
                    ).getOrThrow()
                "shizuku_stay_awake" ->
                    ShizukuBridge.setStayAwake(
                        context,
                        args.optBoolean("enabled", false)
                    ).getOrThrow()
                "mcp_servers" -> McpServerStore.render(context)
                "mcp_refresh" -> McpServerStore.refresh(
                    context,
                    args.requireString("server")
                )
                "mcp_resources" -> McpServerStore.resources(
                    context,
                    args.requireString("server")
                )
                "mcp_resource_read" -> McpServerStore.readResource(
                    context,
                    args.requireString("server"),
                    args.requireString("uri")
                )
                "mcp_prompts" -> McpServerStore.prompts(
                    context,
                    args.requireString("server")
                )
                "mcp_prompt_get" -> {
                    val promptArgs = args.optJSONObject("arguments")?.toString() ?: "{}"
                    McpServerStore.prompt(
                        context,
                        args.requireString("server"),
                        args.requireString("name"),
                        promptArgs
                    )
                }
                "mcp_pending" -> McpPendingStore.render(context)
                "mcp_continue" -> McpClient.continuePending(
                    context,
                    args.optInt("pending_id", -1),
                    (args.optJSONObject("input_responses") ?: JSONObject()).toString()
                )
                "knowledge_reindex" -> KnowledgeIndex.reindex(context)
                "knowledge_search" -> KnowledgeIndex.search(
                    context,
                    args.requireString("query"),
                    args.optInt("limit", 8)
                )
                "durable_enqueue" -> {
                    val (task, started) = DurableAgentService.enqueueAndStart(
                        context,
                        args.requireString("goal")
                    )
                    "Queued durable task #" + task.id +
                        "; foreground_service_started=" + started
                }
                "durable_tasks" -> DurableTaskStore.render(context)
                "durable_cancel" -> DurableAgentService.cancelTask(
                    context,
                    args.optInt("id", -1)
                )
                "durable_resume" ->
                    "durable_service_started=" +
                        DurableAgentService.startIfPending(context)
                "task_plan_create" -> {
                    val steps = args.optJSONArray("steps")
                        ?: throw IllegalArgumentException("Missing tool argument: steps")
                    val plan = TaskPlanStore.create(
                        context,
                        args.requireString("goal"),
                        steps.toString()
                    )
                    "Created task plan #" + plan.id +
                        " with " + plan.nodes.size + " node(s)."
                }
                "task_plan_run" -> TaskPlanStore.run(
                    context,
                    args.optInt("id", -1)
                )
                "task_plan_status" -> TaskPlanStore.render(
                    context,
                    args.optInt("id", -1).takeIf { it >= 0 }
                )
                "task_plan_cancel" -> TaskPlanStore.cancel(
                    context,
                    args.optInt("id", -1)
                )
                "selfdev_status" -> GitHubSelfDev.status(context)
                "selfdev_begin" -> GitHubSelfDev.begin(
                    context,
                    args.requireString("goal")
                )
                "selfdev_tree" -> GitHubSelfDev.tree(
                    context,
                    args.optString("branch", "")
                )
                "selfdev_read" -> GitHubSelfDev.read(
                    context = context,
                    pathArg = args.requireString("path"),
                    branchArg = args.optString("branch", ""),
                    offset = args.optInt("offset", 0),
                    maxChars = args.optInt("max_chars", 6_000)
                )
                "selfdev_find" -> GitHubSelfDev.find(
                    context = context,
                    pathArg = args.requireString("path"),
                    query = args.requireString("query"),
                    branchArg = args.optString("branch", "")
                )
                "selfdev_patch" -> {
                    val changes = args.optJSONArray("changes")
                        ?: throw IllegalArgumentException("Missing tool argument: changes")
                    GitHubSelfDev.patch(
                        context = context,
                        branchArg = args.optString("branch", ""),
                        message = args.requireString("message"),
                        changesJson = changes.toString()
                    )
                }
                "selfdev_review" -> GitHubSelfDev.review(
                    context,
                    args.optString("branch", "")
                )
                "selfdev_ci" -> GitHubSelfDev.ci(
                    context,
                    args.optString("branch", "")
                )
                "selfdev_logs" -> GitHubSelfDev.logs(
                    context,
                    args.optLong("run_id", -1L)
                )
                "selfdev_artifacts" -> GitHubSelfDev.artifacts(
                    context,
                    args.optLong("run_id", -1L)
                )
                "selfdev_fetch_apk" -> GitHubSelfDev.fetchApk(
                    context,
                    args.optLong("run_id", -1L)
                )

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
                        "- " + it.name + ": " + it.description +
                            " [" + it.method + " " + it.endpoint + "; auth=" + it.authType + "]"
                    }
                }

                else -> {
                    when {
                        McpServerStore.isExposedTool(requestedName) ->
                            McpServerStore.callExposed(
                                context,
                                requestedName,
                                argumentsJson
                            )
                        CustomToolStore.find(context, name) != null ->
                            CustomToolStore.call(context, name, argumentsJson)
                        else -> throw IllegalArgumentException("Unknown tool: " + tool)
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
