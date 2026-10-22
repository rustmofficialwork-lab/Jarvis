package com.jarvisassistant.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.speech.RecognitionListener
import android.speech.SpeechRecognizer
import androidx.core.app.NotificationCompat

/** User-started, explicit foreground wake listener. */
class JarvisWakeService : Service() {
    private var recognizer: SpeechRecognizer? = null
    private var wakeWord = "JARVIS"
    private var locale = "en-US"
    private var restarting = false
    private var stopRequested = false
    private var wakePauseUntil = 0L

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(91, notification())
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
        startListening()
        return START_NOT_STICKY
    }

    private fun startListening() {
        if (stopRequested || System.currentTimeMillis() < wakePauseUntil || !SpeechRecognizer.isRecognitionAvailable(this)) return
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).also { r ->
            r.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: android.os.Bundle?) = Unit
                override fun onBeginningOfSpeech() = Unit
                override fun onRmsChanged(rmsdB: Float) = Unit
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onEndOfSpeech() = Unit
                
                override fun onError(error: Int) { 
                    // Thoda wait badha diya taaki baar-baar trigger na ho
                    scheduleRestart(1500L) 
                }
                
                override fun onResults(results: android.os.Bundle?) {
                    val words = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION).orEmpty()
                    
                    // STRICT CHECK: Sirf tab trigger hoga jab exact word mile aur lambai 4 se zyada ho
                    val hit = words.firstOrNull { spoken -> 
                        spoken.length >= 4 && spoken.contains(wakeWord, ignoreCase = true) 
                    }
                    
                    if (hit != null) {
                        // Release this recognizer before handing the microphone to MainActivity.
                        recognizer?.cancel()
                        recognizer?.destroy()
                        recognizer = null
                        wakePauseUntil = System.currentTimeMillis() + 8_000L
                        sendBroadcast(Intent(ACTION_WAKE).setPackage(packageName).putExtra("phrase", hit))
                        scheduleRestart(8_500L)
                    } else {
                        // Agar Jarvis nahi bola, toh chup-chaap wapas restart karo
                        scheduleRestart(1000L)
                    }
                }
                override fun onPartialResults(partialResults: android.os.Bundle?) = Unit
                override fun onEvent(eventType: Int, params: android.os.Bundle?) = Unit
            })
            val i = JarvisVoiceEngine.recognitionIntent(locale, preferOffline = false)
            try { r.startListening(i) } catch (_: Exception) { scheduleRestart(1500L) }
        }
    }

    private fun scheduleRestart(delay: Long) {
        if (restarting || stopRequested) return
        restarting = true
        android.os.Handler(mainLooper).postDelayed({
            restarting = false
            if (!stopRequested) startListening()
        }, delay)
    }

    override fun onDestroy() {
        stopRequested = true
        recognizer?.cancel()
        recognizer?.destroy()
        recognizer = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel("jarvis_assistant", "JARVIS Assistant", NotificationManager.IMPORTANCE_LOW)
            channel.description = "User-started JARVIS microphone wake listener"
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun updateNotification() {
        getSystemService(NotificationManager::class.java).notify(91, notification())
    }

    private fun notification(): Notification {
        val open = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val stop = PendingIntent.getService(
            this, 1,
            Intent(this, JarvisWakeService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(this, "jarvis_assistant")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("JARVIS is listening for $wakeWord")
            .setContentText("Microphone wake listener is active. JARVIS does not start it silently.")
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
