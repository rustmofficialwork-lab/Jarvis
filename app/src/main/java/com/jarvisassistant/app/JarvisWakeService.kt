
package com.jarvisassistant.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import java.util.Locale

class JarvisWakeService : Service(), TextToSpeech.OnInitListener {

    companion object {
        const val ACTION_WAKE =
            "com.jarvisassistant.app.JARVIS_WAKE"

        const val ACTION_STOP =
            "com.jarvisassistant.app.JARVIS_STOP_WAKE"

        private const val TAG = "JarvisWakeService"
        private const val CHANNEL_ID = "jarvis_wake_channel"
        private const val NOTIFICATION_ID = 4101

        private const val MIN_RETRY_MS = 2000L
        private const val MAX_RETRY_MS = 15000L
    }

    private val handler = Handler(Looper.getMainLooper())

    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null

    private var wakeWord = "JARVIS"
    private var localeTag = "en-US"

    private var serviceStarted = false
    private var ttsReady = false
    private var isSpeaking = false
    private var isListeningForCommand = false
    private var recognizerActive = false
    private var stopped = false

    private var retryDelay = MIN_RETRY_MS
    private var sessionId = 0

    private val restartRunnable = Runnable {
        if (!stopped && serviceStarted && !isSpeaking) {
            startListeningSession()
        }
    }

    override fun onCreate() {
        super.onCreate()

        createNotificationChannel()
        startForeground(
            NOTIFICATION_ID,
            buildNotification("Starting JARVIS...")
        )

        tts = TextToSpeech(this, this)
    }

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int
    ): Int {

        if (intent?.action == ACTION_STOP) {
            stopEverything()
            stopSelf()
            return START_NOT_STICKY
        }

        if (
            ContextCompat.checkSelfPermission(
                this,
                android.Manifest.permission.RECORD_AUDIO
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            Log.e(TAG, "Microphone permission not granted")
            stopSelf()
            return START_NOT_STICKY
        }

        wakeWord = intent
            ?.getStringExtra("wake")
            ?.trim()
            ?.ifBlank { "JARVIS" }
            ?: wakeWord

        localeTag = intent
            ?.getStringExtra("locale")
            ?.trim()
            ?.ifBlank { "en-US" }
            ?: localeTag

        if (!serviceStarted) {
            stopped = false
            serviceStarted = true
            retryDelay = MIN_RETRY_MS
            updateNotification("Waiting for \"$wakeWord\"")
            scheduleRestart(500L)
        } else {
            Log.d(TAG, "Service already running; ignoring duplicate start")
        }

        return START_NOT_STICKY
    }

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) {
            Log.e(TAG, "TextToSpeech initialization failed")
            return
        }

        val engine = tts ?: return

        val languageResult = engine.setLanguage(
            Locale.forLanguageTag(localeTag)
        )

        if (
            languageResult == TextToSpeech.LANG_MISSING_DATA ||
            languageResult == TextToSpeech.LANG_NOT_SUPPORTED
        ) {
            engine.setLanguage(Locale.US)
        }

        engine.setOnUtteranceProgressListener(
            object : UtteranceProgressListener() {

                override fun onStart(utteranceId: String?) {
                    handler.post {
                        isSpeaking = true
                        cancelRestart()
                        cancelRecognizer()
                        updateNotification("JARVIS is speaking")
                    }
                }

                override fun onDone(utteranceId: String?) {
                    handler.post {
                        isSpeaking = false
                        isListeningForCommand = false

                        if (!stopped && serviceStarted) {
                            updateNotification(
                                "Waiting for \"$wakeWord\""
                            )
                            scheduleRestart(MIN_RETRY_MS)
                        }
                    }
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    handler.post {
                        onSpeechFinishedWithError()
                    }
                }

                override fun onError(
                    utteranceId: String?,
                    errorCode: Int
                ) {
                    handler.post {
                        Log.e(
                            TAG,
                            "TTS error: $errorCode"
                        )
                        onSpeechFinishedWithError()
                    }
                }
            }
        )

        ttsReady = true

        if (serviceStarted && !stopped) {
            scheduleRestart(500L)
        }
    }

    private fun startListeningSession() {
        if (
            stopped ||
            !serviceStarted ||
            isSpeaking ||
            recognizerActive
        ) {
            return
        }

        if (
            ContextCompat.checkSelfPermission(
                this,
                android.Manifest.permission.RECORD_AUDIO
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            Log.e(TAG, "Microphone permission missing")
            stopSelf()
            return
        }

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.e(TAG, "Speech recognition unavailable")
            scheduleRetry()
            return
        }

        cancelRecognizer()

        val currentSession = ++sessionId

        try {
            recognizer = SpeechRecognizer
                .createSpeechRecognizer(this)
                .also { speechRecognizer ->

                    speechRecognizer.setRecognitionListener(
                        object : RecognitionListener {

                            override fun onReadyForSpeech(
                                params: android.os.Bundle?
                            ) {
                                if (currentSession != sessionId) return

                                recognizerActive = true
                                retryDelay = MIN_RETRY_MS
                                updateNotification(
                                    "Listening for \"$wakeWord\""
                                )
                                Log.d(TAG, "Ready for wake word")
                            }

                            override fun onBeginningOfSpeech() {
                                if (currentSession != sessionId) return
                                updateNotification("Hearing speech...")
                            }

                            override fun onRmsChanged(rmsdB: Float) = Unit

                            override fun onBufferReceived(
                                buffer: ByteArray?
                            ) = Unit

                            override fun onEndOfSpeech() {
                                if (currentSession != sessionId) return
                                updateNotification("Processing speech...")
                            }

                            override fun onError(error: Int) {
                                if (currentSession != sessionId) return

                                Log.w(
                                    TAG,
                                    "Wake recognition error: $error"
                                )

                                recognizerActive = false
                                cancelRecognizer()
                                scheduleRetry()
                            }

                            override fun onResults(
                                results: android.os.Bundle?
                            ) {
                                if (currentSession != sessionId) return

                                recognizerActive = false

                                val matches = results
                                    ?.getStringArrayList(
                                        SpeechRecognizer.RESULTS_RECOGNITION
                                    )
                                    .orEmpty()

                                val detectedWakeWord = matches.any {
                                    it.contains(
                                        wakeWord,
                                        ignoreCase = true
                                    )
                                }

                                cancelRecognizer()

                                if (detectedWakeWord) {
                                    isListeningForCommand = true
                                    speak(
                                        "Yes Sir, how may I help you?",
                                        "wake_ack"
                                    )
                                } else {
                                    scheduleRestart(MIN_RETRY_MS)
                                }
                            }

                            override fun onPartialResults(
                                partialResults: android.os.Bundle?
                            ) = Unit

                            override fun onEvent(
                                eventType: Int,
                                params: android.os.Bundle?
                            ) = Unit
                        }
                    )

                    val speechIntent = Intent(
                        RecognizerIntent.ACTION_RECOGNIZE_SPEECH
                    ).apply {
                        putExtra(
                            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                        )
                        putExtra(
                            RecognizerIntent.EXTRA_LANGUAGE,
                            localeTag
                        )
                        putExtra(
                            RecognizerIntent.EXTRA_PARTIAL_RESULTS,
                            false
                        )
                        putExtra(
                            RecognizerIntent.EXTRA_MAX_RESULTS,
                            3
                        )
                    }

                    recognizerActive = true
                    speechRecognizer.startListening(speechIntent)
                }

        } catch (e: Exception) {
            Log.e(TAG, "Could not start recognizer", e)
            recognizerActive = false
            cancelRecognizer()
            scheduleRetry()
        }
    }

    private fun startCommandListening() {
        if (stopped || isSpeaking || !serviceStarted) return

        cancelRestart()
        cancelRecognizer()

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            speak(
                "Speech recognition is unavailable.",
                "command_error"
            )
            return
        }

        val currentSession = ++sessionId

        try {
            recognizer = SpeechRecognizer
                .createSpeechRecognizer(this)
                .also { speechRecognizer ->

                    speechRecognizer.setRecognitionListener(
                        object : RecognitionListener {

                            override fun onReadyForSpeech(
                                params: android.os.Bundle?
                            ) {
                                if (currentSession != sessionId) return
                                recognizerActive = true
                                updateNotification("Listening for command")
                            }

                            override fun onBeginningOfSpeech() = Unit

                            override fun onRmsChanged(rmsdB: Float) = Unit

                            override fun onBufferReceived(
                                buffer: ByteArray?
                            ) = Unit

                            override fun onEndOfSpeech() {
                                updateNotification("Processing command...")
                            }

                            override fun onError(error: Int) {
                                if (currentSession != sessionId) return

                                Log.w(
                                    TAG,
                                    "Command recognition error: $error"
                                )

                                recognizerActive = false
                                cancelRecognizer()

                                speak(
                                    "I didn't catch that. Please try again.",
                                    "command_error"
                                )
                            }

                            override fun onResults(
                                results: android.os.Bundle?
                            ) {
                                if (currentSession != sessionId) return

                                recognizerActive = false

                                val text = results
                                    ?.getStringArrayList(
                                        SpeechRecognizer.RESULTS_RECOGNITION
                                    )
                                    ?.firstOrNull()
                                    ?.trim()

                                cancelRecognizer()

                                if (!text.isNullOrBlank()) {
                                    processBackgroundCommand(text)
                                } else {
                                    speak(
                                        "I didn't catch that.",
                                        "command_error"
                                    )
                                }
                            }

                            override fun onPartialResults(
                                partialResults: android.os.Bundle?
                            ) = Unit

                            override fun onEvent(
                                eventType: Int,
                                params: android.os.Bundle?
                            ) = Unit
                        }
                    )

                    val speechIntent = Intent(
                        RecognizerIntent.ACTION_RECOGNIZE_SPEECH
                    ).apply {
                        putExtra(
                            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                        )
                        putExtra(
                            RecognizerIntent.EXTRA_LANGUAGE,
                            localeTag
                        )
                        putExtra(
                            RecognizerIntent.EXTRA_PARTIAL_RESULTS,
                            false
                        )
                        putExtra(
                            RecognizerIntent.EXTRA_MAX_RESULTS,
                            1
                        )
                    }

                    recognizerActive = true
                    speechRecognizer.startListening(speechIntent)
                }

        } catch (e: Exception) {
            Log.e(TAG, "Could not listen for command", e)
            recognizerActive = false
            cancelRecognizer()
            speak("I couldn't start listening.", "command_error")
        }
    }

    private fun processBackgroundCommand(rawText: String) {
        val text = CommandNormalizer
            .normalize(rawText, wakeWord)
            .lowercase(Locale.ROOT)

        val reply = when {
            text.contains("time") ||
                text.contains("samay") ||
                text.contains("waqt") -> {
                "It is ${
                    java.text.SimpleDateFormat(
                        "h:mm a",
                        Locale.getDefault()
                    ).format(java.util.Date())
                }."
            }

            text.contains("date") ||
                text.contains("tareekh") -> {
                "Today is ${
                    java.text.SimpleDateFormat(
                        "EEEE, d MMMM yyyy",
                        Locale.getDefault()
                    ).format(java.util.Date())
                }."
            }

            text.startsWith("open ") ||
                text.endsWith(" kholo") -> {
                val appName = text
                    .removePrefix("open ")
                    .removeSuffix(" kholo")
                    .trim()

                val launchIntent = packageManager
                    .getInstalledPackages(0)
                    .firstNotNullOfOrNull { packageInfo ->
                        val label = packageManager
                            .getApplicationLabel(
                                packageInfo.applicationInfo
                            )
                            .toString()

                        if (label.equals(appName, true)) {
                            packageManager.getLaunchIntentForPackage(
                                packageInfo.packageName
                            )
                        } else {
                            null
                        }
                    }

                if (launchIntent != null) {
                    launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    startActivity(launchIntent)
                    "Opening $appName."
                } else {
                    "I couldn't find $appName."
                }
            }

            else -> {
                "I heard $rawText. Please open JARVIS to use the full assistant."
            }
        }

        speak(reply, "cmd_reply")
    }

    private fun speak(text: String, utteranceId: String) {
        if (stopped || !serviceStarted) return

        cancelRestart()
        cancelRecognizer()

        isSpeaking = true
        updateNotification("JARVIS is speaking")

        if (!ttsReady || tts == null) {
            Log.w(TAG, "TTS is not ready")
            isSpeaking = false
            scheduleRestart(MIN_RETRY_MS)
            return
        }

        val result = tts?.speak(
            text,
            TextToSpeech.QUEUE_FLUSH,
            null,
            utteranceId
        )

        if (result == TextToSpeech.ERROR) {
            Log.e(TAG, "TTS speak failed")
            isSpeaking = false
            scheduleRestart(MIN_RETRY_MS)
        }
    }

    private fun onSpeechFinishedWithError() {
        isSpeaking = false
        isListeningForCommand = false

        if (!stopped && serviceStarted) {
            updateNotification("Waiting for \"$wakeWord\"")
            scheduleRestart(MIN_RETRY_MS)
        }
    }

    private fun scheduleRetry() {
        if (stopped || !serviceStarted || isSpeaking) return

        val delay = retryDelay
        retryDelay = (retryDelay * 2).coerceAtMost(MAX_RETRY_MS)

        scheduleRestart(delay)
    }

    private fun scheduleRestart(delay: Long) {
        if (stopped || !serviceStarted || isSpeaking) return

        handler.removeCallbacks(restartRunnable)
        handler.postDelayed(restartRunnable, delay)
    }

    private fun cancelRestart() {
        handler.removeCallbacks(restartRunnable)
    }

    private fun cancelRecognizer() {
        sessionId++
        recognizerActive = false

        val oldRecognizer = recognizer
        recognizer = null

        try {
            oldRecognizer?.cancel()
        } catch (e: Exception) {
            Log.w(TAG, "Recognizer cancel failed", e)
        }

        try {
            oldRecognizer?.destroy()
        } catch (e: Exception) {
            Log.w(TAG, "Recognizer destroy failed", e)
        }
    }

    private fun updateNotification(message: String) {
        val manager = getSystemService(
            Context.NOTIFICATION_SERVICE
        ) as NotificationManager

        manager.notify(
            NOTIFICATION_ID,
            buildNotification(message)
        )
    }

    private fun buildNotification(message: String): Notification {
        val openIntent = Intent(this, MainActivity::class.java)

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    PendingIntent.FLAG_IMMUTABLE
                } else {
                    0
                }
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("JARVIS Assistant")
            .setContentText(message)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "JARVIS voice assistant",
                NotificationManager.IMPORTANCE_LOW
            )

            val manager = getSystemService(
                Context.NOTIFICATION_SERVICE
            ) as NotificationManager

            manager.createNotificationChannel(channel)
        }
    }

    private fun stopEverything() {
        stopped = true
        serviceStarted = false
        isSpeaking = false
        isListeningForCommand = false

        cancelRestart()
        cancelRecognizer()

        try {
            tts?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "TTS stop failed", e)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(STOP_FOREGROUND_REMOVE)
        } else {
            @Suppress("DEPRECATION")
            stopForeground(true)
        }
    }

    override fun onDestroy() {
        stopEverything()

        try {
            tts?.shutdown()
        } catch (e: Exception) {
            Log.w(TAG, "TTS shutdown failed", e)
        }

        tts = null
        ttsReady = false

        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
