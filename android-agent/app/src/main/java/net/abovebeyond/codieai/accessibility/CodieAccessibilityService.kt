package net.abovebeyond.codieai.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.app.AlarmManager
import android.app.SearchManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Path
import android.graphics.Rect
import android.media.AudioManager
import android.net.Uri
import android.os.Bundle
import android.provider.AlarmClock
import android.provider.Settings
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import net.abovebeyond.codieai.agent.ActionType
import net.abovebeyond.codieai.agent.AgentAction
import net.abovebeyond.codieai.agent.AgentRuntime
import net.abovebeyond.codieai.notifications.NotificationBridgeService

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
                ActionType.OPEN_URL -> openUrl(action.url)
                ActionType.WEB_SEARCH -> webSearch(action.query)
                ActionType.SET_CLIPBOARD -> setClipboard(action.text)
                ActionType.SHARE_TEXT -> shareText(action.text)
                ActionType.DIAL -> dial(action.number)
                ActionType.COMPOSE_SMS -> composeSms(action.number, action.text)
                ActionType.COMPOSE_EMAIL -> composeEmail(action.number, action.subject, action.text)
                ActionType.SET_ALARM -> setAlarm(action.hour, action.minute)
                ActionType.SET_TIMER -> setTimer(action.seconds)
                ActionType.MEDIA_PLAY_PAUSE -> mediaKey(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, "Play/pause")
                ActionType.MEDIA_NEXT -> mediaKey(KeyEvent.KEYCODE_MEDIA_NEXT, "Next track")
                ActionType.MEDIA_PREVIOUS -> mediaKey(KeyEvent.KEYCODE_MEDIA_PREVIOUS, "Previous track")
                ActionType.VOLUME_UP -> adjustVolume(AudioManager.ADJUST_RAISE, "Volume up")
                ActionType.VOLUME_DOWN -> adjustVolume(AudioManager.ADJUST_LOWER, "Volume down")
                ActionType.VOLUME_MUTE -> adjustVolume(AudioManager.ADJUST_TOGGLE_MUTE, "Mute toggled")
                ActionType.REPLY_NOTIFICATION -> replyNotification(action.notificationIndex, action.text)
                ActionType.WAIT -> {
                    Thread.sleep(action.milliseconds)
                    ExecutionResult(true, "Waited " + action.milliseconds + " ms")
                }
                ActionType.RESPOND -> ExecutionResult(true, action.text.ifBlank { action.reason })
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

        val action = if (forward) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
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
            "display" -> Settings.ACTION_DISPLAY_SETTINGS
            "sound", "volume" -> Settings.ACTION_SOUND_SETTINGS
            "battery" -> Settings.ACTION_BATTERY_SAVER_SETTINGS
            "location" -> Settings.ACTION_LOCATION_SOURCE_SETTINGS
            "privacy" -> Settings.ACTION_PRIVACY_SETTINGS
            else -> Settings.ACTION_SETTINGS
        }
        startActivity(Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        return ExecutionResult(true, "Opened settings: " + setting)
    }

    private fun openUrl(raw: String): ExecutionResult {
        val trimmed = raw.trim()
        if (trimmed.isEmpty()) return ExecutionResult(false, "URL is blank")
        val normalized = if (trimmed.contains("://")) trimmed else "https://" + trimmed
        startActivity(
            Intent(Intent.ACTION_VIEW, Uri.parse(normalized))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
        return ExecutionResult(true, "Opened " + normalized)
    }

    private fun webSearch(query: String): ExecutionResult {
        if (query.isBlank()) return ExecutionResult(false, "Search query is blank")
        val intent = Intent(SearchManager.INTENT_ACTION_WEB_SEARCH)
            .putExtra(SearchManager.QUERY, query)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        return ExecutionResult(true, "Started web search for " + query)
    }

    private fun setClipboard(text: String): ExecutionResult {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("Codie AI", text))
        return ExecutionResult(true, "Copied text to clipboard")
    }

    private fun shareText(text: String): ExecutionResult {
        val send = Intent(Intent.ACTION_SEND)
            .setType("text/plain")
            .putExtra(Intent.EXTRA_TEXT, text)
        val chooser = Intent.createChooser(send, "Share with")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(chooser)
        return ExecutionResult(true, "Opened Android share sheet")
    }

    private fun dial(number: String): ExecutionResult {
        if (number.isBlank()) return ExecutionResult(false, "Phone number is blank")
        startActivity(
            Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(number)))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
        return ExecutionResult(true, "Opened dialer for " + number)
    }

    private fun composeSms(number: String, text: String): ExecutionResult {
        val uri = if (number.isBlank()) Uri.parse("smsto:") else Uri.parse("smsto:" + Uri.encode(number))
        val intent = Intent(Intent.ACTION_SENDTO, uri)
            .putExtra("sms_body", text)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        return ExecutionResult(true, "Opened message composer")
    }

    private fun composeEmail(address: String, subject: String, text: String): ExecutionResult {
        val uri = if (address.isBlank()) Uri.parse("mailto:") else Uri.parse("mailto:" + Uri.encode(address))
        val intent = Intent(Intent.ACTION_SENDTO, uri)
            .putExtra(Intent.EXTRA_SUBJECT, subject)
            .putExtra(Intent.EXTRA_TEXT, text)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        return ExecutionResult(true, "Opened email composer")
    }

    private fun setAlarm(hour: Int, minute: Int): ExecutionResult {
        if (hour !in 0..23 || minute !in 0..59) {
            return ExecutionResult(false, "Alarm time must be valid hour/minute values")
        }
        val intent = Intent(AlarmClock.ACTION_SET_ALARM)
            .putExtra(AlarmClock.EXTRA_HOUR, hour)
            .putExtra(AlarmClock.EXTRA_MINUTES, minute)
            .putExtra(AlarmClock.EXTRA_SKIP_UI, false)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        return ExecutionResult(true, "Opened alarm setup for " + hour + ":" + minute.toString().padStart(2, '0'))
    }

    private fun setTimer(seconds: Int): ExecutionResult {
        if (seconds <= 0) return ExecutionResult(false, "Timer duration must be positive")
        val intent = Intent(AlarmClock.ACTION_SET_TIMER)
            .putExtra(AlarmClock.EXTRA_LENGTH, seconds)
            .putExtra(AlarmClock.EXTRA_SKIP_UI, false)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        return ExecutionResult(true, "Opened timer for " + seconds + " seconds")
    }

    private fun mediaKey(keyCode: Int, label: String): ExecutionResult {
        val audio = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, keyCode))
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, keyCode))
        return ExecutionResult(true, label + " media command sent")
    }

    private fun adjustVolume(direction: Int, label: String): ExecutionResult {
        val audio = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, direction, AudioManager.FLAG_SHOW_UI)
        return ExecutionResult(true, label)
    }

    private fun replyNotification(index: Int, text: String): ExecutionResult {
        if (text.isBlank()) return ExecutionResult(false, "Reply text is blank")
        val result = NotificationBridgeService.replyTo(index, text)
        return result.fold(
            onSuccess = { ExecutionResult(true, it) },
            onFailure = { ExecutionResult(false, it.message ?: "Notification reply failed") }
        )
    }
}
