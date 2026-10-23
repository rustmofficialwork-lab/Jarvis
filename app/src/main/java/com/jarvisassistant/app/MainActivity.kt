package com.jarvisassistant.app

import android.Manifest
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.BroadcastReceiver
import android.content.IntentFilter
import android.content.Intent
import android.content.pm.PackageManager
import android.database.Cursor
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.media.MediaPlayer
import android.provider.AlarmClock
import android.provider.CalendarContract
import android.provider.ContactsContract
import android.provider.MediaStore
import android.provider.Settings
import android.speech.RecognitionListener
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.telephony.SmsManager
import android.view.KeyEvent
import android.view.View
import android.widget.VideoView
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
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.Future
import android.util.Log

private val Bg = Color(0xFF030303)
private val TextMain = Color(0xFFF4F4F4)

enum class JarvisState { IDLE, LISTENING, THINKING, SPEAKING, SERIOUS, CYBERSECURITY, ERROR, OFFLINE }

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {
    private val prefs by lazy { getSharedPreferences("jarvis", Context.MODE_PRIVATE) }
    private var tts: TextToSpeech? = null
    private var speechRecognizer: SpeechRecognizer? = null
    private var torchOn = false
    private var lastTranscript by mutableStateOf("")
    private var responseText by mutableStateOf("")
    private var state by mutableStateOf(JarvisState.IDLE)
    private var apiKey by mutableStateOf("")
    private var endpoint by mutableStateOf("https://api.openai.com/v1/chat/completions")
    private var model by mutableStateOf("gpt-4o-mini")
    private var speechLocale by mutableStateOf("en-US")
    private var wakeWord by mutableStateOf("JARVIS")
    private var speechRate by mutableStateOf(0.85f)
    private var showSettings by mutableStateOf(false)
    private var history by mutableStateOf(listOf<ChatTurn>())
    private var audioLevel by mutableStateOf(0f)
    private val worker = Executors.newSingleThreadExecutor()
    private var activeTask: Future<*>? = null
    private var requestGeneration = 0L
    
    private var continuousConversation = false 
    private var pendingWakeServiceStart = false
    private var isVideoFinished = false

    // Jab app khuli hai tab background service ko ignore karega, kyunki app khud sun rahi hai
    private val wakeReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            // If app is in foreground, we handle it. Service handles it if app is closed.
        }
    }

    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            if (pendingWakeServiceStart) {
                pendingWakeServiceStart = false
                startWakeService()
            }
        } else {
            pendingWakeServiceStart = false
            state = JarvisState.ERROR
            responseText = "Microphone permission was not granted."
        }
    }
    
    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) toggleTorch()
    }

    private val smsPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) responseText = "SMS permission granted. Please say the command again."
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
            tts = TextToSpeech(this, this)
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    runOnUiThread { state = JarvisState.SPEAKING }
                }
                override fun onDone(utteranceId: String?) {
                    runOnUiThread { state = restingState() }
                }
                override fun onError(utteranceId: String?) {
                    runOnUiThread { state = JarvisState.ERROR }
                }
            })
            
            // Start background service to listen when app is closed
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                startWakeService()
            } else {
                micPermission.launch(Manifest.permission.RECORD_AUDIO)
            }

            setContent {
                val infiniteTransition = rememberInfiniteTransition()
                val pulseScale by infiniteTransition.animateFloat(
                    initialValue = 1f,
                    targetValue = if (state == JarvisState.LISTENING) 1.05f else 1f,
                    animationSpec = infiniteRepeatable(
                        animation = tween(1000, easing = FastOutSlowInEasing),
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
                                .size(320.dp)
                                .scale(pulseScale)
                                .clip(CircleShape)
                        ) {
                            AndroidView(
                                modifier = Modifier.fillMaxSize(),
                                factory = { context ->
                                    VideoView(context).apply {
                                        setVideoURI(Uri.parse("android.resource://${context.packageName}/${R.raw.jarvis_hud_bg}"))
                                        setOnPreparedListener { player ->
                                            player.isLooping = false
                                            player.setVolume(1f, 1f) 
                                            player.setVideoScalingMode(MediaPlayer.VIDEO_SCALING_MODE_SCALE_TO_FIT)
                                            start()
                                        }
                                        setOnCompletionListener {
                                            isVideoFinished = true
                                        }
                                    }
                                }
                            )
                        }

                        // LISTENING ANIMATION REMOVED AS REQUESTED. UI IS CLEAN NOW.

                        if (state == JarvisState.THINKING) {
                            Spacer(modifier = Modifier.height(32.dp))
                            Text("Thinking...", color = TextMain, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        } else if (state == JarvisState.SPEAKING) {
                            Spacer(modifier = Modifier.height(32.dp))
                            Text("Speaking...", color = TextMain, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        }
                    }

                    if (showSettings) {
                        Box(
                            modifier = Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.9f)), 
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

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.let { t ->
                val ukLocale = Locale("en", "GB")
                t.setLanguage(ukLocale)
                val voices = t.voices
                val maleVoice = voices?.firstOrNull { it.locale == ukLocale && !it.isNetworkConnectionRequired && it.name.contains("male", ignoreCase = true) }
                    ?: voices?.firstOrNull { it.locale == ukLocale && !it.isNetworkConnectionRequired }
                if (maleVoice != null) t.voice = maleVoice
                t.setPitch(0.85f) 
                t.setSpeechRate(speechRate) 
            }
        }
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
                    state = JarvisState.IDLE 
                    Log.e("Jarvis", "MainActivity Speech Error: $error")
                }
                override fun onResults(results: Bundle?) {
                    audioLevel = 0f
                    val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                    if (!text.isNullOrBlank()) {
                        handlePrompt(text)
                    } else {
                        state = JarvisState.IDLE
                    }
                }
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            })
            try { recognizer.startListening(JarvisVoiceEngine.recognitionIntent(speechLocale, false)) } catch (_: Exception) {}
        }
    }

    private fun handleLocalCommand(text: String): String? {
        val command = CommandNormalizer.normalize(text, wakeWord)
        val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager

        if (command.contains("introduction") || command.contains("intro") || command.contains("introduce yourself") || command.contains("who are you") || command.contains("tum kaun ho") || command.contains("apna parichay do")) {
            return "Hello, Sir.\n\n" +
                   "I am JARVIS — your personal AI assistant.\n\n" +
                   "I am designed to assist you, understand your commands, answer your questions, and help you accomplish your tasks with intelligence and precision.\n\n" +
                   "Always ready. Always learning. Always at your service.\n\n" +
                   "Systems online. All functions operational.\n\n" +
                   "Welcome back, Sir.\n\n" +
                   "How may I assist you today?"
        }

        if (command.contains("settings") || command.contains("setting")) {
            showSettings = true
            return "Opening settings."
        }

        if (command in setOf("help", "commands", "what can you do", "kya kar sakte ho")) {
            return "I can control calls, sms, music, maps, apps, and use accessibility to click, scroll, and read the screen."
        }

        if (command.contains("recent apps") || command.contains("recents")) return runAccessibility("recents")
        if (command.contains("notifications") || command.contains("notification panel")) return runAccessibility("notifications")
        if (command.contains("power menu") || command.contains("power options")) return runAccessibility("power-menu")
        
        if (command.contains("read screen") || command.contains("screen padho") || command.contains("what is on the screen")) {
            return runAccessibility("read-screen")
        }
        if (command.startsWith("click on ") || command.startsWith("click ")) {
            val target = command.replace("click on ", "").replace("click ", "").trim()
            return runAccessibility("click", text = target)
        }
        if (command.contains("scroll up") || command.contains("upar scroll karo")) return runAccessibility("scroll-up")
        if (command.contains("scroll down") || command.contains("niche scroll karo")) return runAccessibility("scroll-down")

        if (command.contains("time") || command.contains("samay") || command.contains("waqt")) {
            return "It is ${java.text.SimpleDateFormat("h:mm a", Locale.getDefault()).format(java.util.Date())}."
        }
        if (command.contains("date") || command.contains("tareekh")) {
            return "Today is ${java.text.SimpleDateFormat("EEEE, d MMMM yyyy", Locale.getDefault()).format(java.util.Date())}."
        }
        if (command.contains("battery") || command.contains("charge")) {
            val bm = getSystemService(BATTERY_SERVICE) as android.os.BatteryManager
            val pct = bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)
            return if (pct >= 0) "Battery is at $pct percent." else "Battery percentage is unavailable."
        }
        if (command.contains("flashlight") || command.contains("torch") || command.contains("batti")) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                toggleTorch()
                return if (torchOn) "Flashlight on." else "Flashlight off."
            }
            cameraPermission.launch(Manifest.permission.CAMERA)
            return "Requesting camera permission."
        }
        if (command.contains("vibrate") || command.contains("vibration")) {
            val vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            if (Build.VERSION.SDK_INT >= 26) vibrator.vibrate(VibrationEffect.createOneShot(1000, VibrationEffect.DEFAULT_AMPLITUDE))
            else vibrator.vibrate(1000)
            return "Vibrating."
        }
        if (command.contains("volume up") || command.contains("volume badhao") || command.contains("awaaz badhao")) {
            audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
            return "Volume increased."
        }
        if (command.contains("volume down") || command.contains("volume kam karo") || command.contains("awaaz kam karo")) {
            audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
            return "Volume decreased."
        }
        if (command.contains("mute") || command.contains("silent")) {
            audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, AudioManager.FLAG_SHOW_UI)
            return "Phone muted."
        }
        if (command.contains("play music") || command.contains("pause music") || command.contains("next song") || command.contains("previous song") || command.contains("gana chalao") || command.contains("gana roko")) {
            val action = when {
                command.contains("play") || command.contains("chalao") -> KeyEvent.ACTION_DOWN to KeyEvent.KEYCODE_MEDIA_PLAY
                command.contains("pause") || command.contains("roko") -> KeyEvent.ACTION_DOWN to KeyEvent.KEYCODE_MEDIA_PAUSE
                command.contains("next") -> KeyEvent.ACTION_DOWN to KeyEvent.KEYCODE_MEDIA_NEXT
                else -> KeyEvent.ACTION_DOWN to KeyEvent.KEYCODE_MEDIA_PREVIOUS
            }
            audioManager.dispatchMediaKeyEvent(KeyEvent(action.first, action.second))
            return "Music controlled."
        }
        if (command.contains("set alarm") || command.contains("alarm laga")) {
            val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
                putExtra(AlarmClock.EXTRA_HOUR, 7); putExtra(AlarmClock.EXTRA_MINUTES, 0); putExtra(AlarmClock.EXTRA_SKIP_UI, true)
            }
            safeStartActivity(intent)
            return "Setting alarm for 7 AM."
        }
        
        if (command.startsWith("call ") || command.contains("call lagao") || command.contains("phone karo") || command.contains("phone lagao")) {
            val contactName = command
                .replace("call ", "")
                .replace("call lagao", "")
                .replace("phone karo", "")
                .replace("phone lagao", "")
                .replace(" ko", "")
                .trim()
                
            val phoneNumber = getContactNumber(contactName)
            if (phoneNumber != null) {
                val intent = Intent(Intent.ACTION_CALL).apply { data = Uri.parse("tel:$phoneNumber") }
                safeStartActivity(intent)
                return "Calling $contactName."
            } else {
                val intent = Intent(Intent.ACTION_DIAL).apply { data = Uri.parse("tel:$contactName") }
                safeStartActivity(intent)
                return "Contact not found. Opening dialer."
            }
        }
        
        if (command.startsWith("send sms to ") || command.contains("message bhejo") || command.contains("sms bhejo")) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
                smsPermission.launch(Manifest.permission.SEND_SMS)
                return "Requesting SMS permission. Please say again."
            }
            
            var name = ""
            var msg = ""
            if (command.contains(" saying ")) {
                val parts = command.split(" saying ")
                name = parts[0].replace("send sms to ", "").replace(" ko", "").trim()
                msg = parts[1].trim()
            } else if (command.contains(" ko ") && command.contains(" bolo ")) {
                val parts = command.split(" ko ")
                name = parts[0].replace("send sms to ", "").replace("message bhejo ", "").replace("sms bhejo ", "").trim()
                msg = parts[1].replace(" bolo", "").replace(" message bhejo", "").replace(" sms bhejo", "").trim()
            }
            
            if (name.isNotEmpty() && msg.isNotEmpty()) {
                val number = getContactNumber(name)
                if (number != null) {
                    try {
                        SmsManager.getDefault().sendTextMessage(number, null, msg, null, null)
                        return "SMS sent to $name."
                    } catch (e: Exception) { return "Failed to send SMS." }
                } else return "Contact $name not found."
            }
            return "Format: Rahul ko Hello bolo."
        }

        if (command.contains("take photo") || command.contains("open camera") || command.contains("camera kholo")) {
            val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            safeStartActivity(intent)
            return "Opening camera."
        }
        
        if (command == "home" || command == "go home" || command.contains("ghar jao") || command.contains("home jao")) return runAccessibility("home")
        if (command == "back" || command == "go back" || command.contains("wapas jao") || command.contains("peeche jao")) return runAccessibility("back")
        if (command == "lock phone" || command.contains("phone lock karo")) return lockPhone()
        
        var appNameToOpen: String? = null
        if (command.startsWith("open ")) {
            appNameToOpen = command.removePrefix("open ").trim()
        } else if (command.contains(" kholo")) {
            appNameToOpen = command.replace(" kholo", "").replace(" ko", "").trim()
        } else if (command.contains(" chalu karo")) {
            appNameToOpen = command.replace(" chalu karo", "").replace(" ko", "").trim()
        } else if (command.contains(" start karo")) {
            appNameToOpen = command.replace(" start karo", "").replace(" ko", "").trim()
        }
        
        if (appNameToOpen != null) {
            return openInstalledApp(appNameToOpen)
        }
        
        return null
    }

    private fun runAccessibility(action: String, x: Float? = null, y: Float? = null, text: String? = null): String {
        val service = JarvisAccessibilityService.active ?: return "Accessibility service is not active. Please enable it in settings."
        return when (action) {
            "home" -> { service.performCommand("home"); "Going home." }
            "back" -> { service.performCommand("back"); "Going back." }
            "recents" -> { service.performCommand("recents"); "Opening recent apps." }
            "notifications" -> { service.performCommand("notifications"); "Opening notifications." }
            "power-menu" -> { service.performCommand("power-menu"); "Opening power menu." }
            "scroll-up" -> { service.performCommand("scroll-up"); "Scrolling up." }
            "scroll-down" -> { service.performCommand("scroll-down"); "Scrolling down." }
            "read-screen" -> {
                val content = service.readScreenContent()
                if (content.isBlank()) "The screen is empty." else "Screen says: $content"
            }
            "click" -> {
                if (text != null) {
                    val clicked = service.clickByText(text)
                    if (clicked) "Clicked $text." else "Could not find '$text' on screen."
                } else "No text provided to click."
            }
            else -> "Unknown action."
        }
    }

    private fun getContactNumber(name: String): String? {
        val uri = Uri.withAppendedPath(ContactsContract.CommonDataKinds.Phone.CONTENT_FILTER_URI, Uri.encode(name))
        val cursor: Cursor? = contentResolver.query(uri, arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER), null, null, null)
        cursor?.use {
            if (it.moveToFirst()) return it.getString(0)
        }
        return null
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

    private fun safeStartActivity(intent: Intent) {
        try { startActivity(intent) } catch (e: Exception) { Log.e("Jarvis", "Activity start failed: ${e.message}") }
    }

    private fun restingState(): JarvisState = JarvisState.IDLE

    private fun finishTurn(prompt: String, reply: String) {
        history = (history + ChatTurn(prompt, reply, emptyList())).takeLast(40)
        state = restingState()
        tts?.speak(reply, TextToSpeech.QUEUE_FLUSH, null, "jarvis_utterance")
    }

    private fun startWakeService() {
        pendingWakeServiceStart = false
        val intent = Intent(this, JarvisWakeService::class.java).putExtra("wake", wakeWord).putExtra("locale", speechLocale)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ContextCompat.startForegroundService(this, intent) else startService(intent)
        } catch (e: Exception) {}
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
            TextButton(onClick = onClose, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Close", color = TextMain) }
        }
    }
}
