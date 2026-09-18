package net.abovebeyond.codieai.bounty

import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context

class BountyJobService : JobService() {
    private var worker: Thread? = null

    override fun onStartJob(params: JobParameters): Boolean {
        worker = Thread {
            val success = BountyStore.scan(applicationContext)
            if (!Thread.currentThread().isInterrupted) jobFinished(params, !success)
        }.also { it.start() }
        return true
    }

    override fun onStopJob(params: JobParameters): Boolean {
        worker?.interrupt()
        return true
    }

    companion object {
        private const val JOB_ID = 5050
        private fun scheduler(context: Context) = context.getSystemService(JobScheduler::class.java)

        fun enabled(context: Context): Boolean = scheduler(context).getPendingJob(JOB_ID) != null

        fun enable(context: Context): Boolean = scheduler(context).schedule(
            JobInfo.Builder(JOB_ID, ComponentName(context, BountyJobService::class.java))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED)
                .setRequiresBatteryNotLow(true)
                .setPeriodic(6 * 60 * 60 * 1000L)
                .setPersisted(true)
                .build()
        ) == JobScheduler.RESULT_SUCCESS

        fun disable(context: Context) = scheduler(context).cancel(JOB_ID)
    }
}
