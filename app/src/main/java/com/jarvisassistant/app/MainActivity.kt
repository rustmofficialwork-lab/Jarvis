package com.jarvisassistant.app // 🟢 Changed package name

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
import androidx.compose.foundation.layout.offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.Future

// 🟢 NOTE: Aapko apni baaki files me bhi "Maxx*" classes ko "Jarvis*" me rename karna hoga.
// Example: MaxxSecurity -> JarvisSecurity, MaxxVoiceEngine -> JarvisVoiceEngine, etc.
// Is file me sirf UI aur MainActivity ka rebranding kiya gaya hai.

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
    // 🟢 Changed SharedPreferences name
    private val prefs by lazy { getSharedPreferences("jarvis", Context.MODE_PRIVATE) }
    private val historyStore by lazy { HistoryStore(this) }
    
    // 🟢 NOTE: In classes ko aapko apni files me rename karna hoga
    private val longMemory by lazy { MaxxMemoryManager(this) } 
    private val taskStore by lazy { MaxxTaskStore(this) }
    private val recoveryStore by lazy { MaxxRecoveryStore(this) }
    
    private var tts: TextToSpeech? = null
    private var speechRecognizer: SpeechRecognizer? = null
    private var mediaPlayer: MediaPlayer? = null
    private var torchOn = false
    private var lastTranscript by mutableStateOf("")
    private var responseText by mutableStateOf("")
    private var state by mutableStateOf(JarvisState.IDLE) // 🟢 Changed
    private var apiKey by mutableStateOf("")
    private var endpoint by mutableStateOf("https://api.openai.com/v1/chat/completions")
    private var model by mutableStateOf("gpt-4o-mini")
    private var speechLocale by mutableStateOf("en-US")
    private var wakeWord by mutableStateOf("JARVIS") // 🟢 Changed default wake word
    private var speechRate by mutableStateOf(0.90f)
    private var memory by mutableStateOf("")
    private var memoryEnabled by mutableStateOf(true)
    private var seriousModeActive by mutableStateOf(false)
    private var cybersecurityModeActive by mutableStateOf(false)
    private var proactiveMode by mutableStateOf(MaxxProactiveEngine.Mode.NORMAL)
    private var pendingConfirmation: String? = null
    private var pendingAgentConfirmation = false
    private var setupComplete by mutableStateOf(false)
    private var showSettings by mutableStateOf(false)
    private var showPermissionGuide by mutableStateOf(false)
    private var history by mutableStateOf(listOf<ChatTurn>())
    private var auditReport by mutableStateOf("")
    private var emergencyKillSwitch by mutableStateOf(false)
    private var securityAudit by mutableStateOf(listOf<MaxxSecurityCenter.AuditEntry>())
    private var audioLevel by mutableStateOf(0f)
    private var visionText by mutableStateOf("")
    private var pendingVisionUri: Uri? = null
    private val worker = Executors.newSingleThreadExecutor()
    private var activeTask: Future<*>? = null
    private var requestGeneration = 0L
    private var continuousConversation = false
    
    private val wakeReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            lastTranscript = intent?.getStringExtra("phrase").orEmpty()
            state = JarvisState.LISTENING
            startListening()
        }
    }

    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) startListening() else {
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
        emergencyKillSwitch = MaxxSecurityCenter.isKillSwitchEnabled(this)
        recoveryStore.load()?.let { recovered ->
            MaxxAgentRuntime.restore(recovered)
            pendingAgentConfirmation = recovered.status == MaxxAgentRuntime.Status.WAITING_CONFIRMATION
            responseText = if (pendingAgentConfirmation) "A previous JARVIS agent task is waiting for your confirmation. Say yes/haan to resume or no/nahi to cancel." else "A previous JARVIS agent task was recovered and is ready to resume with agent status."
        }
        securityAudit = MaxxSecurityCenter.auditEntries(this)
        MaxxDiagnostics.record(this, "lifecycle", "INFO", "JARVIS activity initialized")
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
        val filter = IntentFilter(MaxxWakeService.ACTION_WAKE) // NOTE: Rename MaxxWakeService to JarvisWakeService in its file
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(wakeReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(wakeReceiver, filter)
        }

        setContent {
            JarvisTheme { // 🟢 Changed
                JarvisApp( // 🟢 Changed
                    state = state,
                    transcript = lastTranscript,
                    response = responseText,
                    visionText = visionText,
                    history = history,
                    sources = history.lastOrNull()?.sources.orEmpty(),
                    apiKey = apiKey,
                    endpoint = endpoint,
                    model = model,
                    speechLocale = speechLocale,
                    wakeWord = wakeWord,
                    speechRate = speechRate,
                    memory = memory,
                    memoryEnabled = memoryEnabled,
                    seriousMode = seriousModeActive,
                    cybersecurityMode = cybersecurityModeActive,
                    setupComplete = setupComplete,
                    showSettings = showSettings,
                    showPermissionGuide = showPermissionGuide,
                    microphoneGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED,
                    cameraGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED,
                    accessibilityEnabled = isAccessibilityEnabled(),
                    deviceAdminEnabled = (getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager)
                        .isAdminActive(ComponentName(this, MaxxDeviceAdminReceiver::class.java)),
                    auditReport = auditReport,
                    emergencyKillSwitch = emergencyKillSwitch,
                    securityAudit = securityAudit,
                    onEmergencyKillSwitch = ::setEmergencyKillSwitch,
                    onClearSecurityAudit = { MaxxSecurityCenter.clearAudit(this); securityAudit = emptyList() },
                    onCompleteSetup = ::completeSetup,
                    onOrbClick = ::onOrbClick,
                    audioLevel = audioLevel,
                    onSubmit = ::handlePrompt,
                    onSettings = { showSettings = true },
                    onCloseSettings = { showSettings = false },
                    onSaveAi = ::saveAiSettings,
                    onSavePreferences = ::savePreferences,
                    onMemoryEnabled = { memoryEnabled = it; prefs.edit().putBoolean("memory_enabled", it).apply() },
                    onSeriousMode = ::setSeriousMode,
                    onCybersecurityMode = ::setCybersecurityMode,
                    onSaveMemory = ::saveMemory,
                    onClearMemory = ::clearMemory,
                    onClearHistory = ::clearHistory,
                    onResetSetup = ::resetSetup,
                    onAccessibilitySetup = { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) },
                    onPermissions = { showPermissionGuide = true },
                    onClosePermissionGuide = { showPermissionGuide = false },
                    onDeviceAdmin = ::requestDeviceAdmin,
                    onAudit = ::runAuthorizedAudit,
                    onPlayVoiceSample = ::playVoiceSample,
                    onOpenSource = ::openSource
                )
            }
        }
        if (!setupComplete) showSettings = false
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
        wakeWord = prefs.getString("wake_word", wakeWord).orEmpty().ifBlank { "JARVIS" } // 🟢 Changed
        speechRate = prefs.getFloat("speech_rate", speechRate).coerceIn(0.5f, 1.5f)
        memoryEnabled = prefs.getBoolean("memory_enabled", true)
        seriousModeActive = prefs.getBoolean("serious_mode", false)
        cybersecurityModeActive = prefs.getBoolean("cybersecurity_mode", false)
        proactiveMode = MaxxProactiveEngine.mode(this)
        setupComplete = prefs.getBoolean("setup_complete", false)
        val oldMemory = prefs.getString("memory", "").orEmpty()
        memory = SecureVault.decrypt(oldMemory).ifBlank { oldMemory }
        if (memoryEnabled && memory.isBlank()) memory = longMemory.context()
        if (oldMemory.isNotBlank() && SecureVault.decrypt(oldMemory).isBlank()) {
            prefs.edit().putString("memory", SecureVault.encrypt(oldMemory)).apply()
        }
        val storedHistory = historyStore.read()
        if (storedHistory != "[]") {
            history = parseHistory(storedHistory)
        } else {
            // One-time migration from the old SharedPreferences history store.
            val legacy = prefs.getString("history", "[]").orEmpty()
            val decoded = SecureVault.decrypt(legacy)
            val legacyJson = if (decoded.isNotBlank()) decoded else legacy
            history = parseHistory(legacyJson)
            if (history.isNotEmpty()) historyStore.write(historyJson(history))
            if (legacy.isNotBlank()) prefs.edit().remove("history").apply()
        }
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
        wakeWord = word.trim().ifBlank { "JARVIS" } // 🟢 Changed
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

    private fun setProactiveMode(mode: MaxxProactiveEngine.Mode) {
        proactiveMode = mode
        MaxxProactiveEngine.setMode(this, mode)
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
        responseText = "Conversation history cleared from this device."
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
        if (!MaxxVoiceEngine.isAvailable(this)) {
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
                    responseText = MaxxVoiceEngine.errorMessage(error)
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
            val intent = MaxxVoiceEngine.recognitionIntent(speechLocale, preferOffline = false)
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

        if (emergencyKillSwitch) {
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
                MaxxSecurity.isConfirmation(prompt) -> {
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
                MaxxSecurity.isRejection(prompt) -> {
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
                MaxxSecurity.isConfirmation(prompt) -> {
                    pendingAgentConfirmation = false
                    val result = MaxxAgentRuntime.confirmAndContinue { step -> executeAgentStep(step) }
                    responseText = formatAgentResult(result)
                    finishTurn(prompt, responseText)
                    return
                }
                MaxxSecurity.isRejection(prompt) -> {
                    pendingAgentConfirmation = false
                    MaxxAgentRuntime.cancel()
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

        val securityDecision = MaxxSecurity.assess(prompt)
        MaxxSecurityCenter.audit(this, prompt, securityDecision.risk.name, if (securityDecision.requiresConfirmation) "confirmation required" else "allowed")
        securityAudit = MaxxSecurityCenter.auditEntries(this)
        MaxxDiagnostics.record(this, "lifecycle", "INFO", "JARVIS activity initialized")
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

        if (!MaxxNetworkResilience.isOnline(this)) {
            MaxxNetworkResilience.queue(this, prompt)
            responseText = "You are offline. I saved this request securely. Say 'retry online' when connectivity returns."
            finishTurn(prompt, responseText)
            return
        }

        state = JarvisState.THINKING
        val capturedHistory = history.takeLast(8)
        val capturedMemory = if (memoryEnabled) listOf(memory, longMemory.context()).filter { it.isNotBlank() }.joinToString("\n") else ""
        val key = apiKey
        val aiEndpoint = endpoint
        val aiModel = model
        val serious = seriousModeActive
        val cyber = cybersecurityModeActive
        activeTask?.cancel(true)
        val generation = ++requestGeneration
        activeTask = worker.submit {
            val cancelled = { Thread.currentThread().isInterrupted || generation != requestGeneration }
            val researchRequested = InternetResearch.shouldSearch(prompt)
            val searchResults = if (researchRequested) InternetResearch.search(prompt, cancelled) else emptyList()
            if (cancelled()) return@submit
            val result = if (key.isBlank()) {
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
                saveHistory()
                speak(answer)
            }
        }
    }

    private fun setEmergencyKillSwitch(enabled: Boolean) {
        emergencyKillSwitch = enabled
        MaxxSecurityCenter.setKillSwitch(this, enabled)
        securityAudit = MaxxSecurityCenter.auditEntries(this)
        MaxxDiagnostics.record(this, "lifecycle", "INFO", "JARVIS activity initialized")
        responseText = if (enabled) "Emergency security lock enabled. JARVIS will not execute actions until you disable it." else "Emergency security lock disabled. JARVIS is ready again."
        if (enabled) { pendingConfirmation = null; pendingAgentConfirmation = false; MaxxAgentRuntime.cancel() }
    }

    private fun handleLocalCommand(text: String): String? {
        val command = CommandNormalizer.normalize(text, wakeWord)
        if (command in setOf("help", "commands", "show commands", "what can you do")) {
            return "JARVIS commands: health, diagnostics, network status, performance status, integration status, agent status, agent cancel, daily briefing, proactive status, memory, screenshot, battery status, settings. High-risk actions always require confirmation."
        }
        if (command in setOf("security status", "privacy status", "security center")) {
            return "Emergency kill switch is ${if (emergencyKillSwitch) "ON" else "OFF"}. ${securityAudit.size} security audit entries are stored locally."
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
            MaxxSecurityCenter.clearAudit(this)
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
            return MaxxPhoneControl.setVolume(this, AudioManager.ADJUST_RAISE)
        }
        if (command in listOf("volume down", "turn volume down", "decrease volume")) {
            return MaxxPhoneControl.setVolume(this, AudioManager.ADJUST_LOWER)
        }
        if (command in listOf("mute", "mute volume")) {
            return MaxxPhoneControl.setVolume(this, AudioManager.ADJUST_MUTE)
        }
        if (command in listOf("play music", "resume music", "play media")) {
            return MaxxPhoneControl.mediaKey(this, android.view.KeyEvent.KEYCODE_MEDIA_PLAY)
        }
        if (command in listOf("pause music", "pause media", "stop music")) {
            return MaxxPhoneControl.mediaKey(this, android.view.KeyEvent.KEYCODE_MEDIA_PAUSE)
        }
        if (command in listOf("next song", "next track", "skip song")) {
            return MaxxPhoneControl.mediaKey(this, android.view.KeyEvent.KEYCODE_MEDIA_NEXT)
        }
        if (command in listOf("previous song", "previous track")) {
            return MaxxPhoneControl.mediaKey(this, android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS)
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
            return MaxxPhoneControl.brightness(this, match.groupValues[1].toIntOrNull() ?: 50)
        }
        if (command in listOf("copy last response", "copy response", "copy that")) {
            return MaxxPhoneControl.copy(this, responseText)
        }
        if (command in listOf("read clipboard", "clipboard", "clipboard read", "clipboard kya hai")) {
            return MaxxPhoneControl.readClipboard(this)
        }
        if (command in listOf("notification access", "notification access settings", "enable notification access")) {
            safeStartActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            return "Opening Android notification access settings. JARVIS only reads notifications after you explicitly enable access."
        }
        if (command in listOf("recent notifications", "read notifications", "notifications read karo")) {
            return MaxxNotificationListenerService.recent(this)
        }
        if (command in listOf("take screenshot", "screenshot lo", "screen shot lo", "capture screen")) {
            val service = MaxxAccessibilityService.active
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
        if (command in listOf("integration status", "integrations", "integration hub", "integrations status", "इंटीग्रेशन स्टेटस", "इंटीग्रेशन दिखाओ")) {
            val rows = MaxxIntegrationHub.list().joinToString("; ") { "${it.label}: ${it.status.name.lowercase()}${if (it.authRequired) " (account auth)" else ""}" }
            return "Integration Hub: $rows"
        }
        if (command.startsWith("open integration ")) {
            val name = command.removePrefix("open integration ").trim().replace(' ', '_').uppercase()
            val provider = MaxxIntegrationHub.Provider.entries.firstOrNull { it.name == name }
                ?: return "I don't recognize that integration. Say integration status to see supported providers."
            return if (MaxxIntegrationHub.openOfficialEntry(this, provider)) "Opening the official ${provider.name.replace('_', ' ').lowercase()} entry point." else "I couldn't open that integration."
        }
        if (command in listOf("what can you do", "capabilities", "help", "what can jarvis do")) {
            return MaxxCapabilities.describe(this)
        }
        if (command in listOf("list tasks", "show tasks", "my tasks", "मेरे टास्क", "टास्क दिखाओ")) {
            val tasks = taskStore.list()
            return if (tasks.isEmpty()) "You have no open tasks." else tasks.mapIndexed { i, t -> "${i + 1}. ${t.text}" }.joinToString("\n")
        }
        Regex("^(?:add task|create task|task|टास्क जोड़ो|टास्क बनाओ) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { m ->
            val task = taskStore.add(m.groupValues[1])
            return "Task added: ${task.text}"
        }
        Regex("^(?:complete task|finish task|done task|टास्क पूरा) (\d+)$", RegexOption.IGNORE_CASE).find(command)?.let { m ->
            val tasks = taskStore.list()
            val index = m.groupValues[1].toIntOrNull()?.minus(1) ?: -1
            val task = tasks.getOrNull(index)
            return if (task != null && taskStore.complete(task.id)) "Completed: ${task.text}" else "I couldn't find that open task."
        }
        if (command in listOf("daily briefing", "morning briefing", "brief me", "आज का ब्रीफिंग")) {
            val context = MaxxContextEngine.snapshot(this)
            val tasks = taskStore.list().take(5)
            val event = context.nextEvent?.let { "Next calendar event: ${it.title}." } ?: "No upcoming calendar event found."
            val taskText = if (tasks.isEmpty()) "No open tasks." else "Open tasks: " + tasks.joinToString("; ") { it.text }
            return "Battery ${context.batteryPercent}%${if (context.charging) " and charging" else ""}. $event $taskText"
        }
        if (command in listOf("show memories", "my memories", "what do you remember", "यादें दिखाओ", "तुम्हें क्या याद है")) {
            val memories = longMemory.list().asReversed().take(20)
            return if (memories.isEmpty()) "I don't have any saved long-term memories." else memories.mapIndexed { i, m -> "${i + 1}. [${m.kind}] ${m.text}" }.joinToString("\n")
        }
        Regex("^(?:show memories of|show memory|search memory|search memories|याद में खोजो) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { match ->
            val found = longMemory.search(match.groupValues[1]).asReversed().take(20)
            return if (found.isEmpty()) "I couldn't find matching memories." else found.mapIndexed { i, m -> "${i + 1}. [${m.kind}] ${m.text}" }.joinToString("\n")
        }
        Regex("^(?:remember|remember that|याद रखो|याद रखना) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { match ->
            longMemory.remember(match.groupValues[1], MaxxMemoryManager.Kind.USER.wire)
            return "I'll remember that on this device."
        }
        Regex("^(?:remember preference|save preference|पसंद याद रखो) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { match ->
            longMemory.remember(match.groupValues[1], MaxxMemoryManager.Kind.PREFERENCE.wire)
            return "Saved as a preference."
        }
        Regex("^(?:remember person|save person|व्यक्ति याद रखो) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { match ->
            longMemory.remember(match.groupValues[1], MaxxMemoryManager.Kind.PERSON.wire)
            return "Saved as a person-related memory."
        }
        Regex("^(?:remember project|save project|प्रोजेक्ट याद रखो) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { match ->
            longMemory.remember(match.groupValues[1], MaxxMemoryManager.Kind.PROJECT.wire)
            return "Saved as a project memory."
        }
        Regex("^(?:remember event|save event|यादगार घटना याद रखो) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { match ->
            longMemory.remember(match.groupValues[1], MaxxMemoryManager.Kind.EPISODIC.wire)
            return "Saved as an episodic memory."
        }
        Regex("^(?:forget|भूल जाओ) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { match ->
            val removed = longMemory.forget(match.groupValues[1])
            return if (removed > 0) "I removed $removed matching long-term memor${if (removed == 1) "y" else "ies"} from this device." else "I couldn't find a matching memory."
        }
        if (command in listOf("clear all memories", "delete all memories", "forget everything you remember", "सारी यादें मिटाओ")) {
            longMemory.clear()
            memory = ""
            prefs.edit().remove("memory").apply()
            return "All long-term memories were cleared from this device."
        }
        if (command in listOf("open calendar", "calendar kholo", "कैलेंडर खोलो")) {
            return if (MaxxProductivity.openCalendar(this)) "Opening Calendar." else "I couldn't open a calendar app."
        }
        if (command in listOf("create calendar event", "new calendar event", "meeting schedule")) {
            return if (MaxxProductivity.createEvent(this, "JARVIS event")) "Opening a new calendar event." else "I couldn't open the calendar event editor."
        }
        if (command in listOf("set reminder", "create reminder", "reminder lagao", "रिमाइंडर लगाओ")) {
            return if (MaxxProductivity.createReminder(this, "JARVIS reminder")) "Opening the Android alarm/reminder flow." else "I couldn't open the reminder flow."
        }
        Regex("^(?:map|maps|navigate to|directions to) (.+)$").find(command)?.let { match ->
            return if (MaxxProductivity.openMaps(this, match.groupValues[1])) "Opening Maps for ${match.groupValues[1]}." else "I couldn't open Maps."
        }
        if (command in listOf("open camera", "camera kholo", "कैमरा खोलो")) {
            return if (MaxxVision.openCamera(this)) "Opening the camera." else "I couldn't open the camera."
        }
        if (command in listOf("take photo", "capture photo", "photo lo", "फोटो लो", "तस्वीर लो", "scan document", "document scan", "स्कैन करो")) {
            return startVisionCapture()
        }
        if (command in listOf("choose photo", "pick image", "select image", "gallery kholo", "फोटो चुनो", "इमेज चुनो")) {
            pickVisionImage.launch("image/*")
            return "Choose an image and JARVIS will read visible text from it on-device."
        }
        if (command in listOf("read image text", "read photo", "ocr", "image text", "फोटो का टेक्स्ट पढ़ो", "इमेज का टेक्स्ट पढ़ो")) {
            if (visionText.isBlank()) {
                pickVisionImage.launch("image/*")
                return "Choose an image and JARVIS will extract its text on-device."
            }
            return visionText
        }
        if (command in listOf("open email", "email kholo", "ईमेल खोलो")) {
            return if (MaxxProductivity.openEmail(this)) "Opening your email app." else "I couldn't open an email app."
        }
        if (command in listOf("open youtube", "youtube kholo", "यूट्यूब खोलो")) {
            return if (MaxxProductivity.openYouTube(this)) "Opening YouTube." else "I couldn't open YouTube."
        }
        if (command in listOf("open spotify", "spotify kholo", "स्पॉटिफाई खोलो")) {
            return if (MaxxProductivity.openSpotify(this)) "Opening Spotify." else "I couldn't open Spotify."
        }
        if (command in listOf("open drive", "drive kholo", "गूगल ड्राइव खोलो", "ड्राइव खोलो")) {
            return if (MaxxProductivity.openDrive(this)) "Opening Google Drive." else "I couldn't open Google Drive."
        }
        if (command in listOf("open whatsapp", "whatsapp kholo", "व्हाट्सऐप खोलो", "व्हाट्सएप खोलो")) {
            return if (MaxxProductivity.openWhatsApp(this)) "Opening WhatsApp." else "I couldn't open WhatsApp."
        }
        if (command in listOf("open telegram", "telegram kholo", "टेलीग्राम खोलो")) {
            return if (MaxxProductivity.openTelegram(this)) "Opening Telegram." else "I couldn't open Telegram."
        }
        Regex("^(?:find contact|contact search|contact dhundo|कॉन्टैक्ट ढूंढो) (.+)$", RegexOption.IGNORE_CASE).find(command)?.let { m ->
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
                contactsPermission.launch(Manifest.permission.READ_CONTACTS)
                return "Android will ask for contacts permission. JARVIS will only read contact names and phone numbers after you allow it."
            }
            return MaxxProductivity.findContact(this, m.groupValues[1].trim()) ?: "Contacts access is not available."
        }
        if (command in listOf("enable contacts", "contacts access on", "contacts on", "कॉन्टैक्ट एक्सेस चालू करो")) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) return "Contacts access is already enabled."
            contactsPermission.launch(Manifest.permission.READ_CONTACTS)
            return "Android will ask for contacts permission."
        }
        if (command in listOf("notification settings", "notification settings kholo")) {
            return if (MaxxProductivity.openNotificationSettings(this)) "Opening notification settings." else "I couldn't open notification settings."
        }
        if (command in listOf("enable notifications", "notifications on", "notification access on")) {
            if (Build.VERSION.SDK_INT >= 33) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            return "Android will ask for notification permission."
        }
        if (command in listOf("enable calendar context", "calendar context on", "calendar context enable", "calendar access on")) {
            if (MaxxContextEngine.calendarAccessEnabled(this)) return "Calendar context is already enabled."
            calendarPermission.launch(Manifest.permission.READ_CALENDAR)
            return "Android will ask for calendar permission. JARVIS will only read upcoming events after you allow it."
        }
        if (command in listOf("disable calendar context", "calendar context off", "calendar access off")) {
            return "Calendar access can be revoked from Android Settings → App permissions. JARVIS will stop using calendar context once permission is revoked."
        }
        if (command in listOf("daily briefing", "morning briefing", "brief me", "आज का ब्रीफिंग")) {
            return MaxxProactiveEngine.dailyBriefing(this)
        }
        if (command in listOf("proactive suggestions", "what should i know", "what should i know now", "अभी क्या जरूरी है", "क्या जरूरी है")) {
            MaxxProactiveEngine.evaluate(this)
            return "I checked your current context, calendar and upcoming tasks and applied the proactive priority rules."
        }
        if (command in listOf("context status", "show context", "what is my context")) {
            val c = MaxxContextEngine.snapshot(this)
            val event = c.nextEvent?.let { "next event: ${it.title}" } ?: "no upcoming calendar event available"
            return "Context: battery ${c.batteryPercent}%${if (c.charging) " (charging)" else ""}; $event; proactive mode ${proactiveMode.name}."
        }
        if (command in setOf("online status", "network status", "internet status", "ऑनलाइन स्टेटस", "नेटवर्क स्टेटस")) {
            val pending = MaxxNetworkResilience.peek(this)
            return "Network is ${if (MaxxNetworkResilience.isOnline(this)) "online" else "offline"}. ${if (pending != null) "1 request is queued for explicit retry." else "No request is queued."}"
        }
        if (command in setOf("retry online", "retry network", "retry queued request", "try again online", "ऑनलाइन फिर से कोशिश")) {
            if (!MaxxNetworkResilience.isOnline(this)) return "Still offline. I will not send the queued request yet."
            val pending = MaxxNetworkResilience.take(this) ?: return "No offline request is waiting."
            handlePrompt(pending.prompt)
            return "Retrying the saved request now."
        }
        if (command in setOf("clear offline queue", "clear network queue", "ऑफलाइन क्यू साफ करो")) {
            MaxxNetworkResilience.clear(this)
            return "Offline request queue cleared."
        }
        if (command in listOf("proactive test", "test notification")) {
            MaxxProactiveEngine.notify(this, "JARVIS", "Proactive assistant notifications are working.", important = true)
            return "I sent a local JARVIS test notification."
        }
        if (command in listOf("proactive status", "proactive mode", "proactive intelligence status")) {
            return "Proactive Mode is ${proactiveMode.name}. Priority engine is active; calendar context is ${if (MaxxContextEngine.calendarAccessEnabled(this)) "enabled" else "disabled"}."
        }
        Regex("^proactive mode (off|low|normal|high)$").find(command)?.let { match ->
            setProactiveMode(MaxxProactiveEngine.Mode.valueOf(match.groupValues[1].uppercase()))
            return "Proactive Mode set to ${proactiveMode.name}."
        }
        if (command in listOf("vision status", "screen understanding")) {
            return if (MaxxVision.accessibilityAvailable()) "Screen understanding is available through the enabled Accessibility service." else "Enable JARVIS Accessibility to let JARVIS inspect the currently focused UI text."
        }
        if (command.startsWith("plan ") || command.startsWith("agent plan ")) {
            val goal = command.removePrefix("agent ").removePrefix("plan ").trim()
            val plan = MaxxAgent.plan(goal)
            return if (plan.steps.isEmpty()) "I understand the goal, but no safe local tool was selected yet. Online AI can plan it further." else
                "Plan ready: " + plan.steps.joinToString(" → ") { it.tool.name + if (it.requiresConfirmation) " (confirm)" else "" }
        }
        if (command.startsWith("agent run ")) {
            val goal = command.removePrefix("agent run ").trim()
            if (goal.isBlank()) return "Tell me the goal after 'agent run'."
            val plan = MaxxAgent.plan(goal)
            if (plan.steps.isEmpty()) return "No executable local tool was selected. Online AI reasoning is needed for this goal."
            if (plan.needsOnlineReasoning && plan.steps.any { it.tool == MaxxToolSystem.Tool.WEB_RESEARCH }) {
                return "This plan includes web research. Use the normal JARVIS request flow for the online research portion; the local agent runtime will not pretend it executed web work."
            }
            MaxxDiagnostics.record(this, "agent", "INFO", "Agent started: ${plan.steps.size} step(s)")
            val result = MaxxAgentRuntime.start(plan) { step -> executeAgentStep(step) }
            recoveryStore.save(result.state)
            MaxxDiagnostics.record(this, "agent", if (result.state.status == MaxxAgentRuntime.Status.FAILED) "ERROR" else "INFO", "Agent ${result.state.status.name.lowercase()} at step ${result.state.nextIndex}/${result.state.plan.steps.size}")
            if (result.needsConfirmation) pendingAgentConfirmation = true
            return formatAgentResult(result)
        }
        if (command in listOf("performance status", "resource status", "memory status", "performance", "सिस्टम स्टेटस", "परफॉर्मेंस स्टेटस")) {
            return MaxxResourceManager.status(this)
        }
        if (command in listOf("health", "health status", "diagnostics", "diagnostic status")) {
            return MaxxDiagnostics.health(this)
        }
        if (command in listOf("diagnostics report", "health report", "troubleshooting report")) {
            return MaxxDiagnostics.report(this)
        }
        if (command in listOf("clear diagnostics", "diagnostics clear")) {
            MaxxDiagnostics.clear(this)
            return "Local diagnostics cleared."
        }
        if (command == "agent status") {
            val current = MaxxAgentRuntime.current() ?: return "No agent run is active."
            return "Agent ${current.status.name.lowercase()}: step ${current.nextIndex}/${current.plan.steps.size}. Goal: ${current.goal}"
        }
        if (command == "agent cancel") {
            pendingAgentConfirmation = false
            val cancelled = MaxxAgentRuntime.cancel()
            recoveryStore.clear()
            if (cancelled != null) MaxxDiagnostics.record(this, "agent", "WARN", "Agent cancelled at step ${cancelled.nextIndex}")
            return if (cancelled != null) "Agent run cancelled." else "No agent run is active."
        }
        return null
    }

    private fun executeAgentStep(step: MaxxAgent.Step): String? {
        return when (step.tool) {
            MaxxToolSystem.Tool.CALENDAR, MaxxToolSystem.Tool.MAPS, MaxxToolSystem.Tool.CAMERA,
            MaxxToolSystem.Tool.EMAIL, MaxxToolSystem.Tool.YOUTUBE, MaxxToolSystem.Tool.SPOTIFY,
            MaxxToolSystem.Tool.DRIVE, MaxxToolSystem.Tool.WHATSAPP, MaxxToolSystem.Tool.TELEGRAM,
            MaxxToolSystem.Tool.APP_LAUNCH, MaxxToolSystem.Tool.SCREEN -> handleLocalCommand(step.command)
            MaxxToolSystem.Tool.PHONE, MaxxToolSystem.Tool.SMS, MaxxToolSystem.Tool.SMART_HOME -> handleLocalCommand(step.command)
            else -> null
        }
    }

    private fun formatAgentResult(result: MaxxAgentRuntime.Result): String {
        val state = result.state
        if (result.needsConfirmation) {
            val tool = state.plan.steps.getOrNull(state.nextIndex)?.tool?.name ?: "action"
            return "Agent paused before ${tool.lowercase()} because confirmation is required. Say yes/haan to continue or no/nahi to cancel."
        }
        return when (state.status) {
            MaxxAgentRuntime.Status.COMPLETED -> "Agent completed the goal in ${state.plan.steps.size} step(s)."
            MaxxAgentRuntime.Status.FAILED -> "Agent stopped safely at step ${state.nextIndex}/${state.plan.steps.size}."
            MaxxAgentRuntime.Status.CANCELLED -> "Agent run cancelled."
            else -> "Agent ${state.status.name.lowercase()}: ${state.nextIndex}/${state.plan.steps.size} step(s) processed."
        }
    }

    private fun safeStartActivity(intent: Intent): Boolean {
        return try {
            if (intent.resolveActivity(packageManager) == null) {
                responseText = "No Android app or settings screen can handle that action on this device."
                false
            } else {
                startActivity(intent)
                true
            }
        } catch (e: Exception) {
            responseText = "Android blocked that action: ${e.message ?: "unsupported"}."
            false
        }
    }

    private fun runAccessibility(command: String, x: Float = 0f, y: Float = 0f, text: String = ""): String {
        val service = MaxxAccessibilityService.active
        if (service == null) {
            return "Enable JARVIS Accessibility in Settings → Permissions first. Android requires you to turn it on manually."
        }
        val accepted = service.performCommand(command, x, y, text)
        return if (accepted) "Android accepted the $command command."
        else "Android could not perform that command on the current screen."
    }

    private fun openInstalledApp(label: String): String {
        val query = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val matches = packageManager.queryIntentActivities(query, 0)
        val target = matches.firstOrNull {
            it.loadLabel(packageManager).toString().equals(label, ignoreCase = true)
        } ?: matches.firstOrNull {
            it.loadLabel(packageManager).toString().contains(label, ignoreCase = true)
        } ?: return "I couldn't find an installed app named “$label”."
        val info = target.activityInfo
        val launch = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
            .setClassName(info.packageName, info.name)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            startActivity(launch)
            "Opening ${target.loadLabel(packageManager)}."
        } catch (_: Exception) {
            "Android did not allow that app to open."
        }
    }

    private fun startVisionCapture(): String {
        return try {
            val dir = File(cacheDir, "vision").apply { mkdirs() }
            val file = File(dir, "capture_${System.currentTimeMillis()}.jpg")
            val uri = FileProvider.getUriForFile(this, "${BuildConfig.APPLICATION_ID}.fileprovider", file)
            pendingVisionUri = uri
            takeVisionPhoto.launch(uri)
            "Camera opened. After capture, JARVIS will extract visible text on-device."
        } catch (e: Exception) {
            "I couldn't start the camera capture: ${e.message ?: "unsupported"}."
        }
    }

    private fun runVisionOcr(uri: Uri) {
        responseText = "Reading image text on-device…"
        state = JarvisState.THINKING
        MaxxVisionEngine.recognizeText(this, uri) { result ->
            runOnUiThread {
                state = restingState()
                result.onSuccess { ocr ->
                    visionText = if (ocr.text.isBlank()) "No readable text detected." else ocr.text.take(6000)
                    responseText = if (ocr.text.isBlank()) "No readable text detected." else "I found ${ocr.blocks} text block(s)."
                    pendingVisionUri = null
                }.onFailure { error ->
                    visionText = ""
                    responseText = "I couldn't read that image: ${error.message ?: "OCR failed"}."
                    pendingVisionUri = null
                }
            }
        }
    }

    private fun toggleTorch() {
        try {
            val camera = getSystemService(CAMERA_SERVICE) as CameraManager
            val cameraId = camera.cameraIdList.firstOrNull { camera.getCameraCharacteristics(it)
                .get(android.hardware.camera2.CameraCharacteristics.FLASH_INFO_AVAILABLE) == true }
            if (cameraId == null) {
                responseText = "This device does not report a controllable flashlight."
                return
            }
            torchOn = !torchOn
            camera.setTorchMode(cameraId, torchOn)
        } catch (e: Exception) {
            responseText = "Android could not control the flashlight: ${e.message ?: "unsupported"}."
        }
    }

    private fun lockPhone(): String {
        val manager = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val admin = ComponentName(this, MaxxDeviceAdminReceiver::class.java)
        if (manager.isAdminActive(admin)) {
            manager.lockNow()
            return "Phone locked using Android's active device-admin permission."
        }
        val activate = Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN)
            .putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, admin)
            .putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, "JARVIS can lock this phone only when you explicitly activate its Android device-admin permission.")
        startActivity(activate)
        return "Android is showing the optional device-admin screen. Activate it only if you want JARVIS to lock the phone."
    }

    private fun requestDeviceAdmin() {
        val manager = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val admin = ComponentName(this, MaxxDeviceAdminReceiver::class.java)
        if (!manager.isAdminActive(admin)) {
            startActivity(
                Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN)
                    .putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, admin)
                    .putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, "This permission allows JARVIS to lock the phone only when you explicitly ask.")
            )
        } else {
            responseText = "Phone-lock permission is currently enabled in Android."
        }
    }

    private fun runAuthorizedAudit(host: String, authorized: Boolean) {
        if (!cybersecurityModeActive) {
            auditReport = "Turn on Cybersecurity Mode before running an audit."
            return
        }
        if (!authorized) {
            auditReport = "Confirm that you own this target or have explicit permission before any check. No network request was made."
            return
        }
        auditReport = "Checking DNS, HTTPS and common security headers for $host…"
        Thread {
            val report = try {
                val result = CybersecurityAudit.run(host)
                buildString {
                    append("Passive HTTPS review: ${result.target}\n")
                    append("Observed: ${result.tls}\n")
                    append("DNS addresses: ${result.addresses.joinToString()}\n\n")
                    result.findings.forEach { finding ->
                        append("${finding.severity} — ${finding.evidence}\n")
                        append("Impact: ${finding.impact}\n")
                        append("Remediation: ${finding.remediation}\n\n")
                    }
                    append("Scope: one DNS lookup and one HTTPS HEAD request only. No ports, credentials, crawling or exploit tests.")
                }
            } catch (e: Exception) {
                "Audit could not complete: ${e.message ?: "network error"}. No wider scan was attempted."
            }
            runOnUiThread { auditReport = report }
        }.start()
    }

    private fun isAccessibilityEnabled(): Boolean {
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES).orEmpty()
        return enabled.contains(packageName, ignoreCase = true) &&
            enabled.contains(MaxxAccessibilityService::class.java.simpleName, ignoreCase = true)
    }

    private fun finishTurn(prompt: String, answer: String) {
        MaxxSecurityCenter.audit(this, prompt, "ACTION", "completed")
        securityAudit = MaxxSecurityCenter.auditEntries(this)
        MaxxDiagnostics.record(this, "lifecycle", "INFO", "JARVIS activity initialized")
        history = (history + ChatTurn(prompt, answer)).takeLast(40)
        saveHistory()
        speak(answer)
    }

    private fun historyJson(turns: List<ChatTurn>): String {
        val array = JSONArray()
        turns.takeLast(40).forEach { turn ->
            val sources = JSONArray()
            turn.sources.take(5).forEach { source ->
                sources.put(JSONObject().put("title", source.title).put("url", source.url).put("excerpt", source.excerpt.take(500)))
            }
            array.put(JSONObject()
                .put("u", turn.user.take(4_000))
                .put("a", turn.assistant.take(8_000))
                .put("sources", sources))
        }
        return array.toString()
    }

    private fun saveHistory() {
        history = history.takeLast(40)
        historyStore.write(historyJson(history))
    }

    private fun parseHistory(raw: String): List<ChatTurn> = try {
        val json = JSONArray(raw)
        (0 until json.length()).mapNotNull { index ->
            val item = json.optJSONObject(index) ?: return@mapNotNull null
            val sourceJson = item.optJSONArray("sources") ?: JSONArray()
            val sources = (0 until sourceJson.length()).mapNotNull { sourceIndex ->
                sourceJson.optJSONObject(sourceIndex)?.let {
                    ResearchSource(it.optString("title"), it.optString("url"), it.optString("excerpt"))
                }
            }
            ChatTurn(item.optString("u"), item.optString("a"), sources)
        }.takeLast(40)
    } catch (_: Exception) { emptyList() }

    private fun openSource(url: String) {
        if (!url.startsWith("https://")) return
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (_: Exception) {
            responseText = "No browser is available to open that source."
        }
    }

    private fun speak(text: String) {
        if (tts == null) {
            state = restingState()
            return
        }
        state = JarvisState.SPEAKING
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "jarvis-${SystemClock.uptimeMillis()}")
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) applyTtsPreferences()
    }

    private fun applyTtsPreferences() {
        tts?.let { engine ->
            MaxxVoiceEngine.configureTts(engine, speechLocale, speechRate, seriousModeActive)
        }
    }

    private fun restingState(): JarvisState = when {
        seriousModeActive -> JarvisState.SERIOUS
        cybersecurityModeActive -> JarvisState.CYBERSECURITY
        else -> JarvisState.IDLE
    }

    private fun playVoiceSample() {
        mediaPlayer?.release()
        // 🟢 NOTE: Rename maxx_voice_sample to jarvis_voice_sample in res/raw
        mediaPlayer = MediaPlayer.create(this, R.raw.maxx_voice_sample)?.also { player ->
            player.start()
            player.setOnCompletionListener { it.release(); mediaPlayer = null }
        }
    }

    private fun startWakeService() {
        if (Build.VERSION.SDK_INT >= 29 && ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return
        val intent = Intent(this, MaxxWakeService::class.java) // NOTE: Rename MaxxWakeService to JarvisWakeService
            .putExtra("wake", wakeWord)
            .putExtra("locale", speechLocale)
        try {
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
        } catch (_: Exception) { responseText = "Android did not allow the background JARVIS listener to start." }
    }

    private fun stopWakeService() {
        try { stopService(Intent(this, MaxxWakeService::class.java)) } catch (_: Exception) {}
    }

    override fun onResume() {
        super.onResume()
        MaxxDiagnostics.record(this, "resource", "INFO", "Resources: ${MaxxResourceManager.snapshot(this).pressure.name.lowercase()}")
        MaxxProactiveEngine.evaluate(this)
    }

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        val severity = if (level >= android.content.ComponentCallbacks2.TRIM_MEMORY_RUNNING_CRITICAL) "WARN" else "INFO"
        MaxxDiagnostics.record(this, "resource", severity, "Android trim-memory level=$level")
        if (level >= android.content.ComponentCallbacks2.TRIM_MEMORY_RUNNING_CRITICAL) {
            // 🟢 BUG FIX: Safe cancellation if worker is already shutdown
            try {
                activeTask?.cancel(true)
            } catch (_: Exception) { }
            activeTask = null
            responseText = "Android reported critical memory pressure. JARVIS paused the active background request safely."
            state = JarvisState.IDLE
        }
    }

    override fun onDestroy() {
        requestGeneration++
        speechRecognizer?.cancel()
        speechRecognizer?.destroy()
        tts?.stop()
        tts?.shutdown()
        mediaPlayer?.release()
        try {
            activeTask?.cancel(true)
        } catch (_: Exception) { }
        worker.shutdownNow()
        stopWakeService()
        try { unregisterReceiver(wakeReceiver) } catch (_: Exception) {}
        super.onDestroy()
    }
}

@Composable
private fun JarvisTheme(content: @Composable () -> Unit) { // 🟢 Changed
    MaterialTheme(
        colorScheme = darkColorScheme(
            background = Bg, surface = Bg, primary = Gold, onBackground = TextMain, onSurface = TextMain
        ),
        content = content
    )
}

@Composable
private fun JarvisApp( // 🟢 Changed
    state: JarvisState,
    transcript: String,
    response: String,
    visionText: String,
    history: List<ChatTurn>,
    sources: List<ResearchSource>,
    apiKey: String,
    endpoint: String,
    model: String,
    speechLocale: String,
    wakeWord: String,
    speechRate: Float,
    memory: String,
    memoryEnabled: Boolean,
    seriousMode: Boolean,
    cybersecurityMode: Boolean,
    proactiveMode: MaxxProactiveEngine.Mode,
    onProactiveMode: (MaxxProactiveEngine.Mode) -> Unit,
    setupComplete: Boolean,
    showSettings: Boolean,
    showPermissionGuide: Boolean,
    microphoneGranted: Boolean,
    cameraGranted: Boolean,
    accessibilityEnabled: Boolean,
    deviceAdminEnabled: Boolean,
    auditReport: String,
    emergencyKillSwitch: Boolean,
    securityAudit: List<MaxxSecurityCenter.AuditEntry>,
    onEmergencyKillSwitch: (Boolean) -> Unit,
    onClearSecurityAudit: () -> Unit,
    onCompleteSetup: () -> Unit,
    onOrbClick: () -> Unit,
    audioLevel: Float,
    onSubmit: (String) -> Unit,
    onSettings: () -> Unit,
    onCloseSettings: () -> Unit,
    onSaveAi: (String, String, String) -> Unit,
    onSavePreferences: (String, String, Float) -> Unit,
    onMemoryEnabled: (Boolean) -> Unit,
    onSeriousMode: (Boolean) -> Unit,
    onCybersecurityMode: (Boolean) -> Unit,
    onSaveMemory: (String) -> Unit,
    onClearMemory: () -> Unit,
    onClearHistory: () -> Unit,
    onResetSetup: () -> Unit,
    onAccessibilitySetup: () -> Unit,
    onPermissions: () -> Unit,
    onClosePermissionGuide: () -> Unit,
    onDeviceAdmin: () -> Unit,
    onAudit: (String, Boolean) -> Unit,
    onPlayVoiceSample: () -> Unit,
    onOpenSource: (String) -> Unit
) {
    if (!setupComplete) {
        SetupScreen(onComplete = onCompleteSetup)
        return
    }
    if (showPermissionGuide) {
        PermissionGuideScreen(
            microphoneGranted, cameraGranted, accessibilityEnabled, deviceAdminEnabled,
            onClose = onClosePermissionGuide,
            onAccessibilitySetup = onAccessibilitySetup,
            onDeviceAdmin = onDeviceAdmin
        )
        return
    }
    if (showSettings) {
        SettingsScreen(
            apiKey, endpoint, model, speechLocale, wakeWord, speechRate, memory, memoryEnabled,
            seriousMode, cybersecurityMode, proactiveMode, onProactiveMode, history, auditReport,
            emergencyKillSwitch, securityAudit, onEmergencyKillSwitch, onClearSecurityAudit,
            onCloseSettings, onSaveAi, onSavePreferences, onMemoryEnabled, onSeriousMode,
            onCybersecurityMode, onSaveMemory, onClearMemory, onClearHistory, onResetSetup,
            onAccessibilitySetup, onPermissions, onDeviceAdmin, onAudit, onPlayVoiceSample,
            onOpenSource
        )
        return
    }
    val accent = when {
        seriousMode -> Red
        cybersecurityMode -> Cyber
        state == JarvisState.ERROR -> Red
        else -> Gold
    }

    // The supplied reference image is the visual shell of the home screen.
    // The settings gear and central core are transparent hit targets layered over it,
    // so the original image remains visually exact while the existing JARVIS actions stay usable.
    Surface(modifier = Modifier.fillMaxSize(), color = Color.Black) {
        Box(modifier = Modifier.fillMaxSize()) {
            // 🟢 NOTE: Rename maxx_ui to jarvis_ui in res/drawable
            Image(
                painter = painterResource(R.drawable.maxx_ui),
                contentDescription = "JARVIS core interface",
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.FillBounds
            )

            // Transparent settings hit target over the gear already present in the artwork.
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(top = 52.dp, end = 22.dp)
                    .size(68.dp)
                    .clickable(onClick = onSettings)
            )

            // The artwork remains the visual base, while this Canvas turns its golden core
            // into a live reactive JARVIS core. The animation speed/intensity follows JARVIS state.
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .offset(y = (-36).dp)
                    .fillMaxWidth(0.78f)
                    .aspectRatio(1f)
                    .clip(CircleShape)
            ) {
                JarvisCoreAnimation(state = state, accent = accent, audioLevel = audioLevel)
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .clickable(onClick = onOrbClick)
                )
            }

            if (state == JarvisState.THINKING || state == JarvisState.LISTENING || state == JarvisState.SPEAKING || state == JarvisState.ERROR) {
                val label = when (state) {
                    JarvisState.THINKING -> "THINKING"
                    JarvisState.LISTENING -> "LISTENING"
                    JarvisState.SPEAKING -> "SPEAKING"
                    else -> "CHECK STATUS"
                }
                Text(
                    label,
                    color = accent,
                    fontSize = 10.sp,
                    letterSpacing = 3.sp,
                    modifier = Modifier
                        .align(Alignment.TopCenter)
                        .padding(top = 18.dp)
                )
            }

            if (transcript.isNotBlank() || response.isNotBlank()) {
                Column(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .fillMaxWidth()
                        .padding(horizontal = 18.dp, vertical = 20.dp)
                        .clip(RoundedCornerShape(18.dp))
                        .background(Color.Black.copy(alpha = 0.72f))
                        .padding(horizontal = 14.dp, vertical = 10.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    if (transcript.isNotBlank()) {
                        Text(
                            "“$transcript”",
                            color = TextMuted,
                            fontSize = 11.sp,
                            textAlign = TextAlign.Center,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    if (response.isNotBlank()) {
                        Spacer(Modifier.height(4.dp))
                        Text(
                            response,
                            color = TextMain,
                            fontSize = 13.sp,
                            textAlign = TextAlign.Center,
                            maxLines = 4,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    if (visionText.isNotBlank()) {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "OCR: $visionText",
                            color = Cyber,
                            fontSize = 11.sp,
                            textAlign = TextAlign.Center,
                            maxLines = 8,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    if (sources.isNotEmpty()) {
                        Row(horizontalArrangement = Arrangement.Center) {
                            sources.take(2).forEach { source ->
                                TextButton(onClick = { onOpenSource(source.url) }) {
                                    Text(
                                        source.title,
                                        color = accent,
                                        fontSize = 10.sp,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun JarvisCoreAnimation(state: JarvisState, accent: Color, audioLevel: Float) { // 🟢 Changed
    val transition = rememberInfiniteTransition(label = "jarvis-core")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = when (state) {
                    JarvisState.LISTENING -> 4200
                    JarvisState.THINKING -> 2600
                    JarvisState.SPEAKING -> 1800
                    JarvisState.ERROR -> 700
                    else -> 7600
                },
                easing = LinearEasing
            )
        ),
        label = "orbit-rotation"
    )
    val pulse by transition.animateFloat(
        initialValue = 0.78f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = when (state) {
                    JarvisState.LISTENING -> 650
                    JarvisState.SPEAKING -> 480
                    JarvisState.THINKING -> 900
                    JarvisState.ERROR -> 240
                    else -> 1500
                },
                easing = androidx.compose.animation.core.FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "core-pulse"
    )
    val sweep by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (state == JarvisState.THINKING) 1200 else 2200,
                easing = LinearEasing
            )
        ),
        label = "scan-sweep"
    )

    val intensity = when (state) {
        JarvisState.LISTENING -> 1.0f
        JarvisState.THINKING -> 0.92f
        JarvisState.SPEAKING -> 1.0f
        JarvisState.ERROR -> 0.95f
        else -> 0.68f
    }

    Canvas(modifier = Modifier.fillMaxSize()) {
        val cx = size.width / 2f
        val cy = size.height / 2f
        val base = size.minDimension
        val reactive = 1f + (audioLevel * if (state == JarvisState.LISTENING || state == JarvisState.SPEAKING) 0.32f else 0.08f)
        val ring = base * 0.36f
        val gold = accent.copy(alpha = intensity)
        val soft = accent.copy(alpha = 0.18f * intensity)
        val bright = accent.copy(alpha = 0.86f * intensity)

        // Soft breathing halo.
        drawCircle(
            color = soft,
            radius = base * 0.19f * pulse * reactive,
            center = androidx.compose.ui.geometry.Offset(cx, cy)
        )
        drawCircle(
            color = accent.copy(alpha = 0.10f * intensity),
            radius = base * 0.28f * pulse * reactive,
            center = androidx.compose.ui.geometry.Offset(cx, cy)
        )

        // Multiple orbital planes recreate the screenshot's layered energy rings.
        for (i in 0 until 8) {
            val angle = rotation * (if (i % 2 == 0) 1f else -1f) + i * 22f
            val rx = ring * (0.70f + i * 0.055f)
            val ry = ring * (0.28f + (i % 4) * 0.075f)
            androidx.compose.ui.graphics.drawscope.rotate(angle, androidx.compose.ui.geometry.Offset(cx, cy)) {
                drawOval(
                    color = gold.copy(alpha = 0.20f + i * 0.045f),
                    topLeft = androidx.compose.ui.geometry.Offset(cx - rx, cy - ry),
                    size = androidx.compose.ui.geometry.Size(rx * 2f, ry * 2f),
                    style = androidx.compose.ui.graphics.drawscope.Stroke(
                        width = if (i % 3 == 0) 2.4f else 1.2f
                    )
                )
            }
        }

        // Rotating energy arcs and a scanner line.
        androidx.compose.ui.graphics.drawscope.rotate(sweep, androidx.compose.ui.geometry.Offset(cx, cy)) {
            drawArc(
                color = bright,
                startAngle = -18f,
                sweepAngle = 78f,
                useCenter = false,
                topLeft = androidx.compose.ui.geometry.Offset(cx - ring, cy - ring),
                size = androidx.compose.ui.geometry.Size(ring * 2f, ring * 2f),
                style = androidx.compose.ui.graphics.drawscope.Stroke(width = 5f, cap = StrokeCap.Round)
            )
            drawArc(
                color = bright.copy(alpha = 0.62f),
                startAngle = 160f,
                sweepAngle = 48f,
                useCenter = false,
                topLeft = androidx.compose.ui.geometry.Offset(cx - ring * 0.78f, cy - ring * 0.78f),
                size = androidx.compose.ui.geometry.Size(ring * 1.56f, ring * 1.56f),
                style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2.5f, cap = StrokeCap.Round)
            )
            drawLine(
                color = bright.copy(alpha = 0.30f),
                start = androidx.compose.ui.geometry.Offset(cx - ring * 1.2f, cy),
                end = androidx.compose.ui.geometry.Offset(cx + ring * 1.2f, cy),
                strokeWidth = 1.2f
            )
        }

        // Pulsing reactor core.
        drawCircle(
            color = accent.copy(alpha = 0.28f * intensity),
            radius = base * 0.12f * pulse,
            center = androidx.compose.ui.geometry.Offset(cx, cy)
        )
        drawCircle(
            color = accent.copy(alpha = 0.72f * intensity),
            radius = base * 0.065f * pulse,
            center = androidx.compose.ui.geometry.Offset(cx, cy)
        )
        drawCircle(
            color = Color.White.copy(alpha = 0.92f),
            radius = base * 0.018f * pulse,
            center = androidx.compose.ui.geometry.Offset(cx, cy)
        )

        // State-specific radial ticks. They move during listening/thinking/speaking,
        // making the visualizer communicate that JARVIS is actively processing audio.
        val ticks = when (state) {
            JarvisState.LISTENING -> 32
            JarvisState.THINKING -> 48
            JarvisState.SPEAKING -> 38
            JarvisState.ERROR -> 20
            else -> 24
        }
        for (i in 0 until ticks) {
            val a = Math.toRadians((360f / ticks) * i + rotation * 0.55f)
            val r1 = base * (0.30f + (i % 3) * 0.018f)
            val r2 = r1 + if (i % 4 == 0) base * 0.075f else base * 0.038f
            val x1 = cx + kotlin.math.cos(a).toFloat() * r1
            val y1 = cy + kotlin.math.sin(a).toFloat() * r1
            val x2 = cx + kotlin.math.cos(a).toFloat() * r2
            val y2 = cy + kotlin.math.sin(a).toFloat() * r2
            drawLine(
                color = gold.copy(alpha = if (i % 4 == 0) 0.70f else 0.28f),
                start = androidx.compose.ui.geometry.Offset(x1, y1),
                end = androidx.compose.ui.geometry.Offset(x2, y2),
                strokeWidth = if (i % 4 == 0) 2.1f else 1f,
                cap = StrokeCap.Round
            )
        }
    }
}

@Composable
private fun SetupScreen(onComplete: () -> Unit) {
    var acknowledged by remember { mutableStateOf(false) }
    Surface(Modifier.fillMaxSize(), color = Bg) {
        Column(
            Modifier.fillMaxSize().padding(28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Image(
                painter = painterResource(R.drawable.maxx_ui), // NOTE: Rename maxx_ui to jarvis_ui in res/drawable
                contentDescription = "JARVIS interface preview",
                modifier = Modifier
                    .size(width = 220.dp, height = 390.dp)
                    .clip(RoundedCornerShape(22.dp)),
                contentScale = ContentScale.FillBounds
            )
            Text("MEET JARVIS", color = Gold, fontSize = 12.sp, letterSpacing = 4.sp)
            Spacer(Modifier.height(12.dp))
            Text("Your personal AI assistant", color = TextMain, fontSize = 23.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            Text(
                "Tap the core to speak, or type a request. Add your own compatible AI provider key in Settings for online answers. Phone actions use Android's visible permissions and confirmation screens.",
                color = TextMuted, fontSize = 14.sp, textAlign = TextAlign.Center
            )
            Spacer(Modifier.height(10.dp))
            Text(
                "Optional background wake-word listening is available after setup. Android shows a persistent microphone notification while it is active. You can also use the core button for one-shot voice.",
                color = TextMuted, fontSize = 12.sp, textAlign = TextAlign.Center
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = acknowledged, onCheckedChange = { acknowledged = it })
                Text("I understand microphone access is user-controlled", color = TextMuted, fontSize = 12.sp)
            }
            Button(onClick = {
                if (acknowledged) {
                    onComplete()
                }
            }, enabled = acknowledged) { Text("Set up JARVIS") }
        }
    }
}

@Composable
private fun PermissionGuideScreen(
    microphoneGranted: Boolean,
    cameraGranted: Boolean,
    accessibilityEnabled: Boolean,
    deviceAdminEnabled: Boolean,
    onClose: () -> Unit,
    onAccessibilitySetup: () -> Unit,
    onDeviceAdmin: () -> Unit
) {
    Surface(Modifier.fillMaxSize(), color = Bg) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onClose) {
                    Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = Gold)
                }
                Text("PERMISSIONS", color = TextMain, fontSize = 17.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(12.dp))
            Text("JARVIS requests each permission only for a feature you choose.", color = TextMuted, fontSize = 13.sp)
            Spacer(Modifier.height(14.dp))
            PermissionRow("Microphone", if (microphoneGranted) "Allowed" else "Not granted", "Only used after you tap the core to speak.")
            PermissionRow("Camera", if (cameraGranted) "Allowed" else "Not granted", "Used only by Android's flashlight control; the app does not capture photos.")
            PermissionRow("Accessibility", if (accessibilityEnabled) "Enabled" else "Optional · disabled", "Enables explicit back/home, tap, scroll and text-entry commands. You must enable it in Android settings.")
            Button(onClick = onAccessibilitySetup, modifier = Modifier.fillMaxWidth()) {
                Text("Open Accessibility settings")
            }
            PermissionRow("Device admin", if (deviceAdminEnabled) "Enabled" else "Optional · disabled", "Required only if you ask JARVIS to lock the phone. Android can revoke this at any time.")
            Button(onClick = onDeviceAdmin, modifier = Modifier.fillMaxWidth()) {
                Text("Manage lock-phone permission")
            }
            PermissionRow("Notifications", "Not requested", "JARVIS does not send notifications.")
            PermissionRow("Phone, SMS, contacts, location, Bluetooth", "Not requested", "Calling and SMS open system UI; JARVIS does not directly call or send.")
            Spacer(Modifier.height(18.dp))
            Text(
                "JARVIS does not bypass the lock screen, place calls, send SMS, secretly record, or run a hidden microphone service.",
                color = TextMuted, fontSize = 12.sp
            )
        }
    }
}

@Composable
private fun PermissionRow(title: String, status: String, explanation: String) {
    Card(
        Modifier.fillMaxWidth().padding(vertical = 5.dp),
        colors = CardDefaults.cardColors(containerColor = Panel)
    ) {
        Column(Modifier.padding(13.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, color = TextMain, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                Text(status, color = Gold, fontSize = 11.sp)
            }
            Spacer(Modifier.height(4.dp))
            Text(explanation, color = TextMuted, fontSize = 11.sp)
        }
    }
}

@Composable
private fun SettingsScreen(
    currentKey: String,
    currentEndpoint: String,
    currentModel: String,
    currentLocale: String,
    currentWakeWord: String,
    currentRate: Float,
    currentMemory: String,
    memoryEnabled: Boolean,
    seriousMode: Boolean,
    cybersecurityMode: Boolean,
    proactiveMode: MaxxProactiveEngine.Mode,
    onProactiveMode: (MaxxProactiveEngine.Mode) -> Unit,
    history: List<ChatTurn>,
    auditReport: String,
    emergencyKillSwitch: Boolean,
    securityAudit: List<MaxxSecurityCenter.AuditEntry>,
    onEmergencyKillSwitch: (Boolean) -> Unit,
    onClearSecurityAudit: () -> Unit,
    onClose: () -> Unit,
    onSaveAi: (String, String, String) -> Unit,
    onSavePreferences: (String, String, Float) -> Unit,
    onMemoryEnabled: (Boolean) -> Unit,
    onSeriousMode: (Boolean) -> Unit,
    onCybersecurityMode: (Boolean) -> Unit,
    onSaveMemory: (String) -> Unit,
    onClearMemory: () -> Unit,
    onClearHistory: () -> Unit,
    onResetSetup: () -> Unit,
    onAccessibilitySetup: () -> Unit,
    onPermissions: () -> Unit,
    onDeviceAdmin: () -> Unit,
    onAudit: (String, Boolean) -> Unit,
    onPlayVoiceSample: () -> Unit,
    onOpenSource: (String) -> Unit
) {
    var key by remember { mutableStateOf(currentKey) }
    var endpoint by remember { mutableStateOf(currentEndpoint) }
    var model by remember { mutableStateOf(currentModel) }
    var locale by remember { mutableStateOf(currentLocale) }
    var wakeWord by remember { mutableStateOf(currentWakeWord) }
    var rate by remember { mutableStateOf(currentRate) }
    var memory by remember { mutableStateOf(currentMemory) }
    var auditHost by remember { mutableStateOf("") }
    var authorized by remember { mutableStateOf(false) }
    var showHistory by remember { mutableStateOf(false) }
    var showAbout by remember { mutableStateOf(false) }

    Surface(Modifier.fillMaxSize(), color = Bg) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onClose) {
                    Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = Gold)
                }
                Text("JARVIS SETTINGS", color = TextMain, fontSize = 17.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
            }
            Spacer(Modifier.height(12.dp))

            SettingsSection("AI PROVIDER")
            OutlinedTextField(
                value = key, onValueChange = { key = it },
                label = { Text("API key") }, modifier = Modifier.fillMaxWidth(),
                singleLine = true, visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password)
            )
            OutlinedTextField(
                value = endpoint, onValueChange = { endpoint = it },
                label = { Text("HTTPS endpoint (OpenAI-compatible Chat Completions)") },
                modifier = Modifier.fillMaxWidth(), singleLine = true
            )
            OutlinedTextField(
                value = model, onValueChange = { model = it },
                label = { Text("Model") }, modifier = Modifier.fillMaxWidth(), singleLine = true
            )
            Text(
                "The key is encrypted with Android Keystore and stays on this device. Use a provider endpoint compatible with the Chat Completions format.",
                color = TextMuted, fontSize = 11.sp
            )
            Button(onClick = { onSaveAi(key, endpoint, model) }, modifier = Modifier.fillMaxWidth()) {
                Text("Save AI provider")
            }
            Spacer(Modifier.height(16.dp))

            SettingsSection("VOICE")
            OutlinedTextField(
                value = locale, onValueChange = { locale = it },
                label = { Text("Speech language (e.g. en-US)") }, modifier = Modifier.fillMaxWidth(), singleLine = true
            )
            Text("Speech rate: ${"%.2f".format(Locale.US, rate)}×", color = TextMuted, fontSize = 12.sp)
            Slider(value = rate, onValueChange = { rate = it }, valueRange = 0.5f..1.5f)
            OutlinedTextField(
                value = wakeWord, onValueChange = { wakeWord = it },
                label = { Text("Wake word preference") }, modifier = Modifier.fillMaxWidth(), singleLine = true
            )
            Text(
                "Wake-word listening is user-started and runs as an Android microphone foreground service. Android/OEM restrictions can still stop it; JARVIS never starts the microphone silently.",
                color = TextMuted, fontSize = 11.sp
            )
            Button(onClick = {
                onSavePreferences(locale, wakeWord, rate)
                onPlayVoiceSample()
            }, modifier = Modifier.fillMaxWidth()) { Text("Save voice settings · Play sample") }
            Spacer(Modifier.height(16.dp))

            SettingsSection("MODES")
            SettingSwitch("Serious Mode · red core", seriousMode, onSeriousMode)
            SettingSwitch("Cybersecurity Mode · authorized scope only", cybersecurityMode, onCybersecurityMode)
            Text("Voice commands: “JARVIS, serious mode on/off” and “JARVIS, cybersecurity mode on/off”.", color = TextMuted, fontSize = 11.sp)
            Spacer(Modifier.height(10.dp))
            Text("PROACTIVE INTELLIGENCE", color = Gold, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            Text("JARVIS can surface useful local context without executing high-risk actions.", color = TextMuted, fontSize = 11.sp)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                MaxxProactiveEngine.Mode.values().forEach { mode ->
                    TextButton(onClick = { onProactiveMode(mode) }) {
                        Text(
                            mode.name,
                            color = if (mode == proactiveMode) Gold else TextMuted,
                            fontWeight = if (mode == proactiveMode) FontWeight.Bold else FontWeight.Normal
                        )
                    }
                }
            }
            Text(
                "OFF = silent · LOW = only important alerts · NORMAL = useful context · HIGH = more proactive alerts. Battery alerts are local and rate-limited.",
                color = TextMuted, fontSize = 11.sp
            )
            if (cybersecurityMode) {
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = auditHost,
                    onValueChange = { auditHost = it },
                    label = { Text("One authorized HTTPS hostname") },
                    placeholder = { Text("example.org") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = authorized, onCheckedChange = { authorized = it })
                    Text("I own this target or have explicit permission to assess it", color = TextMuted, fontSize = 12.sp)
                }
                Button(onClick = { onAudit(auditHost, authorized) }, modifier = Modifier.fillMaxWidth()) {
                    Text("Run passive HTTPS review")
                }
                Text(
                    auditReport.ifBlank { "Only DNS, HTTPS handshake and common security headers are checked; no port scan, login, crawling or exploit test." },
                    color = TextMuted, fontSize = 11.sp
                )
            }
            Spacer(Modifier.height(16.dp))

            SettingsSection("MEMORY")
            SettingSwitch("Use saved memory in AI context", memoryEnabled, onMemoryEnabled)
            OutlinedTextField(
                value = memory, onValueChange = { memory = it },
                label = { Text("JARVIS memory (only what you choose to save)") },
                modifier = Modifier.fillMaxWidth(), minLines = 2, maxLines = 5
            )
            Button(onClick = { onSaveMemory(memory) }, modifier = Modifier.fillMaxWidth()) { Text("Save memory encrypted") }
            TextButton(onClick = onClearMemory) { Text("Clear local memory", color = Gold) }
            Row {
                TextButton(onClick = { showHistory = !showHistory }) {
                    Text(if (showHistory) "Hide conversation history" else "View conversation history (${history.size})", color = Gold)
                }
                TextButton(onClick = onClearHistory) { Text("Clear history", color = Gold) }
            }
            if (showHistory) {
                history.asReversed().take(15).forEach { turn ->
                    Card(
                        Modifier.fillMaxWidth().padding(vertical = 4.dp),
                        colors = CardDefaults.cardColors(containerColor = Panel)
                    ) {
                        Column(Modifier.padding(12.dp)) {
                            Text("YOU  ·  ${turn.user}", color = TextMain, fontSize = 12.sp)
                            Spacer(Modifier.height(4.dp))
                            Text("JARVIS  ·  ${turn.assistant}", color = TextMuted, fontSize = 12.sp)
                            turn.sources.forEach { source ->
                                TextButton(onClick = { onOpenSource(source.url) }) {
                                    Text(source.title, color = Gold, fontSize = 11.sp)
                                }
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.height(16.dp))

            SettingsSection("PERMISSIONS & ACCESSIBILITY")
            Text(
                "Microphone is requested when you first tap to speak. Camera is requested only for the flashlight. Calls/SMS use Android's dialer/draft screens. No contacts, location, Bluetooth or notification access is required.",
                color = TextMuted, fontSize = 12.sp
            )
            Button(onClick = onPermissions, modifier = Modifier.fillMaxWidth()) { Text("Show permission guide") }
            Button(onClick = onAccessibilitySetup, modifier = Modifier.fillMaxWidth()) { Text("Open Accessibility settings") }
            Button(onClick = onDeviceAdmin, modifier = Modifier.fillMaxWidth()) { Text("Optional: enable lock-phone permission") }
            Text(
                "Accessibility is optional and must be enabled by you in Android settings. JARVIS does not record or store screen content.",
                color = TextMuted, fontSize = 11.sp
            )
            Spacer(Modifier.height(16.dp))

            SettingsSection("SECURITY CENTER")
            SettingSwitch("Emergency kill switch", emergencyKillSwitch, onEmergencyKillSwitch)
            Text("When enabled, JARVIS stops agent execution and device actions. Disable it manually to resume.", color = TextMuted, fontSize = 11.sp)
            Text("Permission status", color = TextMain, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            MaxxSecurityCenter.permissionSummary(LocalContext.current).forEach { Text(it, color = TextMuted, fontSize = 11.sp) }
            Text("Recent security audit", color = TextMain, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 8.dp))
            securityAudit.take(10).forEach { entry ->
                Text("${java.text.SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(java.util.Date(entry.time))} · ${entry.risk} · ${entry.action} · ${entry.outcome}", color = TextMuted, fontSize = 10.sp)
            }
            TextButton(onClick = onClearSecurityAudit) { Text("Clear security audit", color = Gold) }
            Spacer(Modifier.height(16.dp))

            SettingsSection("PRIVACY & APP")
            Text("Online AI and web search send the prompt to the configured provider/search service. Local memory and history are encrypted in app storage.", color = TextMuted, fontSize = 12.sp)
            TextButton(onClick = { key = ""; onSaveAi("", endpoint, model) }) {
                Text("Remove saved AI key", color = Gold)
            }
            TextButton(onClick = onResetSetup) { Text("Reset Setup", color = Gold) }
            TextButton(onClick = { showAbout = !showAbout }) { Text("About JARVIS", color = Gold) }
            if (showAbout) {
                Text(
                    "JARVIS is a personal assistant using Android speech services, TextToSpeech, explicit phone intents, configurable OpenAI-compatible AI providers, passive web research and a user-started foreground wake listener. It does not use a hidden microphone or unrestricted device control.",
                    color = TextMuted, fontSize = 12.sp
                )
            }
            Spacer(Modifier.height(28.dp))
        }
    }
}

@Composable
private fun SettingsSection(title: String) {
    Text(title, color = Gold, fontSize = 11.sp, letterSpacing = 2.sp, fontWeight = FontWeight.Bold)
    Divider(color = Gold.copy(alpha = 0.22f), modifier = Modifier.padding(top = 7.dp, bottom = 8.dp))
}

@Composable
private fun SettingSwitch(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = TextMain, fontSize = 13.sp, modifier = Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
