package net.abovebeyond.codieai.notifications

import java.util.concurrent.ConcurrentLinkedDeque

data class NotificationSummary(
    val packageName: String,
    val title: String,
    val text: String,
    val timestamp: Long
)

object NotificationStore {
    private const val MAX_ITEMS = 40
    private val items = ConcurrentLinkedDeque<NotificationSummary>()

    fun add(item: NotificationSummary) {
        items.addFirst(item)
        while (items.size > MAX_ITEMS) items.pollLast()
    }

    fun render(limit: Int = 12): String {
        val recent = items.take(limit)
        if (recent.isEmpty()) return "No notification summaries are available."
        return buildString {
            recent.forEachIndexed { index, item ->
                append("[notification=").append(index).append("]")
                    .append(" pkg=").append(clean(item.packageName))
                    .append(" title=").append(clean(item.title))
                    .append(" text=").append(clean(item.text))
                    .append('\n')
            }
        }
    }

    private fun clean(value: String): String =
        value.replace('\n', ' ').replace('\r', ' ').trim().take(500)
}
