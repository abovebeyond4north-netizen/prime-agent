package net.abovebeyond.codieai.automation

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.atomic.AtomicInteger

data class ScheduledGoal(
    val id: Int,
    val triggerAtMillis: Long,
    val goal: String,
    val repeatMinutes: Int = 0
)

object AutomationScheduler {
    private const val PREFS = "codie_ai_automation"
    private const val KEY_TASKS = "tasks"
    private const val MIN_REPEAT_MINUTES = 15
    private val nextId = AtomicInteger((System.currentTimeMillis() % 1_000_000L).toInt())

    fun schedule(context: Context, start: String, goal: String): Result<ScheduledGoal> =
        scheduleInternal(context, start, goal, 0)

    fun scheduleRecurring(
        context: Context,
        start: String,
        goal: String,
        repeatMinutes: Int
    ): Result<ScheduledGoal> {
        if (repeatMinutes < MIN_REPEAT_MINUTES) {
            return Result.failure(
                IllegalArgumentException("Recurring goals must repeat every 15 minutes or longer")
            )
        }
        return scheduleInternal(context, start, goal, repeatMinutes.coerceAtMost(525_600))
    }

    private fun scheduleInternal(
        context: Context,
        start: String,
        goal: String,
        repeatMinutes: Int
    ): Result<ScheduledGoal> {
        val cleanedGoal = goal.trim()
        if (cleanedGoal.isBlank()) {
            return Result.failure(IllegalArgumentException("Scheduled goal is blank"))
        }

        val trigger = parseDateTime(start)
            ?: return Result.failure(
                IllegalArgumentException(
                    "Scheduled time must be ISO-8601, for example 2026-09-18T19:30:00-04:00"
                )
            )

        if (trigger <= System.currentTimeMillis() + 2_000L) {
            return Result.failure(IllegalArgumentException("Scheduled time must be in the future"))
        }

        return runCatching {
            requireExactAlarmAccess(context)
            val id = nextUniqueId(context)
            val task = ScheduledGoal(id, trigger, cleanedGoal, repeatMinutes)
            scheduleAlarm(context, task)
            saveTask(context, task)
            task
        }
    }

    fun cancel(context: Context, id: Int): Result<String> {
        val task = tasks(context).firstOrNull { it.id == id }
            ?: return Result.failure(IllegalArgumentException("No scheduled goal has id " + id))

        val manager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        pendingIntent(context, task, PendingIntent.FLAG_NO_CREATE)?.let(manager::cancel)
        remove(context, id)
        return Result.success("Cancelled scheduled goal #" + id)
    }

    fun handleTrigger(context: Context, id: Int): ScheduledGoal? {
        val task = tasks(context).firstOrNull { it.id == id } ?: return null
        if (task.repeatMinutes <= 0) {
            remove(context, id)
            return task
        }

        val intervalMs = task.repeatMinutes * 60_000L
        var next = task.triggerAtMillis + intervalMs
        val now = System.currentTimeMillis()
        while (next <= now + 2_000L) next += intervalMs

        val updated = task.copy(triggerAtMillis = next)
        runCatching {
            requireExactAlarmAccess(context)
            scheduleAlarm(context, updated)
            saveTask(context, updated)
        }
        return task
    }

    fun restoreAll(context: Context): String {
        val current = tasks(context)
        if (current.isEmpty()) return "No scheduled goals to restore."

        requireExactAlarmAccess(context)
        val now = System.currentTimeMillis()
        val restored = ArrayList<ScheduledGoal>()

        current.forEach { task ->
            val adjusted = when {
                task.triggerAtMillis > now + 5_000L -> task
                task.repeatMinutes > 0 -> {
                    val interval = task.repeatMinutes * 60_000L
                    var next = task.triggerAtMillis
                    while (next <= now + 5_000L) next += interval
                    task.copy(triggerAtMillis = next)
                }
                else -> task.copy(triggerAtMillis = now + 10_000L)
            }

            scheduleAlarm(context, adjusted)
            restored.add(adjusted)
        }

        writeTasks(context, restored)
        return "Restored " + restored.size + " scheduled goal(s)."
    }

    fun render(context: Context): String {
        val items = tasks(context).sortedBy { it.triggerAtMillis }
        if (items.isEmpty()) return "No scheduled goals."

        val formatter = java.text.SimpleDateFormat(
            "yyyy-MM-dd HH:mm:ss Z",
            java.util.Locale.getDefault()
        )
        return buildString {
            append("Scheduled goals:")
            items.take(30).forEach { task ->
                append("\n#").append(task.id)
                    .append(" at ")
                    .append(formatter.format(java.util.Date(task.triggerAtMillis)))
                if (task.repeatMinutes > 0) {
                    append(" every ").append(task.repeatMinutes).append(" min")
                }
                append(": ").append(task.goal)
            }
        }
    }

    fun tasks(context: Context): List<ScheduledGoal> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_TASKS, "[]")
            .orEmpty()

        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.getJSONObject(i)
                    add(
                        ScheduledGoal(
                            id = item.getInt("id"),
                            triggerAtMillis = item.getLong("trigger"),
                            goal = item.getString("goal"),
                            repeatMinutes = item.optInt("repeat_minutes", 0)
                        )
                    )
                }
            }
        }.getOrElse { emptyList() }
    }

    private fun requireExactAlarmAccess(context: Context) {
        val manager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        if (Build.VERSION.SDK_INT >= 31 && !manager.canScheduleExactAlarms()) {
            throw SecurityException(
                "Alarms & reminders access is required for autonomous scheduled goals."
            )
        }
    }

    private fun scheduleAlarm(context: Context, task: ScheduledGoal) {
        val manager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        manager.setExactAndAllowWhileIdle(
            AlarmManager.RTC_WAKEUP,
            task.triggerAtMillis,
            createPendingIntent(context, task)
        )
    }

    private fun nextUniqueId(context: Context): Int {
        val used = tasks(context).mapTo(HashSet()) { it.id }
        repeat(10_000) {
            val candidate = nextId.updateAndGet { current ->
                if (current >= 2_000_000_000) 1000 else current + 1
            }
            if (candidate !in used) return candidate
        }
        throw IllegalStateException("Could not allocate scheduled goal id")
    }

    private fun serviceIntent(context: Context, task: ScheduledGoal): Intent =
        Intent(context, ScheduledGoalService::class.java)
            .putExtra(ScheduledGoalService.EXTRA_TASK_ID, task.id)
            .putExtra(ScheduledGoalService.EXTRA_GOAL, task.goal)

    private fun pendingIntent(
        context: Context,
        task: ScheduledGoal,
        flags: Int
    ): PendingIntent? =
        PendingIntent.getForegroundService(
            context,
            task.id,
            serviceIntent(context, task),
            flags or PendingIntent.FLAG_IMMUTABLE
        )

    private fun createPendingIntent(context: Context, task: ScheduledGoal): PendingIntent =
        requireNotNull(pendingIntent(context, task, PendingIntent.FLAG_UPDATE_CURRENT))

    private fun saveTask(context: Context, task: ScheduledGoal) {
        val all = tasks(context).filterNot { it.id == task.id }.toMutableList()
        all.add(task)
        writeTasks(context, all)
    }

    private fun remove(context: Context, id: Int) {
        writeTasks(context, tasks(context).filterNot { it.id == id })
    }

    private fun writeTasks(context: Context, items: List<ScheduledGoal>) {
        val array = JSONArray()
        items.forEach { task ->
            array.put(
                JSONObject()
                    .put("id", task.id)
                    .put("trigger", task.triggerAtMillis)
                    .put("goal", task.goal)
                    .put("repeat_minutes", task.repeatMinutes)
            )
        }

        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_TASKS, array.toString())
            .apply()
    }

    private fun parseDateTime(value: String): Long? {
        if (value.isBlank()) return null
        return runCatching {
            OffsetDateTime.parse(value).toInstant().toEpochMilli()
        }.getOrNull() ?: runCatching {
            LocalDateTime.parse(value, DateTimeFormatter.ISO_LOCAL_DATE_TIME)
                .atZone(ZoneId.systemDefault())
                .toInstant()
                .toEpochMilli()
        }.getOrNull()
    }
}
