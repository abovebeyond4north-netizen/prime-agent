package net.abovebeyond.codieai.agent

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicInteger

data class TaskPlanNode(
    val id: String,
    val goal: String,
    val dependsOn: List<String>,
    val state: String = "pending",
    val durableTaskId: Int = -1,
    val lastMessage: String = ""
)

data class TaskPlan(
    val id: Int,
    val goal: String,
    val state: String,
    val nodes: List<TaskPlanNode>,
    val createdAt: Long,
    val updatedAt: Long
)

object TaskPlanStore {
    private const val PREFS = "codie_ai_task_plans"
    private const val KEY_PLANS = "plans"
    private const val MAX_PLANS = 30
    private const val MAX_NODES = 24
    private val nextId = AtomicInteger((System.currentTimeMillis() % 1_000_000L).toInt())

    fun create(context: Context, goal: String, rawSteps: String): TaskPlan {
        val cleanedGoal = goal.trim()
        require(cleanedGoal.isNotBlank()) { "Task-plan goal is blank" }

        val array = JSONArray(rawSteps)
        require(array.length() in 1..MAX_NODES) {
            "Task plan must contain 1.." + MAX_NODES + " steps"
        }

        val nodes = ArrayList<TaskPlanNode>()
        val ids = HashSet<String>()

        for (i in 0 until array.length()) {
            val step = array.getJSONObject(i)
            val id = normalizeNodeId(step.getString("id"))
            require(ids.add(id)) { "Duplicate task-plan node id: " + id }

            val nodeGoal = step.getString("goal").trim()
            require(nodeGoal.isNotBlank()) { "Task-plan node '" + id + "' has a blank goal" }

            val depsArray = step.optJSONArray("depends_on") ?: JSONArray()
            val deps = buildList {
                for (j in 0 until depsArray.length()) {
                    add(normalizeNodeId(depsArray.getString(j)))
                }
            }.distinct()

            nodes.add(
                TaskPlanNode(
                    id = id,
                    goal = nodeGoal,
                    dependsOn = deps
                )
            )
        }

        validateGraph(nodes)

        val existing = plans(context).toMutableList()
        require(existing.size < MAX_PLANS) {
            "Task-plan store is full; finish/remove old plans before creating more"
        }

        val now = System.currentTimeMillis()
        val plan = TaskPlan(
            id = nextUniqueId(existing),
            goal = cleanedGoal,
            state = "created",
            nodes = nodes,
            createdAt = now,
            updatedAt = now
        )
        existing.add(plan)
        write(context, existing)
        return plan
    }

    fun run(context: Context, planId: Int): String {
        val plan = find(context, planId)
            ?: throw IllegalArgumentException("Task plan not found: #" + planId)

        require(plan.state !in setOf("complete", "failed", "cancelled")) {
            "Task plan #" + planId + " is already " + plan.state
        }

        val queued = dispatchReady(context, planId)
        val started = DurableAgentService.startIfPending(context)
        return "Task plan #" + planId +
            " queued_ready_nodes=" + queued +
            " durable_service_started=" + started
    }

    fun onTaskFinished(
        context: Context,
        planId: Int,
        nodeId: String,
        success: Boolean,
        message: String
    ) {
        if (planId <= 0 || nodeId.isBlank()) return
        val plan = find(context, planId) ?: return
        if (plan.state in setOf("cancelled", "complete", "failed")) return

        val updatedNodes = plan.nodes.map { node ->
            if (node.id == nodeId) {
                node.copy(
                    state = if (success) "complete" else "failed",
                    lastMessage = message.take(1000)
                )
            } else node
        }

        val nextState = when {
            !success -> "failed"
            updatedNodes.all { it.state == "complete" } -> "complete"
            else -> "running"
        }

        save(
            context,
            plan.copy(
                state = nextState,
                nodes = updatedNodes,
                updatedAt = System.currentTimeMillis()
            )
        )

        if (nextState == "running") {
            dispatchReady(context, planId)
            DurableAgentService.startIfPending(context)
        }
    }

    fun cancel(context: Context, planId: Int): String {
        val plan = find(context, planId)
            ?: throw IllegalArgumentException("Task plan not found: #" + planId)

        plan.nodes
            .filter { it.durableTaskId >= 0 && it.state in setOf("queued", "running") }
            .forEach { node ->
                runCatching { DurableAgentService.cancelTask(context, node.durableTaskId) }
            }

        val updated = plan.copy(
            state = "cancelled",
            nodes = plan.nodes.map { node ->
                if (node.state in setOf("pending", "queued", "running")) {
                    node.copy(state = "cancelled", lastMessage = "Plan cancelled.")
                } else node
            },
            updatedAt = System.currentTimeMillis()
        )
        save(context, updated)
        return "Cancelled task plan #" + planId
    }

    fun render(context: Context, planId: Int? = null): String {
        val selected = if (planId == null) {
            plans(context).sortedByDescending { it.updatedAt }.take(20)
        } else {
            listOfNotNull(find(context, planId))
        }

        if (selected.isEmpty()) return "No task plans."

        return buildString {
            append("Task plans:")
            selected.forEach { plan ->
                append("\n\n#").append(plan.id)
                    .append(" [").append(plan.state).append("] ")
                    .append(plan.goal.take(300))
                plan.nodes.forEach { node ->
                    append("\n  - ").append(node.id)
                        .append(" [").append(node.state).append("]")
                    if (node.dependsOn.isNotEmpty()) {
                        append(" deps=").append(node.dependsOn.joinToString(","))
                    }
                    if (node.durableTaskId >= 0) {
                        append(" durable=#").append(node.durableTaskId)
                    }
                    append(": ").append(node.goal.take(240))
                    if (node.lastMessage.isNotBlank()) {
                        append("\n    last=")
                            .append(node.lastMessage.replace('\n', ' ').take(280))
                    }
                }
            }
        }.take(12_000)
    }

    fun plans(context: Context): List<TaskPlan> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_PLANS, "[]")
            .orEmpty()

        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    val nodeArray = obj.getJSONArray("nodes")
                    val nodes = buildList {
                        for (j in 0 until nodeArray.length()) {
                            val n = nodeArray.getJSONObject(j)
                            val depsArray = n.optJSONArray("depends_on") ?: JSONArray()
                            val deps = buildList {
                                for (k in 0 until depsArray.length()) {
                                    add(depsArray.getString(k))
                                }
                            }
                            add(
                                TaskPlanNode(
                                    id = n.getString("id"),
                                    goal = n.getString("goal"),
                                    dependsOn = deps,
                                    state = n.optString("state", "pending"),
                                    durableTaskId = n.optInt("durable_task_id", -1),
                                    lastMessage = n.optString("last_message", "")
                                )
                            )
                        }
                    }

                    add(
                        TaskPlan(
                            id = obj.getInt("id"),
                            goal = obj.getString("goal"),
                            state = obj.optString("state", "created"),
                            nodes = nodes,
                            createdAt = obj.optLong("created_at", 0L),
                            updatedAt = obj.optLong("updated_at", 0L)
                        )
                    )
                }
            }
        }.getOrElse { emptyList() }
    }

    private fun dispatchReady(context: Context, planId: Int): Int {
        val plan = find(context, planId)
            ?: throw IllegalArgumentException("Task plan not found: #" + planId)

        if (plan.state in setOf("complete", "failed", "cancelled")) return 0

        val completed = plan.nodes
            .filter { it.state == "complete" }
            .mapTo(HashSet()) { it.id }

        val ready = plan.nodes.filter { node ->
            node.state == "pending" && node.dependsOn.all { it in completed }
        }

        if (ready.isEmpty()) {
            save(
                context,
                plan.copy(
                    state = if (plan.nodes.all { it.state == "complete" }) "complete" else "running",
                    updatedAt = System.currentTimeMillis()
                )
            )
            return 0
        }

        val taskIds = HashMap<String, Int>()
        ready.forEach { node ->
            val existing = DurableTaskStore.findPlanNode(context, planId, node.id)
                ?.takeIf { it.state == "queued" || it.state == "running" }
            val task = existing ?: DurableTaskStore.enqueue(
                context = context,
                goal = node.goal,
                planId = planId,
                nodeId = node.id
            )
            taskIds[node.id] = task.id
        }

        val updated = plan.copy(
            state = "running",
            nodes = plan.nodes.map { node ->
                taskIds[node.id]?.let { taskId ->
                    node.copy(
                        state = "queued",
                        durableTaskId = taskId,
                        lastMessage = "Queued as durable task #" + taskId
                    )
                } ?: node
            },
            updatedAt = System.currentTimeMillis()
        )
        save(context, updated)
        return ready.size
    }

    private fun find(context: Context, id: Int): TaskPlan? =
        plans(context).firstOrNull { it.id == id }

    private fun save(context: Context, plan: TaskPlan) {
        val all = plans(context).toMutableList()
        val index = all.indexOfFirst { it.id == plan.id }
        if (index >= 0) all[index] = plan else all.add(plan)
        write(context, all)
    }

    private fun validateGraph(nodes: List<TaskPlanNode>) {
        val ids = nodes.mapTo(HashSet()) { it.id }
        nodes.forEach { node ->
            require(node.id !in node.dependsOn) {
                "Task-plan node '" + node.id + "' cannot depend on itself"
            }
            node.dependsOn.forEach { dep ->
                require(dep in ids) {
                    "Task-plan node '" + node.id + "' depends on unknown node '" + dep + "'"
                }
            }
        }

        val byId = nodes.associateBy { it.id }
        val visiting = HashSet<String>()
        val visited = HashSet<String>()

        fun visit(id: String) {
            if (id in visited) return
            require(visiting.add(id)) { "Task plan contains a dependency cycle at '" + id + "'" }
            byId.getValue(id).dependsOn.forEach(::visit)
            visiting.remove(id)
            visited.add(id)
        }

        nodes.forEach { visit(it.id) }
    }

    private fun normalizeNodeId(raw: String): String {
        val id = raw.trim().lowercase()
        require(id.matches(Regex("""[a-z][a-z0-9_-]{0,39}"""))) {
            "Task-plan node ids must match [a-z][a-z0-9_-]{0,39}"
        }
        return id
    }

    private fun nextUniqueId(existing: List<TaskPlan>): Int {
        val used = existing.mapTo(HashSet()) { it.id }
        repeat(10_000) {
            val id = nextId.updateAndGet { current ->
                if (current >= 2_000_000_000) 2000 else current + 1
            }
            if (id !in used) return id
        }
        throw IllegalStateException("Could not allocate task-plan id")
    }

    private fun write(context: Context, plans: List<TaskPlan>) {
        val array = JSONArray()
        plans.forEach { plan ->
            val nodes = JSONArray()
            plan.nodes.forEach { node ->
                val deps = JSONArray()
                node.dependsOn.forEach { dep -> deps.put(dep) }
                nodes.put(
                    JSONObject()
                        .put("id", node.id)
                        .put("goal", node.goal)
                        .put("depends_on", deps)
                        .put("state", node.state)
                        .put("durable_task_id", node.durableTaskId)
                        .put("last_message", node.lastMessage)
                )
            }

            array.put(
                JSONObject()
                    .put("id", plan.id)
                    .put("goal", plan.goal)
                    .put("state", plan.state)
                    .put("nodes", nodes)
                    .put("created_at", plan.createdAt)
                    .put("updated_at", plan.updatedAt)
            )
        }

        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_PLANS, array.toString())
            .apply()
    }
}
