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
import android.os.Build
import android.os.Bundle
import android.media.MediaPlayer
import android.provider.Settings
import android.speech.RecognitionListener
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.View
import android.view.Gravity
import android.widget.FrameLayout
import android.widget.VideoView
import kotlin.math.max
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
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
                val infiniteTransition = rememberInfiniteTransition()
                val pulseScale by infiniteTransition.animateFloat(
                    initialValue = 1f,
                    targetValue = if (state == JarvisState.LISTENING) 1.06f else 1f,
                    animationSpec = infiniteRepeatable(
                        animation = tween(800, easing = LinearEasing),
                        repeatMode = RepeatMode.Reverse
                    )
                )

                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(
                            Brush.radialGradient(
                                colors = listOf(Color(0xFF2d001f), Bg),
                                radius = 1200f,
                                center = Offset.Unspecified
                            )
                        )
                ) {
                    // HUD background video (full screen, muted, looping, center-crop)
                    AndroidView(
                        modifier = Modifier.fillMaxSize(),
                        factory = { context ->
                            FrameLayout(context).apply {
                                val bgVideo = VideoView(context)
                                addView(
                                    bgVideo,
                                    FrameLayout.LayoutParams(
                                        FrameLayout.LayoutParams.MATCH_PARENT,
                                        FrameLayout.LayoutParams.MATCH_PARENT,
                                        Gravity.CENTER
                                    )
                                )
                                bgVideo.setVideoURI(Uri.parse("android.resource://${context.packageName}/${R.raw.jarvis_hud_bg}"))
                                bgVideo.setOnPreparedListener { player ->
                                    player.isLooping = true
                                    player.setVolume(0f, 0f)
                                    // Center-crop: video ko poori screen me fill karo (aspect ratio bacha ke)
                                    this.post {
                                        val vw = player.videoWidth
                                        val vh = player.videoHeight
                                        if (width > 0 && height > 0 && vw > 0 && vh > 0) {
                                            val scale = max(width.toFloat() / vw, height.toFloat() / vh)
                                            bgVideo.layoutParams = FrameLayout.LayoutParams(
                                                (vw * scale).toInt(),
                                                (vh * scale).toInt(),
                                                Gravity.CENTER
                                            )
                                        }
                                    }
                                    bgVideo.start()
                                }
                                bgVideo.setOnErrorListener { _, what, extra ->
                                    Log.e("Jarvis", "HUD bg video error: what=$what extra=$extra")
                                    true
                                }
                            }
                        }
                    )
                    // Dark scrim taaki text/buttons clearly dikhein
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color.Black.copy(alpha = 0.35f))
                    )

                    Column(
                        modifier = Modifier.fillMaxSize(),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Spacer(modifier = Modifier.weight(1f))

                        // Tap area (purani orb video hata di; ab HUD video background me chalti hai)
                        Box(
                            modifier = Modifier
                                .size(260.dp)
                                .scale(pulseScale)
                                .clip(CircleShape)
                                .border(
                                    width = 2.dp,
                                    color = Color(0xFFFF4444).copy(alpha = if (state == JarvisState.LISTENING) 0.9f else 0.35f),
                                    shape = CircleShape
                                )
                                .clickable { onOrbClick() }
                        )

                        Spacer(modifier = Modifier.height(16.dp))

                        // Status Text
                        val statusText = when (state) {
                            JarvisState.LISTENING -> "Listening..."
                            JarvisState.THINKING -> "Thinking..."
                            JarvisState.SPEAKING -> "Speaking..."
                            JarvisState.ERROR -> "Error"
                            else -> "Tap to speak"
                        }
                        Text(
                            text = statusText,
                            color = TextMain,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Medium
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        // Voice Waveform
                        if (state == JarvisState.LISTENING) {
                            VoiceWaveform(audioLevel = audioLevel)
                        } else {
                            Spacer(modifier = Modifier.height(40.dp))
                        }

                        // Chat History
                        if (history.isNotEmpty()) {
                            val listState = rememberLazyListState()
                            LaunchedEffect(history.size) {
                                if (history.isNotEmpty()) {
                                    listState.animateScrollToItem(history.size - 1)
                                }
                            }
                            LazyColumn(
                                state = listState,
                                modifier = Modifier
                                    .weight(1f)
                                    .fillMaxWidth()
                                    .padding(horizontal = 24.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                items(history) { turn ->
                                    Text(
                                        text = "You: ${turn.user}",
                                        color = Color.White.copy(alpha = 0.7f),
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                    Text(
                                        text = "JARVIS: ${turn.assistant}",
                                        color = Color(0xFFFF4444),
                                        style = MaterialTheme.typography.bodyMedium,
                                        modifier = Modifier.padding(bottom = 12.dp)
                                    )
                                }
                            }
                        } else {
                            Spacer(modifier = Modifier.weight(1f))
                        }

                        // Bottom Panel
                        if (showSettings) {
                            GlassPanel(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(16.dp),
                                onStart = { startWakeService(); showSettings = false },
                                onStop = { stopWakeService(); showSettings = false },
                                onClose = { showSettings = false }
                            )
                        } else {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(bottom = 32.dp),
                                horizontalArrangement = Arrangement.Center,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Button(
                                    onClick = { onOrbClick() },
                                    shape = CircleShape,
                                    modifier = Modifier.size(72.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = Color.White.copy(alpha = 0.1f))
                                ) {
                                    Text(if (state == JarvisState.LISTENING) "Stop" else "Mic", color = TextMain, fontWeight = FontWeight.Bold)
                                }
                                Spacer(modifier = Modifier.width(24.dp))
                                Button(
                                    onClick = { showSettings = true },
                                    shape = CircleShape,
                                    modifier = Modifier.size(72.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = Color.White.copy(alpha = 0.1f))
                                ) {
                                    Text("⚙", color = TextMain, style = MaterialTheme.typography.headlineMedium)
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

@Composable
fun VoiceWaveform(audioLevel: Float) {
    Canvas(modifier = Modifier.height(40.dp).fillMaxWidth(0.6f)) {
        val barCount = 20
        val barWidth = size.width / (barCount * 2f)
        val spacing = barWidth
        
        for (i in 0 until barCount) {
            val level = if (audioLevel > 0.1f) audioLevel else 0.1f
            val randomFactor = 0.5f + kotlin.random.Random.nextFloat() * 0.5f
            val randomHeight = size.height * level * randomFactor
            val x = i * (barWidth + spacing) + barWidth / 2f
            
            drawLine(
                color = Color.Red,
                start = Offset(x, size.height / 2f - randomHeight / 2f),
                end = Offset(x, size.height / 2f + randomHeight / 2f),
                strokeWidth = barWidth
            )
        }
    }
}

@Composable
fun GlassPanel(modifier: Modifier = Modifier, onStart: () -> Unit, onStop: () -> Unit, onClose: () -> Unit) {
    Surface(
        modifier = modifier.clip(RoundedCornerShape(25.dp)),
        color = Color.White.copy(alpha = 0.08f),
        shadowElevation = 8.dp
    ) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("JARVIS Controls", color = TextMain, fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = onStart, modifier = Modifier.weight(1f), shape = RoundedCornerShape(12.dp)) { Text("Start") }
                Button(onClick = onStop, modifier = Modifier.weight(1f), shape = RoundedCornerShape(12.dp)) { Text("Stop") }
            }
            TextButton(onClick = onClose, modifier = Modifier.align(Alignment.CenterHorizontally)) { 
                Text("Close", color = TextMain) 
            }
        }
    }
}
