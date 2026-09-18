package net.abovebeyond.codieai

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.speech.RecognizerIntent
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import net.abovebeyond.codieai.agent.AgentRuntime

class MainActivity : Activity() {
    private lateinit var endpointInput: EditText
    private lateinit var modelInput: EditText
    private lateinit var goalInput: EditText
    private lateinit var modelStatus: TextView
    private lateinit var statusView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 64)
        }

        root.addView(title("Codie AI"))
        root.addView(body(
            "Local-first Android agent. Accessibility performs phone actions; a local LiteRT model " +
                "or a GPT-OSS-compatible LAN endpoint plans multi-step tasks."
        ))

        root.addView(button("1. Enable phone control") {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        })

        root.addView(button("2. Enable notification context") {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        })

        root.addView(label("GPT-OSS / OpenAI-compatible endpoint (optional)"))
        endpointInput = edit(
            AgentRuntime.plannerEndpoint(this),
            "http://192.168.1.20:11434/v1/chat/completions"
        ).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        }
        root.addView(endpointInput)

        root.addView(label("Model name"))
        modelInput = edit(AgentRuntime.plannerModel(this), "gpt-oss-20b")
        root.addView(modelInput)

        root.addView(button("Save planner settings") {
            AgentRuntime.savePlannerSettings(
                this,
                endpointInput.text.toString(),
                modelInput.text.toString()
            )
            appendStatus("Planner settings saved.")
        })

        root.addView(label("Phone-only local model"))
        modelStatus = body(localModelDescription())
        root.addView(modelStatus)

        root.addView(button("Import .litertlm model") {
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "*/*"
            }
            startActivityForResult(intent, REQUEST_MODEL)
        })

        root.addView(body(
            "For this 8 GB phone, Gemma 3n E2B INT4 is the strongest practical phone-only target. " +
                "If a GPT-OSS endpoint is configured, Codie AI prefers it because GPT-OSS-20B needs more memory than the phone has."
        ))

        root.addView(label("Goal"))
        goalInput = edit("", "Open Settings and turn on Bluetooth")
        goalInput.minLines = 3
        root.addView(goalInput)

        val goalButtons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        goalButtons.addView(button("Run") {
            AgentRuntime.savePlannerSettings(
                this,
                endpointInput.text.toString(),
                modelInput.text.toString()
            )
            val goal = goalInput.text.toString()
            AgentRuntime.executeGoal(this, goal) { message ->
                runOnUiThread { appendStatus(message) }
            }
        }, weighted())
        goalButtons.addView(button("Voice") {
            startVoiceInput()
        }, weighted())
        goalButtons.addView(button("Stop") {
            AgentRuntime.cancelCurrentGoal()
            appendStatus("Cancellation requested.")
        }, weighted())
        root.addView(goalButtons)

        root.addView(label("Agent status"))
        statusView = body("")
        statusView.setTextIsSelectable(true)
        root.addView(statusView)

        root.addView(body(
            "Privacy note: accessibility snapshots and recent notification summaries stay on the phone " +
                "when using the local model. If you configure a LAN/HTTPS planner endpoint, those text summaries " +
                "are sent to that endpoint so the model can decide the next action."
        ))

        val scroll = ScrollView(this).apply { addView(root) }
        setContentView(scroll)
    }

    override fun onResume() {
        super.onResume()
        if (::statusView.isInitialized) {
            appendStatus(
                if (AgentRuntime.isServiceConnected()) "Accessibility service connected."
                else "Accessibility service is not connected."
            )
        }
    }

    @Deprecated("Uses the platform activity result API to avoid an AndroidX dependency.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK) return

        when (requestCode) {
            REQUEST_MODEL -> {
                val uri = data?.data ?: return
                importModel(uri)
            }
            REQUEST_VOICE -> {
                val text = data
                    ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    ?.firstOrNull()
                    .orEmpty()
                if (text.isNotBlank()) goalInput.setText(text)
            }
        }
    }

    private fun importModel(uri: android.net.Uri) {
        appendStatus("Copying local model into private app storage...")
        Thread {
            val destination = AgentRuntime.localModelFile(this)
            try {
                destination.parentFile?.mkdirs()
                contentResolver.openInputStream(uri).use { input ->
                    requireNotNull(input) { "Could not open selected model" }
                    destination.outputStream().buffered(1024 * 1024).use { output ->
                        input.copyTo(output, 1024 * 1024)
                    }
                }
                runOnUiThread {
                    modelStatus.text = localModelDescription()
                    appendStatus("Local model imported successfully.")
                }
            } catch (error: Throwable) {
                destination.delete()
                runOnUiThread {
                    appendStatus("Model import failed: " + (error.message ?: error.javaClass.simpleName))
                }
            }
        }.start()
    }

    private fun startVoiceInput() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Tell Codie AI what to do")
        }
        try {
            startActivityForResult(intent, REQUEST_VOICE)
        } catch (error: Throwable) {
            appendStatus("Voice recognition is unavailable: " + (error.message ?: error.javaClass.simpleName))
        }
    }

    private fun localModelDescription(): String {
        val file = AgentRuntime.localModelFile(this)
        return if (file.isFile) {
            "Installed: " + file.name + " (" + formatBytes(file.length()) + ")"
        } else {
            "No local model installed. Basic one-step commands still work without a model."
        }
    }

    private fun appendStatus(message: String) {
        if (!::statusView.isInitialized) return
        val current = statusView.text.toString()
        statusView.text = if (current.isBlank()) message else current + "\n" + message
    }

    private fun title(text: String): TextView = TextView(this).apply {
        this.text = text
        textSize = 28f
        setPadding(0, 8, 0, 24)
    }

    private fun label(text: String): TextView = TextView(this).apply {
        this.text = text
        textSize = 17f
        setPadding(0, 24, 0, 8)
    }

    private fun body(text: String): TextView = TextView(this).apply {
        this.text = text
        textSize = 15f
        setPadding(0, 8, 0, 16)
    }

    private fun edit(value: String, hintText: String): EditText = EditText(this).apply {
        setText(value)
        hint = hintText
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        )
    }

    private fun button(text: String, action: (View) -> Unit): Button = Button(this).apply {
        this.text = text
        setOnClickListener(action)
    }

    private fun weighted(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)

    private fun formatBytes(bytes: Long): String {
        val gib = bytes.toDouble() / (1024.0 * 1024.0 * 1024.0)
        return String.format("%.2f GiB", gib)
    }

    companion object {
        private const val REQUEST_MODEL = 42
        private const val REQUEST_VOICE = 43
    }
}
