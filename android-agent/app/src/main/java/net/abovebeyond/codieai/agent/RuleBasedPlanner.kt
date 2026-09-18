package net.abovebeyond.codieai.agent

class RuleBasedPlanner : Planner {
    private var executed = false

    override fun nextAction(goal: String, snapshot: String, step: Int): AgentAction {
        if (executed) {
            return AgentAction(ActionType.DONE, reason = "Completed the requested one-step device action")
        }

        val trimmed = goal.trim()
        val lower = trimmed.lowercase()
        val contactMessage = parseContactMessage(trimmed)

        val action = when {
            lower == "back" -> AgentAction(ActionType.BACK)
            lower == "home" || lower == "go home" -> AgentAction(ActionType.HOME)
            lower == "recents" || lower == "recent apps" -> AgentAction(ActionType.RECENTS)
            lower == "take screenshot" || lower == "take a screenshot" || lower == "screenshot" ->
                AgentAction(ActionType.TAKE_SCREENSHOT)
            lower == "lock screen" || lower == "lock my phone" || lower == "lock phone" ->
                AgentAction(ActionType.LOCK_SCREEN)
            lower == "power menu" || lower == "show power menu" ->
                AgentAction(ActionType.POWER_DIALOG)

            lower.contains("flashlight") && (lower.contains("on") || lower.contains("enable")) ->
                AgentAction(ActionType.FLASHLIGHT_ON)
            lower.contains("flashlight") && (lower.contains("off") || lower.contains("disable")) ->
                AgentAction(ActionType.FLASHLIGHT_OFF)

            parseBrightness(lower) >= 0 ->
                AgentAction(ActionType.SET_BRIGHTNESS, value = parseBrightness(lower))

            lower.contains("do not disturb") && (lower.contains("on") || lower.contains("enable")) ->
                AgentAction(ActionType.DND_ON)
            lower.contains("do not disturb") && (lower.contains("off") || lower.contains("disable")) ->
                AgentAction(ActionType.DND_OFF)

            lower == "open camera" || lower == "camera" ->
                AgentAction(ActionType.OPEN_CAMERA)

            lower.startsWith("navigate to ") ->
                AgentAction(ActionType.NAVIGATE, query = trimmed.substring(12).trim())
            lower.startsWith("directions to ") ->
                AgentAction(ActionType.NAVIGATE, query = trimmed.substring(14).trim())
            lower.startsWith("map ") ->
                AgentAction(ActionType.OPEN_MAP, query = trimmed.substring(4).trim())

            lower.contains("notifications") && (lower.startsWith("open") || lower.startsWith("show")) ->
                AgentAction(ActionType.NOTIFICATIONS)
            lower.contains("quick settings") && (lower.startsWith("open") || lower.startsWith("show")) ->
                AgentAction(ActionType.QUICK_SETTINGS)

            lower == "scroll down" -> AgentAction(ActionType.SCROLL_FORWARD)
            lower == "scroll up" -> AgentAction(ActionType.SCROLL_BACKWARD)
            lower.startsWith("type ") -> AgentAction(ActionType.SET_TEXT, text = trimmed.substring(5))

            lower.startsWith("search for ") ->
                AgentAction(ActionType.WEB_SEARCH, query = trimmed.substring(11).trim())
            lower.startsWith("web search ") ->
                AgentAction(ActionType.WEB_SEARCH, query = trimmed.substring(11).trim())
            lower.startsWith("open http://") || lower.startsWith("open https://") ->
                AgentAction(ActionType.OPEN_URL, url = trimmed.substring(5).trim())

            lower.startsWith("copy ") ->
                AgentAction(ActionType.SET_CLIPBOARD, text = trimmed.substring(5))
            lower.startsWith("share ") ->
                AgentAction(ActionType.SHARE_TEXT, text = trimmed.substring(6))
            lower.startsWith("find contact ") ->
                AgentAction(ActionType.LOOKUP_CONTACT, query = trimmed.substring(13).trim())
            lower.startsWith("look up contact ") ->
                AgentAction(ActionType.LOOKUP_CONTACT, query = trimmed.substring(16).trim())
            contactMessage != null ->
                AgentAction(
                    ActionType.COMPOSE_SMS_CONTACT,
                    query = contactMessage.first,
                    text = contactMessage.second
                )
            lower.startsWith("call ") ->
                AgentAction(ActionType.DIAL_CONTACT, query = trimmed.substring(5).trim())
            lower.startsWith("dial ") ->
                AgentAction(ActionType.DIAL, number = trimmed.substring(5).trim())

            lower == "play music" || lower == "pause music" || lower == "play pause" ->
                AgentAction(ActionType.MEDIA_PLAY_PAUSE)
            lower == "next track" || lower == "next song" ->
                AgentAction(ActionType.MEDIA_NEXT)
            lower == "previous track" || lower == "previous song" ->
                AgentAction(ActionType.MEDIA_PREVIOUS)
            lower == "volume up" || lower == "turn volume up" ->
                AgentAction(ActionType.VOLUME_UP)
            lower == "volume down" || lower == "turn volume down" ->
                AgentAction(ActionType.VOLUME_DOWN)
            lower == "mute" || lower == "mute volume" ->
                AgentAction(ActionType.VOLUME_MUTE)

            parseTimerSeconds(lower) > 0 ->
                AgentAction(ActionType.SET_TIMER, seconds = parseTimerSeconds(lower))

            lower == "show scheduled goals" || lower == "list scheduled goals" ->
                AgentAction(ActionType.LIST_SCHEDULED)
            lower == "app usage" || lower == "show app usage" ||
                lower == "screen time" || lower == "show screen time" ->
                AgentAction(ActionType.APP_USAGE_REPORT, value = 24)

            lower.startsWith("open wifi settings") || lower.startsWith("open wi-fi settings") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "wifi")
            lower.startsWith("open bluetooth settings") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "bluetooth")
            lower.startsWith("open accessibility settings") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "accessibility")
            lower.startsWith("open notification access") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "notification_access")
            lower.startsWith("open display settings") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "display")
            lower.startsWith("open sound settings") ->
                AgentAction(ActionType.OPEN_SETTINGS, setting = "sound")

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
                reason = "No AI planner is configured for this request. Add the local LiteRT model or a GPT-OSS compatible endpoint."
            )
        }

        if (action.type != ActionType.FAIL) executed = true
        return action
    }

    private fun parseContactMessage(text: String): Pair<String, String>? {
        val match = Regex(
            """^(?:text|message)\s+(.+?)\s+(?:saying|that|:)\s+(.+)$""",
            RegexOption.IGNORE_CASE
        ).find(text) ?: return null

        val name = match.groupValues[1].trim()
        val message = match.groupValues[2].trim()
        return if (name.isBlank() || message.isBlank()) null else name to message
    }

    private fun parseBrightness(lower: String): Int {
        if (!lower.contains("brightness")) return -1
        val value = Regex("""(\d{1,3})\s*%?""")
            .find(lower)?.groupValues?.getOrNull(1)?.toIntOrNull()
            ?: return -1
        return value.coerceIn(0, 100)
    }

    private fun parseTimerSeconds(lower: String): Int {
        if (!lower.contains("timer")) return -1
        val minutes = Regex("""(\d+)\s*(minute|minutes|min)""")
            .find(lower)?.groupValues?.getOrNull(1)?.toIntOrNull()
        if (minutes != null) return minutes.coerceAtMost(24 * 60) * 60

        val seconds = Regex("""(\d+)\s*(second|seconds|sec)""")
            .find(lower)?.groupValues?.getOrNull(1)?.toIntOrNull()
        return seconds?.coerceAtMost(24 * 60 * 60) ?: -1
    }

    private fun findNode(snapshot: String, target: String): Int {
        val idRegex = Regex("""\[id=(\d+)]""")
        val exact = snapshot.lineSequence()
            .firstOrNull { line -> line.contains(target, ignoreCase = true) }
            ?: return -1
        return idRegex.find(exact)?.groupValues?.getOrNull(1)?.toIntOrNull() ?: -1
    }
}
