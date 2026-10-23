package com.jarvisassistant.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
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
import java.util.Date
import java.util.Locale
import java.text.SimpleDateFormat

class JarvisWakeService : Service() {
    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var wakeWord = "JARVIS"
    private var locale = "en-US"
    private var restarting = false
    private var stopRequested = false
    private var wakePauseUntil = 0L
    private var isListeningForCommand = false

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(91, notification())
        
        // TTS Setup for Background
        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale.UK // British accent for JARVIS
                tts?.setPitch(0.85f) // Deep voice
                tts?.setSpeechRate(0.90f)
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {}
                    override fun onDone(utteranceId: String?) {
                        if (utteranceId == "wake_ack") {
                            // After saying "Yes Sir...", start listening for command
                            Handler(Looper.getMainLooper()).postDelayed({
                                startCommandListening()
                            }, 300L)
                        }
                    }
                    override fun onError(utteranceId: String?) {}
                })
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopRequested = true
            stopSelf()
            return START_NOT_STICKY
        }
        stopRequested = false
        wakeWord = intent?.getStringExtra("wake")?.trim().orEmpty().ifBlank { "JARVIS" }
        locale = intent?.getStringExtra("locale")?.trim().orEmpty().ifBlank { "en-US" }
        updateNotification()
        isListeningForCommand = false
        startListening()
        return START_NOT_STICKY
    }

    // 1. Listen for Wake Word
    private fun startListening() {
        if (stopRequested || System.currentTimeMillis() < wakePauseUntil || !SpeechRecognizer.isRecognitionAvailable(this)) return
        
        recognizer?.cancel()
        recognizer?.destroy()
        
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).also { r ->
            r.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) = Unit
                override fun onBeginningOfSpeech() = Unit
                override fun onRmsChanged(rmsdB: Float) = Unit
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onEndOfSpeech() = Unit
                
                override fun onError(error: Int) { scheduleRestart(1000L) }
                
                override fun onResults(results: Bundle?) {
                    val words = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION).orEmpty()
                    
                    var hit = false
                    for (spoken in words) {
                        val cleanText = spoken.trim().lowercase()
                        if (cleanText.contains("jarvis") && cleanText.length < 30) {
                            hit = true
                            break
                        }
                    }
                    
                    if (hit) {
                        recognizer?.cancel()
                        recognizer?.destroy()
                        recognizer = null
                        
                        // Active! Speak "Yes Sir..."
                        wakePauseUntil = System.currentTimeMillis() + 20000L // 20 sec pause for wake word
                        tts?.speak("Yes Sir, how may I help you?", TextToSpeech.QUEUE_FLUSH, null, "wake_ack")
                    } else {
                        scheduleRestart(800L)
                    }
                }
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            })
            
            val i = JarvisVoiceEngine.recognitionIntent(locale, preferOffline = true)
            try { r.startListening(i) } catch (_: Exception) { scheduleRestart(1000L) }
        }
    }

    // 2. Listen for the actual command
    private fun startCommandListening() {
        if (stopRequested) return
        isListeningForCommand = true
        
        recognizer?.cancel()
        recognizer?.destroy()
        
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).also { r ->
            r.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) = Unit
                override fun onBeginningOfSpeech() = Unit
                override fun onRmsChanged(rmsdB: Float) = Unit
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onEndOfSpeech() = Unit
                
                override fun onError(error: Int) {
                    tts?.speak("I didn't catch that.", TextToSpeech.QUEUE_FLUSH, null, "")
                    isListeningForCommand = false
                    scheduleRestart(2000L)
                }
                
                override fun onResults(results: Bundle?) {
                    isListeningForCommand = false
                    val words = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION).orEmpty()
                    val command = words.firstOrNull() ?: ""
                    
                    if (command.isNotBlank()) {
                        processBackgroundCommand(command)
                    } else {
                        scheduleRestart(1000L)
                    }
                }
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            })
            
            val i = JarvisVoiceEngine.recognitionIntent(locale, preferOffline = false)
            try { r.startListening(i) } catch (_: Exception) { scheduleRestart(1000L) }
        }
    }

    // 3. Process the command directly in background (without opening app)
    private fun processBackgroundCommand(command: String) {
        val lower = command.lowercase()
        var reply = ""

        if (lower.contains("time")) {
            reply = "It is ${SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date())}."
        } else if (lower.contains("date")) {
            reply = "Today is ${SimpleDateFormat("EEEE, d MMMM yyyy", Locale.getDefault()).format(Date())}."
        } else if (lower.contains("open") || lower.contains("kholo")) {
            val appName = lower.replace("open ", "").replace(" kholo", "").replace(" ko", "").trim()
            reply = openAppInBackground(appName)
        } else {
            reply = "I heard: $command. Please open the JARVIS app to use advanced commands."
        }

        tts?.speak(reply, TextToSpeech.QUEUE_FLUSH, null, "cmd_reply")
        // After replying, go back to wake word listening
        scheduleRestart(3000L) 
    }

    private fun openAppInBackground(appName: String): String {
        val pm = packageManager
        for (pkg in pm.getInstalledPackages(0)) {
            val label = pm.getApplicationLabel(pkg.applicationInfo).toString()
            if (label.equals(appName, ignoreCase = true)) {
                val intent = pm.getLaunchIntentForPackage(pkg.packageName)
                if (intent != null) {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    startActivity(intent)
                    return "Opening $label."
                }
            }
        }
        return "App not found: $appName"
    }

    private fun scheduleRestart(delay: Long) {
        if (restarting || stopRequested) return
        restarting = true
        Handler(Looper.getMainLooper()).postDelayed({
            restarting = false
            if (!stopRequested) {
                isListeningForCommand = false
                startListening()
            }
        }, delay)
    }

    override fun onDestroy() {
        stopRequested = true
        recognizer?.cancel()
        recognizer?.destroy()
        recognizer = null
        tts?.stop()
        tts?.shutdown()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel("jarvis_assistant", "JARVIS Assistant", NotificationManager.IMPORTANCE_LOW)
            channel.description = "JARVIS background listener"
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun updateNotification() {
        getSystemService(NotificationManager::class.java).notify(91, notification())
    }

    private fun notification(): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stop = PendingIntent.getService(this, 1, Intent(this, JarvisWakeService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        
        val title = if (isListeningForCommand) "JARVIS is listening..." else "JARVIS is ready"
        
        return NotificationCompat.Builder(this, "jarvis_assistant")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle(title)
            .setContentText("Say 'Jarvis' to activate.")
            .setContentIntent(open)
            .addAction(NotificationCompat.Action.Builder(0, "Stop", stop).build())
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    companion object {
        const val ACTION_WAKE = "com.jarvisassistant.app.JARVIS_WAKE"
        const val ACTION_STOP = "com.jarvisassistant.app.JARVIS_STOP_WAKE"
    }
}
