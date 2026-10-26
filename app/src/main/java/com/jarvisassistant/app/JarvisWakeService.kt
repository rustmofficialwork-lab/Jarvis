package com.jarvisassistant.app

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.ToneGenerator
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import java.util.Locale
import java.util.concurrent.Executors

class JarvisWakeService : Service(), TextToSpeech.OnInitListener {

    companion object {
        const val ACTION_WAKE = "com.jarvisassistant.app.JARVIS_WAKE"
        const val ACTION_STOP = "com.jarvisassistant.app.JARVIS_STOP_WAKE"
        const val ACTION_PAUSE = "com.jarvisassistant.app.JARVIS_PAUSE_WAKE"
        const val ACTION_RESUME = "com.jarvisassistant.app.JARVIS_RESUME_WAKE"
        const val ACTION_SHUT_UP = "com.jarvisassistant.app.JARVIS_STOP_TALKING"

        /** Broadcast sent to the app after every command (package-restricted). */
        const val ACTION_EVENT = "com.jarvisassistant.app.JARVIS_EVENT"
        const val EXTRA_USER = "user"
        const val EXTRA_REPLY = "reply"

        private const val TAG = "JarvisWakeService"
        private const val CHANNEL_ID = "jarvis_wake_channel"
        private const val NOTIFICATION_ID = 4101

        /** false = service keeps running when app is swiped from recents. */
        private const val STOP_ON_TASK_REMOVED = false

        private const val MIN_RETRY_MS = 2000L
        private const val MAX_RETRY_MS = 15000L
        private const val TTS_WATCHDOG_BASE_MS = 12000L
        private const val TTS_WATCHDOG_PER_CHAR_MS = 100L
        private const val RECOGNIZER_WATCHDOG_MS = 30000L
        private const val AI_TIMEOUT_MS = 30000L
        private const val MAX_FOLLOW_UPS = 5
        private const val MAX_EXCHANGES = 4
        private const val HISTORY_EXPIRE_MS = 5 * 60 * 1000L
        private const val WAKE_LOCK_MS = 12 * 60 * 60 * 1000L

        // "service" is intentionally NOT here: it triggers on normal talk.
        private val JARVIS_VARIANTS = listOf(
            "jarvish", "jaarvis", "jarwis", "jarvice", "jar vis",
            "जार्विस", "जारविस", "जर्विस", "जार्विज़"
        )
        private val STOP_WORDS = setOf(
            "stop", "cancel", "never mind", "nevermind", "chup", "chup raho",
            "ruko", "ruk jao", "रुको", "चुप", "चुप रहो", "रहने दो"
        )
        private val END_WORDS = setOf(
            "thanks", "thank you", "that's all", "thats all", "bas", "bas itna hi",
            "dhanyavaad", "dhanyawad", "shukriya", "धन्यवाद", "शुक्रिया", "बस"
        )
        private val PAUSE_WORDS = setOf(
            "pause", "pause listening", "mute", "mute listening", "stop listening",
            "सुनना बंद करो"
        )

        @Volatile var isRunning: Boolean = false
            private set
    }

    private val handler = Handler(Looper.getMainLooper())
    private val worker = Executors.newCachedThreadPool()
    private val prefs by lazy { getSharedPreferences("jarvis", Context.MODE_PRIVATE) }
    private val audioManager by lazy { getSystemService(Context.AUDIO_SERVICE) as AudioManager }

    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null

    private var wakeWord = "JARVIS"
    private var localeTag = "en-US"

    private var initFailed = false
    private var serviceStarted = false
    private var ttsReady = false
    private var isSpeaking = false
    private var isThinking = false
    private var recognizerActive = false
    private var stopped = false
    private var paused = false

    private var retryDelay = MIN_RETRY_MS
    private var sessionId = 0
    private var commandMode = false
    private var followUp = false
    private var followUpCount = 0
    private var currentTtsWatchdogMs = TTS_WATCHDOG_BASE_MS

    @Volatile private var aiCancelled = false
    private var aiRequestId = 0

    private val history = mutableListOf<Pair<String, String>>()
    private var lastInteraction = 0L

    private var wakeLock: PowerManager.WakeLock? = null
    private var focusRequest: AudioFocusRequest? = null
    private var btRouted = false

    // ---- Runnables ----
    private val ttsWatchdog = Runnable {
        if (isSpeaking) {
            Log.w(TAG, "TTS watchdog fired — recovering")
            try { tts?.stop() } catch (_: Exception) {}
            isSpeaking = false
            if (!stopped && serviceStarted) leaveConversation()
        }
    }

    private val recognizerWatchdog = Runnable {
        if (recognizerActive && !stopped && serviceStarted) {
            Log.w(TAG, "Recognizer watchdog fired — resetting")
            val wasCommand = commandMode
            cancelRecognizer()
            if (wasCommand) onCommandNotHeard() else scheduleRetry()
        }
    }

    private val aiTimeout = Runnable {
        if (isThinking) {
            Log.w(TAG, "AI timeout")
            aiCancelled = true
            aiRequestId++
            isThinking = false
            commandMode = false
            speak(t("That took too long. Please try again.", "इसमें बहुत समय लग गया। कृपया फिर कोशिश करें।"), "cmd_final")
        }
    }

    private val restartRunnable = Runnable {
        if (!stopped && serviceStarted && !paused && !isBusy()) {
            if (commandMode) startCommandListening() else startListeningSession()
        }
    }

    private val focusListener = AudioManager.OnAudioFocusChangeListener { change ->
        if (change == AudioManager.AUDIOFOCUS_LOSS ||
            change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT
        ) {
            handler.post { if (isSpeaking) interruptSpeech() }
        }
    }

    // ---- Lifecycle ----
    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()

        // Check permission BEFORE startForeground (Android 14+ throws otherwise).
        val ok = hasMicPermission() && try {
            startAsForeground("Starting JARVIS...")
            true
        } catch (e: Exception) {
            Log.e(TAG, "startForeground refused", e)
            false
        }
        if (!ok) {
            Log.e(TAG, "Cannot start: mic permission missing or foreground start refused")
            initFailed = true
            stopSelf()
            return
        }

        isRunning = true
        acquireWakeLock()
        tts = TextToSpeech(this, this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (initFailed) {
            stopSelf()
            return START_NOT_STICKY
        }

        when (intent?.action) {
            ACTION_STOP -> {
                stopEverything()
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_SHUT_UP -> { interruptSpeech(); return START_NOT_STICKY }
            ACTION_PAUSE -> { setPaused(true); return START_NOT_STICKY }
            ACTION_RESUME -> { setPaused(false); return START_NOT_STICKY }
        }

        if (!hasMicPermission()) {
            Log.e(TAG, "Microphone permission not granted")
            stopSelf()
            return START_NOT_STICKY
        }

        // Extras first, then saved settings (adjust key names to your app's prefs).
        val wakeRaw = intent?.getStringExtra("wake") ?: prefs.getString("wake_word", null)
        wakeWord = wakeRaw?.trim()?.ifBlank { "JARVIS" } ?: wakeWord

        val localeRaw = intent?.getStringExtra("locale") ?: prefs.getString("speech_locale", null)
        val newLocale = localeRaw?.trim()?.ifBlank { "en-US" } ?: localeTag
        val localeChanged = newLocale != localeTag
        localeTag = newLocale
        if (localeChanged && ttsReady) applyTtsLanguage()

        if (!serviceStarted) {
            stopped = false
            commandMode = false
            serviceStarted = true
            retryDelay = MIN_RETRY_MS
            updateNotification(waitingText())
            scheduleRestart(500L)
        }
        return START_NOT_STICKY
    }

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) {
            Log.e(TAG, "TTS init failed")
            return
        }
        val engine = tts ?: return
        applyTtsLanguage()
        engine.setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANT)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build()
        )

        engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {
                handler.post {
                    handler.removeCallbacks(ttsWatchdog)
                    handler.postDelayed(ttsWatchdog, currentTtsWatchdogMs)
                }
            }

            override fun onDone(utteranceId: String?) {
                handler.post {
                    handler.removeCallbacks(ttsWatchdog)
                    if (!isSpeaking) return@post // interrupted or watchdog already handled it
                    isSpeaking = false
                    if (stopped || !serviceStarted) return@post

                    when (utteranceId) {
                        "wake_ack" -> {
                            commandMode = true
                            updateNotification("Listening for command")
                            handler.postDelayed({
                                if (!stopped && serviceStarted && !isBusy() && !paused) {
                                    startCommandListening()
                                }
                            }, 350L)
                        }
                        "cmd_reply" -> {
                            if (prefs.getBoolean("follow_up", true) && followUpCount < MAX_FOLLOW_UPS) {
                                followUpCount++
                                followUp = true
                                commandMode = true
                                updateNotification("Listening for follow-up")
                                handler.postDelayed({
                                    if (!stopped && serviceStarted && !isBusy() && !paused) {
                                        startCommandListening()
                                    }
                                }, 350L)
                            } else {
                                leaveConversation()
                            }
                        }
                        else -> leaveConversation()
                    }
                }
            }

            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                Log.w(TAG, "Legacy TTS onError ignored")
            }

            override fun onError(utteranceId: String?, errorCode: Int) {
                handler.post {
                    handler.removeCallbacks(ttsWatchdog)
                    Log.e(TAG, "TTS error: $errorCode")
                    isSpeaking = false
                    if (!stopped && serviceStarted) leaveConversation()
                }
            }
        })

        ttsReady = true
        if (serviceStarted && !stopped) scheduleRestart(500L)
    }

    private fun applyTtsLanguage() {
        val engine = tts ?: return
        val result = engine.setLanguage(Locale.forLanguageTag(localeTag))
        if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            engine.setLanguage(Locale.US)
        }
    }

    // ---- Wake word session ----
    private fun startListeningSession() {
        if (stopped || !serviceStarted || paused || isBusy() || recognizerActive) return
        if (!hasMicPermission()) { stopSelf(); return }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.e(TAG, "Speech recognition unavailable")
            scheduleRetry()
            return
        }

        val currentSession = ++sessionId
        val rec = createRecognizer()

        rec.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                if (currentSession != sessionId) return
                recognizerActive = true
                retryDelay = MIN_RETRY_MS
                updateNotification("Listening for \"$wakeWord\"")
            }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onError(error: Int) {
                if (currentSession != sessionId) return
                handler.removeCallbacks(recognizerWatchdog)
                recognizerActive = false
                when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH,
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> {
                        // Normal silence — quick straight retry, no backoff
                        scheduleRestart(200L)
                    }
                    else -> {
                        Log.w(TAG, "Wake error: $error")
                        cancelRecognizer()
                        scheduleRetry()
                    }
                }
            }
            override fun onResults(results: Bundle?) {
                if (currentSession != sessionId) return
                handler.removeCallbacks(recognizerWatchdog)
                recognizerActive = false
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION).orEmpty()
                val detected = matches.any { matchesWake(it) }
                cancelRecognizer()
                if (detected) {
                    commandMode = true
                    followUp = false
                    followUpCount = 0
                    if (prefs.getBoolean("wake_beep", false)) {
                        beepThenListen()
                    } else {
                        speak(t("Yes Sir, how may I help you?", "जी, बोलिए।"), "wake_ack")
                    }
                } else {
                    scheduleRestart(MIN_RETRY_MS)
                }
            }
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        try {
            recognizerActive = true
            rec.startListening(buildSpeechIntent(maxResults = 3))
            handler.removeCallbacks(recognizerWatchdog)
            handler.postDelayed(recognizerWatchdog, RECOGNIZER_WATCHDOG_MS)
        } catch (e: Exception) {
            Log.e(TAG, "startListening wake failed", e)
            recognizerActive = false
            cancelRecognizer()
            scheduleRetry()
        }
    }

    // ---- Command session ----
    private fun startCommandListening() {
        if (stopped || paused || isBusy() || !serviceStarted) return
        cancelRestart()
        enableBtMic()

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            commandMode = false
            speak(t("Speech recognition is unavailable.", "स्पीच रिकग्निशन उपलब्ध नहीं है।"), "cmd_final")
            return
        }

        val currentSession = ++sessionId
        val rec = createRecognizer()

        rec.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                if (currentSession != sessionId) return
                recognizerActive = true
                updateNotification("Listening for command")
            }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onError(error: Int) {
                if (currentSession != sessionId) return
                handler.removeCallbacks(recognizerWatchdog)
                recognizerActive = false
                cancelRecognizer()
                onCommandNotHeard()
            }
            override fun onResults(results: Bundle?) {
                if (currentSession != sessionId) return
                handler.removeCallbacks(recognizerWatchdog)
                recognizerActive = false
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()?.trim()
                cancelRecognizer()
                if (!text.isNullOrBlank()) {
                    processBackgroundCommand(text)
                } else {
                    onCommandNotHeard()
                }
            }
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        try {
            recognizerActive = true
            rec.startListening(buildSpeechIntent(maxResults = 1))
            handler.removeCallbacks(recognizerWatchdog)
            handler.postDelayed(recognizerWatchdog, RECOGNIZER_WATCHDOG_MS)
        } catch (e: Exception) {
            Log.e(TAG, "startListening command failed", e)
            recognizerActive = false
            cancelRecognizer()
            commandMode = false
            speak(t("I couldn't start listening.", "मैं सुनना शुरू नहीं कर पाया।"), "cmd_final")
        }
    }

    /** Nothing usable was heard in command mode. */
    private fun onCommandNotHeard() {
        if (followUp) {
            // Follow-up window expired: quietly go back to wake word mode.
            leaveConversation()
        } else {
            commandMode = false
            speak(t("I didn't catch that. Please try again.", "मैं समझ नहीं पाया। कृपया फिर से बोलिए।"), "cmd_final")
        }
    }

    private fun processBackgroundCommand(rawText: String) {
        val norm = normalizeCommand(rawText)

        // Built-in voice controls
        when {
            norm in STOP_WORDS -> {
                broadcastEvent(rawText, "")
                leaveConversation()
                return
            }
            norm in END_WORDS -> {
                commandMode = false
                reply(rawText, t("You're welcome.", "कोई बात नहीं।"), "cmd_final", remember = false)
                return
            }
            norm in PAUSE_WORDS -> {
                commandMode = false
                setPaused(true)
                reply(
                    rawText,
                    t("Paused. Use the notification to resume.", "रुका हुआ है। चालू करने के लिए नोटिफिकेशन का उपयोग करें।"),
                    "cmd_final", remember = false
                )
                return
            }
        }

        val requestId = ++aiRequestId
        aiCancelled = false
        isThinking = true
        updateNotification("Thinking...")
        handler.removeCallbacks(aiTimeout)
        handler.postDelayed(aiTimeout, AI_TIMEOUT_MS)

        val aiPrompt = buildAiPrompt(rawText)

        worker.execute {
            val result: Pair<String, Boolean> = try {
                runPipeline(rawText, aiPrompt)
            } catch (e: Exception) {
                "AI request failed: ${e.message ?: "Check internet."}" to false
            }
            handler.post {
                if (requestId != aiRequestId || stopped) return@post // cancelled or timed out
                handler.removeCallbacks(aiTimeout)
                isThinking = false
                commandMode = false
                reply(rawText, result.first, if (result.second) "cmd_reply" else "cmd_final", remember = result.second)
            }
        }
    }

    /** Runs off the main thread. Returns (text, success). */
    private fun runPipeline(rawText: String, aiPrompt: String): Pair<String, Boolean> {
        // 1) Shared router (same commands as in-app)
        val localReply = try {
            JarvisCommandRouter.handle(this, rawText, wakeWord)
        } catch (e: Exception) {
            Log.e(TAG, "Router failed", e)
            null
        }
        if (localReply != null) return localReply to true

        // 2) Offline engine
        val offlineReply = try {
            OfflineAssistantEngine.handleCommand(rawText)
        } catch (e: Exception) {
            Log.e(TAG, "Offline engine failed", e)
            null
        }
        if (offlineReply != null) return offlineReply to true

        // 3) AI fallback
        val key = ApiKeyStore.get(this)
        val endpoint = prefs.getString("endpoint", "https://api.openai.com/v1/chat/completions")
            .orEmpty().ifBlank { "https://api.openai.com/v1/chat/completions" }
        val model = prefs.getString("model", "gpt-4o-mini")
            .orEmpty().ifBlank { "gpt-4o-mini" }

        if (key.isBlank()) {
            return t(
                "I couldn't answer that offline. Add an API key in Settings.",
                "मैं इसका जवाब ऑफ़लाइन नहीं दे सका। सेटिंग्स में API key जोड़ें।"
            ) to false
        }
        if (!hasInternet()) {
            return when (JarvisLanguage.detect(rawText)) {
                JarvisLanguage.Language.HINDI -> "अभी इंटरनेट नहीं है, सर। ऑफ़लाइन कमांड उपलब्ध हैं, लेकिन AI जवाब के लिए इंटरनेट चाहिए।"
                JarvisLanguage.Language.HINGLISH -> "Sir, abhi internet offline hai. Local commands available hain, lekin AI answer ke liye internet chahiye."
                JarvisLanguage.Language.ENGLISH -> "I'm offline right now, Sir. Local commands still work, but AI answers require internet."
            } to false
        }

        val answer = try {
            AiProvider.answer(
                endpoint, model, key, aiPrompt, emptyList(), "", emptyList(),
                false, false, false
            ) { aiCancelled }
        } catch (e: Exception) {
            return "AI request failed: ${e.message ?: "Check internet."}" to false
        }
        return answer to true
    }

    // ---- Reply / TTS ----
    private fun reply(userText: String, text: String, utteranceId: String, remember: Boolean = true) {
        val detectedLocale = JarvisLanguage.ttsLocale(userText)
        val languageResult = tts?.setLanguage(detectedLocale)
        if (languageResult == TextToSpeech.LANG_MISSING_DATA || languageResult == TextToSpeech.LANG_NOT_SUPPORTED) {
            tts?.setLanguage(if (JarvisLanguage.detect(userText) == JarvisLanguage.Language.HINDI) Locale("hi", "IN") else Locale.US)
        }
        if (remember) remember(userText, text)
        broadcastEvent(userText, text)
        speak(text, utteranceId)
    }

    private fun speak(text: String, utteranceId: String) {
        if (stopped || !serviceStarted) return
        cancelRestart()
        cancelRecognizer()

        isSpeaking = true
        updateNotification("JARVIS is speaking")

        if (!ttsReady || tts == null) {
            Log.w(TAG, "TTS not ready")
            isSpeaking = false
            scheduleRestart(MIN_RETRY_MS)
            return
        }

        requestFocus()

        val safeText = text.take(TextToSpeech.getMaxSpeechInputLength() - 1)
        currentTtsWatchdogMs = TTS_WATCHDOG_BASE_MS + safeText.length * TTS_WATCHDOG_PER_CHAR_MS
        handler.removeCallbacks(ttsWatchdog)
        handler.postDelayed(ttsWatchdog, currentTtsWatchdogMs)

        val result = tts?.speak(safeText, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
        if (result == TextToSpeech.ERROR) {
            Log.e(TAG, "TTS speak failed")
            handler.removeCallbacks(ttsWatchdog)
            isSpeaking = false
            scheduleRestart(MIN_RETRY_MS)
        }
    }

    /** Stops talking / thinking right now and goes back to wake word mode. */
    private fun interruptSpeech() {
        aiCancelled = true
        aiRequestId++
        handler.removeCallbacks(aiTimeout)
        handler.removeCallbacks(ttsWatchdog)
        try { tts?.stop() } catch (_: Exception) {}
        isSpeaking = false
        isThinking = false
        leaveConversation()
    }

    private fun leaveConversation() {
        commandMode = false
        followUp = false
        followUpCount = 0
        disableBtMic()
        abandonFocus()
        if (!stopped && serviceStarted) {
            updateNotification(waitingText())
            scheduleRestart(MIN_RETRY_MS)
        }
    }

    private fun setPaused(value: Boolean) {
        paused = value
        if (value) {
            cancelRestart()
            cancelRecognizer()
            commandMode = false
            followUp = false
            releaseWakeLock()
            updateNotification("Paused")
        } else {
            acquireWakeLock()
            updateNotification(waitingText())
            scheduleRestart(300L)
        }
    }

    // ---- Wake word matching ----
    private fun matchesWake(text: String): Boolean {
        val lower = text.lowercase(Locale.ROOT)
        val wake = wakeWord.lowercase(Locale.ROOT)
        if (lower.contains(wake)) return true
        if (wake == "jarvis" && JARVIS_VARIANTS.any { lower.contains(it) }) return true
        if (wake.length >= 5) {
            return lower.split(Regex("[\\s,.!?]+"))
                .any { it.length >= 4 && editDistance(it, wake) <= 1 }
        }
        return false
    }

    private fun editDistance(a: String, b: String): Int {
        if (kotlin.math.abs(a.length - b.length) > 1) return 2
        val dp = IntArray(b.length + 1) { it }
        for (i in 1..a.length) {
            var prev = dp[0]
            dp[0] = i
            for (j in 1..b.length) {
                val tmp = dp[j]
                dp[j] = minOf(
                    dp[j] + 1,
                    dp[j - 1] + 1,
                    prev + if (a[i - 1] == b[j - 1]) 0 else 1
                )
                prev = tmp
            }
        }
        return dp[b.length]
    }

    private fun normalizeCommand(raw: String): String =
        raw.lowercase(Locale.ROOT)
            .replace(wakeWord.lowercase(Locale.ROOT), " ")
            .replace(Regex("[^\\p{L}\\p{M}\\p{N}' ]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

    // ---- Conversation memory ----
    private fun buildAiPrompt(newText: String): String {
        if (System.currentTimeMillis() - lastInteraction > HISTORY_EXPIRE_MS) history.clear()
        if (history.isEmpty()) return newText
        val sb = StringBuilder("Earlier in this conversation:\n")
        history.forEach { (u, a) ->
            sb.append("User: ").append(u).append("\nAssistant: ").append(a).append('\n')
        }
        sb.append("\nNow the user says: ").append(newText)
        return sb.toString()
    }

    private fun remember(user: String, assistant: String) {
        lastInteraction = System.currentTimeMillis()
        history.add(user to assistant.take(400))
        while (history.size > MAX_EXCHANGES) history.removeAt(0)
    }

    // ---- App updates ----
    private fun broadcastEvent(user: String, reply: String) {
        try {
            sendBroadcast(
                Intent(ACTION_EVENT)
                    .setPackage(packageName)
                    .putExtra(EXTRA_USER, user)
                    .putExtra(EXTRA_REPLY, reply)
            )
        } catch (e: Exception) {
            Log.w(TAG, "broadcast failed", e)
        }
    }

    // ---- Beep instead of "Yes Sir" ----
    private fun beepThenListen() {
        try {
            val tg = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 80)
            tg.startTone(ToneGenerator.TONE_PROP_ACK, 150)
            handler.postDelayed({ try { tg.release() } catch (_: Exception) {} }, 500L)
        } catch (e: Exception) {
            Log.w(TAG, "beep failed", e)
        }
        updateNotification("Listening for command")
        handler.postDelayed({
            if (!stopped && serviceStarted && !isBusy() && !paused) startCommandListening()
        }, 450L)
    }

    // ---- Audio focus ----
    private fun requestFocus() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val req = focusRequest ?: AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                    .setAudioAttributes(
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ASSISTANT)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .build()
                    )
                    .setOnAudioFocusChangeListener(focusListener, handler)
                    .build()
                    .also { focusRequest = it }
                audioManager.requestAudioFocus(req)
            } else {
                @Suppress("DEPRECATION")
                audioManager.requestAudioFocus(
                    focusListener, AudioManager.STREAM_MUSIC,
                    AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK
                )
            }
        } catch (e: Exception) {
            Log.w(TAG, "requestFocus failed", e)
        }
    }

    private fun abandonFocus() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                focusRequest?.let { audioManager.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                audioManager.abandonAudioFocus(focusListener)
            }
        } catch (e: Exception) {
            Log.w(TAG, "abandonFocus failed", e)
        }
    }

    // ---- Bluetooth headset mic (opt-in, experimental) ----
    private fun hasBtPermission(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) ==
            PackageManager.PERMISSION_GRANTED

    @Suppress("DEPRECATION")
    private fun enableBtMic() {
        if (btRouted || !prefs.getBoolean("bt_mic", false) || !hasBtPermission()) return
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val device = audioManager.availableCommunicationDevices
                    .firstOrNull { it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO }
                if (device != null) btRouted = audioManager.setCommunicationDevice(device)
            } else if (audioManager.isBluetoothScoAvailableOffCall) {
                audioManager.startBluetoothSco()
                audioManager.isBluetoothScoOn = true
                btRouted = true
            }
        } catch (e: Exception) {
            Log.w(TAG, "enableBtMic failed", e)
        }
    }

    @Suppress("DEPRECATION")
    private fun disableBtMic() {
        if (!btRouted) return
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                audioManager.clearCommunicationDevice()
            } else {
                audioManager.isBluetoothScoOn = false
                audioManager.stopBluetoothSco()
            }
        } catch (e: Exception) {
            Log.w(TAG, "disableBtMic failed", e)
        }
        btRouted = false
    }

    // ---- Wake lock ----
    private fun acquireWakeLock() {
        if (!prefs.getBoolean("use_wakelock", true)) return
        try {
            if (wakeLock?.isHeld == true) return
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "jarvis:wake").apply {
                setReferenceCounted(false)
                acquire(WAKE_LOCK_MS)
            }
        } catch (e: Exception) {
            Log.w(TAG, "wakelock acquire failed", e)
        }
    }

    private fun releaseWakeLock() {
        try {
            wakeLock?.let { if (it.isHeld) it.release() }
        } catch (e: Exception) {
            Log.w(TAG, "wakelock release failed", e)
        }
        wakeLock = null
    }

    // ---- Helpers ----
    private fun t(en: String, hi: String): String =
        if (localeTag.startsWith("hi", ignoreCase = true)) hi else en

    private fun isBusy(): Boolean = isSpeaking || isThinking

    private fun waitingText(): String =
        if (paused) "Paused" else "Waiting for \"$wakeWord\""

    private fun hasInternet(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        return try {
            val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        } catch (e: Exception) {
            true // don't block AI on a failed check
        }
    }

    private fun buildSpeechIntent(maxResults: Int): Intent =
        Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, localeTag)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, maxResults)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L)
        }

    private fun createRecognizer(): SpeechRecognizer {
        recognizer?.let {
            try { it.destroy() } catch (_: Exception) {}
            recognizer = null
        }
        return SpeechRecognizer.createSpeechRecognizer(this).also { recognizer = it }
    }

    private fun hasMicPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private fun scheduleRetry() {
        if (stopped || !serviceStarted || isBusy()) return
        val delay = retryDelay
        retryDelay = (retryDelay * 2).coerceAtMost(MAX_RETRY_MS)
        scheduleRestart(delay)
    }

    private fun scheduleRestart(delay: Long) {
        if (stopped || !serviceStarted || paused || isBusy()) return
        handler.removeCallbacks(restartRunnable)
        handler.postDelayed(restartRunnable, delay)
    }

    private fun cancelRestart() = handler.removeCallbacks(restartRunnable)

    private fun cancelRecognizer() {
        sessionId++
        recognizerActive = false
        handler.removeCallbacks(recognizerWatchdog)
        val old = recognizer
        recognizer = null
        try { old?.cancel() } catch (_: Exception) {}
        try { old?.destroy() } catch (_: Exception) {}
    }

    // ---- Notification ----
    private fun pendingFlags(): Int =
        PendingIntent.FLAG_UPDATE_CURRENT or
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0

    private fun serviceAction(action: String, requestCode: Int): PendingIntent =
        PendingIntent.getService(
            this, requestCode,
            Intent(this, JarvisWakeService::class.java).setAction(action),
            pendingFlags()
        )

    private fun startAsForeground(message: String) {
        val notification = buildNotification(message)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun updateNotification(message: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, buildNotification(message))
    }

    private fun buildNotification(message: String): Notification {
        val openIntent = Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pi = PendingIntent.getActivity(this, 0, openIntent, pendingFlags())

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("JARVIS Assistant")
            .setContentText(message)
            .setContentIntent(pi)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(
                0,
                if (paused) "Resume" else "Pause",
                serviceAction(if (paused) ACTION_RESUME else ACTION_PAUSE, 11)
            )
            .addAction(0, "Stop talking", serviceAction(ACTION_SHUT_UP, 12))
            .addAction(0, "Turn off", serviceAction(ACTION_STOP, 13))
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID, "JARVIS voice assistant", NotificationManager.IMPORTANCE_LOW
            )
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(channel)
        }
    }

    // ---- Shutdown ----
    private fun stopEverything() {
        stopped = true
        serviceStarted = false
        isSpeaking = false
        isThinking = false
        commandMode = false
        followUp = false
        isRunning = false
        aiCancelled = true
        aiRequestId++

        handler.removeCallbacksAndMessages(null)
        cancelRecognizer()
        disableBtMic()
        abandonFocus()
        releaseWakeLock()

        try { tts?.stop() } catch (_: Exception) {}

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(STOP_FOREGROUND_REMOVE)
        } else {
            @Suppress("DEPRECATION") stopForeground(true)
        }
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        if (STOP_ON_TASK_REMOVED) {
            stopEverything()
            stopSelf()
        }
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        stopEverything()
        try { tts?.shutdown() } catch (_: Exception) {}
        tts = null
        ttsReady = false
        worker.shutdownNow()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
