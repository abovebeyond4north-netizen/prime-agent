package net.abovebeyond.codieai.bounty

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class BountyActivity : Activity() {
    private lateinit var root: LinearLayout
    private var scanning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 28, 28, 48)
        }
        setContentView(ScrollView(this).apply { addView(root) })
        render()
    }

    override fun onResume() {
        super.onResume()
        if (::root.isInitialized) render()
    }

    private fun text(value: String, size: Float = 16f) {
        root.addView(TextView(this).apply {
            text = value
            textSize = size
            setTextIsSelectable(true)
            setPadding(0, 14, 0, 12)
        })
    }

    private fun button(label: String, action: () -> Unit) {
        root.addView(Button(this).apply {
            text = label
            setOnClickListener { action() }
        })
    }

    private fun render() {
        root.removeAllViews()
        text("Codie Bounty Bot", 28f)
        text("Autonomous discovery and work-plan preparation. Payments are not connected. No earnings have been verified.")
        val enabled = BountyJobService.enabled(this)
        text(if (enabled) "Scheduled: about every 6 hours on unmetered internet, battery permitting. Android may delay scans."
            else "Background discovery is off.")
        button(if (enabled) "Stop background discovery" else "Start background discovery") {
            if (enabled) BountyJobService.disable(this)
            else if (!BountyJobService.enable(this)) {
                AlertDialog.Builder(this).setMessage("Android could not schedule discovery.")
                    .setPositiveButton("OK", null).show()
            }
            render()
        }
        button(if (scanning) "Scanning..." else "Scan now (uses current internet)") {
            if (!scanning) {
                scanning = true
                render()
                val app = applicationContext
                Thread {
                    BountyStore.scan(app)
                    runOnUiThread {
                        scanning = false
                        if (!isFinishing && !isDestroyed) render()
                    }
                }.start()
            }
        }
        text(BountyStore.status(this))
        text("Manual scans are limited to one per 15 minutes. Next eligible: ${BountyStore.formatTime(BountyStore.nextScan(this))}")
        val snapshot = BountyStore.snapshot(this)
        text("Last successful scan: ${BountyStore.formatTime(snapshot.optLong("scanned_at"))}")
        val items = snapshot.optJSONArray("items")
        text("Newest ${items?.length() ?: 0} cached candidates from ${snapshot.optInt("total_matches")} search matches. " +
            "Query: ${BountyStore.QUERY}. " + if (snapshot.optBoolean("incomplete")) "GitHub reported incomplete results." else "")
        text("Priority scores favor unassigned work, amount mentions, reproduction details, tests, and Python/Kotlin/TypeScript. Scores are triage heuristics, not profit forecasts. Amounts may refer to other payments.")
        if (items == null || items.length() == 0) text("No cached opportunities. Run a scan to discover candidates.")
        for (index in 0 until (items?.length() ?: 0)) {
            val issue = items!!.getJSONObject(index)
            text(issue.getString("title"), 20f)
            text("Priority ${issue.getInt("score")}/100 · ${issue.getString("amount")} (unverified)" +
                "\nAssigned: ${issue.getBoolean("assigned")} · Updated: ${issue.getString("updated")}")
            button("Open bounty and current terms") {
                val url = issue.getString("url")
                if (BountyPolicy.validIssueUrl(url)) {
                    runCatching { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
                        .onFailure { AlertDialog.Builder(this).setMessage("No browser available.").setPositiveButton("OK", null).show() }
                }
            }
            button("View prepared work plan") {
                val plan = BountyStore.workPlan(issue)
                val view = TextView(this).apply {
                    text = plan
                    setTextIsSelectable(true)
                    setPadding(24, 16, 24, 16)
                }
                AlertDialog.Builder(this).setTitle("Work plan")
                    .setView(ScrollView(this).apply { addView(view) })
                    .setPositiveButton("Close", null)
                    .setNeutralButton("Copy plan") { _, _ ->
                        getSystemService(ClipboardManager::class.java)
                            .setPrimaryClip(ClipData.newPlainText("Bounty work plan", plan))
                    }.show()
            }
        }
    }
}
