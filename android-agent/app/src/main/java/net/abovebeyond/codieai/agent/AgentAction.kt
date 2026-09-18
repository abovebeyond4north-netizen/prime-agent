package net.abovebeyond.codieai.agent

import org.json.JSONObject

enum class ActionType {
    TAP_NODE,
    TAP_COORDINATE,
    SET_TEXT,
    BACK,
    HOME,
    RECENTS,
    NOTIFICATIONS,
    QUICK_SETTINGS,
    SCROLL_FORWARD,
    SCROLL_BACKWARD,
    LAUNCH_APP,
    OPEN_SETTINGS,
    WAIT,
    DONE,
    FAIL
}

data class AgentAction(
    val type: ActionType,
    val nodeId: Int = -1,
    val text: String = "",
    val app: String = "",
    val setting: String = "",
    val x: Int = -1,
    val y: Int = -1,
    val milliseconds: Long = 700,
    val reason: String = ""
) {
    companion object {
        fun parse(raw: String): AgentAction {
            val cleaned = raw.trim()
            val start = cleaned.indexOf('{')
            val end = cleaned.lastIndexOf('}')
            require(start >= 0 && end > start) { "Planner did not return a JSON object: " + raw }

            val json = JSONObject(cleaned.substring(start, end + 1))
            val actionName = json.getString("action").trim().uppercase()
            return AgentAction(
                type = ActionType.valueOf(actionName),
                nodeId = json.optInt("node", -1),
                text = json.optString("text", ""),
                app = json.optString("app", ""),
                setting = json.optString("setting", ""),
                x = json.optInt("x", -1),
                y = json.optInt("y", -1),
                milliseconds = json.optLong("milliseconds", 700L).coerceIn(100L, 5_000L),
                reason = json.optString("reason", "")
            )
        }
    }
}
