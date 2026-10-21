package com.jarvisassistant.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.BatteryManager
import androidx.core.app.NotificationCompat
import java.util.Calendar

/** User-controlled proactive layer. It never sends messages or performs high-risk actions silently. */
object JarvisProactiveEngine {
    enum class Mode { OFF, LOW, NORMAL, HIGH }

    private const val PREFS = "jarvis_proactive"
    private const val MODE_KEY = "mode"
    private const val CHANNEL = "jarvis_proactive"
    private const val ID = 3001
    private const val COOLDOWN_MS = 4 * 60 * 60 * 1000L
    private const val DAILY_LIMIT = 6

    fun mode(context: Context): Mode {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(MODE_KEY, Mode.NORMAL.name).orEmpty()
        return runCatching { Mode.valueOf(raw) }.getOrDefault(Mode.NORMAL)
    }

    fun setMode(context: Context, mode: Mode) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(MODE_KEY, mode.name).apply()
    }

    fun notify(context: Context, title: String, body: String, important: Boolean = false) {
        if (mode(context) == Mode.OFF) return
        if (!important && !allowedByMode(context)) return
        if (!important && dailyCount(context) >= DAILY_LIMIT) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "JARVIS Proactive", if (mode(context) == Mode.HIGH || important) NotificationManager.IMPORTANCE_HIGH else NotificationManager.IMPORTANCE_DEFAULT)
        )
        manager.notify(ID, NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .build())
        markSent(context, "daily", increment = true)
    }

    fun evaluate(context: Context) {
        val currentMode = mode(context)
        if (currentMode == Mode.OFF) return
        val snapshot = JarvisContextEngine.snapshot(context)
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val tasks = JarvisTaskStore(context).list()
        JarvisProactivePlanner.plan(snapshot.nowMillis, snapshot.batteryPercent, snapshot.charging, snapshot.nextEvent, tasks)
            .forEach { suggestion ->
                val decision = JarvisPriorityEngine.score(suggestion.candidate, currentMode, hour)
                if (decision.level != JarvisPriorityEngine.Level.IGNORE && canSend(context, suggestion.key)) {
                    markSent(context, suggestion.key)
                    notify(context, suggestion.title, suggestion.body, decision.level == JarvisPriorityEngine.Level.CRITICAL)
                }
            }
    }

    fun dailyBriefing(context: Context): String {
        val snapshot = JarvisContextEngine.snapshot(context)
        val tasks = JarvisTaskStore(context).list()
        val taskText = tasks.take(5).joinToString("; ") { it.text }
        val eventText = snapshot.nextEvent?.let { "Next: ${it.title}." } ?: "No upcoming calendar event available."
        val batteryText = if (snapshot.batteryPercent >= 0) "Battery: ${snapshot.batteryPercent}%." else "Battery status unavailable."
        return listOf(batteryText, eventText, if (taskText.isBlank()) "No open tasks." else "Open tasks: $taskText").joinToString(" ")
    }

    /** Safe, local context check kept for compatibility with older callers. */
    fun checkBattery(context: Context) = evaluate(context)

    private fun allowedByMode(context: Context): Boolean = mode(context) != Mode.LOW && mode(context) != Mode.OFF

    private fun canSend(context: Context, key: String): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return System.currentTimeMillis() - prefs.getLong("sent_$key", 0L) >= COOLDOWN_MS
    }

    private fun markSent(context: Context, key: String, increment: Boolean = false) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val edit = prefs.edit().putLong("sent_$key", System.currentTimeMillis())
        if (increment) edit.putInt("daily_count", prefs.getInt("daily_count", 0) + 1)
        edit.apply()
    }

    private fun dailyCount(context: Context): Int {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val today = Calendar.getInstance().get(Calendar.DAY_OF_YEAR)
        val stored = prefs.getInt("daily_day", -1)
        if (stored != today) {
            prefs.edit().putInt("daily_day", today).putInt("daily_count", 0).apply()
            return 0
        }
        return prefs.getInt("daily_count", 0)
    }
}
