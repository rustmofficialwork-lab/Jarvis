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
import androidx.core.app.NotificationCompat

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
                    scheduleRestart(1000L) 
                }
                
                override fun onResults(results: Bundle?) {
                    val words = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION).orEmpty()
                    
                    var hit = false
                    for (spoken in words) {
                        val cleanText = spoken.trim().lowercase()
                        
                        // RELAXED CHECK: Agar line me 'jarvis' hai aur line bahut lambi nahi hai (to avoid TV noise)
                        if (cleanText.contains("jarvis") && cleanText.length < 30) {
                            hit = true
                            break
                        }
                    }
                    
                    if (hit) {
                        recognizer?.cancel()
                        recognizer?.destroy()
                        recognizer = null
                        
                        // 2 second ka pause
                        wakePauseUntil = System.currentTimeMillis() + 2000L
                        
                        sendBroadcast(Intent(ACTION_WAKE).setPackage(packageName).putExtra("phrase", "JARVIS"))
                        scheduleRestart(2500L)
                    } else {
                        scheduleRestart(800L)
                    }
                }
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            })
            
            val i = JarvisVoiceEngine.recognitionIntent(locale, preferOffline = false)
            try { 
                r.startListening(i) 
            } catch (_: Exception) { 
                scheduleRestart(1000L) 
            }
        }
    }

    private fun scheduleRestart(delay: Long) {
        if (restarting || stopRequested) return
        restarting = true
        Handler(Looper.getMainLooper()).postDelayed({
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
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val stop = PendingIntent.getService(
            this, 1, Intent(this, JarvisWakeService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(this, "jarvis_assistant")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("JARVIS is listening for $wakeWord")
            .setContentText("Microphone wake listener is active.")
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
