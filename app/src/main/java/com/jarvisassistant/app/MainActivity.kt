package com.jarvisassistant.app

import android.Manifest
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.BroadcastReceiver
import android.content.IntentFilter
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.media.MediaPlayer
import android.provider.AlarmClock
import android.provider.Settings
import android.speech.RecognitionListener
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.View
import android.widget.VideoView
import android.net.Uri
import java.io.File
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.Future
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo

private val Bg = Color(0xFF030303)
private val Panel = Color(0xFF101010)
private val TextMain = Color(0xFFF4F4F4)

enum class JarvisState { IDLE, LISTENING, THINKING, SPEAKING, SERIOUS, CYBERSECURITY, ERROR, OFFLINE }

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {
    private val prefs by lazy { getSharedPreferences("jarvis", Context.MODE_PRIVATE) }
    private val historyStore by lazy { HistoryStore(this) }
    private val longMemory by lazy { JarvisMemoryManager(this) } 
    private val taskStore by lazy { JarvisTaskStore(this) }
    private val recoveryStore by lazy { JarvisRecoveryStore(this) }
    
    private var tts: TextToSpeech? = null
    private var speechRecognizer: SpeechRecognizer? = null
    private var mediaPlayer: MediaPlayer? = null
    private var torchOn = false
    private var lastTranscript by mutableStateOf("")
    private var responseText by mutableStateOf("")
    private var state by mutableStateOf(JarvisState.IDLE)
    private var apiKey by mutableStateOf("")
    private var endpoint by mutableStateOf("https://api.openai.com/v1/chat/completions")
    private var model by mutableStateOf("gpt-4o-mini")
    private var speechLocale by mutableStateOf("en-US")
    private var wakeWord by mutableStateOf("JARVIS")
    private var speechRate by mutableStateOf(0.90f)
    private var memory by mutableStateOf("")
    private var memoryEnabled by mutableStateOf(true)
    private var seriousModeActive by mutableStateOf(false)
    private var cybersecurityModeActive by mutableStateOf(false)
    private var currentProactiveMode by mutableStateOf(JarvisProactiveEngine.Mode.NORMAL)
    private var pendingConfirmation: String? = null
    private var pendingAgentConfirmation = false
    private var setupComplete by mutableStateOf(false)
    private var showSettings by mutableStateOf(false)
    private var history by mutableStateOf(listOf<ChatTurn>())
    private var isEmergencyKillSwitchEnabled by mutableStateOf(false)
    private var securityAudit by mutableStateOf(listOf<JarvisSecurityCenter.AuditEntry>())
    private var audioLevel by mutableStateOf(0f)
    private val worker = Executors.newSingleThreadExecutor()
    private var activeTask: Future<*>? = null
    private var requestGeneration = 0L
    private var continuousConversation = false
    private var pendingWakeServiceStart = false
    
    private val wakeReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            lastTranscript = intent?.getStringExtra("phrase").orEmpty()
            state = JarvisState.LISTENING
            startListening()
        }
    }

    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            if (pendingWakeServiceStart) {
                pendingWakeServiceStart = false
                startWakeService()
            } else startListening()
        } else {
            pendingWakeServiceStart = false
            state = JarvisState.ERROR
            responseText = "Microphone permission was not granted."
        }
    }
    
    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) toggleTorch()
        else responseText = "Camera permission is required by Android to control the flashlight."
    }

    private val calendarPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        responseText = if (granted) "Calendar context enabled." else "Calendar access was not granted."
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        responseText = if (granted) "JARVIS notifications enabled." else "Notification permission was not granted."
    }

    @Suppress("DEPRECATION")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
            window.statusBarColor = android.graphics.Color.BLACK
            window.navigationBarColor = android.graphics.Color.BLACK
            window.decorView.systemUiVisibility = (
                View.SYSTEM_UI_FLAG_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                )
            migrateAndLoadPreferences()
            isEmergencyKillSwitchEnabled = JarvisSecurityCenter.isKillSwitchEnabled(this)
            securityAudit = JarvisSecurityCenter.auditEntries(this)
            JarvisDiagnostics.record(this, "lifecycle", "INFO", "JARVIS activity initialized")
            tts = TextToSpeech(this, this)
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    runOnUiThread { state = JarvisState.SPEAKING }
                }
                override fun onDone(utteranceId: String?) {
                    runOnUiThread {
                        state = restingState()
                        if (continuousConversation && !isFinishing && !isDestroyed) startListening()
                    }
                }
                override fun onError(utteranceId: String?) {
                    runOnUiThread { state = JarvisState.ERROR }
                }
            })
            
            val filter = IntentFilter(JarvisWakeService.ACTION_WAKE)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                registerReceiver(wakeReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
            } else {
                registerReceiver(wakeReceiver, filter)
            }

            setContent {
                Box(modifier = Modifier.fillMaxSize().background(Bg)) {
                    AndroidView(
                        modifier = Modifier.fillMaxSize(),
                        factory = { context ->
                            VideoView(context).apply {
                                setVideoURI(Uri.parse("android.resource://${context.packageName}/${R.raw.jarvis_interface}"))
                                setOnClickListener { showSettings = true }
                                setOnPreparedListener { player ->
                                    player.isLooping = true
                                    player.setVolume(0f, 0f)
                                    start()
                                }
                                setOnErrorListener { _, what, extra ->
                                    Log.e("Jarvis", "Video error: what=$what extra=$extra")
                                    responseText = "Interface video failed to play."
                                    true
                                }
                            }
                        },
                        update = { videoView -> if (!videoView.isPlaying) videoView.start() }
                    )
                    if (showSettings) {
                        Surface(color = Panel.copy(alpha = 0.96f), modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("JARVIS Controls", color = TextMain, fontWeight = FontWeight.Bold)
                                Text("Wake word: $wakeWord", color = TextMain)
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Button(onClick = { startWakeService() }) { Text("Start listening") }
                                    Button(onClick = { stopWakeService() }) { Text("Stop listening") }
                                    TextButton(onClick = { showSettings = false }) { Text("Close") }
                                }
                            }
                        }
                    }
                }
            }
        } catch (t: Throwable) {
            Log.e("Jarvis", "Startup failure", t)
            state = JarvisState.ERROR
            responseText = "Startup failed: ${t.message}"
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            applyTtsPreferences()
        } else {
            Log.e("Jarvis", "TTS Initialization failed")
        }
    }

    private fun applyTtsPreferences() {
        tts?.let { t ->
            t.language = Locale.forLanguageTag(speechLocale)
            t.setSpeechRate(speechRate)
        }
    }

    private fun speak(text: String) {
        if (text.isBlank()) return
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "jarvis_utterance")
    }

    private fun restingState(): JarvisState {
        return if (seriousModeActive) JarvisState.SERIOUS
        else if (cybersecurityModeActive) JarvisState.CYBERSECURITY
        else JarvisState.IDLE
    }

    private fun finishTurn(prompt: String, reply: String) {
        history = (history + ChatTurn(prompt, reply, emptyList())).takeLast(40)
        if (!continuousConversation) state = restingState()
        speak(reply)
    }

    private fun toggleTorch() {
        try {
            val cameraManager = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraId = cameraManager.cameraIdList[0]
            cameraManager.setTorchMode(cameraId, !torchOn)
            torchOn = !torchOn
        } catch (e: Exception) {
            responseText = "Could not toggle flashlight: ${e.message}"
        }
    }

    private fun startWakeService() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            pendingWakeServiceStart = true
            micPermission.launch(Manifest.permission.RECORD_AUDIO)
            return
        }
        pendingWakeServiceStart = false
        val intent = Intent(this, JarvisWakeService::class.java)
            .putExtra("wake", wakeWord)
            .putExtra("locale", speechLocale)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ContextCompat.startForegroundService(this, intent)
            else startService(intent)
            responseText = "Wake-word listening started."
        } catch (e: Exception) {
            responseText = "Could not start wake-word listening: ${e.message}"
        }
    }

    private fun stopWakeService() {
        try {
            startService(Intent(this, JarvisWakeService::class.java).setAction(JarvisWakeService.ACTION_STOP))
            responseText = "Wake-word listening stopped."
        } catch (e: Exception) {
            stopService(Intent(this, JarvisWakeService::class.java))
        }
    }

    private fun migrateAndLoadPreferences() {
        endpoint = prefs.getString("endpoint", endpoint).orEmpty().ifBlank { endpoint }
        model = prefs.getString("model", model).orEmpty().ifBlank { model }
        speechLocale = prefs.getString("speech_locale", speechLocale).orEmpty().ifBlank { "en-US" }
        wakeWord = prefs.getString("wake_word", wakeWord).orEmpty().ifBlank { "JARVIS" }
        speechRate = prefs.getFloat("speech_rate", speechRate).coerceIn(0.5f, 1.5f)
        setupComplete = prefs.getBoolean("setup_complete", false)
    }

    private fun setSeriousMode(enabled: Boolean) {
        seriousModeActive = enabled
        prefs.edit().putBoolean("serious_mode", enabled).apply()
        responseText = if (enabled) "Serious Mode is on." else "Serious Mode is off."
    }

    private fun setCybersecurityMode(enabled: Boolean) {
        cybersecurityModeActive = enabled
        prefs.edit().putBoolean("cybersecurity_mode", enabled).apply()
        responseText = if (enabled) "Cybersecurity Mode is on." else "Cybersecurity Mode is off."
    }

    private fun onOrbClick() {
        when (state) {
            JarvisState.LISTENING -> stopListening()
            JarvisState.SPEAKING -> {
                tts?.stop()
                state = restingState()
            }
            else -> {
                tts?.stop()
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    startListening()
                } else micPermission.launch(Manifest.permission.RECORD_AUDIO)
            }
        }
    }

    private fun startListening() {
        if (!JarvisVoiceEngine.isAvailable(this)) {
            state = JarvisState.ERROR
            responseText = "Android speech recognition is unavailable."
            return
        }
        stopListening()
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).also { recognizer ->
            recognizer.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) { state = JarvisState.LISTENING }
                override fun onBeginningOfSpeech() { state = JarvisState.LISTENING }
                override fun onRmsChanged(rmsdB: Float) { audioLevel = ((rmsdB + 2f) / 12f).coerceIn(0f, 1f) }
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onEndOfSpeech() { state = JarvisState.THINKING }
                override fun onError(error: Int) {
                    audioLevel = 0f
                    state = if (error == SpeechRecognizer.ERROR_NETWORK) JarvisState.OFFLINE else JarvisState.ERROR
                    responseText = JarvisVoiceEngine.errorMessage(error)
                }
                override fun onResults(results: Bundle?) {
                    audioLevel = 0f
                    val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                    if (text.isNullOrBlank()) {
                        state = JarvisState.ERROR
                        responseText = "No speech was recognized."
                    } else {
                        lastTranscript = text
                        handlePrompt(text)
                    }
                }
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            })
            val intent = JarvisVoiceEngine.recognitionIntent(speechLocale, preferOffline = false)
            try { recognizer.startListening(intent) } catch (_: Exception) {
                state = JarvisState.ERROR
                responseText = "Voice recognition could not start."
                recognizer.destroy()
                speechRecognizer = null
            }
        }
    }

    private fun stopListening() {
        speechRecognizer?.cancel()
        speechRecognizer?.destroy()
        speechRecognizer = null
        state = restingState()
    }

    private fun handlePrompt(rawPrompt: String) {
        val prompt = rawPrompt.trim()
        if (prompt.isBlank()) return
        lastTranscript = prompt

        if (isEmergencyKillSwitchEnabled) {
            responseText = "Emergency security lock is ON."
            finishTurn(prompt, responseText)
            return
        }

        val localReply = handleLocalCommand(prompt)
        if (localReply != null) {
            responseText = localReply
            finishTurn(prompt, localReply)
            return
        }

        state = JarvisState.THINKING
        val key = apiKey
        if (key.isBlank()) {
            responseText = "Add an AI provider key in Settings."
            finishTurn(prompt, responseText)
            return
        }

        activeTask?.cancel(true)
        val generation = ++requestGeneration
        activeTask = worker.submit {
            try {
                val result = AiProvider.answer(endpoint, model, key, prompt, history, "", emptyList(), false, false, false) { false }
                runOnUiThread {
                    if (generation != requestGeneration) return@runOnUiThread
                    responseText = result
                    finishTurn(prompt, result)
                }
            } catch (e: Exception) {
                runOnUiThread {
                    responseText = "Error: ${e.message}"
                    finishTurn(prompt, responseText)
                }
            }
        }
    }

    private fun handleLocalCommand(text: String): String? {
        val command = CommandNormalizer.normalize(text, wakeWord)
        if (command in setOf("help", "commands", "what can you do")) {
            return "JARVIS commands: time, date, battery, flashlight, home, back, scroll up/down, open app, lock phone, screenshot."
        }
        if (command.matches(Regex("(what('?s| is) the )?time( now)?\\??"))) {
            return "It is ${java.text.SimpleDateFormat("h:mm a", Locale.getDefault()).format(java.util.Date())}."
        }
        if (command.matches(Regex("(what('?s| is) the )?date( today)?\\??"))) {
            return "Today is ${java.text.SimpleDateFormat("EEEE, d MMMM yyyy", Locale.getDefault()).format(java.util.Date())}."
        }
        if (command in listOf("battery status", "battery percentage")) {
            val bm = getSystemService(BATTERY_SERVICE) as android.os.BatteryManager
            val pct = bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)
            return if (pct >= 0) "Battery is at $pct percent." else "Battery percentage is unavailable."
        }
        if (command in listOf("flashlight", "toggle flashlight")) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                toggleTorch()
                return if (torchOn) "Flashlight on." else "Flashlight off."
            }
            cameraPermission.launch(Manifest.permission.CAMERA)
            return "Requesting camera permission."
        }
        if (command == "home" || command == "go home") return runAccessibility("home")
        if (command == "back" || command == "go back") return runAccessibility("back")
        if (command.startsWith("scroll up")) return runAccessibility("scroll-up")
        if (command.startsWith("scroll down")) return runAccessibility("scroll-down")
        if (command == "lock phone") return lockPhone()
        Regex("^open (.+)$").find(command)?.let { match ->
            return openInstalledApp(match.groupValues[1].trim())
        }
        return null
    }

    private fun safeStartActivity(intent: Intent) {
        try {
            startActivity(intent)
        } catch (e: Exception) {
            responseText = "I couldn't open that app or settings screen."
        }
    }

    // 🟢 FIXED: Accessibility logic updated for scroll, tap, and type
    private fun runAccessibility(action: String, x: Float? = null, y: Float? = null, text: String? = null): String {
        val service = JarvisAccessibilityService.active
            ?: return "Accessibility service is not active. Enable JARVIS Accessibility in settings."
        
        return when (action) {
            "home" -> { 
                service.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_HOME)
                "Going home." 
            }
            "back" -> { 
                service.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK)
                "Going back." 
            }
            "scroll-up" -> { 
                val root = service.rootInActiveWindow
                if (root != null) {
                    root.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD)
                    "Scrolling up."
                } else "Cannot scroll up."
            }
            "scroll-down" -> { 
                val root = service.rootInActiveWindow
                if (root != null) {
                    root.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)
                    "Scrolling down."
                } else "Cannot scroll down."
            }
            "tap" -> {
                if (x != null && y != null) {
                    service.performTap(x, y)
                    "Tapping at ($x, $y)."
                } else "Invalid coordinates."
            }
            "type" -> {
                if (text != null) {
                    service.inputText(text)
                    "Typing text."
                } else "No text provided."
            }
            else -> "Unknown accessibility action."
        }
    }

    private fun lockPhone(): String {
        val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val adminComponent = ComponentName(this, JarvisDeviceAdminReceiver::class.java)
        return if (dpm.isAdminActive(adminComponent)) {
            dpm.lockNow()
            "Phone locked."
        } else {
            "Device admin permission required."
        }
    }

    private fun openInstalledApp(appName: String): String {
        val pm = packageManager
        for (pkg in pm.getInstalledPackages(0)) {
            val label = pm.getApplicationLabel(pkg.applicationInfo).toString()
            if (label.equals(appName, ignoreCase = true)) {
                val intent = pm.getLaunchIntentForPackage(pkg.packageName)
                if (intent != null) {
                    safeStartActivity(intent)
                    return "Opening $label."
                }
            }
        }
        return "App not found: $appName"
    }

    private fun executeAgentStep(step: String): String {
        return "Agent step executed: $step"
    }

    private fun formatAgentResult(result: String): String {
        return "Agent result: $result"
    }
}
