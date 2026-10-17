package com.jarvisassistant.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Bounded, encrypted local diagnostics. Never stores prompt payloads or secrets. */
object JarvisDiagnostics {
    private const val PREFS = "jarvis_diagnostics"
    private const val KEY = "events"
    private const val MAX = 150

    data class Entry(val time: Long, val category: String, val level: String, val message: String)

    fun record(context: Context, category: String, level: String, message: String) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val existing = try { JSONArray(SecureVault.decrypt(prefs.getString(KEY, "").orEmpty())) } catch (_: Exception) { JSONArray() }
        val out = JSONArray()
        val start = (existing.length() - MAX + 1).coerceAtLeast(0)
        for (i in start until existing.length()) out.put(existing.opt(i))
        out.put(JSONObject().apply {
            put("time", System.currentTimeMillis())
            put("category", category.take(32))
            put("level", level.take(12))
            put("message", message.take(300))
        })
        prefs.edit().putString(KEY, SecureVault.encrypt(out.toString())).apply()
    }

    fun entries(context: Context): List<Entry> {
        val raw = SecureVault.decrypt(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, "").orEmpty())
        val json = try { JSONArray(raw) } catch (_: Exception) { return emptyList() }
        return (0 until json.length()).mapNotNull { i -> json.optJSONObject(i)?.let { o ->
            Entry(o.optLong("time"), o.optString("category"), o.optString("level"), o.optString("message"))
        }}.asReversed()
    }

    fun clear(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(KEY).apply()

    fun health(context: Context): String {
        val events = entries(context)
        val errors = events.count { it.level == "ERROR" }
        val warnings = events.count { it.level == "WARN" }
        val agent = JarvisAgentRuntime.current()
        val network = JarvisNetworkResilience.status(context)
        return "Health: diagnostics=${events.size}/$MAX, errors=$errors, warnings=$warnings, " +
            "agent=${agent?.status?.name?.lowercase() ?: "idle"}, network=$network, killSwitch=${JarvisSecurityCenter.isKillSwitchEnabled(context)}."
    }

    fun report(context: Context): String {
        val lines = entries(context).take(12).joinToString("\n") { "${it.level} ${it.category}: ${it.message}" }
        return if (lines.isBlank()) health(context) else health(context) + "\nRecent diagnostics:\n" + lines
    }
}
