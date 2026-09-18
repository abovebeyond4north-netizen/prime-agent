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

    private fun active(index: Int): Pair<NotificationSummary, StatusBarNotification>? {
        val summary = NotificationStore.get(index) ?: return null
        val sbn = activeNotifications.firstOrNull { it.key == summary.key } ?: return null
        return summary to sbn
    }

    private fun open(index: Int): Result<String> {
        val (summary, sbn) = active(index)
            ?: return Result.failure(IllegalArgumentException("Notification is no longer active"))
        val pending = sbn.notification.contentIntent
            ?: return Result.failure(IllegalStateException("Notification has no open action"))

        return runCatching {
            pending.send()
            "Opened notification from " + summary.title.ifBlank { summary.packageName }
        }
    }

    private fun dismiss(index: Int): Result<String> {
        val (summary, _) = active(index)
            ?: return Result.failure(IllegalArgumentException("Notification is no longer active"))

        return runCatching {
            cancelNotification(summary.key)
            NotificationStore.remove(summary.key)
            "Dismissed notification from " + summary.title.ifBlank { summary.packageName }
        }
    }

    private fun snooze(index: Int, durationMs: Long): Result<String> {
        val (summary, _) = active(index)
            ?: return Result.failure(IllegalArgumentException("Notification is no longer active"))
        val duration = durationMs.coerceIn(1_000L, 86_400_000L)

        return runCatching {
            snoozeNotification(summary.key, duration)
            "Snoozed notification for " + duration / 1000L + " seconds"
        }
    }

    private fun reply(index: Int, replyText: String): Result<String> {
        val (summary, sbn) = active(index)
            ?: return Result.failure(IllegalArgumentException("Notification is no longer active"))

        for (action in sbn.notification.actions.orEmpty()) {
            val remoteInputs = action.remoteInputs ?: continue
            if (remoteInputs.isEmpty()) continue

            val fillInIntent = Intent()
            val results = Bundle()
            remoteInputs.forEach { input ->
                results.putCharSequence(input.resultKey, replyText)
            }
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

        private fun service(): Result<NotificationBridgeService> {
            val value = instance?.get()
                ?: return Result.failure(
                    IllegalStateException("Notification access service is not connected")
                )
            return Result.success(value)
        }

        fun openNotification(index: Int): Result<String> =
            service().fold(
                onSuccess = { it.open(index) },
                onFailure = { Result.failure(it) }
            )

        fun dismissNotification(index: Int): Result<String> =
            service().fold(
                onSuccess = { it.dismiss(index) },
                onFailure = { Result.failure(it) }
            )

        fun snoozeNotification(index: Int, durationMs: Long): Result<String> =
            service().fold(
                onSuccess = { it.snooze(index, durationMs) },
                onFailure = { Result.failure(it) }
            )

        fun replyTo(index: Int, text: String): Result<String> =
            service().fold(
                onSuccess = { it.reply(index, text) },
                onFailure = { Result.failure(it) }
            )
    }
}
