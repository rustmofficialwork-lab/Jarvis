package com.jarvisassistant.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.core.app.NotificationCompat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class JarvisWakeService : Service() {

    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null

    private var wakeWord = "JARVIS"
    private var locale = "en-US"

    private var stopRequested = false
    private var isListeningForCommand = false
    private var isSpeaking = false
    private var ttsReady = false
    private var serviceStarted = false

    private var restartRunnable: Runnable? = null
    private var restartDelay = 1500L

    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onCreate() {
        super.onCreate()

        createChannel()
        startForeground(91, notification())

        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                ttsReady = true

                tts?.language = Locale.UK
                tts?.setPitch(0.85f)
                tts?.setSpeechRate(0.90f)

                tts?.setOnUtteranceProgressListener(
                    object : UtteranceProgressListener() {

                        override fun onStart(utteranceId: String?) {
                            mainHandler.post {
                                isSpeaking = true
                            }
                        }

                        override fun onDone(utteranceId: String?) {
                            mainHandler.post {
                                isSpeaking = false

                                when (utteranceId) {
                                    "wake_ack" -> {
                                        if (!stopRequested) {
                                            isListeningForCommand = true
                                            updateNotification()
                                            scheduleRestart(500L)
                                        }
                                    }

                                    "cmd_reply", "command_error" -> {
                                        isListeningForCommand = false
                                        updateNotification()
                                        scheduleRestart(1500L)
                                    }
                                }
                            }
                        }

                        override fun onError(utteranceId: String?) {
                            mainHandler.post {
                                isSpeaking = false
                                isListeningForCommand = false
                                updateNotification()
                                scheduleRestart(2000L)
                            }
                        }
                    }
                )

                if (serviceStarted && !stopRequested) {
                    scheduleRestart(500L)
                }
            }
        }
    }

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int
    ): Int {

        if (intent?.action == ACTION_STOP) {
            stopRequested = true
            cancelRestart()
            stopSelf()
            return START_NOT_STICKY
        }

        stopRequested = false
        serviceStarted = true

        wakeWord = intent
            ?.getStringExtra("wake")
            ?.trim()
            ?.ifBlank { "JARVIS" }
            ?: "JARVIS"

        locale = intent
            ?.getStringExtra("locale")
            ?.trim()
            ?.ifBlank { "en-US" }
            ?: "en-US"

        isListeningForCommand = false
        updateNotification()

        cancelRestart()

        if (ttsReady) {
            scheduleRestart(500L)
        }

        return START_NOT_STICKY
    }

    private fun startListening() {
        if (stopRequested || isSpeaking || isListeningForCommand) {
            return
        }

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            scheduleRestart(10000L)
            return
        }

        cancelRecognizer()

        try {
            val newRecognizer =
                SpeechRecognizer.createSpeechRecognizer(this)

            recognizer = newRecognizer

            newRecognizer.setRecognitionListener(
                object : RecognitionListener {

                    override fun onReadyForSpeech(params: Bundle?) {
                        restartDelay = 1500L
                    }

                    override fun onBeginningOfSpeech() = Unit

                    override fun onRmsChanged(rmsdB: Float) = Unit

                    override fun onBufferReceived(buffer: ByteArray?) = Unit

                    override fun onEndOfSpeech() = Unit

                    override fun onPartialResults(
                        partialResults: Bundle?
                    ) = Unit

                    override fun onEvent(
                        eventType: Int,
                        params: Bundle?
                    ) = Unit

                    override fun onError(error: Int) {
                        if (stopRequested || isListeningForCommand) {
                            return
                        }

                        recognizer?.destroy()
                        recognizer = null

                        // Gradually back off when recognition keeps failing.
                        val delay = restartDelay
                        restartDelay = (restartDelay * 2)
                            .coerceAtMost(15000L)

                        scheduleRestart(delay)
                    }

                    override fun onResults(results: Bundle?) {
                        if (stopRequested) return

                        val spokenWords = results
                            ?.getStringArrayList(
                                SpeechRecognizer.RESULTS_RECOGNITION
                            )
                            .orEmpty()

                        val wakeDetected = spokenWords.any { spoken ->
                            spoken.trim().contains(
                                wakeWord,
                                ignoreCase = true
                            )
                        }

                        cancelRecognizer()

                        if (wakeDetected) {
                            isListeningForCommand = true
                            updateNotification()

                            speak(
                                "Yes Sir, how may I help you?",
                                "wake_ack"
                            )
                        } else {
                            scheduleRestart(500L)
                        }
                    }
                }
            )

            val intent = JarvisVoiceEngine.recognitionIntent(
                locale,
                preferOffline = false
            )

            newRecognizer.startListening(intent)

        } catch (_: Exception) {
            cancelRecognizer()
            scheduleRestart(restartDelay)

            restartDelay = (restartDelay * 2)
                .coerceAtMost(15000L)
        }
    }

    private fun startCommandListening() {
        if (stopRequested || isSpeaking) return

        cancelRecognizer()

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            isListeningForCommand = false
            scheduleRestart(10000L)
            return
        }

        isListeningForCommand = true
        updateNotification()

        try {
            val newRecognizer =
                SpeechRecognizer.createSpeechRecognizer(this)

            recognizer = newRecognizer

            newRecognizer.setRecognitionListener(
                object : RecognitionListener {

                    override fun onReadyForSpeech(params: Bundle?) = Unit

                    override fun onBeginningOfSpeech() = Unit

                    override fun onRmsChanged(rmsdB: Float) = Unit

                    override fun onBufferReceived(buffer: ByteArray?) = Unit

                    override fun onEndOfSpeech() = Unit

                    override fun onPartialResults(
                        partialResults: Bundle?
                    ) = Unit

                    override fun onEvent(
                        eventType: Int,
                        params: Bundle?
                    ) = Unit

                    override fun onError(error: Int) {
                        if (stopRequested) return

                        cancelRecognizer()
                        isListeningForCommand = false
                        updateNotification()

                        speak(
                            "I didn't catch that.",
                            "command_error"
                        )
                    }

                    override fun onResults(results: Bundle?) {
                        if (stopRequested) return

                        val words = results
                            ?.getStringArrayList(
                                SpeechRecognizer.RESULTS_RECOGNITION
                            )
                            .orEmpty()

                        val command = words.firstOrNull().orEmpty()

                        cancelRecognizer()
                        isListeningForCommand = false
                        updateNotification()

                        if (command.isNotBlank()) {
                            processBackgroundCommand(command)
                        } else {
                            scheduleRestart(1000L)
                        }
                    }
                }
            )

            val intent = JarvisVoiceEngine.recognitionIntent(
                locale,
                preferOffline = false
            )

            newRecognizer.startListening(intent)

        } catch (_: Exception) {
            cancelRecognizer()
            isListeningForCommand = false
            updateNotification()
            scheduleRestart(3000L)
        }
    }

    private fun speak(text: String, utteranceId: String) {
        if (stopRequested || !ttsReady) {
            isSpeaking = false
            isListeningForCommand = false
            scheduleRestart(2000L)
            return
        }

        cancelRecognizer()
        isSpeaking = true

        val result = tts?.speak(
            text,
            TextToSpeech.QUEUE_FLUSH,
            null,
            utteranceId
        )

        if (result == TextToSpeech.ERROR) {
            isSpeaking = false
            isListeningForCommand = false
            scheduleRestart(2000L)
        }
    }

    private fun processBackgroundCommand(command: String) {
        val lower = command.lowercase(Locale.ROOT)
        val reply: String = when {
            lower.contains("time") ->
                "It is ${
                    SimpleDateFormat(
                        "h:mm a",
                        Locale.getDefault()
                    ).format(Date())
                }."

            lower.contains("date") ->
                "Today is ${
                    SimpleDateFormat(
                        "EEEE, d MMMM yyyy",
                        Locale.getDefault()
                    ).format(Date())
                }."

            lower.contains("open") || lower.contains("kholo") -> {
                val appName = lower
                    .replace("open ", "")
                    .replace(" kholo", "")
                    .replace(" ko", "")
                    .trim()

                openAppInBackground(appName)
            }

            else ->
                "I heard: $command. Please open the JARVIS app for advanced commands."
        }

        speak(reply, "cmd_reply")
    }

    private fun openAppInBackground(appName: String): String {
        val pm = packageManager

        return try {
            val apps = pm.getInstalledApplications(0)

            for (app in apps) {
                val label = pm.getApplicationLabel(app).toString()

                if (label.equals(appName, ignoreCase = true)) {
                    val launchIntent =
                        pm.getLaunchIntentForPackage(app.packageName)

                    if (launchIntent != null) {
                        launchIntent.addFlags(
                            Intent.FLAG_ACTIVITY_NEW_TASK
                        )
                        startActivity(launchIntent)
                        return "Opening $label."
                    }
                }
            }

            "App not found: $appName"

        } catch (_: Exception) {
            "I couldn't open that app."
        }
    }

    private fun scheduleRestart(delay: Long) {
        if (stopRequested) return

        cancelRestart()

        val task = Runnable {
            restartRunnable = null

            if (stopRequested || isSpeaking) return@Runnable

            if (isListeningForCommand) {
                startCommandListening()
            } else {
                startListening()
            }
        }

        restartRunnable = task
        mainHandler.postDelayed(task, delay)
    }

    private fun cancelRestart() {
        restartRunnable?.let {
            mainHandler.removeCallbacks(it)
        }
        restartRunnable = null
    }

    private fun cancelRecognizer() {
        val oldRecognizer = recognizer
        recognizer = null

        try {
            oldRecognizer?.cancel()
        } catch (_: Exception) {
        }

        try {
            oldRecognizer?.destroy()
        } catch (_: Exception) {
        }
    }

    override fun onDestroy() {
        stopRequested = true
        serviceStarted = false

        cancelRestart()
        mainHandler.removeCallbacksAndMessages(null)
        cancelRecognizer()

        try {
            tts?.stop()
            tts?.shutdown()
        } catch (_: Exception) {
        }

        tts = null
        ttsReady = false

        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "jarvis_assistant",
                "JARVIS Assistant",
                NotificationManager.IMPORTANCE_LOW
            )

            channel.description = "JARVIS background listener"

            getSystemService(
                NotificationManager::class.java
            ).createNotificationChannel(channel)
        }
    }

    private fun updateNotification() {
        getSystemService(NotificationManager::class.java)
            .notify(91, notification())
    }

    private fun notification(): Notification {
        val openIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or
                PendingIntent.FLAG_UPDATE_CURRENT
        )

        val stopIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, JarvisWakeService::class.java)
                .setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE or
                PendingIntent.FLAG_UPDATE_CURRENT
        )

        val title = when {
            isSpeaking -> "JARVIS is speaking..."
            isListeningForCommand -> "JARVIS is listening for command..."
            else -> "JARVIS is ready"
        }

        return NotificationCompat.Builder(
            this,
            "jarvis_assistant"
        )
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle(title)
            .setContentText("Say '$wakeWord' to activate.")
            .setContentIntent(openIntent)
            .addAction(
                NotificationCompat.Action.Builder(
                    0,
                    "Stop",
                    stopIntent
                ).build()
            )
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    companion object {
        const val ACTION_WAKE =
            "com.jarvisassistant.app.JARVIS_WAKE"

        const val ACTION_STOP =
            "com.jarvisassistant.app.JARVIS_STOP_WAKE"
    }
}
