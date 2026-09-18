package net.abovebeyond.codieai.agent

class RuleBasedPlanner : Planner {
    private var executed = false

    override fun nextAction(goal: String, snapshot: String, step: Int): AgentAction {
        if (executed) {
            return AgentAction(ActionType.DONE, reason = "Completed the requested one-step device action")
        }

        val trimmed = goal.trim()
        val lower = trimmed.lowercase()

        val action = when {
            lower == "back" -> AgentAction(ActionType.BACK)
            lower == "home" || lower == "go home" -> AgentAction(ActionType.HOME)
            lower == "recents" || lower == "recent apps" -> AgentAction(ActionType.RECENTS)
            lower.contains("notifications") && (lower.startsWith("open") || lower.startsWith("show")) ->
                AgentAction(ActionType.NOTIFICATIONS)
            lower.contains("quick settings") && (lower.startsWith("open") || lower.startsWith("show")) ->
                AgentAction(ActionType.QUICK_SETTINGS)
            lower == "scroll down" -> AgentAction(ActionType.SCROLL_FORWARD)
            lower == "scroll up" -> AgentAction(ActionType.SCROLL_BACKWARD)
            lower.startsWith("type ") -> AgentAction(ActionType.SET_TEXT, text = trimmed.substring(5))
            lower.startsWith("open wifi settings") || lower.startsWith("open wi-fi settings") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "wifi")
            lower.startsWith("open bluetooth settings") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "bluetooth")
            lower.startsWith("open accessibility settings") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "accessibility")
            lower.startsWith("open notification access") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "notification_access")
            lower.startsWith("tap ") || lower.startsWith("click ") -> {
                val target = trimmed.substringAfter(' ').trim()
                val node = findNode(snapshot, target)
                if (node >= 0) AgentAction(ActionType.TAP_NODE, nodeId = node)
                else AgentAction(ActionType.FAIL, reason = "No visible node matched '" + target + "'")
            }
            lower.startsWith("open ") ->
                AgentAction(ActionType.LAUNCH_APP, app = trimmed.substring(5).trim())
            else -> AgentAction(
                ActionType.FAIL,
                reason = "No AI planner is configured. Add a local LiteRT model or a GPT-OSS compatible endpoint."
            )
        }

        if (action.type != ActionType.FAIL) executed = true
        return action
    }

    private fun findNode(snapshot: String, target: String): Int {
        val idRegex = Regex("""\[id=(\d+)]""")
        val exact = snapshot.lineSequence()
            .firstOrNull { line -> line.contains(target, ignoreCase = true) }
            ?: return -1
        return idRegex.find(exact)?.groupValues?.getOrNull(1)?.toIntOrNull() ?: -1
    }
}
