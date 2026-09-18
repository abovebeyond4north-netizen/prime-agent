package net.abovebeyond.codieai.tools

import android.app.AppOpsManager
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Process

object UsageTools {
    fun report(context: Context, hours: Int = 24): Result<String> {
        if (!hasAccess(context)) {
            return Result.failure(
                SecurityException("Usage access is required. Use 'Allow app usage access' in Codie AI.")
            )
        }

        val boundedHours = hours.coerceIn(1, 24 * 30)
        val end = System.currentTimeMillis()
        val start = end - boundedHours * 60L * 60L * 1000L
        val manager = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val stats = manager.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY,
            start,
            end
        ).orEmpty()
            .filter { it.totalTimeInForeground > 0L }
            .sortedByDescending { it.totalTimeInForeground }
            .take(10)

        if (stats.isEmpty()) {
            return Result.success("No foreground app usage was recorded in the last " + boundedHours + " hours.")
        }

        val report = buildString {
            append("Top app usage in the last ").append(boundedHours).append(" hours:")
            stats.forEachIndexed { index, item ->
                val label = runCatching {
                    val info = context.packageManager.getApplicationInfo(item.packageName, 0)
                    context.packageManager.getApplicationLabel(info).toString()
                }.getOrElse { item.packageName }

                val minutes = item.totalTimeInForeground / 60_000L
                append("\n").append(index + 1).append(". ")
                    .append(label).append(": ").append(minutes).append(" min")
            }
        }

        return Result.success(report)
    }

    fun hasAccess(context: Context): Boolean {
        val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = appOps.unsafeCheckOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            context.packageName
        )
        return mode == AppOpsManager.MODE_ALLOWED
    }
}
