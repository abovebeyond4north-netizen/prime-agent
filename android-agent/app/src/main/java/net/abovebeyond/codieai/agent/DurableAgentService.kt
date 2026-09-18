package net.abovebeyond.codieai.agent

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import net.abovebeyond.codieai.MainActivity
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

class DurableAgentService : Service() {
    private val worker = Executors.newSingleThreadExecutor()
    private val processing = AtomicBoolean(false)

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(
            NOTIFICATION_ID,
            buildNotification("Durable agent queue", "Checking queued tasks…")
        )
        processQueue(startId)
        return START_STICKY
    }

    override fun onDestroy() {
        worker.shutdownNow()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun processQueue(startId: Int) {
        if (!processing.compareAndSet(false, true)) return

        worker.execute {
            try {
                while (!Thread.currentThread().isInterrupted) {
                    val next = DurableTaskStore.next(this) ?: break
                    val task = DurableTaskStore.markRunning(this, next.id)
                    currentTaskId.set(task.id)

                    updateNotification(
                        "Running durable task #" + task.id,
                        task.goal.take(220)
                    )

                    val terminal = arrayOfNulls<String>(1)
                    val latch = CountDownLatch(1)

                    AgentRuntime.executeGoal(this, task.goal) { message ->
                        DurableTaskStore.updateMessage(this, task.id, message)
                        updateNotification(
                            "Durable task #" + task.id,
                            message.take(220)
                        )

                        if (isTerminal(message)) {
                            terminal[0] = message
                            latch.countDown()
                        }
                    }

                    val completed = latch.await(35, TimeUnit.MINUTES)
                    currentTaskId.compareAndSet(task.id, -1)

                    if (!completed) {
                        AgentRuntime.cancelCurrentGoal()
                        DurableTaskStore.finish(
                            this,
                            task.id,
                            success = false,
                            message = "Durable task timed out after 35 minutes."
                        )
                        continue
                    }

                    if (DurableTaskStore.find(this, task.id)?.state == "cancelled") {
                        continue
                    }

                    val finalMessage = terminal[0].orEmpty()
                    val success =
                        finalMessage.startsWith("Reply: ") ||
                        finalMessage.startsWith("Complete: ")

                    DurableTaskStore.finish(
                        this,
                        task.id,
                        success = success,
                        message = finalMessage.ifBlank { "Task ended without a final message." }
                    )
                }
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
            } finally {
                currentTaskId.set(-1)
                processing.set(false)
                if (DurableTaskStore.next(this) == null) {
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf(startId)
                }
            }
        }
    }

    private fun isTerminal(message: String): Boolean =
        message.startsWith("Reply: ") ||
            message.startsWith("Complete: ") ||
            message.startsWith("Stopped: ") ||
            message.startsWith("Stopped after ") ||
            message.startsWith("Step failed: ") ||
            message.startsWith("Planner setup failed: ") ||
            message == "Goal cancelled." ||
            message.startsWith("Enable Codie AI")

    private fun createChannel() {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "Codie AI durable agent",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Runs user-created persistent Codie AI tasks."
            }
        )
    }

    private fun updateNotification(title: String, text: String) {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, buildNotification(title, text))
    }

    private fun buildNotification(title: String, text: String): Notification {
        val openIntent = PendingIntent.getActivity(
            this,
            91,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_popup_sync)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setOngoing(true)
            .setContentIntent(openIntent)
            .build()
    }

    companion object {
        private const val CHANNEL_ID = "codie_ai_durable_agent"
        private const val NOTIFICATION_ID = 57_001
        private val currentTaskId = AtomicInteger(-1)

        fun enqueueAndStart(context: Context, goal: String): Pair<DurableTask, Boolean> {
            val task = DurableTaskStore.enqueue(context, goal)
            return task to startIfPending(context)
        }

        fun startIfPending(context: Context): Boolean {
            if (DurableTaskStore.next(context) == null) return false

            return runCatching {
                context.startForegroundService(
                    Intent(context, DurableAgentService::class.java)
                )
                true
            }.getOrElse { false }
        }

        fun cancelTask(context: Context, id: Int): String {
            val message = DurableTaskStore.cancel(context, id)
            if (currentTaskId.get() == id) {
                AgentRuntime.cancelCurrentGoal()
            }
            return message
        }
    }
}
