package com.jarvisassistant.app

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONArray
import org.json.JSONObject

/** Optional user-enabled notification reader. It keeps only a small, local rolling list. */
class JarvisNotificationListenerService : NotificationListenerService() {
    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val title = sbn.notification.extras?.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = sbn.notification.extras?.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        if (title.isBlank() && text.isBlank()) return
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        val array = runCatching { JSONArray(prefs.getString(KEY, "[]")) }.getOrDefault(JSONArray())
        val next = JSONArray()
        next.put(JSONObject().apply {
            put("package", sbn.packageName)
            put("title", title.take(200))
            put("text", text.take(500))
            put("time", sbn.postTime)
        })
        for (i in 0 until minOf(array.length(), 19)) next.put(array.optJSONObject(i))
        prefs.edit().putString(KEY, next.toString()).apply()
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) = Unit

    companion object {
        private const val PREFS = "jarvis_notifications"
        private const val KEY = "recent"

        fun recent(context: android.content.Context): String {
            val raw = context.getSharedPreferences(PREFS, android.content.Context.MODE_PRIVATE).getString(KEY, "[]") ?: "[]"
            val array = runCatching { JSONArray(raw) }.getOrDefault(JSONArray())
            if (array.length() == 0) return "There are no recent notifications available to JARVIS."
            return buildString {
                for (i in 0 until array.length()) {
                    val item = array.optJSONObject(i) ?: continue
                    append("• ").append(item.optString("title", "Notification"))
                    val text = item.optString("text").trim()
                    if (text.isNotBlank()) append(": ").append(text)
                    append('\n')
                }
            }.trim().take(6000)
        }
    }
}
