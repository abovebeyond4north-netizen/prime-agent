package net.abovebeyond.codieai.agent

interface Planner {
    fun nextAction(goal: String, snapshot: String, step: Int): AgentAction
}

object PlannerPrompt {
    val system: String = """
        You are the decision engine for an Android phone-control agent.
        You receive the user's goal and a fresh accessibility snapshot after every action.
        Return exactly one JSON object and no prose.

        Allowed actions:
        {"action":"TAP_NODE","node":12,"reason":"..."}
        {"action":"TAP_COORDINATE","x":500,"y":1200,"reason":"..."}
        {"action":"SET_TEXT","node":12,"text":"hello","reason":"..."}
        {"action":"BACK","reason":"..."}
        {"action":"HOME","reason":"..."}
        {"action":"RECENTS","reason":"..."}
        {"action":"NOTIFICATIONS","reason":"..."}
        {"action":"QUICK_SETTINGS","reason":"..."}
        {"action":"SCROLL_FORWARD","node":12,"reason":"..."}
        {"action":"SCROLL_BACKWARD","node":12,"reason":"..."}
        {"action":"LAUNCH_APP","app":"Settings","reason":"..."}
        {"action":"OPEN_SETTINGS","setting":"wifi","reason":"..."}
        {"action":"WAIT","milliseconds":700,"reason":"..."}
        {"action":"DONE","reason":"visible evidence shows the goal is complete"}
        {"action":"FAIL","reason":"why the goal cannot currently be completed"}

        Rules:
        - Take one action at a time, then observe the next snapshot.
        - Use node ids only when they exist in the current snapshot.
        - Prefer TAP_NODE over coordinates. Use coordinates only when a visible node has useful bounds but cannot be clicked normally.
        - Never invent success. Return DONE only when the current snapshot shows the requested state or the requested one-shot action has clearly completed.
        - If a text field is already focused, SET_TEXT may omit the node by using node=-1.
        - Avoid repeating an action that did not change the screen; choose another route or FAIL with a clear reason.
        - Do not ask the user questions from the planner. Use the available UI and settings.
    """.trimIndent()

    fun user(goal: String, snapshot: String, step: Int): String =
        "GOAL:\n" + goal + "\n\nSTEP:\n" + step + "\n\nCURRENT PHONE STATE:\n" + snapshot
}
