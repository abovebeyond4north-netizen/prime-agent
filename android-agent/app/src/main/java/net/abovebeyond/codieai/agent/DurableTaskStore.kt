package net.abovebeyond.codieai.agent

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicInteger

data class DurableTask(
    val id: Int,
    val goal: String,
    val state: String,
    val lastMessage: String,
    val createdAt: Long,
    val updatedAt: Long,
    val attempts: Int
)

object DurableTaskStore {
    private const val PREFS = "codie_ai_durable_tasks"
    private const val KEY_TASKS = "tasks"
    private const val MAX_TASKS = 50
    private val nextId = AtomicInteger((System.currentTimeMillis() % 1_000_000L).toInt())

    fun enqueue(context: Context, goal: String): DurableTask {
        val cleaned = goal.trim()
        require(cleaned.isNotBlank()) { "Durable goal is blank" }

        val current = tasks(context).toMutableList()
        require(current.count { it.state in setOf("queued", "running") } < MAX_TASKS) {
            "Durable task queue is full"
        }

        val now = System.currentTimeMillis()
        val task = DurableTask(
            id = nextUniqueId(current),
            goal = cleaned,
            state = "queued",
            lastMessage = "Queued.",
            createdAt = now,
            updatedAt = now,
            attempts = 0
        )
        current.add(task)
        write(context, current)
        return task
    }

    fun tasks(context: Context): List<DurableTask> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_TASKS, "[]")
            .orEmpty()

        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.getJSONObject(i)
                    add(
                        DurableTask(
                            id = item.getInt("id"),
                            goal = item.getString("goal"),
                            state = item.optString("state", "queued"),
                            lastMessage = item.optString("last_message", ""),
                            createdAt = item.optLong("created_at", 0L),
                            updatedAt = item.optLong("updated_at", 0L),
                            attempts = item.optInt("attempts", 0)
                        )
                    )
                }
            }
        }.getOrElse { emptyList() }
    }

    fun find(context: Context, id: Int): DurableTask? =
        tasks(context).firstOrNull { it.id == id }

    fun next(context: Context): DurableTask? =
        tasks(context)
            .filter { it.state == "running" || it.state == "queued" }
            .sortedWith(
                compareBy<DurableTask> { if (it.state == "running") 0 else 1 }
                    .thenBy { it.createdAt }
            )
            .firstOrNull()

    fun markRunning(context: Context, id: Int): DurableTask =
        update(context, id) {
            it.copy(
                state = "running",
                lastMessage = "Starting/resuming durable execution.",
                updatedAt = System.currentTimeMillis(),
                attempts = it.attempts + 1
            )
        }

    fun updateMessage(context: Context, id: Int, message: String) {
        val existing = find(context, id) ?: return
        if (existing.state == "cancelled") return

        update(context, id) {
            it.copy(
                lastMessage = message.take(2_000),
                updatedAt = System.currentTimeMillis()
            )
        }
    }

    fun finish(context: Context, id: Int, success: Boolean, message: String) {
        val existing = find(context, id) ?: return
        if (existing.state == "cancelled") return

        update(context, id) {
            it.copy(
                state = if (success) "complete" else "failed",
                lastMessage = message.take(2_000),
                updatedAt = System.currentTimeMillis()
            )
        }
        prune(context)
    }

    fun cancel(context: Context, id: Int): String {
        update(context, id) {
            require(it.state == "queued" || it.state == "running") {
                "Task #" + id + " is already " + it.state
            }
            it.copy(
                state = "cancelled",
                lastMessage = "Cancelled by user.",
                updatedAt = System.currentTimeMillis()
            )
        }
        return "Cancelled durable task #" + id
    }

    fun recoverRunning(context: Context): Int {
        val current = tasks(context)
        var changed = 0
        val updated = current.map { task ->
            if (task.state == "running") {
                changed++
                task.copy(
                    state = "queued",
                    lastMessage = "Recovered after process/reboot interruption.",
                    updatedAt = System.currentTimeMillis()
                )
            } else task
        }
        if (changed > 0) write(context, updated)
        return changed
    }

    fun render(context: Context): String {
        val all = tasks(context).sortedByDescending { it.updatedAt }
        if (all.isEmpty()) return "No durable tasks."

        return buildString {
            append("Durable tasks:")
            all.take(30).forEach { task ->
                append("\n#").append(task.id)
                    .append(" [").append(task.state).append("]")
                    .append(" attempts=").append(task.attempts)
                    .append(": ").append(task.goal.take(200))
                if (task.lastMessage.isNotBlank()) {
                    append("\n  last=").append(
                        task.lastMessage.replace('\n', ' ').take(300)
                    )
                }
            }
        }
    }

    private fun update(
        context: Context,
        id: Int,
        transform: (DurableTask) -> DurableTask
    ): DurableTask {
        val current = tasks(context).toMutableList()
        val index = current.indexOfFirst { it.id == id }
        require(index >= 0) { "Durable task not found: #" + id }
        val updated = transform(current[index])
        current[index] = updated
        write(context, current)
        return updated
    }

    private fun prune(context: Context) {
        val all = tasks(context)
        if (all.size <= MAX_TASKS) return

        val active = all.filter { it.state == "queued" || it.state == "running" }
        val historical = all
            .filterNot { it.state == "queued" || it.state == "running" }
            .sortedByDescending { it.updatedAt }
            .take((MAX_TASKS - active.size).coerceAtLeast(0))

        write(context, active + historical)
    }

    private fun nextUniqueId(existing: List<DurableTask>): Int {
        val used = existing.mapTo(HashSet()) { it.id }
        repeat(10_000) {
            val id = nextId.updateAndGet { current ->
                if (current >= 2_000_000_000) 1000 else current + 1
            }
            if (id !in used) return id
        }
        throw IllegalStateException("Could not allocate durable task id")
    }

    private fun write(context: Context, tasks: List<DurableTask>) {
        val array = JSONArray()
        tasks.forEach { task ->
            array.put(
                JSONObject()
                    .put("id", task.id)
                    .put("goal", task.goal)
                    .put("state", task.state)
                    .put("last_message", task.lastMessage)
                    .put("created_at", task.createdAt)
                    .put("updated_at", task.updatedAt)
                    .put("attempts", task.attempts)
            )
        }

        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_TASKS, array.toString())
            .apply()
    }
}
