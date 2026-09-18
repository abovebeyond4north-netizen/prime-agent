package net.abovebeyond.codieai.automation

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.IBinder
import net.abovebeyond.codieai.MainActivity
import net.abovebeyond.codieai.agent.AgentRuntime

class ScheduledGoalService : Service() {
    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val taskId = intent?.getIntExtra(EXTRA_TASK_ID, -1) ?: -1
        val fallbackGoal = intent?.getStringExtra(EXTRA_GOAL).orEmpty().trim()
        val triggeredTask = if (taskId >= 0) AutomationScheduler.handleTrigger(this, taskId) else null
        val goal = triggeredTask?.goal ?: fallbackGoal

        if (taskId < 0 || goal.isBlank()) {
            stopSelf()
            return START_NOT_STICKY
        }

        startForeground(
            NOTIFICATION_ID_BASE + (taskId % 10_000),
            buildNotification("Running scheduled goal", goal)
        )

        AgentRuntime.executeGoal(this, goal) { message ->
            val terminal =
                message.startsWith("Reply: ") ||
                message.startsWith("Complete: ") ||
                message.startsWith("Stopped: ") ||
                message.startsWith("Stopped after ") ||
                message.startsWith("Step failed: ") ||
                message.startsWith("Planner setup failed: ") ||
                message == "Goal cancelled." ||
                message.startsWith("Enable Codie AI")

            if (terminal) {
                val repeatNote = if ((triggeredTask?.repeatMinutes ?: 0) > 0) {
                    " Recurs every " + triggeredTask!!.repeatMinutes + " minutes."
                } else ""

                val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
                manager.notify(
                    COMPLETION_NOTIFICATION_BASE + (taskId % 10_000),
                    buildNotification(
                        "Scheduled goal finished",
                        (message + repeatNote).take(700)
                    )
                )
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf(startId)
            }
        }

        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "Codie AI scheduled automation",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Runs user-scheduled and recurring Codie AI goals."
            }
        )
    }

    private fun buildNotification(title: String, text: String): Notification {
        val openIntent = PendingIntent.getActivity(
            this,
            1,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setContentIntent(openIntent)
            .setAutoCancel(true)
            .build()
    }

    companion object {
        const val EXTRA_TASK_ID = "scheduled_task_id"
        const val EXTRA_GOAL = "scheduled_goal"

        private const val CHANNEL_ID = "codie_ai_scheduled"
        private const val NOTIFICATION_ID_BASE = 31_000
        private const val COMPLETION_NOTIFICATION_BASE = 42_000
    }
}
