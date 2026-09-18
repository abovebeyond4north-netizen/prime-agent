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
    TAKE_SCREENSHOT,
    LOCK_SCREEN,
    POWER_DIALOG,
    SCROLL_FORWARD,
    SCROLL_BACKWARD,
    LAUNCH_APP,
    OPEN_SETTINGS,
    OPEN_URL,
    WEB_SEARCH,
    OPEN_MAP,
    NAVIGATE,
    OPEN_CAMERA,
    SET_CLIPBOARD,
    SHARE_TEXT,
    DIAL,
    COMPOSE_SMS,
    COMPOSE_EMAIL,
    CREATE_CALENDAR_EVENT,
    SET_ALARM,
    SET_TIMER,
    FLASHLIGHT_ON,
    FLASHLIGHT_OFF,
    SET_BRIGHTNESS,
    DND_ON,
    DND_OFF,
    MEDIA_PLAY_PAUSE,
    MEDIA_NEXT,
    MEDIA_PREVIOUS,
    VOLUME_UP,
    VOLUME_DOWN,
    VOLUME_MUTE,
    OPEN_NOTIFICATION,
    DISMISS_NOTIFICATION,
    SNOOZE_NOTIFICATION,
    REPLY_NOTIFICATION,
    WAIT,
    RESPOND,
    DONE,
    FAIL
}

data class AgentAction(
    val type: ActionType,
    val nodeId: Int = -1,
    val text: String = "",
    val app: String = "",
    val setting: String = "",
    val url: String = "",
    val query: String = "",
    val number: String = "",
    val subject: String = "",
    val title: String = "",
    val start: String = "",
    val end: String = "",
    val value: Int = -1,
    val notificationIndex: Int = -1,
    val hour: Int = -1,
    val minute: Int = -1,
    val seconds: Int = -1,
    val x: Int = -1,
    val y: Int = -1,
    val milliseconds: Long = 700,
    val reason: String = ""
) {
    companion object {
        fun parse(raw: String): AgentAction {
            val cleaned = raw.trim()
            val startIndex = cleaned.indexOf('{')
            val endIndex = cleaned.lastIndexOf('}')
            require(startIndex >= 0 && endIndex > startIndex) {
                "Planner did not return a JSON object: " + raw
            }

            val json = JSONObject(cleaned.substring(startIndex, endIndex + 1))
            val actionName = json.getString("action").trim().uppercase()
            return AgentAction(
                type = ActionType.valueOf(actionName),
                nodeId = json.optInt("node", -1),
                text = json.optString("text", ""),
                app = json.optString("app", ""),
                setting = json.optString("setting", ""),
                url = json.optString("url", ""),
                query = json.optString("query", ""),
                number = json.optString("number", ""),
                subject = json.optString("subject", ""),
                title = json.optString("title", ""),
                start = json.optString("start", ""),
                end = json.optString("end", ""),
                value = json.optInt("value", -1),
                notificationIndex = json.optInt("notification", -1),
                hour = json.optInt("hour", -1),
                minute = json.optInt("minute", -1),
                seconds = json.optInt("seconds", -1),
                x = json.optInt("x", -1),
                y = json.optInt("y", -1),
                milliseconds = json.optLong("milliseconds", 700L).coerceIn(100L, 3_600_000L),
                reason = json.optString("reason", "")
            )
        }
    }
}
