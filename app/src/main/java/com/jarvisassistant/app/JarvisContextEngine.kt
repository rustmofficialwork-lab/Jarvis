package com.jarvisassistant.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.CalendarContract
import androidx.core.content.ContextCompat

/** Read-only local context. Calendar access is explicitly opt-in. */
object JarvisContextEngine {
    data class CalendarEvent(val id: Long, val title: String, val beginMillis: Long, val endMillis: Long)
    data class Snapshot(
        val nowMillis: Long,
        val batteryPercent: Int,
        val charging: Boolean,
        val nextEvent: CalendarEvent?
    )

    fun snapshot(context: Context, nowMillis: Long = System.currentTimeMillis()): Snapshot {
        val battery = context.registerReceiver(null, android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED))
        val level = battery?.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = (battery?.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, 100) ?: 100).coerceAtLeast(1)
        val percent = if (level >= 0) (level * 100 / scale).coerceIn(0, 100) else -1
        val charging = battery?.getIntExtra(android.os.BatteryManager.EXTRA_PLUGGED, 0)?.let { it != 0 } ?: false
        return Snapshot(nowMillis, percent, charging, nextCalendarEvent(context, nowMillis))
    }

    fun calendarAccessEnabled(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CALENDAR) == PackageManager.PERMISSION_GRANTED

    private fun nextCalendarEvent(context: Context, now: Long): CalendarEvent? {
        if (!calendarAccessEnabled(context)) return null
        val end = now + 24L * 60L * 60L * 1000L
        val uri = CalendarContract.Instances.CONTENT_URI.buildUpon()
            .appendQueryParameter("begin", now.toString())
            .appendQueryParameter("end", end.toString())
            .build()
        val projection = arrayOf(
            CalendarContract.Instances.EVENT_ID,
            CalendarContract.Instances.TITLE,
            CalendarContract.Instances.BEGIN,
            CalendarContract.Instances.END
        )
        return runCatching {
            context.contentResolver.query(uri, projection, "${CalendarContract.Instances.BEGIN} >= ?", arrayOf(now.toString()), "${CalendarContract.Instances.BEGIN} ASC")
                ?.use { c ->
                    if (!c.moveToFirst()) return@use null
                    CalendarEvent(
                        c.getLong(0),
                        c.getString(1).orEmpty().ifBlank { "Calendar event" },
                        c.getLong(2),
                        c.getLong(3)
                    )
                }
        }.getOrNull()
    }
}
