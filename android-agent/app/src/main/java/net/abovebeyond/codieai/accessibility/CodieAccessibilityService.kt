package net.abovebeyond.codieai.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.provider.Settings
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import net.abovebeyond.codieai.agent.ActionType
import net.abovebeyond.codieai.agent.AgentAction
import net.abovebeyond.codieai.agent.AgentRuntime

data class ExecutionResult(val ok: Boolean, val message: String)

class CodieAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() {
        AgentRuntime.attachService(this)
    }

    override fun onDestroy() {
        AgentRuntime.detachService(this)
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    fun captureSnapshot(): UiSnapshot = UiSnapshotter.capture(rootInActiveWindow)

    fun execute(action: AgentAction, snapshot: UiSnapshot): ExecutionResult {
        return try {
            when (action.type) {
                ActionType.TAP_NODE -> tapNode(snapshot.nodes[action.nodeId])
                ActionType.TAP_COORDINATE -> tapCoordinate(action.x, action.y)
                ActionType.SET_TEXT -> setText(snapshot, action.nodeId, action.text)
                ActionType.BACK -> global(GLOBAL_ACTION_BACK, "Back")
                ActionType.HOME -> global(GLOBAL_ACTION_HOME, "Home")
                ActionType.RECENTS -> global(GLOBAL_ACTION_RECENTS, "Recents")
                ActionType.NOTIFICATIONS -> global(GLOBAL_ACTION_NOTIFICATIONS, "Notifications")
                ActionType.QUICK_SETTINGS -> global(GLOBAL_ACTION_QUICK_SETTINGS, "Quick settings")
                ActionType.SCROLL_FORWARD -> scroll(snapshot, action.nodeId, true)
                ActionType.SCROLL_BACKWARD -> scroll(snapshot, action.nodeId, false)
                ActionType.LAUNCH_APP -> launchApp(action.app)
                ActionType.OPEN_SETTINGS -> openSettings(action.setting)
                ActionType.WAIT -> {
                    Thread.sleep(action.milliseconds)
                    ExecutionResult(true, "Waited " + action.milliseconds + " ms")
                }
                ActionType.DONE -> ExecutionResult(true, "Done")
                ActionType.FAIL -> ExecutionResult(false, action.reason.ifBlank { "Planner reported failure" })
            }
        } catch (error: Throwable) {
            ExecutionResult(false, error.message ?: error.javaClass.simpleName)
        }
    }

    private fun tapNode(node: AccessibilityNodeInfo?): ExecutionResult {
        if (node == null) return ExecutionResult(false, "Target node is no longer available")
        if (node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
            return ExecutionResult(true, "Clicked accessibility node")
        }

        var parent = node.parent
        repeat(4) {
            val current = parent ?: return@repeat
            if (current.isClickable && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                return ExecutionResult(true, "Clicked clickable parent")
            }
            parent = current.parent
        }

        val bounds = Rect()
        node.getBoundsInScreen(bounds)
        if (!bounds.isEmpty) {
            return tapCoordinate(bounds.centerX(), bounds.centerY())
        }
        return ExecutionResult(false, "Node could not be clicked")
    }

    private fun tapCoordinate(x: Int, y: Int): ExecutionResult {
        if (x < 0 || y < 0) return ExecutionResult(false, "Invalid tap coordinates")
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 70))
            .build()
        val accepted = dispatchGesture(gesture, null, null)
        return ExecutionResult(accepted, if (accepted) "Gesture dispatched" else "Gesture was rejected")
    }

    private fun setText(snapshot: UiSnapshot, nodeId: Int, text: String): ExecutionResult {
        val node = if (nodeId >= 0) {
            snapshot.nodes[nodeId]
        } else {
            snapshot.nodes.values.firstOrNull { it.isEditable && it.isFocused }
                ?: snapshot.nodes.values.firstOrNull { it.isEditable }
        } ?: return ExecutionResult(false, "No editable node is available")

        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        val ok = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        return ExecutionResult(ok, if (ok) "Text entered" else "Text entry failed")
    }

    private fun scroll(snapshot: UiSnapshot, nodeId: Int, forward: Boolean): ExecutionResult {
        val node = (
            if (nodeId >= 0) snapshot.nodes[nodeId]
            else snapshot.nodes.values.firstOrNull { it.isScrollable }
        ) ?: return ExecutionResult(false, "No scrollable node is available")

        val action = if (forward) {
            AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        } else {
            AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        }
        val ok = node.performAction(action)
        return ExecutionResult(ok, if (ok) "Scrolled" else "Scroll action failed")
    }

    private fun global(action: Int, label: String): ExecutionResult {
        val ok = performGlobalAction(action)
        return ExecutionResult(ok, if (ok) label + " action sent" else label + " action failed")
    }

    private fun launchApp(requestedName: String): ExecutionResult {
        val name = requestedName.trim()
        if (name.isEmpty()) return ExecutionResult(false, "App name is blank")

        val query = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val candidates = packageManager.queryIntentActivities(query, 0)
        val exact = candidates.firstOrNull {
            it.loadLabel(packageManager).toString().equals(name, ignoreCase = true)
        }
        val partial = candidates.firstOrNull {
            it.loadLabel(packageManager).toString().contains(name, ignoreCase = true)
        }
        val match = exact ?: partial ?: return ExecutionResult(false, "No launcher app matched '" + name + "'")
        val packageName = match.activityInfo.packageName
        val intent = packageManager.getLaunchIntentForPackage(packageName)
            ?: return ExecutionResult(false, "App has no launch intent")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        return ExecutionResult(true, "Launched " + match.loadLabel(packageManager))
    }

    private fun openSettings(setting: String): ExecutionResult {
        val action = when (setting.trim().lowercase()) {
            "wifi", "wi-fi" -> Settings.ACTION_WIFI_SETTINGS
            "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
            "accessibility" -> Settings.ACTION_ACCESSIBILITY_SETTINGS
            "notification_access", "notifications" -> Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS
            "apps" -> Settings.ACTION_APPLICATION_SETTINGS
            else -> Settings.ACTION_SETTINGS
        }
        startActivity(Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        return ExecutionResult(true, "Opened settings: " + setting)
    }
}
