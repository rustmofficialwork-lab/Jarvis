package com.jarvisassistant.app

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import org.json.JSONObject

/** Offline-first network guard. Network-dependent work is never silently executed while offline. */
object JarvisNetworkResilience {
    data class PendingRequest(val prompt: String, val queuedAt: Long)

    private const val PREFS = "jarvis_network_resilience"
    private const val KEY = "pending_request"
    private const val MAX_PROMPT = 2000L

    fun isOnline(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    fun status(context: Context): String = if (isOnline(context)) "online" else "offline"

    fun queue(context: Context, prompt: String) {
        val value = JSONObject().apply {
            put("prompt", prompt.take(MAX_PROMPT.toInt()))
            put("queuedAt", System.currentTimeMillis())
        }.toString()
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, SecureVault.encrypt(value)).apply()
    }

    fun peek(context: Context): PendingRequest? {
        val raw = SecureVault.decrypt(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, "").orEmpty())
        if (raw.isBlank()) return null
        return try {
            val o = JSONObject(raw)
            PendingRequest(o.optString("prompt").take(MAX_PROMPT.toInt()), o.optLong("queuedAt"))
        } catch (_: Exception) { null }
    }

    fun take(context: Context): PendingRequest? {
        val item = peek(context)
        if (item != null) clear(context)
        return item
    }

    fun clear(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(KEY).apply()
    }

    fun retryDelayMillis(attempt: Int): Long {
        val safe = attempt.coerceIn(0, 5)
        return (1_000L shl safe).coerceAtMost(30_000L)
    }

    fun isTransientNetworkFailure(error: Throwable): Boolean {
        val name = error.javaClass.name.lowercase()
        val message = (error.message ?: "").lowercase()
        return name.contains("timeout") || name.contains("unknownhost") ||
            name.contains("connect") || message.contains("network") ||
            message.contains("timeout") || message.contains("connection")
    }
}
