package net.abovebeyond.codieai.notifications

import android.app.Notification
import android.app.RemoteInput
import android.content.Intent
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import java.lang.ref.WeakReference

class NotificationBridgeService : NotificationListenerService() {
    override fun onListenerConnected() {
        instance = WeakReference(this)
    }

    override fun onListenerDisconnected() {
        if (instance?.get() === this) instance = null
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        val notification = sbn?.notification ?: return
        val extras = notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        if (title.isBlank() && text.isBlank()) return

        NotificationStore.add(
            NotificationSummary(
                key = sbn.key,
                packageName = sbn.packageName.orEmpty(),
                title = title,
                text = text,
                timestamp = sbn.postTime
            )
        )
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        sbn?.key?.let(NotificationStore::remove)
    }

    private fun reply(index: Int, replyText: String): Result<String> {
        val summary = NotificationStore.get(index)
            ?: return Result.failure(IllegalArgumentException("Notification index is no longer available"))

        val sbn = activeNotifications.firstOrNull { it.key == summary.key }
            ?: return Result.failure(IllegalStateException("Notification is no longer active"))

        for (action in sbn.notification.actions.orEmpty()) {
            val remoteInputs = action.remoteInputs ?: continue
            if (remoteInputs.isEmpty()) continue

            val fillInIntent = Intent()
            val results = Bundle()
            remoteInputs.forEach { input -> results.putCharSequence(input.resultKey, replyText) }
            RemoteInput.addResultsToIntent(remoteInputs, fillInIntent, results)

            return try {
                action.actionIntent.send(this, 0, fillInIntent)
                Result.success("Reply sent to " + summary.title.ifBlank { summary.packageName })
            } catch (error: Throwable) {
                Result.failure(error)
            }
        }

        return Result.failure(IllegalStateException("This notification has no inline reply action"))
    }

    companion object {
        @Volatile
        private var instance: WeakReference<NotificationBridgeService>? = null

        fun replyTo(index: Int, text: String): Result<String> {
            val service = instance?.get()
                ?: return Result.failure(IllegalStateException("Notification access service is not connected"))
            return service.reply(index, text)
        }
    }
}
