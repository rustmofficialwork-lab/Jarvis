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
import android.speech.RecognitionListener
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.View
import android.widget.VideoView
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
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
    private var seriousModeActive by mutableStateOf(false)
    private var cybersecurityModeActive by mutableStateOf(false)
    private var showSettings by mutableStateOf(false)
    private var history by mutableStateOf(listOf<ChatTurn>())
    private var isEmergencyKillSwitchEnabled by mutableStateOf(false)
    private var audioLevel by mutableStateOf(0f)
    private val worker = Executors.newSingleThreadExecutor()
    private var activeTask: Future<*>? = null
    private var requestGeneration = 0L
    private var continuousConversation = true 
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

            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                startWakeService()
            } else {
                micPermission.launch(Manifest.permission.RECORD_AUDIO)
            }

            setContent {
                val infiniteTransition = rememberInfiniteTransition()
                val pulseScale by infiniteTransition.animateFloat(
                    initialValue = 1f,
                    targetValue = if (state == JarvisState.LISTENING) 1.03f else 1f,
                    animationSpec = infiniteRepeatable(
                        animation = tween(1000, easing = LinearEasing),
                        repeatMode = RepeatMode.Reverse
                    )
                )

                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Bg)
                ) {
                    Column(
                        modifier = Modifier.fillMaxSize(),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        
                        Box(
                            contentAlignment = Alignment.Center,
                            modifier = Modifier
                                .size(340.dp)
                                .scale(pulseScale)
                                .clip(CircleShape)
                        ) {
                            AndroidView(
                                modifier = Modifier.fillMaxSize(),
                                factory = { context ->
                                    VideoView(context).apply {
                                        setVideoURI(Uri.parse("android.resource://${context.packageName}/${R.raw.jarvis_hud_bg}"))
                                        setOnPreparedListener { player ->
                                            player.isLooping = true
                                            player.setVolume(0f, 0f)
                                            player.setVideoScalingMode(MediaPlayer.VIDEO_SCALING_MODE_SCALE_TO_FIT)
                                            start()
                                        }
                                    }
                                },
                                update = { videoView -> if (!videoView.isPlaying) videoView.start() }
                            )

                            if (state == JarvisState.LISTENING) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text(
                                        text = "Listening...",
                                        color = Color.White,
                                        style = MaterialTheme.typography.titleLarge,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Spacer(modifier = Modifier.height(16.dp))
                                    VoiceWaveform(audioLevel = audioLevel)
                                }
                            } else if (state == JarvisState.THINKING) {
                                Text(
                                    text = "Thinking...",
                                    color = Color.White,
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold
                                )
                            } else if (state == JarvisState.SPEAKING) {
                                Text(
                                    text = "Speaking...",
                                    color = Color.White,
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }

                    if (showSettings) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .background(Color.Black.copy(alpha = 0.9f)), 
                            contentAlignment = Alignment.Center
                        ) {
                            GlassPanel(
                                modifier = Modifier.padding(16.dp),
                                onStart = { startWakeService(); showSettings = false },
                                onStop = { stopWakeService(); showSettings = false },
                                onClose = { showSettings = false }
                            )
                        }
                    }
                }
            }
        } catch (t: Throwable) {
            Log.e("Jarvis", "Startup failure", t)
            state = JarvisState.ERROR
        }
    }

    private fun handleLocalCommand(text: String): String? {
        val command = CommandNormalizer.normalize(text, wakeWord)
        
        if (command.contains("settings") || command.contains("setting")) {
            showSettings = true
            return "Opening settings."
        }

        if (command in setOf("help", "commands", "what can you do")) {
            return "JARVIS commands: time, date, battery, flashlight, home, back, open app, lock phone."
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
        if (command == "lock phone") return lockPhone()
        Regex("^open (.+)$").find(command)?.let { match ->
            return openInstalledApp(match.groupValues[1].trim())
        }
        return null
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.forLanguageTag(speechLocale)
            tts?.setSpeechRate(speechRate)
        }
    }

    private fun restingState(): JarvisState {
        return if (seriousModeActive) JarvisState.SERIOUS
        else if (cybersecurityModeActive) JarvisState.CYBERSECURITY
        else JarvisState.IDLE
    }

    private fun finishTurn(prompt: String, reply: String) {
        history = (history + ChatTurn(prompt, reply, emptyList())).takeLast(40)
        if (!continuousConversation) state = restingState()
        tts?.speak(reply, TextToSpeech.QUEUE_FLUSH, null, "jarvis_utterance")
    }

    private fun startWakeService() {
        pendingWakeServiceStart = false
        val intent = Intent(this, JarvisWakeService::class.java)
            .putExtra("wake", wakeWord)
            .putExtra("locale", speechLocale)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ContextCompat.startForegroundService(this, intent)
            else startService(intent)
        } catch (e: Exception) {
            Log.e("Jarvis", "Wake service error: ${e.message}")
        }
    }

    private fun stopWakeService() {
        try { startService(Intent(this, JarvisWakeService::class.java).setAction(JarvisWakeService.ACTION_STOP)) } catch (e: Exception) {}
    }

    private fun migrateAndLoadPreferences() {
        endpoint = prefs.getString("endpoint", endpoint).orEmpty().ifBlank { endpoint }
        model = prefs.getString("model", model).orEmpty().ifBlank { model }
        speechLocale = prefs.getString("speech_locale", speechLocale).orEmpty().ifBlank { "en-US" }
        wakeWord = prefs.getString("wake_word", wakeWord).orEmpty().ifBlank { "JARVIS" }
        speechRate = prefs.getFloat("speech_rate", speechRate).coerceIn(0.5f, 1.5f)
    }

    private fun startListening() {
        if (!JarvisVoiceEngine.isAvailable(this)) return
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
                    state = JarvisState.ERROR
                }
                override fun onResults(results: Bundle?) {
                    audioLevel = 0f
                    val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                    if (!text.isNullOrBlank()) handlePrompt(text)
                }
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            })
            try { recognizer.startListening(JarvisVoiceEngine.recognitionIntent(speechLocale, false)) } catch (_: Exception) {}
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

        val localReply = handleLocalCommand(prompt)
        if (localReply != null) {
            finishTurn(prompt, localReply)
            return
        }

        state = JarvisState.THINKING
        val key = apiKey
        if (key.isBlank()) {
            finishTurn(prompt, "Add an AI provider key in Settings.")
            return
        }

        activeTask?.cancel(true)
        activeTask = worker.submit {
            try {
                val result = AiProvider.answer(endpoint, model, key, prompt, history, "", emptyList(), false, false, false) { false }
                runOnUiThread { finishTurn(prompt, result) }
            } catch (e: Exception) {
                runOnUiThread { finishTurn(prompt, "Error: ${e.message}") }
            }
        }
    }

    private fun toggleTorch() {
        try {
            val cameraManager = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            cameraManager.setTorchMode(cameraManager.cameraIdList[0], !torchOn)
            torchOn = !torchOn
        } catch (e: Exception) {}
    }

    private fun safeStartActivity(intent: Intent) {
        try { startActivity(intent) } catch (e: Exception) {}
    }

    private fun runAccessibility(action: String, x: Float? = null, y: Float? = null, text: String? = null): String {
        val service = JarvisAccessibilityService.active ?: return "Accessibility service is not active."
        return when (action) {
            "home" -> { service.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_HOME); "Going home." }
            "back" -> { service.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK); "Going back." }
            else -> "Unknown action."
        }
    }

    private fun lockPhone(): String {
        val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val adminComponent = ComponentName(this, JarvisDeviceAdminReceiver::class.java)
        return if (dpm.isAdminActive(adminComponent)) { dpm.lockNow(); "Phone locked." } else { "Device admin permission required." }
    }

    private fun openInstalledApp(appName: String): String {
        val pm = packageManager
        for (pkg in pm.getInstalledPackages(0)) {
            val label = pm.getApplicationLabel(pkg.applicationInfo).toString()
            if (label.equals(appName, ignoreCase = true)) {
                val intent = pm.getLaunchIntentForPackage(pkg.packageName)
                if (intent != null) { safeStartActivity(intent); return "Opening $label." }
            }
        }
        return "App not found: $appName"
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
                color = Color(0xFFFF4444),
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
        color = Color.Black.copy(alpha = 0.9f),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.2f))
    ) {
        Column(modifier = Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("JARVIS Settings", color = TextMain, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
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
