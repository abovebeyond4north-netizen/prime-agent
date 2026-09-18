package net.abovebeyond.codieai

import android.Manifest
import android.app.Activity
import android.app.AlarmManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.StatFs
import android.provider.Settings
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import net.abovebeyond.codieai.agent.AgentRuntime
import net.abovebeyond.codieai.automation.AutomationScheduler
import net.abovebeyond.codieai.service.AssistantOverlayService
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

class MainActivity : Activity() {
    private lateinit var endpointInput: EditText
    private lateinit var modelInput: EditText
    private lateinit var goalInput: EditText
    private lateinit var modelStatus: TextView
    private lateinit var chatView: TextView
    private lateinit var statusView: TextView
    private lateinit var speakRepliesToggle: CheckBox
    private lateinit var autoRunVoiceToggle: CheckBox

    private val handler = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var speechRecognizer: SpeechRecognizer? = null
    private var handsFreeEnabled = false
    private var awaitingAgent = false
    private var pendingHandsFreePermission = false
    private var lastAssistantReply = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        initializeSpeech()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 64)
        }

        root.addView(title("Codie AI"))
        root.addView(body(
            "Local-first Android assistant with phone control, spoken replies, persistent chat memory, " +
                "hands-free conversation, a floating assistant bubble, LiteRT reasoning, and optional GPT-OSS."
        ))

        root.addView(label("Conversation"))
        chatView = body("")
        chatView.setTextIsSelectable(true)
        root.addView(chatView)
        renderConversation()

        val conversationButtons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        conversationButtons.addView(button("Clear chat") {
            AgentRuntime.clearConversation(this)
            lastAssistantReply = ""
            renderConversation()
            appendStatus("Conversation history cleared.")
        }, weighted())
        conversationButtons.addView(button("Repeat reply") {
            if (lastAssistantReply.isNotBlank()) speak(lastAssistantReply)
            else appendStatus("There is no assistant reply to repeat yet.")
        }, weighted())
        conversationButtons.addView(button("Stop speech") {
            tts?.stop()
        }, weighted())
        root.addView(conversationButtons)

        speakRepliesToggle = CheckBox(this).apply {
            text = "Speak replies and final results"
            isChecked = true
        }
        root.addView(speakRepliesToggle)

        autoRunVoiceToggle = CheckBox(this).apply {
            text = "Run one-shot voice commands immediately"
            isChecked = true
        }
        root.addView(autoRunVoiceToggle)

        val handsFreeButtons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        handsFreeButtons.addView(button("Start hands-free") {
            startHandsFreeMode()
        }, weighted())
        handsFreeButtons.addView(button("Stop hands-free") {
            stopHandsFreeMode()
        }, weighted())
        root.addView(handsFreeButtons)

        root.addView(body(
            "Hands-free mode listens for one command, runs it, speaks the result, then listens again. " +
                "It remains active while Codie AI is running and can be stopped at any time."
        ))

        root.addView(label("Android control permissions"))
        root.addView(button("1. Enable phone control") {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        })
        root.addView(button("2. Enable notification context/replies") {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        })
        root.addView(button("3. Grant microphone + camera") {
            requestAssistantRuntimePermissions()
        })
        root.addView(button("4. Allow modify system settings") {
            startActivity(
                Intent(
                    Settings.ACTION_MANAGE_WRITE_SETTINGS,
                    Uri.parse("package:" + packageName)
                )
            )
        })
        root.addView(button("5. Allow Do Not Disturb control") {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS))
        })
        root.addView(button("6. Allow contact lookup") {
            requestContactPermission()
        })
        root.addView(button("7. Allow app usage access") {
            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
        })
        root.addView(button("8. Allow scheduled automation") {
            requestExactAlarmAccess()
        })

        val automationButtons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        automationButtons.addView(button("Show scheduled goals") {
            appendStatus(AutomationScheduler.render(this))
        }, weighted())
        automationButtons.addView(button("Open alarm access") {
            requestExactAlarmAccess()
        }, weighted())
        root.addView(automationButtons)

        val bubbleButtons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        bubbleButtons.addView(button("Start AI bubble") {
            startAssistantBubble()
        }, weighted())
        bubbleButtons.addView(button("Stop AI bubble") {
            stopService(Intent(this, AssistantOverlayService::class.java))
            appendStatus("Floating assistant stopped.")
        }, weighted())
        root.addView(bubbleButtons)

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

        root.addView(button("Download recommended Gemma 4 E2B (~2.6 GB)") {
            downloadRecommendedModel()
        })

        root.addView(button("Import another .litertlm model") {
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "*/*"
            }
            startActivityForResult(intent, REQUEST_MODEL)
        })

        root.addView(label("Ask or command"))
        goalInput = edit("", "Example: Navigate home, turn on flashlight, or tell me the battery level")
        goalInput.minLines = 3
        root.addView(goalInput)

        val goalButtons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        goalButtons.addView(button("Run") {
            runGoal()
        }, weighted())
        goalButtons.addView(button("Voice") {
            startVoiceInput()
        }, weighted())
        goalButtons.addView(button("Stop") {
            awaitingAgent = false
            AgentRuntime.cancelCurrentGoal()
            speechRecognizer?.cancel()
            tts?.stop()
            appendStatus("Cancellation requested.")
            if (handsFreeEnabled) scheduleHandsFreeListening()
        }, weighted())
        root.addView(goalButtons)

        root.addView(label("Execution log"))
        statusView = body("")
        statusView.setTextIsSelectable(true)
        root.addView(statusView)

        root.addView(body(
            "Direct capabilities now include flashlight, screen brightness, Do Not Disturb, maps/navigation, " +
                "camera launch, calendar event creation, web search/URLs, clipboard/share, SMS/email composition, " +
                "dialer, alarms/timers, media/volume controls, notification replies, app/settings navigation, " +
                "accessibility-driven UI interaction, screen summarization, screenshots, screen locking, " +
                "notification open/dismiss/snooze controls, contact-aware communication, app-usage reports, " +
                "and exact user-scheduled autonomous goals."
        ))

        val scroll = ScrollView(this).apply { addView(root) }
        setContentView(scroll)
        handleLaunchIntent(intent)
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        if (intent != null) {
            setIntent(intent)
            handleLaunchIntent(intent)
        }
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

    override fun onDestroy() {
        stopHandsFreeMode()
        speechRecognizer?.destroy()
        speechRecognizer = null
        tts?.stop()
        tts?.shutdown()
        tts = null
        super.onDestroy()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_RUNTIME_PERMISSIONS) {
            appendStatus("Runtime permission request completed.")
        } else if (requestCode == REQUEST_CONTACTS_PERMISSION) {
            val granted = grantResults.isNotEmpty() &&
                grantResults[0] == PackageManager.PERMISSION_GRANTED
            appendStatus(
                if (granted) "Contact lookup enabled."
                else "Contact lookup permission was not granted."
            )
        } else if (requestCode == REQUEST_HANDS_FREE_PERMISSION) {
            val granted = grantResults.isNotEmpty() &&
                grantResults[0] == PackageManager.PERMISSION_GRANTED
            if (granted && pendingHandsFreePermission) {
                pendingHandsFreePermission = false
                startHandsFreeMode()
            } else {
                pendingHandsFreePermission = false
                appendStatus("Microphone permission is required for hands-free mode.")
            }
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

                if (text.isNotBlank()) {
                    goalInput.setText(text)
                    if (autoRunVoiceToggle.isChecked) runGoal()
                }
            }
        }
    }

    private fun runGoal() {
        AgentRuntime.savePlannerSettings(
            this,
            endpointInput.text.toString(),
            modelInput.text.toString()
        )

        val goal = goalInput.text.toString().trim()
        if (goal.isBlank()) {
            appendStatus("Enter or speak a goal first.")
            return
        }

        speechRecognizer?.cancel()
        awaitingAgent = true
        AgentRuntime.recordUserMessage(this, goal)
        renderConversation()
        appendStatus("You: " + goal)

        AgentRuntime.executeGoal(this, goal) { message ->
            runOnUiThread { handleAgentMessage(message) }
        }
    }

    private fun handleAgentMessage(message: String) {
        appendStatus(message)

        val finalText = when {
            message.startsWith("Reply: ") -> message.removePrefix("Reply: ").trim()
            message.startsWith("Complete: ") -> message.removePrefix("Complete: ").trim()
            message.startsWith("Stopped: ") ->
                "I couldn't complete that. " + message.removePrefix("Stopped: ").trim()
            message.startsWith("Step failed: ") ->
                "I hit an error: " + message.removePrefix("Step failed: ").trim()
            message.startsWith("Planner setup failed: ") ->
                "The AI planner could not start: " + message.removePrefix("Planner setup failed: ").trim()
            message == "Goal cancelled." -> "Cancelled."
            else -> ""
        }

        if (finalText.isNotBlank()) {
            awaitingAgent = false
            lastAssistantReply = finalText
            AgentRuntime.recordAssistantMessage(this, finalText)
            renderConversation()

            if (speakRepliesToggle.isChecked && ttsReady) {
                speak(finalText)
            } else if (handsFreeEnabled) {
                scheduleHandsFreeListening()
            }
        }
    }

    private fun initializeSpeech() {
        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val engine = tts ?: return@TextToSpeech
                val languageResult = engine.setLanguage(Locale.getDefault())
                ttsReady = languageResult != TextToSpeech.LANG_MISSING_DATA &&
                    languageResult != TextToSpeech.LANG_NOT_SUPPORTED
                engine.setSpeechRate(1.0f)
                engine.setPitch(1.0f)
                engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) = Unit
                    override fun onError(utteranceId: String?) {
                        if (handsFreeEnabled && !awaitingAgent) scheduleHandsFreeListening()
                    }
                    override fun onDone(utteranceId: String?) {
                        if (handsFreeEnabled && !awaitingAgent) scheduleHandsFreeListening()
                    }
                })
            } else {
                ttsReady = false
            }
        }
    }

    private fun speak(text: String) {
        if (!ttsReady) {
            appendStatus("Text-to-Speech is not ready on this device.")
            if (handsFreeEnabled && !awaitingAgent) scheduleHandsFreeListening()
            return
        }
        speechRecognizer?.cancel()
        tts?.speak(text.take(3_000), TextToSpeech.QUEUE_FLUSH, null, "codie-ai-reply")
    }

    private fun startHandsFreeMode() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            pendingHandsFreePermission = true
            requestPermissions(
                arrayOf(Manifest.permission.RECORD_AUDIO),
                REQUEST_HANDS_FREE_PERMISSION
            )
            return
        }

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            appendStatus("Android speech recognition is unavailable on this device.")
            return
        }

        runCatching {
            startForegroundService(
                Intent(this, AssistantOverlayService::class.java)
                    .putExtra(AssistantOverlayService.EXTRA_MICROPHONE_MODE, true)
            )
        }.onFailure {
            appendStatus("Could not start background microphone service: " +
                (it.message ?: it.javaClass.simpleName))
        }

        handsFreeEnabled = true
        ensureSpeechRecognizer()
        appendStatus("Hands-free conversation enabled.")
        if (!awaitingAgent) startHandsFreeListening()
    }

    private fun stopHandsFreeMode() {
        if (handsFreeEnabled) appendStatus("Hands-free conversation disabled.")
        handsFreeEnabled = false
        pendingHandsFreePermission = false
        handler.removeCallbacksAndMessages(null)
        speechRecognizer?.cancel()
    }

    private fun ensureSpeechRecognizer() {
        if (speechRecognizer != null) return

        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).also { recognizer ->
            recognizer.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    appendStatus("Listening...")
                }

                override fun onBeginningOfSpeech() = Unit
                override fun onRmsChanged(rmsdB: Float) = Unit
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onEndOfSpeech() = Unit

                override fun onError(error: Int) {
                    if (!handsFreeEnabled || awaitingAgent) return
                    if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                        appendStatus("Microphone permission is required for hands-free mode.")
                        handsFreeEnabled = false
                    } else {
                        scheduleHandsFreeListening(1_200L)
                    }
                }

                override fun onResults(results: Bundle?) {
                    val spoken = results
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.firstOrNull()
                        .orEmpty()
                        .trim()

                    if (spoken.isBlank()) {
                        if (handsFreeEnabled) scheduleHandsFreeListening()
                        return
                    }

                    goalInput.setText(spoken)
                    appendStatus("Heard: " + spoken)
                    runGoal()
                }

                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            })
        }
    }

    private fun startHandsFreeListening() {
        if (!handsFreeEnabled || awaitingAgent) return
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return

        ensureSpeechRecognizer()
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        }

        runCatching {
            speechRecognizer?.cancel()
            speechRecognizer?.startListening(intent)
        }.onFailure {
            appendStatus("Hands-free listening failed: " + (it.message ?: it.javaClass.simpleName))
            scheduleHandsFreeListening(1_500L)
        }
    }

    private fun scheduleHandsFreeListening(delay: Long = 650L) {
        if (!handsFreeEnabled) return
        handler.postDelayed({
            if (handsFreeEnabled && !awaitingAgent) startHandsFreeListening()
        }, delay)
    }

    private fun startVoiceInput() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Tell Codie AI what to do")
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }

        try {
            startActivityForResult(intent, REQUEST_VOICE)
        } catch (error: Throwable) {
            appendStatus("Voice recognition is unavailable: " + (error.message ?: error.javaClass.simpleName))
        }
    }

    private fun requestContactPermission() {
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            appendStatus("Contact lookup is already enabled.")
        } else {
            requestPermissions(
                arrayOf(Manifest.permission.READ_CONTACTS),
                REQUEST_CONTACTS_PERMISSION
            )
        }
    }

    private fun requestExactAlarmAccess() {
        if (Build.VERSION.SDK_INT < 31) {
            appendStatus("This Android version does not require special exact-alarm access.")
            return
        }

        val alarmManager = getSystemService(ALARM_SERVICE) as AlarmManager
        if (alarmManager.canScheduleExactAlarms()) {
            appendStatus("Scheduled automation access is already enabled.")
            return
        }

        appendStatus(
            "Enable 'Alarms & reminders' so Codie AI can execute user-scheduled goals at the requested time."
        )
        startActivity(
            Intent(
                Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,
                Uri.parse("package:" + packageName)
            )
        )
    }

    private fun requestAssistantRuntimePermissions() {
        val permissions = mutableListOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA
        )
        if (Build.VERSION.SDK_INT >= 33) permissions.add(Manifest.permission.POST_NOTIFICATIONS)

        val missing = permissions.filter {
            checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }

        if (missing.isEmpty()) {
            appendStatus("Microphone, camera, and notification permissions are already granted.")
        } else {
            requestPermissions(missing.toTypedArray(), REQUEST_RUNTIME_PERMISSIONS)
        }
    }

    private fun startAssistantBubble() {
        if (!Settings.canDrawOverlays(this)) {
            appendStatus("Allow 'Display over other apps', then tap Start AI bubble again.")
            startActivity(
                Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + packageName)
                )
            )
            return
        }

        val serviceIntent = Intent(this, AssistantOverlayService::class.java)
        startForegroundService(serviceIntent)
        appendStatus("Floating assistant started. Tap the AI bubble for voice input; long-press it to stop.")
    }

    private fun handleLaunchIntent(launchIntent: Intent?) {
        if (launchIntent?.getBooleanExtra(EXTRA_START_VOICE, false) == true) {
            launchIntent.removeExtra(EXTRA_START_VOICE)
            handler.postDelayed({
                if (handsFreeEnabled) startHandsFreeListening()
                else startVoiceInput()
            }, 350L)
        }
    }

    private fun renderConversation() {
        if (!::chatView.isInitialized) return
        val history = AgentRuntime.conversationTranscript(this)
        chatView.text = if (history.isBlank()) "No conversation yet." else history
    }

    private fun downloadRecommendedModel() {
        val available = StatFs(filesDir.absolutePath).availableBytes
        if (available < RECOMMENDED_MODEL_MIN_FREE_BYTES) {
            appendStatus(
                "Not enough free storage for the local model. Need about " +
                    formatBytes(RECOMMENDED_MODEL_MIN_FREE_BYTES) + " free; available: " +
                    formatBytes(available) + "."
            )
            return
        }

        appendStatus("Downloading Gemma 4 E2B. Wi-Fi is recommended (~2.6 GB).")
        Thread {
            val destination = AgentRuntime.localModelFile(this)
            val temporary = File(destination.parentFile, destination.name + ".part")
            var connection: HttpURLConnection? = null

            try {
                destination.parentFile?.mkdirs()
                temporary.delete()

                connection = (URL(RECOMMENDED_MODEL_URL).openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 30_000
                    readTimeout = 120_000
                    instanceFollowRedirects = true
                    setRequestProperty("User-Agent", "CodieAI/0.5 Android")
                }

                val status = connection.responseCode
                require(status in 200..299) { "Model server returned HTTP " + status }

                val expected = connection.contentLengthLong
                if (expected > 0L) {
                    val freeNow = StatFs(filesDir.absolutePath).availableBytes
                    val required = expected + DOWNLOAD_RESERVE_BYTES
                    require(freeNow >= required) {
                        "Need " + formatBytes(required) + " free for this download; available: " +
                            formatBytes(freeNow)
                    }
                }

                var copied = 0L
                var lastReportedPercent = -1
                val buffer = ByteArray(1024 * 1024)

                connection.inputStream.buffered(1024 * 1024).use { input ->
                    temporary.outputStream().buffered(1024 * 1024).use { output ->
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            output.write(buffer, 0, count)
                            copied += count

                            if (expected > 0L) {
                                val percent = ((copied * 100L) / expected).toInt().coerceIn(0, 100)
                                if (percent >= lastReportedPercent + 5 || percent == 100) {
                                    lastReportedPercent = percent
                                    runOnUiThread {
                                        appendStatus("Local model download: " + percent + "%")
                                    }
                                }
                            }
                        }
                    }
                }

                require(copied >= RECOMMENDED_MODEL_MIN_BYTES) {
                    "Downloaded file is unexpectedly small: " + formatBytes(copied)
                }
                if (expected > 0L) {
                    require(copied == expected) {
                        "Incomplete download: " + copied + " of " + expected + " bytes"
                    }
                }

                destination.delete()
                if (!temporary.renameTo(destination)) {
                    temporary.copyTo(destination, overwrite = true)
                    temporary.delete()
                }

                runOnUiThread {
                    modelStatus.text = localModelDescription()
                    appendStatus("Gemma 4 E2B installed. Phone-only AI planning is ready.")
                }
            } catch (error: Throwable) {
                temporary.delete()
                runOnUiThread {
                    appendStatus("Model download failed: " + (error.message ?: error.javaClass.simpleName))
                }
            } finally {
                connection?.disconnect()
            }
        }.start()
    }

    private fun importModel(uri: Uri) {
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

    private fun localModelDescription(): String {
        val file = AgentRuntime.localModelFile(this)
        return if (file.isFile) {
            "Installed: " + file.name + " (" + formatBytes(file.length()) + ")"
        } else {
            "No local model installed. Basic direct commands still work without a model."
        }
    }

    private fun appendStatus(message: String) {
        if (!::statusView.isInitialized) return
        val current = statusView.text.toString()
        val combined = if (current.isBlank()) message else current + "\n" + message
        statusView.text = combined.takeLast(MAX_LOG_CHARS)
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
        const val EXTRA_START_VOICE = "start_voice"

        private const val REQUEST_MODEL = 42
        private const val REQUEST_VOICE = 43
        private const val REQUEST_RUNTIME_PERMISSIONS = 44
        private const val REQUEST_HANDS_FREE_PERMISSION = 45
        private const val REQUEST_CONTACTS_PERMISSION = 46
        private const val MAX_LOG_CHARS = 20_000
        private const val RECOMMENDED_MODEL_MIN_BYTES = 2_000_000_000L
        private const val RECOMMENDED_MODEL_MIN_FREE_BYTES = 3_200_000_000L
        private const val DOWNLOAD_RESERVE_BYTES = 536_870_912L
        private const val RECOMMENDED_MODEL_URL =
            "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm"
    }
}
