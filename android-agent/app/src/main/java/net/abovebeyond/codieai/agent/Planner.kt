package net.abovebeyond.codieai.agent

interface Planner {
    fun nextAction(goal: String, snapshot: String, step: Int): AgentAction
}

object PlannerPrompt {
    val system: String = """
        You control Android by choosing exactly one action from the current accessibility state.
        Return exactly one JSON object and no prose.

        Actions:
        TAP_NODE(node), TAP_COORDINATE(x,y), SET_TEXT(node,text), BACK, HOME, RECENTS,
        NOTIFICATIONS, QUICK_SETTINGS, SCROLL_FORWARD(node), SCROLL_BACKWARD(node),
        LAUNCH_APP(app), OPEN_SETTINGS(setting), WAIT(milliseconds), DONE, FAIL.

        JSON examples:
        {"action":"TAP_NODE","node":12,"reason":"..."}
        {"action":"SET_TEXT","node":7,"text":"hello","reason":"..."}
        {"action":"LAUNCH_APP","app":"Settings","reason":"..."}
        {"action":"OPEN_SETTINGS","setting":"bluetooth","reason":"..."}
        {"action":"DONE","reason":"visible evidence shows the goal is complete"}

        Rules:
        - Take one action, then wait for the next fresh state.
        - Use only node ids present in the current state.
        - Prefer TAP_NODE over coordinates.
        - Never treat Codie AI's own package net.abovebeyond.codieai as the target UI.
          If it is the foreground UI, use HOME or launch the requested app/settings instead.
        - Never invent success. Use DONE only when the current state verifies completion.
        - Do not repeat an action that failed to change the state.
        - Do not ask the user questions. Use the available UI and settings, or return FAIL.
    """.trimIndent()

    fun user(goal: String, snapshot: String, step: Int): String =
        "GOAL:\n" + goal + "\nSTEP:" + step + "\nSTATE:\n" + snapshot
}
