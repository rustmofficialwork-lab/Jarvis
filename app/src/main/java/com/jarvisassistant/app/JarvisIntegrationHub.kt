package com.jarvisassistant.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

/**
 * Safe account-integration registry. It never stores OAuth tokens or client secrets.
 * Provider SDK/OAuth credentials belong in the release environment/backend.
 */
object JarvisIntegrationHub {
    enum class Provider { GOOGLE_CALENDAR, GOOGLE_CONTACTS, GOOGLE_DRIVE, GMAIL, MAPS, YOUTUBE, SPOTIFY, WHATSAPP, TELEGRAM }

    data class Integration(
        val provider: Provider,
        val label: String,
        val authRequired: Boolean,
        val installedAppSupported: Boolean,
        val status: Status = Status.NOT_CONNECTED
    )
    enum class Status { NOT_CONNECTED, CONNECTED, DISABLED }

    private val states = ConcurrentHashMap<Provider, Status>()

    fun list(): List<Integration> = Provider.entries.map { p ->
        Integration(p, label(p), authRequired(p), installedAppSupported(p), states[p] ?: Status.NOT_CONNECTED)
    }

    fun setStatus(provider: Provider, status: Status) { states[provider] = status }
    fun status(provider: Provider): Status = states[provider] ?: Status.NOT_CONNECTED

    /** Opens an official provider/app entry point without pretending that OAuth is complete. */
    fun openOfficialEntry(context: Context, provider: Provider): Boolean {
        val uri = when (provider) {
            Provider.GOOGLE_CALENDAR -> "https://calendar.google.com/"
            Provider.GOOGLE_CONTACTS -> "https://contacts.google.com/"
            Provider.GOOGLE_DRIVE -> "https://drive.google.com/"
            Provider.GMAIL -> "https://mail.google.com/"
            Provider.MAPS -> "https://maps.google.com/"
            Provider.YOUTUBE -> "https://www.youtube.com/"
            Provider.SPOTIFY -> "https://open.spotify.com/"
            Provider.WHATSAPP -> "https://www.whatsapp.com/"
            Provider.TELEGRAM -> "https://telegram.org/"
        }
        return try {
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(uri)))
            true
        } catch (_: Exception) { false }
    }

    /** Minimal manifest for a future backend/OAuth implementation; no token persistence. */
    fun exportSafeManifest(): String = JSONArray(list().map { i ->
        JSONObject().put("provider", i.provider.name).put("label", i.label)
            .put("authRequired", i.authRequired).put("installedAppSupported", i.installedAppSupported)
            .put("status", i.status.name)
    }).toString()

    private fun authRequired(p: Provider) = p in setOf(Provider.GOOGLE_CALENDAR, Provider.GOOGLE_CONTACTS, Provider.GOOGLE_DRIVE, Provider.GMAIL, Provider.SPOTIFY)
    private fun installedAppSupported(p: Provider) = p in setOf(Provider.GOOGLE_CALENDAR, Provider.GOOGLE_CONTACTS, Provider.GOOGLE_DRIVE, Provider.GMAIL, Provider.MAPS, Provider.YOUTUBE, Provider.SPOTIFY, Provider.WHATSAPP, Provider.TELEGRAM)
    private fun label(p: Provider) = p.name.replace('_', ' ').lowercase().replaceFirstChar { it.uppercase() }
}
