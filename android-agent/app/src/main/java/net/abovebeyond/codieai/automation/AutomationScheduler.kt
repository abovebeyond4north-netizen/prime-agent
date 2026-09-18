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
    val goal: String
)

object AutomationScheduler {
    private const val PREFS = "codie_ai_automation"
    private const val KEY_TASKS = "tasks"
    private val nextId = AtomicInteger((System.currentTimeMillis() % 1_000_000L).toInt())

    fun schedule(context: Context, start: String, goal: String): Result<ScheduledGoal> {
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

        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        if (Build.VERSION.SDK_INT >= 31 && !alarmManager.canScheduleExactAlarms()) {
            return Result.failure(
                SecurityException(
                    "Alarms & reminders access is required for autonomous scheduled goals."
                )
            )
        }

        val id = nextUniqueId(context)
        val task = ScheduledGoal(id, trigger, cleanedGoal)
        val operation = createPendingIntent(context, task)

        alarmManager.setExactAndAllowWhileIdle(
            AlarmManager.RTC_WAKEUP,
            trigger,
            operation
        )

        saveTask(context, task)
        return Result.success(task)
    }

    fun cancel(context: Context, id: Int): Result<String> {
        val task = tasks(context).firstOrNull { it.id == id }
            ?: return Result.failure(IllegalArgumentException("No scheduled goal has id " + id))

        val manager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val existing = PendingIntent.getForegroundService(
            context,
            task.id,
            serviceIntent(context, task),
            PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE
        )
        if (existing != null) manager.cancel(existing)

        remove(context, id)
        return Result.success("Cancelled scheduled goal #" + id)
    }

    fun markTriggered(context: Context, id: Int) {
        remove(context, id)
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
            items.take(20).forEach { task ->
                append("\n#").append(task.id)
                    .append(" at ")
                    .append(formatter.format(java.util.Date(task.triggerAtMillis)))
                    .append(": ")
                    .append(task.goal)
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
                            goal = item.getString("goal")
                        )
                    )
                }
            }
        }.getOrElse { emptyList() }
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

    private fun createPendingIntent(context: Context, task: ScheduledGoal): PendingIntent =
        PendingIntent.getForegroundService(
            context,
            task.id,
            serviceIntent(context, task),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

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
