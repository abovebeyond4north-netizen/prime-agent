package net.abovebeyond.codieai.tools

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicInteger

data class McpPendingRequest(
    val id: Int,
    val server: String,
    val method: String,
    val targetName: String,
    val paramsJson: String,
    val inputRequestsJson: String,
    val requestState: String,
    val rounds: Int,
    val updatedAt: Long
)

object McpPendingStore {
    private const val PREFS = "codie_ai_mcp_pending"
    private const val KEY_PENDING = "pending"
    private const val MAX_PENDING = 20
    private val nextId = AtomicInteger((System.currentTimeMillis() % 900_000L).toInt() + 1000)

    fun save(
        context: Context,
        server: String,
        method: String,
        targetName: String?,
        params: JSONObject,
        result: JSONObject,
        existingId: Int? = null,
        rounds: Int = 1
    ): McpPendingRequest {
        require(rounds in 1..10) { "MCP multi-round-trip exceeded 10 rounds" }

        val inputRequests = result.optJSONObject("inputRequests") ?: JSONObject()
        val requestState = result.optString("requestState", "")
        require(inputRequests.length() > 0 || requestState.isNotBlank()) {
            "MCP input_required result contained neither inputRequests nor requestState"
        }

        val all = list(context).toMutableList()
        val id = existingId ?: nextUniqueId(all)
        all.removeAll { it.id == id }

        require(all.size < MAX_PENDING) { "Too many pending MCP requests" }

        val pending = McpPendingRequest(
            id = id,
            server = server,
            method = method,
            targetName = targetName.orEmpty(),
            paramsJson = params.toString(),
            inputRequestsJson = inputRequests.toString(),
            requestState = requestState,
            rounds = rounds,
            updatedAt = System.currentTimeMillis()
        )
        all.add(pending)
        write(context, all)
        return pending
    }

    fun get(context: Context, id: Int): McpPendingRequest =
        list(context).firstOrNull { it.id == id }
            ?: throw IllegalArgumentException("Pending MCP request not found: #" + id)

    fun remove(context: Context, id: Int) {
        write(context, list(context).filterNot { it.id == id })
    }

    fun render(context: Context): String {
        val all = list(context).sortedByDescending { it.updatedAt }
        if (all.isEmpty()) return "No pending MCP multi-round-trip requests."

        return buildString {
            append("Pending MCP requests:")
            all.forEach { pending ->
                append("\n#").append(pending.id)
                    .append(" server=").append(pending.server)
                    .append(" method=").append(pending.method)
                    .append(" rounds=").append(pending.rounds)
                if (pending.targetName.isNotBlank()) {
                    append(" target=").append(pending.targetName)
                }
                append("\n  inputRequests=")
                    .append(pending.inputRequestsJson.take(3000))
            }
        }.take(12_000)
    }

    private fun list(context: Context): List<McpPendingRequest> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_PENDING, "[]")
            .orEmpty()

        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    add(
                        McpPendingRequest(
                            id = obj.getInt("id"),
                            server = obj.getString("server"),
                            method = obj.getString("method"),
                            targetName = obj.optString("target_name", ""),
                            paramsJson = obj.getString("params_json"),
                            inputRequestsJson = obj.optString("input_requests_json", "{}"),
                            requestState = obj.optString("request_state", ""),
                            rounds = obj.optInt("rounds", 1),
                            updatedAt = obj.optLong("updated_at", 0L)
                        )
                    )
                }
            }
        }.getOrElse { emptyList() }
    }

    private fun nextUniqueId(existing: List<McpPendingRequest>): Int {
        val used = existing.mapTo(HashSet()) { it.id }
        repeat(10_000) {
            val id = nextId.updateAndGet { current ->
                if (current >= 2_000_000_000) 1000 else current + 1
            }
            if (id !in used) return id
        }
        throw IllegalStateException("Could not allocate pending MCP id")
    }

    private fun write(context: Context, all: List<McpPendingRequest>) {
        val array = JSONArray()
        all.forEach { pending ->
            array.put(
                JSONObject()
                    .put("id", pending.id)
                    .put("server", pending.server)
                    .put("method", pending.method)
                    .put("target_name", pending.targetName)
                    .put("params_json", pending.paramsJson)
                    .put("input_requests_json", pending.inputRequestsJson)
                    .put("request_state", pending.requestState)
                    .put("rounds", pending.rounds)
                    .put("updated_at", pending.updatedAt)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_PENDING, array.toString())
            .apply()
    }
}
