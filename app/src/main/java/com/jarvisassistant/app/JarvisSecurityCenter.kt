package com.jarvisassistant.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject

/** Local privacy/security controls. No network access and no sensitive payloads are persisted in the audit log. */
object JarvisSecurityCenter {
    private const val PREFS = "jarvis_security"
    private const val KILL = "emergency_kill_switch"
    private const val LOG = "audit_log"
    private const val MAX_ENTRIES = 100

    data class AuditEntry(val time: Long, val action: String, val risk: String, val outcome: String)

    fun isKillSwitchEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KILL, false)

    fun setKillSwitch(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KILL, enabled).apply()
        audit(context, "emergency kill switch", "HIGH", if (enabled) "enabled" else "disabled")
    }

    fun audit(context: Context, action: String, risk: String, outcome: String) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val existing = try { JSONArray(SecureVault.decrypt(prefs.getString(LOG, "").orEmpty())) } catch (_: Exception) { JSONArray() }
        val items = JSONArray()
        val start = (existing.length() - MAX_ENTRIES + 1).coerceAtLeast(0)
        for (i in start until existing.length()) items.put(existing.opt(i))
        items.put(JSONObject().apply {
            put("time", System.currentTimeMillis())
            put("action", action.take(80))
            put("risk", risk.take(12))
            put("outcome", outcome.take(120))
        })
        prefs.edit().putString(LOG, SecureVault.encrypt(items.toString())).apply()
    }

    fun auditEntries(context: Context): List<AuditEntry> {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val raw = SecureVault.decrypt(prefs.getString(LOG, "").orEmpty())
        val json = try { JSONArray(raw) } catch (_: Exception) { return emptyList() }
        return (0 until json.length()).mapNotNull { i ->
            json.optJSONObject(i)?.let { o ->
                AuditEntry(o.optLong("time"), o.optString("action"), o.optString("risk"), o.optString("outcome"))
            }
        }.asReversed()
    }

    fun clearAudit(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(LOG).apply()
    }

    fun permissionSummary(context: Context): List<String> = listOf(
        "Microphone" to Manifest.permission.RECORD_AUDIO,
        "Camera" to Manifest.permission.CAMERA,
        "Calendar" to Manifest.permission.READ_CALENDAR,
        "Contacts" to Manifest.permission.READ_CONTACTS,
        "Notifications" to if (android.os.Build.VERSION.SDK_INT >= 33) Manifest.permission.POST_NOTIFICATIONS else null
    ).mapNotNull { (name, permission) ->
        if (permission == null) "$name: system-managed" else "$name: " +
            if (ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED) "granted" else "not granted"
    }
}
