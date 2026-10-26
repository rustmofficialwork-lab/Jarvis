package com.jarvisassistant.app

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat

/**
 * A microphone foreground service cannot be started straight from BOOT_COMPLETED
 * (blocked on Android 14/15). So after boot we only show a notification;
 * tapping it opens a invisible activity that starts the service legally.
 */
class JarvisBootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return

        val prefs = context.getSharedPreferences("jarvis", Context.MODE_PRIVATE)
        if (!prefs.getBoolean("wake_on_boot", true)) return

        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) return

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) return

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "JARVIS startup", NotificationManager.IMPORTANCE_DEFAULT)
            )
        }

        val startIntent = Intent(context, JarvisWakeStarterActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0
        val pi = PendingIntent.getActivity(context, 1, startIntent, flags)

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("JARVIS is ready")
            .setContentText("Tap to start listening for your wake word")
            .setContentIntent(pi)
            .setAutoCancel(true)
            .build()

        manager.notify(NOTIFICATION_ID, notification)
    }

    private companion object {
        const val CHANNEL_ID = "jarvis_boot_channel"
        const val NOTIFICATION_ID = 4102
    }
}
