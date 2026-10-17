package com.jarvisassistant.app

import android.content.Context
import android.content.Intent
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import java.util.Locale

/** Shared voice policy for one-shot speech, TTS and the explicit wake listener. */
object JarvisVoiceEngine {
    const val AUTO_LOCALE = "auto"
    const val DEFAULT_LOCALE = "en-US"

    fun recognitionIntent(locale: String, preferOffline: Boolean = false): Intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        if (!locale.equals(AUTO_LOCALE, ignoreCase = true)) {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, locale)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, locale)
        }
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, preferOffline)
        putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
    }

    fun wakeAliases(wakeWord: String): List<String> = buildList {
        val normalized = wakeWord.trim().ifBlank { "JARVIS" }
        add(normalized)
        if (normalized.equals("JARVIS", ignoreCase = true)) {
            add("jarvis")
            add("jarvix")
            add("जार्विस")
            add("जारविस")
        }
    }.distinct()

    fun containsWakeWord(spoken: String, wakeWord: String): Boolean {
        return wakeAliases(wakeWord).any { alias ->
            Regex("(?i)(^|\\s|[^\\p{L}])${Regex.escape(alias)}($|\\s|[^\\p{L}])").containsMatchIn(spoken)
        }
    }

    fun ttsLocale(requested: String, deviceLocale: Locale = Locale.getDefault()): Locale {
        if (requested.equals(AUTO_LOCALE, ignoreCase = true)) return deviceLocale
        return Locale.forLanguageTag(requested).takeUnless { it.language.isBlank() } ?: deviceLocale
    }

    fun configureTts(engine: TextToSpeech, requestedLocale: String, speechRate: Float, serious: Boolean): Locale {
        val requested = ttsLocale(requestedLocale)
        val result = engine.setLanguage(requested)
        val active = if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            val fallback = if (requested.language.equals("hi", true)) Locale("hi", "IN") else Locale.US
            engine.setLanguage(fallback)
            fallback
        } else requested
        engine.setPitch(if (serious) 0.9f else 0.82f)
        engine.setSpeechRate(speechRate.coerceIn(0.5f, 1.5f))
        return active
    }

    fun isAvailable(context: Context): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    fun errorMessage(error: Int): String = when (error) {
        SpeechRecognizer.ERROR_NETWORK,
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Speech recognition needs a network connection or an offline speech pack."
        SpeechRecognizer.ERROR_NO_MATCH -> "I didn't catch that. Please try again."
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Allow microphone permission in Android settings to use voice input."
        SpeechRecognizer.ERROR_AUDIO -> "The microphone could not be opened. Check that another app is not using it."
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Speech recognition is busy. Please try again in a moment."
        else -> "Voice input stopped. Please try again."
    }
}
