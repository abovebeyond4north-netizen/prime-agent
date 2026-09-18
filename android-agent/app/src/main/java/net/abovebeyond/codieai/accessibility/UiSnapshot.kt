package net.abovebeyond.codieai.accessibility

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo
import java.util.ArrayDeque
import java.util.LinkedHashMap

data class UiSnapshot(
    val text: String,
    val nodes: Map<Int, AccessibilityNodeInfo>
) : AutoCloseable {
    override fun close() {
        nodes.values.forEach { node ->
            try {
                node.recycle()
            } catch (_: Throwable) {
            }
        }
    }
}

object UiSnapshotter {
    fun capture(root: AccessibilityNodeInfo?, maxNodes: Int = 220, maxChars: Int = 18_000): UiSnapshot {
        if (root == null) {
            return UiSnapshot("No active accessibility window is available.", emptyMap())
        }

        val nodes = LinkedHashMap<Int, AccessibilityNodeInfo>()
        val output = StringBuilder()
        val queue = ArrayDeque<Pair<AccessibilityNodeInfo, Int>>()
        queue.add(AccessibilityNodeInfo.obtain(root) to 0)
        var nextId = 0

        while (queue.isNotEmpty() && nextId < maxNodes && output.length < maxChars) {
            val (node, depth) = queue.removeFirst()
            val id = nextId++
            nodes[id] = AccessibilityNodeInfo.obtain(node)

            val bounds = Rect()
            node.getBoundsInScreen(bounds)
            val flags = buildString {
                if (node.isClickable) append(" clickable")
                if (node.isEditable) append(" editable")
                if (node.isScrollable) append(" scrollable")
                if (node.isFocused) append(" focused")
                if (node.isCheckable) append(" checkable")
                if (node.isChecked) append(" checked")
                if (!node.isEnabled) append(" disabled")
            }.trim()

            val className = node.className?.toString()?.substringAfterLast('.').orEmpty()
            val text = clean(node.text?.toString())
            val description = clean(node.contentDescription?.toString())
            val viewId = clean(node.viewIdResourceName)
            val packageName = clean(node.packageName?.toString())

            output.append("[id=").append(id).append("]")
                .append(" depth=").append(depth)
                .append(" class=").append(className)
                .append(" bounds=").append(bounds.flattenToString())
            if (text.isNotEmpty()) output.append(" text=").append(JSONObjectEscaper.quote(text))
            if (description.isNotEmpty()) output.append(" desc=").append(JSONObjectEscaper.quote(description))
            if (viewId.isNotEmpty()) output.append(" viewId=").append(viewId)
            if (packageName.isNotEmpty()) output.append(" pkg=").append(packageName)
            if (flags.isNotEmpty()) output.append(" flags=").append(flags)
            output.append('\n')

            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { child -> queue.add(child to depth + 1) }
            }
            try {
                node.recycle()
            } catch (_: Throwable) {
            }
        }

        return UiSnapshot(output.toString(), nodes)
    }

    private fun clean(value: String?): String =
        value.orEmpty()
            .replace('\n', ' ')
            .replace('\r', ' ')
            .trim()
            .take(300)
}

private object JSONObjectEscaper {
    fun quote(value: String): String =
        """ + value
            .replace("\\", "\\\\")
            .replace(""", "\\"") + """
}
