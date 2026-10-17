package com.jarvisassistant.app

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.provider.Settings

/** Unified, explicit phone-control facade. No hidden/background device mutations. */
object JarvisPhoneControl {
    fun setVolume(context: Context, direction: Int): String {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, direction, AudioManager.FLAG_SHOW_UI)
        return when (direction) {
            AudioManager.ADJUST_RAISE -> "Raised media volume."
            AudioManager.ADJUST_LOWER -> "Lowered media volume."
            AudioManager.ADJUST_MUTE -> "Muted media audio."
            else -> "Adjusted media volume."
        }
    }

    fun mediaKey(context: Context, keyCode: Int): String {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, keyCode))
        audio.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, keyCode))
        return when (keyCode) {
            android.view.KeyEvent.KEYCODE_MEDIA_PLAY -> "Requested media playback."
            android.view.KeyEvent.KEYCODE_MEDIA_PAUSE -> "Requested media pause."
            android.view.KeyEvent.KEYCODE_MEDIA_NEXT -> "Skipped to the next track."
            android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS -> "Requested the previous track."
            else -> "Requested media control."
        }
    }

    fun copy(context: Context, text: String): String {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("JARVIS", text.take(10_000)))
        return "Copied the text to the clipboard."
    }

    fun readClipboard(context: Context): String {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = clipboard.primaryClip ?: return "The clipboard is empty."
        return clip.getItemAt(0).coerceToText(context).toString().take(10_000).ifBlank { "The clipboard is empty." }
    }

    fun brightness(context: Context, percent: Int): String {
        val value = percent.coerceIn(1, 100)
        if (!Settings.System.canWrite(context)) {
            val intent = Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, Uri.parse("package:${context.packageName}"))
            context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return "Android needs Write System Settings permission before JARVIS can change brightness."
        }
        val raw = (value * 255 / 100).coerceIn(1, 255)
        Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, raw)
        return "Screen brightness set to $value percent."
    }
}
