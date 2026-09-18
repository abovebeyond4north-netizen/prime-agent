package net.abovebeyond.codieai.agent

import android.content.Context
import net.abovebeyond.codieai.accessibility.CodieAccessibilityService
import net.abovebeyond.codieai.notifications.NotificationStore
import java.io.File
import java.lang.ref.WeakReference
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

object AgentRuntime {
    private const val PREFS = "codie_ai"
    private const val KEY_ENDPOINT = "planner_endpoint"
    private const val KEY_MODEL = "planner_model"
    private const val MAX_UI_CHARS = 5_500

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

            moveAwayFromOwnUiIfNeeded(service, appContext.packageName, status)

            var lastResult = "No action has run yet."
            for (step in 1..32) {
                if (generation.get() != runId) {
                    status("Goal cancelled.")
                    return@execute
                }

                val snapshot = service.captureSnapshot()
                try {
                    val state = buildString {
                        append("UI:\n")
                        append(compactUi(snapshot.text))
                        append("\nNOTIFICATIONS:\n")
                        append(NotificationStore.render(limit = 4))
                        append("\nLAST_RESULT:\n")
                        append(lastResult.take(500))
                    }

                    status("Step " + step + ": reasoning over current phone state")
                    val action = planner.nextAction(normalizedGoal, state, step)
                    status(
                        "Step " + step + ": " + action.type.name +
                            if (action.reason.isBlank()) "" else " — " + action.reason
                    )

                    if (action.type == ActionType.DONE) {
                        status("Complete: " + action.reason.ifBlank { "goal satisfied" })
                        return@execute
                    }
                    if (action.type == ActionType.FAIL) {
                        status("Stopped: " + action.reason.ifBlank { "planner could not continue" })
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

    private fun moveAwayFromOwnUiIfNeeded(
        service: CodieAccessibilityService,
        packageName: String,
        status: (String) -> Unit
    ) {
        val snapshot = service.captureSnapshot()
        try {
            if (snapshot.text.contains("pkg=" + packageName)) {
                status("Leaving Codie AI before acting on the phone.")
                service.execute(AgentAction(ActionType.HOME, reason = "Avoid controlling Codie AI itself"), snapshot)
                Thread.sleep(650L)
            }
        } finally {
            snapshot.close()
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
