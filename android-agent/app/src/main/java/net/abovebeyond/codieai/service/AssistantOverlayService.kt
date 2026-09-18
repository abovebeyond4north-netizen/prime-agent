package net.abovebeyond.codieai.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.IBinder
import android.provider.Settings
import android.view.Gravity
import android.view.WindowManager
import android.widget.TextView
import net.abovebeyond.codieai.MainActivity

class AssistantOverlayService : Service() {
    private var bubble: TextView? = null
    private var windowManager: WindowManager? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        if (Settings.canDrawOverlays(this)) showBubble()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (Settings.canDrawOverlays(this) && bubble == null) showBubble()
        return START_STICKY
    }

    override fun onDestroy() {
        bubble?.let { view ->
            runCatching { windowManager?.removeView(view) }
        }
        bubble = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun showBubble() {
        val wm = getSystemService(WINDOW_SERVICE) as WindowManager
        windowManager = wm

        val view = TextView(this).apply {
            text = "AI"
            textSize = 17f
            gravity = Gravity.CENTER
            setPadding(28, 18, 28, 18)
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(0xDD222222.toInt())
            }
            setTextColor(0xFFFFFFFF.toInt())
            setOnClickListener { openAssistant(true) }
            setOnLongClickListener {
                stopSelf()
                true
            }
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.END
            x = 24
            y = 180
        }

        wm.addView(view, params)
        bubble = view
    }

    private fun openAssistant(startVoice: Boolean) {
        startActivity(
            Intent(this, MainActivity::class.java)
                .putExtra(MainActivity.EXTRA_START_VOICE, startVoice)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        )
    }

    private fun createChannel() {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Codie AI assistant",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Keeps the floating Codie AI assistant available."
        }
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val openIntent = PendingIntent.getActivity(
            this,
            1,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val stopIntent = PendingIntent.getService(
            this,
            2,
            Intent(this, AssistantOverlayService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Codie AI is ready")
            .setContentText("Tap the floating AI bubble to speak a command.")
            .setContentIntent(openIntent)
            .setOngoing(true)
            .addAction(
                Notification.Action.Builder(
                    android.R.drawable.ic_menu_close_clear_cancel,
                    "Stop",
                    stopIntent
                ).build()
            )
            .build()
    }

    companion object {
        private const val CHANNEL_ID = "codie_ai_assistant"
        private const val NOTIFICATION_ID = 2101
        private const val ACTION_STOP = "net.abovebeyond.codieai.STOP_OVERLAY"
    }
}
