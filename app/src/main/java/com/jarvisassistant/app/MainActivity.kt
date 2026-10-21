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
import android.media.AudioFocusRequest
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.media.MediaPlayer
import android.os.Bundle
import android.os.SystemClock
import android.provider.AlarmClock
import android.provider.Settings
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.View
import android.widget.VideoView
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.File
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.foundation.layout.offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.Future
import android.util.Log

private val Bg = Color(0xFF030303)
private val Panel = Color(0xFF101010)
private val Gold = Color(0xFFFFA91F)
private val Red = Color(0xFFFF4242)
private val Cyber = Color(0xFF4DE6D2)
private val TextMain = Color(0xFFF4F4F4)
private val TextMuted = Color(0xFF9B9B9B)

// 🟢 Changed enum name
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
    private var currentProactiveMode by mutableStateOf(JarvisProactiveEngine.Mode.NORMAL) // 🟢 FIX: Renamed property
    private var pendingConfirmation: String? = null
    private var pendingAgentConfirmation = false
    private var setupComplete by mutableStateOf(false)
    private var showSettings by mutableStateOf(false)
    private var showPermissionGuide by mutableStateOf(false)
    private var history by mutableStateOf(listOf<ChatTurn>())
    private var auditReport by mutableStateOf("")
    private var isEmergencyKillSwitchEnabled by mutableStateOf(false) // 🟢 FIX: Renamed property
    private var securityAudit by mutableStateOf(listOf<JarvisSecurityCenter.AuditEntry>())
    private var audioLevel by mutableStateOf(0f)
    private var visionText by mutableStateOf("")
    private var pendingVisionUri: Uri? = null
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
            responseText = "Microphone permission was not granted. Typed commands still work."
        }
    }
    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) toggleTorch()
        else responseText = "Camera permission is required by Android to control the flashlight."
    }

    private val takeVisionPhoto = registerForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        val uri = pendingVisionUri
        if (saved && uri != null) runVisionOcr(uri) else responseText = "Camera capture was cancelled."
    }

    private val pickVisionImage = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) runVisionOcr(uri) else responseText = "Image selection was cancelled."
    }

    private val calendarPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        responseText = if (granted) "Calendar context enabled. JARVIS can use upcoming events for proactive alerts." else "Calendar access was not granted. JARVIS will not read calendar events."
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        responseText = if (granted) "JARVIS notifications enabled." else "Notification permission was not granted; proactive alerts may stay hidden."
    }

    private val contactsPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        responseText = if (granted) "Contacts access enabled. Ask JARVIS to find a contact." else "Contacts access was not granted."
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
            isEmergencyKillSwitchEnabled = JarvisSecurityCenter.isKillSwitchEnabled(this) // 🟢 FIX: Updated reference
            recoveryStore.load()?.let { recovered ->
                JarvisAgentRuntime.restore(recovered)
                pendingAgentConfirmation = recovered.status == JarvisAgentRuntime.Status.WAITING_CONFIRMATION
                responseText = if (pendingAgentConfirmation) "A previous JARVIS agent task is waiting for your confirmation. Say yes/haan to resume or no/nahi to cancel." else "A previous JARVIS agent task was recovered and is ready to resume with agent status."
            }
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
            
            // 🟢 BUG FIX: Context.RECEIVER_NOT_EXPORTED crash on Android < 13 (API 33)
            val filter = IntentFilter(JarvisWakeService.ACTION_WAKE) // Start the JARVIS wake service
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                registerReceiver(wakeReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
            } else {
                registerReceiver(wakeReceiver, filter)
            }

            setContent {
                // Full-screen animated JARVIS orb video. It is muted and loops continuously.
                Box(modifier = androidx.compose.ui.Modifier.fillMaxSize().background(Bg)) {
                    AndroidView(
                        modifier = androidx.compose.ui.Modifier.fillMaxSize(),
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
                                    Log.e("Jarvis", "Interface video playback error: what=$what extra=$extra")
                                    responseText = "Interface video failed to play. Check the video file in res/raw."
                                    true
                                }
                            }
                        },
                        update = { videoView -> if (!videoView.isPlaying) videoView.start() }
                    )
                    // Tap the video to open controls; controls are rendered above the video.
                    if (showSettings) {
                        Surface(color = Panel.copy(alpha = 0.96f), modifier = androidx.compose.ui.Modifier.align(Alignment.BottomCenter).fillMaxWidth()) {
                            Column(modifier = androidx.compose.ui.Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
            if (!setupComplete) showSettings = false
        } catch (t: Throwable) {
            // Log the throwable (full stacktrace) and record it so you can inspect the real startup failure
            Log.e("Jarvis", "Startup failure in MainActivity.onCreate", t)
            try {
                JarvisDiagnostics.record(this, "startup", "ERROR", "onCreate failure: ${t.stackTraceToString()}")
            } catch (_: Throwable) { /* best-effort; keep going */ }
            // Surface an in-app error state. Do not swallow the error silently — we keep the stacktrace in logcat and diagnostics.
            state = JarvisState.ERROR
            responseText = "Startup failed — check Logcat for details: ${t.message ?: "unknown error"}"
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
            responseText = "Wake-word listening started. Say $wakeWord."
        } catch (e: Exception) {
            Log.e("Jarvis", "Could not start wake service", e)
            responseText = "Could not start wake-word listening: ${e.message ?: "unknown error"}"
        }
    }

    private fun stopWakeService() {
        try {
            startService(Intent(this, JarvisWakeService::class.java).setAction(JarvisWakeService.ACTION_STOP))
            responseText = "Wake-word listening stopped."
        } catch (e: Exception) {
            Log.e("Jarvis", "Could not stop wake service", e)
            stopService(Intent(this, JarvisWakeService::class.java))
        }
    }

    private fun migrateAndLoadPreferences() {
        val oldKey = prefs.getString("api_key", "").orEmpty()
        val decryptedKey = SecureVault.decrypt(oldKey)
        apiKey = if (decryptedKey.isNotBlank()) decryptedKey else oldKey
        if (oldKey.isNotBlank() && decryptedKey.isBlank()) {
            prefs.edit().putString("api_key", SecureVault.encrypt(oldKey)).apply()
        }
        endpoint = prefs.getString("endpoint", endpoint).orEmpty().ifBlank { endpoint }
        model = prefs.getString("model", model).orEmpty().ifBlank { model }
        speechLocale = prefs.getString("speech_locale", speechLocale).orEmpty().ifBlank { "en-US" }
        wakeWord = prefs.getString("wake_word", wakeWord).orEmpty().ifBlank { "JARVIS" }
        speechRate = prefs.getFloat("speech_rate", speechRate).coerceIn(0.5f, 1.5f)
        memoryEnabled = prefs.getBoolean("memory_enabled", true)
        seriousModeActive = prefs.getBoolean("serious_mode", false)
        cybersecurityModeActive = prefs.getBoolean("cybersecurity_mode", false)
        currentProactiveMode = JarvisProactiveEngine.mode(this) // 🟢 FIX: Updated reference
        setupComplete = prefs.getBoolean("setup_complete", false)
        val oldMemory = prefs.getString("memory", "").orEmpty()
        memory = SecureVault.decrypt(oldMemory).ifBlank { oldMemory }
        if (memoryEnabled && memory.isBlank()) memory = longMemory.context()
        if (oldMemory.isNotBlank() && SecureVault.decrypt(oldMemory).isBlank()) {
            prefs.edit().putString("memory", SecureVault.encrypt(oldMemory)).apply()
        }
        // Chat transcripts are session-only; remove any transcript saved by older versions.
        historyStore.clear()
        prefs.edit().remove("history").apply()
        history = emptyList()
    }

    private fun saveAiSettings(key: String, newEndpoint: String, newModel: String) {
        val safeEndpoint = newEndpoint.trim()
        if (!safeEndpoint.startsWith("https://", ignoreCase = true)) {
            responseText = "The provider endpoint must use HTTPS so your key is not sent over an unencrypted connection."
            return
        }
        apiKey = key.trim()
        endpoint = safeEndpoint
        model = newModel.trim().ifBlank { "gpt-4o-mini" }
        prefs.edit()
            .putString("api_key", SecureVault.encrypt(apiKey))
            .putString("endpoint", endpoint)
            .putString("model", model)
            .apply()
        showSettings = false
        responseText = "AI provider settings saved securely on this device."
    }

    private fun savePreferences(locale: String, word: String, rate: Float) {
        speechLocale = locale.trim().ifBlank { "en-US" }
        wakeWord = word.trim().ifBlank { "JARVIS" }
        speechRate = rate.coerceIn(0.5f, 1.5f)
        prefs.edit()
            .putString("speech_locale", speechLocale)
            .putString("wake_word", wakeWord)
            .putFloat("speech_rate", speechRate)
            .apply()
        applyTtsPreferences()
    }

    private fun setSeriousMode(enabled: Boolean) {
        seriousModeActive = enabled
        prefs.edit().putBoolean("serious_mode", enabled).apply()
        responseText = if (enabled) "Serious Mode is on. The core is red and responses will stay focused." 
        else "Serious Mode is off."
    }

    private fun setProactiveMode(mode: JarvisProactiveEngine.Mode) {
        currentProactiveMode = mode // 🟢 FIX: Updated reference
        JarvisProactiveEngine.setMode(this, mode)
        responseText = "Proactive Mode: ${mode.name}"
    }

    private fun setCybersecurityMode(enabled: Boolean) {
        cybersecurityModeActive = enabled
        prefs.edit().putBoolean("cybersecurity_mode", enabled).apply()
        auditReport = ""
        responseText = if (enabled) {
            "Cybersecurity Mode is on. Checks are limited to a target you own or have explicit authorization to assess."
        } else "Cybersecurity Mode is off."
    }

    private fun saveMemory(value: String) {
        memory = value.trim().take(4_000)
        prefs.edit().putString("memory", SecureVault.encrypt(memory)).apply()
        if (memory.isNotBlank()) longMemory.remember(memory, "profile")
        responseText = "Your local memory was saved encrypted on this device."
    }

    private fun clearMemory() {
        memory = ""
        longMemory.clear()
        prefs.edit().remove("memory").apply()
        responseText = "Local memory cleared."
    }

    private fun clearHistory() {
        history = emptyList()
        historyStore.clear()
        prefs.edit().remove("history").apply()
        responseText = "Current session history cleared. Long-term memory is unchanged."
    }

    private fun resetSetup() {
        prefs.edit().putBoolean("setup_complete", false).apply()
        setupComplete = false
        showSettings = false
        responseText = ""
    }

    private fun completeSetup() {
        setupComplete = true
        prefs.edit().putBoolean("setup_complete", true).apply()
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
            responseText = "Android speech recognition is unavailable on this device."
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
                responseText = "Voice recognition could not start. Check microphone permission and try again."
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

        if (isEmergencyKillSwitchEnabled) { // 🟢 FIX: Updated reference
            val normalizedSecurity = CommandNormalizer.normalize(prompt).lowercase()
            when {
                normalizedSecurity in setOf("security kill switch off", "disable emergency kill switch", "turn off emergency kill switch", "kill switch off") -> {
                    setEmergencyKillSwitch(false)
                    return
                }
                normalizedSecurity in setOf("security kill switch status", "security status", "privacy status") -> {
                    responseText = "Emergency kill switch is ON. Risky actions and agent execution are disabled."
                    finishTurn(prompt, responseText)
                    return
                }
                else -> {
                    responseText = "Emergency security lock is ON. Disable the kill switch to resume JARVIS actions."
                    finishTurn(prompt, responseText)
                    return
                }
            }
        }

        // A pending high-risk action must be explicitly confirmed or rejected.
        pendingConfirmation?.let { pending ->
            when {
                JarvisSecurity.isConfirmation(prompt) -> {
                    pendingConfirmation = null
                    responseText = "Confirmed. Executing the requested action."
                    val localReply = handleLocalCommand(pending)
                    if (localReply != null) {
                        responseText = localReply
                        finishTurn(pending, localReply)
                    } else {
                        responseText = "The confirmed action is not available on this device."
                        finishTurn(pending, responseText)
                    }
                    return
                }
                JarvisSecurity.isRejection(prompt) -> {
                    pendingConfirmation = null
                    responseText = "Cancelled. Nothing was executed."
                    finishTurn(prompt, responseText)
                    return
                }
                else -> {
                    responseText = "Please say yes/haan to confirm, or no/nahi to cancel."
                    speak(responseText)
                    return
                }
            }
        }

        if (pendingAgentConfirmation) {
            when {
                JarvisSecurity.isConfirmation(prompt) -> {
                    pendingAgentConfirmation = false
                    val result = JarvisAgentRuntime.confirmAndContinue { step -> executeAgentStep(step) }
                    responseText = formatAgentResult(result)
                    finishTurn(prompt, responseText)
                    return
                }
                JarvisSecurity.isRejection(prompt) -> {
                    pendingAgentConfirmation = false
                    JarvisAgentRuntime.cancel()
                    responseText = "Agent run cancelled. Nothing further will be executed."
                    finishTurn(prompt, responseText)
                    return
                }
                else -> {
                    responseText = "The agent is waiting for confirmation. Say yes/haan or no/nahi."
                    speak(responseText)
                    return
                }
            }
        }

        val securityDecision = JarvisSecurity.assess(prompt)
        JarvisSecurityCenter.audit(this, prompt, securityDecision.risk.name, if (securityDecision.requiresConfirmation) "confirmation required" else "allowed")
        securityAudit = JarvisSecurityCenter.auditEntries(this)
        JarvisDiagnostics.record(this, "lifecycle", "INFO", "JARVIS activity initialized")
        if (securityDecision.requiresConfirmation) {
            pendingConfirmation = prompt
            responseText = "This action involves ${securityDecision.reason}. Should I continue?"
            finishTurn(prompt, responseText)
            return
        }

        val normalized = CommandNormalizer.normalize(prompt, wakeWord)
        val seriousCommand = normalized.replace(",", "").trim()
        when {
            seriousCommand.endsWith("serious mode on") -> {
                setSeriousMode(true)
                finishTurn(prompt, responseText)
                return
            }
            seriousCommand.endsWith("serious mode off") -> {
                setSeriousMode(false)
                finishTurn(prompt, responseText)
                return
            }
            seriousCommand.endsWith("cybersecurity mode on") -> {
                setCybersecurityMode(true)
                finishTurn(prompt, responseText)
                return
            }
            seriousCommand.endsWith("cybersecurity mode off") -> {
                setCybersecurityMode(false)
                finishTurn(prompt, responseText)
                return
            }
        }

        val localReply = handleLocalCommand(prompt)
        if (localReply != null) {
            responseText = localReply
            finishTurn(prompt, localReply)
            return
        }

        if (!JarvisNetworkResilience.isOnline(this)) {
            JarvisNetworkResilience.queue(this, prompt)
            responseText = "You are offline. I saved this request securely. Say 'retry online' when connectivity returns."
            finishTurn(prompt, responseText)
            return
        }

        state = JarvisState.THINKING
        val capturedHistory = history.takeLast(8)
        // Only send query-relevant long-term memories to the provider; avoid uploading the whole vault on every turn.
        val capturedMemory = if (memoryEnabled) listOf(memory, longMemory.contextFor(prompt)).filter { it.isNotBlank() }.joinToString("\n") else ""
        val key = apiKey
        val aiEndpoint = endpoint
        val aiModel = model
        val serious = seriousModeActive
        val cyber = cybersecurityModeActive
        activeTask?.cancel(true)
        val generation = ++requestGeneration
        activeTask = worker.submit {
            val cancelled = { Thread.currentThread().isInterrupted || generation != requestGeneration }
            val isWeatherRequest = Regex("(?i).*(weather|forecast|mausam|मौसम).* ").containsMatchIn(prompt + " ")
            val researchRequested = InternetResearch.shouldSearch(prompt) && !isWeatherRequest
            val searchResults = if (researchRequested) InternetResearch.search(prompt, cancelled) else emptyList()
            if (cancelled()) return@submit
            val result = if (isWeatherRequest) {
                JarvisWeather.answer(prompt, cancelled)
            } else if (key.isBlank()) {
                if (researchRequested && searchResults.isNotEmpty()) {
                    "I found current source snippets, but an AI provider is not configured to synthesize them."
                } else {
                    "I can handle offline phone commands. Add an AI provider key in Settings for general answers."
                }
            } else {
                try {
                    AiProvider.answer(
                        aiEndpoint, aiModel, key, prompt, capturedHistory, capturedMemory,
                        searchResults, researchRequested, serious, cyber, cancelled
                    )
                } catch (e: Exception) {
                    "I couldn't reach the configured AI provider: ${e.message ?: "network unavailable"}."
                }
            }
            if (cancelled()) return@submit
            runOnUiThread {
                if (isFinishing || isDestroyed || generation != requestGeneration) return@runOnUiThread
                val answer = result + if (researchRequested && searchResults.isEmpty()) {
                    "\n\nCurrent web results could not be verified."
                } else ""
                responseText = answer
                history = (history + ChatTurn(prompt, answer, searchResults)).takeLast(40)
                speak(answer)
            }
        }
    }

    private fun setEmergencyKillSwitch(enabled: Boolean) {
        isEmergencyKillSwitchEnabled = enabled // 🟢 FIX: Updated reference
        JarvisSecurityCenter.setKillSwitch(this, enabled)
        securityAudit = JarvisSecurityCenter.auditEntries(this)
        JarvisDiagnostics.record(this, "lifecycle", "INFO", "JARVIS activity initialized")
        responseText = if (enabled) "Emergency security lock enabled. JARVIS will not execute actions until you disable it." else "Emergency security lock disabled. JARVIS is ready again."
        if (enabled) { pendingConfirmation = null; pendingAgentConfirmation = false; JarvisAgentRuntime.cancel() }
    }

    private fun handleLocalCommand(text: String): String? {
        val command = CommandNormalizer.normalize(text, wakeWord)
        if (command in setOf("help", "commands", "show commands", "what can you do")) {
            return "JARVIS commands: health, diagnostics, network status, performance status, integration status, agent status, agent cancel, daily briefing, proactive status, memory, screenshot,[...]"
        }
        if (command in setOf("security status", "privacy status", "security center")) {
            return "Emergency kill switch is ${if (isEmergencyKillSwitchEnabled) "ON" else "OFF"}. ${securityAudit.size} security audit entries are stored locally." // 🟢 FIX: Updated reference
        }
        if (command in setOf("security kill switch on", "enable emergency kill switch", "turn on emergency kill switch", "kill switch on")) {
            setEmergencyKillSwitch(true)
            return responseText
        }
        if (command in setOf("security kill switch off", "disable emergency kill switch", "turn off emergency kill switch", "kill switch off")) {
            setEmergencyKillSwitch(false)
            return responseText
        }
        if (command in setOf("clear security audit", "clear privacy audit")) {
            JarvisSecurityCenter.clearAudit(this)
            securityAudit = emptyList()
            return "Security audit cleared from this device."
        }
        if (command.matches(Regex("(what('?s| is) the )?time( now)?\\??"))) {
            return "It is ${java.text.SimpleDateFormat("h:mm a", Locale.getDefault()).format(java.util.Date())}."
        }
        if (command.matches(Regex("(what('?s| is) the )?date( today)?\\??"))) {
            return "Today is ${java.text.SimpleDateFormat("EEEE, d MMMM yyyy", Locale.getDefault()).format(java.util.Date())}."
        }
        Regex("^(?:set )?timer (?:for )?(\\d+)\\s*(seconds?|minutes?|hours?)$").find(command)?.let { match ->
            val number = match.groupValues[1].toIntOrNull() ?: return "I couldn't read that timer duration."
            val unit = match.groupValues[2]
            val multiplier = when {
                unit.startsWith("hour") -> 3600
                unit.startsWith("minute") -> 60
                else -> 1
            }
            val secondsLong = number.toLong() * multiplier
            if (secondsLong !in 1L..86_399L) return "Choose a timer between one second and 23 hours, 59 minutes."
            val seconds = secondsLong.toInt()
            safeStartActivity(Intent(AlarmClock.ACTION_SET_TIMER).putExtra(AlarmClock.EXTRA_LENGTH, seconds)
                .putExtra(AlarmClock.EXTRA_MESSAGE, "JARVIS timer").putExtra(AlarmClock.EXTRA_SKIP_UI, false))
            return "Opening Android Clock to set a $number $unit timer."
        }
        Regex("^(?:set )?(?:an )?alarm for (\\d{1,2}):(\\d{2})$").find(command)?.let { match ->
            val hour = match.groupValues[1].toInt()
            val minute = match.groupValues[2].toInt()
            if (hour !in 0..23 || minute !in 0..59) return "Use a valid 24-hour time, such as 07:30."
            safeStartActivity(Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_HOUR, hour)
                .putExtra(AlarmClock.EXTRA_MINUTES, minute).putExtra(AlarmClock.EXTRA_MESSAGE, "JARVIS alarm"))
            return "Opening Android Clock to set the alarm."
        }
        if (command in listOf("volume up", "turn volume up", "increase volume")) {
            return JarvisPhoneControl.setVolume(this, AudioManager.ADJUST_RAISE)
        }
        if (command in listOf("volume down", "turn volume down", "decrease volume")) {
            return JarvisPhoneControl.setVolume(this, AudioManager.ADJUST_LOWER)
        }
        if (command in listOf("mute", "mute volume")) {
            return JarvisPhoneControl.setVolume(this, AudioManager.ADJUST_MUTE)
        }
        if (command in listOf("play music", "resume music", "play media")) {
            return JarvisPhoneControl.mediaKey(this, android.view.KeyEvent.KEYCODE_MEDIA_PLAY)
        }
        if (command in listOf("pause music", "pause media", "stop music")) {
            return JarvisPhoneControl.mediaKey(this, android.view.KeyEvent.KEYCODE_MEDIA_PAUSE)
        }
        if (command in listOf("next song", "next track", "skip song")) {
            return JarvisPhoneControl.mediaKey(this, android.view.KeyEvent.KEYCODE_MEDIA_NEXT)
        }
        if (command in listOf("previous song", "previous track")) {
            return JarvisPhoneControl.mediaKey(this, android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS)
        }
        if (command in listOf("wifi settings", "open wifi", "turn on wifi", "turn off wifi")) {
            safeStartActivity(Intent(Settings.ACTION_WIFI_SETTINGS))
            return "Opening Wi-Fi settings. Android controls the actual Wi-Fi switch on modern versions."
        }
        if (command in listOf("bluetooth settings", "open bluetooth")) {
            safeStartActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
            return "Opening Bluetooth settings."
        }
        if (command in listOf("battery status", "battery percentage", "how much battery")) {
            val bm = getSystemService(BATTERY_SERVICE) as android.os.BatteryManager
            val pct = bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)
            return if (pct >= 0) "Battery is at $pct percent." else "Battery percentage is unavailable."
        }
        if (command in listOf("brightness settings", "screen brightness")) {
            safeStartActivity(Intent(Settings.ACTION_DISPLAY_SETTINGS))
            return "Opening display settings for brightness control."
        }
        Regex("^(?:set )?brightness (\\d{1,3})%?$", RegexOption.IGNORE_CASE).find(command)?.let { match ->
            return JarvisPhoneControl.brightness(this, match.groupValues[1].toIntOrNull() ?: 50)
        }
        if (command in listOf("copy last response", "copy response", "copy that")) {
            return JarvisPhoneControl.copy(this, responseText)
        }
        if (command in listOf("read clipboard", "clipboard", "clipboard read", "clipboard kya hai")) {
            return JarvisPhoneControl.readClipboard(this)
        }
        if (command in listOf("notification access", "notification access settings", "enable notification access")) {
            safeStartActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            return "Opening Android notification access settings. JARVIS only reads notifications after you explicitly enable access."
        }
        if (command in listOf("recent notifications", "read notifications", "notifications read karo")) {
            return JarvisNotificationListenerService.recent(this)
        }
        if (command in listOf("take screenshot", "screenshot lo", "screen shot lo", "capture screen")) {
            val service = JarvisAccessibilityService.active
            if (service == null) return "Enable JARVIS Accessibility first so Android can provide a screenshot."
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return "Screenshot automation requires Android 11 or newer."
            val file = File(cacheDir, "jarvis-screenshot-${System.currentTimeMillis()}.png")
            service.captureScreenshot(file) { ok, saved ->
                runOnUiThread { responseText = if (ok && saved != null) "Screenshot saved locally: ${saved.name}" else "Android did not provide a screenshot." }
            }
            return "Taking a screenshot using the enabled JARVIS Accessibility service."
        }
        if (command == "do not disturb settings" || command == "dnd settings") {
            safeStartActivity(Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS))
            return "Opening Do Not Disturb access settings."
        }
        if (command in listOf("flashlight", "toggle flashlight", "turn on flashlight", "turn off flashlight")) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                toggleTorch()
                return if (torchOn) "Flashlight turned on." else "Flashlight turned off."
            }
            cameraPermission.launch(Manifest.permission.CAMERA)
            return "Android will ask for camera permission before changing the flashlight."
        }
        if (command in listOf("start wake word", "enable wake word", "listen in background", "start background listening")) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                micPermission.launch(Manifest.permission.RECORD_AUDIO)
                return "Microphone permission is required before background wake listening can start."
            }
            startWakeService()
            return "JARVIS wake-word listening started. Say $wakeWord, then your command."
        }
        if (command in listOf("stop wake word", "disable wake word", "stop background listening")) {
            stopWakeService()
            return "Background wake-word listening stopped."
        }
        if (command == "open settings" || command == "phone settings") {
            safeStartActivity(Intent(Settings.ACTION_SETTINGS))
            return "Opening Android Settings."
        }
        if (command == "home" || command == "go home") return runAccessibility("home")
        if (command == "back" || command == "go back") return runAccessibility("back")
        if (command.startsWith("scroll up")) return runAccessibility("scroll-up")
        if (command.startsWith("scroll down")) return runAccessibility("scroll-down")
        Regex("^tap (\\d{1,5})[ ,]+(\\d{1,5})$").find(command)?.let { match ->
            return runAccessibility("tap", match.groupValues[1].toFloat(), match.groupValues[2].toFloat())
        }
        if (command.startsWith("type ")) {
            val typedText = command.replaceFirst(Regex("(?i)^type\\s+"), "")
            return runAccessibility("type", text = typedText)
        }
        if (command == "lock phone" || command == "lock my phone") return lockPhone()
        Regex("^(?:call|dial) (.+)$").find(command)?.let { match ->
            val number = match.groupValues[1].trim()
            safeStartActivity(Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", number, null)))
            return "Opening the dialer with that number. Android will wait for you to place the call."
        }
        Regex("^(?:text|sms|message)(?: to)? (\\+?[\\d ()-]{5,})$").find(command)?.let { match ->
            val number = match.groupValues[1].replace(Regex("[^+\\d]"), "")
            safeStartActivity(Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", number, null)))
            return "Opening an SMS draft. JARVIS has not sent a message."
        }
        Regex("^open (.+)$").find(command)?.let { match ->
            return openInstalledApp(match.groupValues[1].trim())
        }
        if (command in listOf("integration status", "integrations", "integration hub", "integrations status", "इंटीग्रेशन स्टेटस", "इंटीग्रेशन [...]") {
            val rows = JarvisIntegrationHub.list().joinToString("; ") { "${it.label}: ${it.status.name.lowercase()}${if (it.authRequired) " (account auth)" else ""}" }
            return "Integration Hub: $rows"
        }
        if (command.startsWith("open integration ")) {
            val name = command.removePrefix("open integration ").trim().replace(' ', '_').uppercase()
            val provider = JarvisIntegrationHub.Provider.entries.firstOrNull { it.name == name }
                ?: return "I don't recognize that integration. Say integration status to see supported providers."
            return if (JarvisIntegrationHub.openOfficialEntry(this, provider)) "Opening the official ${provider.name.replace('_', ' ').lowercase()} entry point." else "I couldn't open that integr[...]
        }
        if (command in listOf("what can you do", "capabilities", "help", "what can jarvis do")) {
            return JarvisCapabilities.describe(this)
        }
        if (command in listOf("list tasks", "show tasks", "my tasks", "मेरे टास्क", "टास्क दिखाओ")) {
            val tasks = taskStore.list()
            return if (tasks.isEmpty()) "You have no open tasks." else tasks.mapIndexed { i, t -> "${i + 1}. ${t.text}" }.joinToString("\n")
        }
        Regex("^(?:add task|create task|task|टास्क जोड़ो|टास्क बनाओ) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { m ->
            val task = taskStore.add(m.groupValues[1])
            return "Task added: ${task.text}"
        }
        // 🟢 FIX: Changed Regex to raw string """ ... """
        Regex("""^(?:complete task|finish task|done task|टास्क पूरा) (\
