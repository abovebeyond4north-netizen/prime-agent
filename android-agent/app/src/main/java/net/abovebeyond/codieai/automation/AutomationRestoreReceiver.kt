package net.abovebeyond.codieai.automation

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import net.abovebeyond.codieai.agent.DurableTaskStore

class AutomationRestoreReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (
            action == Intent.ACTION_BOOT_COMPLETED ||
            action == Intent.ACTION_LOCKED_BOOT_COMPLETED ||
            action == Intent.ACTION_MY_PACKAGE_REPLACED ||
            action == "android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED"
        ) {
            runCatching { AutomationScheduler.restoreAll(context) }
            runCatching { DurableTaskStore.recoverRunning(context) }
        }
    }
}
