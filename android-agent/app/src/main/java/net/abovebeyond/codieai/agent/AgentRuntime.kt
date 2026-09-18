package net.abovebeyond.codieai.agent

import android.Manifest
import android.app.ActivityManager
import android.app.AlarmManager
import android.content.Context
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.StatFs
import net.abovebeyond.codieai.accessibility.CodieAccessibilityService
import net.abovebeyond.codieai.automation.AutomationScheduler
import net.abovebeyond.codieai.notifications.NotificationStore
import net.abovebeyond.codieai.tools.ToolRegistry
import net.abovebeyond.codieai.tools.UsageTools
import java.io.File
import java.lang.ref.WeakReference
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

object AgentRuntime {
    private const val PREFS = "codie_ai"
    private const val KEY_ENDPOINT = "planner_endpoint"
    private const val KEY_MODEL = "planner_model"
    private const val KEY_CONVERSATION = "conversation_history"
    private const val MAX_UI_CHARS = 2_400
    private const val MAX_CONVERSATION_CHARS = 700
    private const val MAX_STORED_CONVERSATION_CHARS = 8_000

    private val executor = Executors.newSingleThreadExecutor()
    private val generation = AtomicLong(0L)

    @Volatile
    private var serviceRef: WeakReference<CodieAccessibilityService>? = null

    fun attachService(service: CodieAccessibilityService) {
        serviceRef = WeakReference(service)
    }

    fun detachService(service: CodieAccessibilityService) {
        if (serviceRef?.get() === service) serviceRef = null
    }

    fun isServiceConnected(): Boolean = serviceRef?.get() != null

    fun savePlannerSettings(context: Context, endpoint: String, model: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ENDPOINT, endpoint.trim())
            .putString(KEY_MODEL, model.trim().ifBlank { "gpt-oss-20b" })
            .apply()
    }

    fun plannerEndpoint(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_ENDPOINT, "")
            .orEmpty()

    fun plannerModel(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_MODEL, "gpt-oss-20b")
            .orEmpty()

    fun localModelFile(context: Context): File =
        File(File(context.filesDir, "models"), "local.litertlm")

    fun recordUserMessage(context: Context, text: String) {
        appendConversation(context, "You", text)
    }

    fun recordAssistantMessage(context: Context, text: String) {
        appendConversation(context, "Codie AI", text)
    }

    fun conversationTranscript(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_CONVERSATION, "")
            .orEmpty()

    fun clearConversation(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(KEY_CONVERSATION)
            .apply()
    }

    fun cancelCurrentGoal() {
        generation.incrementAndGet()
    }

    fun executeGoal(context: Context, goal: String, status: (String) -> Unit) {
        val normalizedGoal = goal.trim()
        if (normalizedGoal.isBlank()) {
            status("Enter a goal first.")
            return
        }

        val runId = generation.incrementAndGet()
        val appContext = context.applicationContext

        executor.execute {
            val service = serviceRef?.get()
            if (service == null) {
                status("Enable Codie AI in Android Accessibility settings first.")
                return@execute
            }

            val planner = try {
                createPlanner(appContext)
            } catch (error: Throwable) {
                status("Planner setup failed: " + (error.message ?: error.javaClass.simpleName))
                return@execute
            }

            val screenContext = needsExternalScreenContext(normalizedGoal)
            if (!looksConversational(normalizedGoal) || screenContext) {
                moveAwayFromOwnUiIfNeeded(
                    service,
                    appContext.packageName,
                    preferBack = screenContext,
                    status = status
                )
            }

            var lastResult = "No action has run yet."
            for (step in 1..32) {
                if (generation.get() != runId) {
                    status("Goal cancelled.")
                    return@execute
                }

                val snapshot = service.captureSnapshot()
                try {
                    val state = buildString {
                        append("SYSTEM:\n")
                        append(systemState(appContext))
                        append("\nTOOL_CATALOG:\n")
                        append(ToolRegistry.promptCatalog(appContext))
                        append("\nLAST_RESULT:\n")
                        append(lastResult.take(3_600))
                        append("\nRECENT_CONVERSATION:\n")
                        append(conversationContext(appContext))
                        append("\nNOTIFICATIONS:\n")
                        append(NotificationStore.render(limit = 2))
                        append("\nUI:\n")
                        append(compactUi(snapshot.text))
                    }

                    status("Step " + step + ": reasoning over current phone state")
                    val action = planner.nextAction(normalizedGoal, state, step)
                    status(
                        "Step " + step + ": " + action.type.name +
                            if (action.reason.isBlank()) "" else " — " + action.reason
                    )

                    if (action.type == ActionType.RESPOND) {
                        status("Reply: " + action.text.ifBlank { action.reason.ifBlank { "Done." } })
                        return@execute
                    }
                    if (action.type == ActionType.DONE) {
                        status("Complete: " + action.reason.ifBlank { "Goal satisfied." })
                        return@execute
                    }
                    if (action.type == ActionType.FAIL) {
                        status("Stopped: " + action.reason.ifBlank { "Planner could not continue." })
                        return@execute
                    }

                    val result = service.execute(action, snapshot)
                    lastResult = (if (result.ok) "SUCCESS: " else "FAILED: ") + result.message
                    status(lastResult)
                } catch (error: Throwable) {
                    status("Step failed: " + (error.message ?: error.javaClass.simpleName))
                    return@execute
                } finally {
                    snapshot.close()
                }

                if (generation.get() != runId) {
                    status("Goal cancelled.")
                    return@execute
                }
                Thread.sleep(650L)
            }

            status("Stopped after 32 steps without verified completion.")
        }
    }

    private fun looksConversational(goal: String): Boolean {
        val lower = goal.lowercase(Locale.getDefault()).trim()
        if (lower.endsWith("?")) return true
        return listOf(
            "what ", "who ", "why ", "how ", "when ", "where ",
            "tell me ", "explain ", "describe ", "summarize ", "answer "
        ).any { lower.startsWith(it) }
    }

    private fun needsExternalScreenContext(goal: String): Boolean {
        val lower = goal.lowercase(Locale.getDefault())
        return listOf(
            "screen", "this page", "this app", "what am i looking",
            "read this", "summarize this", "what does this say",
            "what is open", "what's open", "take a screenshot"
        ).any { lower.contains(it) }
    }

    private fun moveAwayFromOwnUiIfNeeded(
        service: CodieAccessibilityService,
        packageName: String,
        preferBack: Boolean,
        status: (String) -> Unit
    ) {
        val snapshot = service.captureSnapshot()
        try {
            if (snapshot.text.contains("pkg=" + packageName)) {
                status(
                    if (preferBack) "Returning to the previous screen for context."
                    else "Leaving Codie AI before acting on the phone."
                )
                service.execute(
                    AgentAction(
                        if (preferBack) ActionType.BACK else ActionType.HOME,
                        reason = "Avoid controlling Codie AI itself"
                    ),
                    snapshot
                )
                Thread.sleep(650L)
            }
        } finally {
            snapshot.close()
        }
    }

    private fun appendConversation(context: Context, speaker: String, text: String) {
        val cleaned = text.replace('\n', ' ').replace('\r', ' ').trim()
        if (cleaned.isBlank()) return

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val old = prefs.getString(KEY_CONVERSATION, "").orEmpty()
        val entry = speaker + ": " + cleaned
        val combined = (if (old.isBlank()) entry else old + "\n" + entry)
            .takeLast(MAX_STORED_CONVERSATION_CHARS)

        prefs.edit().putString(KEY_CONVERSATION, combined).apply()
    }

    private fun conversationContext(context: Context): String =
        conversationTranscript(context)
            .takeLast(MAX_CONVERSATION_CHARS)
            .ifBlank { "No prior conversation." }

    private fun systemState(context: Context): String {
        val battery = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val percent = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)

        val memory = ActivityManager.MemoryInfo()
        val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        activityManager.getMemoryInfo(memory)

        val stat = StatFs(context.filesDir.absolutePath)
        val connectivity = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = connectivity.activeNetwork
        val capabilities = network?.let { connectivity.getNetworkCapabilities(it) }
        val networkLabel = when {
            capabilities == null -> "offline"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN) -> "vpn"
            else -> "other"
        }

        val now = SimpleDateFormat("yyyy-MM-dd HH:mm:ss Z", Locale.getDefault()).format(Date())
        val localModel = localModelFile(context)
        val contactsGranted =
            context.checkSelfPermission(Manifest.permission.READ_CONTACTS) ==
                PackageManager.PERMISSION_GRANTED
        val usageGranted = UsageTools.hasAccess(context)
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val exactAlarmGranted =
            android.os.Build.VERSION.SDK_INT < 31 || alarmManager.canScheduleExactAlarms()
        val scheduledCount = AutomationScheduler.tasks(context).size

        val plannerMode = when {
            plannerEndpoint(context).isNotBlank() -> "gpt_oss_endpoint"
            localModel.isFile -> "local_litert"
            else -> "deterministic"
        }

        return buildString {
            append("time=").append(now)
            append(" battery=").append(percent).append("%")
            append(" network=").append(networkLabel)
            append(" ram_free_mb=").append(memory.availMem / 1_048_576L)
            append(" ram_total_mb=").append(memory.totalMem / 1_048_576L)
            append(" storage_free_mb=").append(stat.availableBytes / 1_048_576L)
            append(" storage_total_mb=").append(stat.totalBytes / 1_048_576L)
            append(" planner=").append(plannerMode)
            append(" contacts_access=").append(contactsGranted)
            append(" usage_access=").append(usageGranted)
            append(" exact_alarm_access=").append(exactAlarmGranted)
            append(" scheduled_goals=").append(scheduledCount)
        }
    }

    private fun compactUi(raw: String): String {
        val important = ArrayList<String>()
        val context = ArrayList<String>()

        raw.lineSequence()
            .filter { it.isNotBlank() }
            .forEach { line ->
                val priority =
                    line.contains("clickable") ||
                    line.contains("editable") ||
                    line.contains("scrollable") ||
                    line.contains("checked") ||
                    line.contains("focused") ||
                    line.contains(" text=") ||
                    line.contains(" desc=")

                if (priority) important.add(line) else context.add(line)
            }

        val output = StringBuilder()

        fun appendLines(lines: List<String>) {
            for (line in lines) {
                if (output.length + line.length + 1 > MAX_UI_CHARS) return
                output.append(line).append('\n')
            }
        }

        appendLines(important)
        appendLines(context)

        return if (output.isNotEmpty()) output.toString() else raw.take(MAX_UI_CHARS)
    }

    private fun createPlanner(context: Context): Planner {
        val endpoint = plannerEndpoint(context)
        if (endpoint.isNotBlank()) {
            return OpenAiCompatiblePlanner(endpoint, plannerModel(context))
        }

        val modelFile = localModelFile(context)
        if (modelFile.isFile && modelFile.length() > 100_000_000L) {
            return LiteRtPlanner(modelFile, context.cacheDir)
        }

        return RuleBasedPlanner()
    }
}
