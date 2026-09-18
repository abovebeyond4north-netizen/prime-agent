package net.abovebeyond.codieai.tools

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.BatteryManager
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

object DeviceTools {
    fun clipboardRead(context: Context): String {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = clipboard.primaryClip
            ?: return "Clipboard is empty or Android does not allow clipboard access in the current context."
        if (clip.itemCount == 0) return "Clipboard is empty."

        return buildString {
            append("Clipboard:")
            for (i in 0 until clip.itemCount.coerceAtMost(10)) {
                val value = clip.getItemAt(i).coerceToText(context)?.toString().orEmpty()
                if (value.isNotBlank()) append("\n").append(value.take(4_000))
            }
        }.take(8_000)
    }

    fun clipboardWrite(context: Context, text: String): String {
        require(text.isNotBlank()) { "Clipboard text is blank" }
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("Codie AI", text))
        return "Copied " + text.length + " characters to the clipboard."
    }

    fun sensorReport(context: Context): String {
        val manager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val wanted = listOf(
            Sensor.TYPE_ACCELEROMETER to "accelerometer",
            Sensor.TYPE_GYROSCOPE to "gyroscope",
            Sensor.TYPE_LIGHT to "ambient_light",
            Sensor.TYPE_PROXIMITY to "proximity",
            Sensor.TYPE_PRESSURE to "pressure",
            Sensor.TYPE_MAGNETIC_FIELD to "magnetic_field"
        )

        val reports = ArrayList<String>()
        wanted.forEach { (type, label) ->
            sample(manager, type)?.let { values ->
                reports.add(label + "=" + values.joinToString(",") { format(it) })
            }
        }

        val battery = context.registerReceiver(
            null,
            IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        )
        val batteryTempTenths = battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE)
        if (batteryTempTenths != null && batteryTempTenths != Int.MIN_VALUE) {
            reports.add("battery_temp_c=" + format(batteryTempTenths / 10f))
        }

        return if (reports.isEmpty()) {
            "No supported sensor samples were available."
        } else {
            "Device sensor snapshot:\n" + reports.joinToString("\n")
        }
    }

    private fun sample(manager: SensorManager, type: Int): FloatArray? {
        val sensor = manager.getDefaultSensor(type) ?: return null
        val latch = CountDownLatch(1)
        val result = AtomicReference<FloatArray?>()

        val listener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                result.set(event.values.copyOf())
                latch.countDown()
            }

            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
        }

        manager.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        try {
            latch.await(900, TimeUnit.MILLISECONDS)
        } finally {
            manager.unregisterListener(listener)
        }
        return result.get()
    }

    private fun format(value: Float): String =
        String.format(java.util.Locale.US, "%.3f", value)
}
