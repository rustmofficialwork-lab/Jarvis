package com.jarvisassistant.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.AlarmClock
import android.provider.CalendarContract
import android.provider.Settings
import android.provider.ContactsContract

object JarvisProductivity {
    fun openCalendar(context: Context): Boolean = safe(context, Intent(Intent.ACTION_VIEW, CalendarContract.CONTENT_URI))
    fun createEvent(context: Context, title: String): Boolean = safe(context, Intent(Intent.ACTION_INSERT, CalendarContract.Events.CONTENT_URI).putExtra(CalendarContract.Events.TITLE, title))
    fun createReminder(context: Context, title: String): Boolean = safe(context, Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_MESSAGE, title).putExtra(AlarmClock.EXTRA_SKIP_UI, false))
    fun openMaps(context: Context, query: String): Boolean = safe(context, Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=${Uri.encode(query)}")))
    fun openCamera(context: Context): Boolean = safe(context, Intent("android.media.action.IMAGE_CAPTURE"))
    fun openEmail(context: Context, subject: String = ""): Boolean = safe(context, Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:")).putExtra(Intent.EXTRA_SUBJECT, subject))
    fun openYouTube(context: Context): Boolean = safe(context, Intent(Intent.ACTION_VIEW, Uri.parse("https://www.youtube.com/")))
    fun openSpotify(context: Context): Boolean = safe(context, Intent(Intent.ACTION_VIEW, Uri.parse("https://open.spotify.com/")))

    fun openDrive(context: Context): Boolean = safe(context, Intent(Intent.ACTION_VIEW, Uri.parse("https://drive.google.com/")))
    fun openWhatsApp(context: Context, text: String = ""): Boolean {
        val uri = if (text.isBlank()) Uri.parse("https://wa.me/") else Uri.parse("https://wa.me/?text=${Uri.encode(text)}")
        return safe(context, Intent(Intent.ACTION_VIEW, uri))
    }
    fun openTelegram(context: Context, text: String = ""): Boolean {
        val uri = if (text.isBlank()) Uri.parse("https://t.me/") else Uri.parse("https://t.me/share/url?url=&text=${Uri.encode(text)}")
        return safe(context, Intent(Intent.ACTION_VIEW, uri))
    }
    fun findContact(context: Context, name: String): String? {
        if (androidx.core.content.ContextCompat.checkSelfPermission(context, android.Manifest.permission.READ_CONTACTS) != android.content.pm.PackageManager.PERMISSION_GRANTED) return null
        val projection = arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.NUMBER)
        val selection = "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?"
        context.contentResolver.query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI, projection, selection, arrayOf("%$name%"), "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} ASC")?.use { c ->
            if (c.moveToFirst()) return "${c.getString(0)}: ${c.getString(1)}"
        }
        return "No matching contact found."
    }
    fun openNotificationSettings(context: Context): Boolean = safe(context, Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
    private fun safe(context: Context, intent: Intent): Boolean = try { if (intent.resolveActivity(context.packageManager) == null) false else { context.startActivity(intent); true } } catch (_: Exception) { false }
}
