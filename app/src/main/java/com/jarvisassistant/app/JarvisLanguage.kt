package com.jarvisassistant.app

import java.util.Locale

/** Lightweight language detection for offline routing, AI instructions, and speech output. */
object JarvisLanguage {
    enum class Language { HINDI, ENGLISH, HINGLISH }

    private val hindiRomanWords = setOf(
        "hai", "hain", "ho", "kaise", "kya", "kyun", "kyu", "mujhe", "mera", "meri",
        "mere", "tum", "aap", "apko", "batao", "bataiye", "karo", "karna", "kar do",
        "chahiye", "nahi", "nahin", "haan", "han", "acha", "achha", "theek", "abhi",
        "kal", "aaj", "kyunki", "ka", "ki", "ke", "mein", "se", "par", "wala",
        "wali", "kitna", "kitni", "kab", "kahan", "kidhar", "dikhao", "samjhao", "madad",
        "shukriya", "namaste", "dhanyavaad", "bata", "kar", "raha", "rahi", "rahe"
    )

    fun detect(text: String): Language {
        if (text.any { it in '\u0900'..'\u097F' }) return Language.HINDI
        val words = Regex("[\\p{L}]+(?:'[\\p{L}]+)?").findAll(text.lowercase(Locale.ROOT))
            .map { it.value }.toList()
        if (words.isEmpty()) return Language.ENGLISH
        val hindiCount = words.count { it in hindiRomanWords }
        val englishCount = words.count { it in setOf("the", "is", "are", "please", "what", "how", "can", "could", "would", "tell", "me", "your", "you", "weather", "today", "search", "open", "calculate", "time", "date", "hello", "thanks") }
        return when {
            hindiCount > 0 && englishCount > 0 -> Language.HINGLISH
            hindiCount >= 2 -> Language.HINGLISH
            hindiCount == 1 -> Language.HINGLISH
            else -> Language.ENGLISH
        }
    }

    fun aiInstruction(text: String): String = when (detect(text)) {
        Language.HINDI -> "Reply entirely in natural Hindi using Devanagari script. Keep technical names unchanged when needed."
        Language.HINGLISH -> "Reply in natural Hinglish, mixing Hindi and English naturally in Roman script, matching the user's style. Do not switch to formal pure Hindi."
        Language.ENGLISH -> "Reply in English."
    }

    fun ttsLocale(text: String): Locale = when (detect(text)) {
        Language.HINDI -> Locale.forLanguageTag("hi-IN")
        Language.HINGLISH -> Locale.forLanguageTag("hi-IN")
        Language.ENGLISH -> Locale.forLanguageTag("en-GB")
    }


    /** Localize common deterministic device-command responses without altering free-form AI text. */
    fun localizeCommandReply(prompt: String, reply: String): String {
        val language = detect(prompt)
        if (language == Language.ENGLISH || reply.isBlank()) return reply
        val timeMatch = Regex("(?i)(?:it is|the current time is)\\s+(.+?)(?:, sir)?\\.?$").find(reply.trim())
        val dateMatch = Regex("(?i)(?:today is)\\s+(.+?)\\.?$").find(reply.trim())
        val batteryMatch = Regex("(?i)battery (?:stands at|is at) (\\d+) percent(?:, and charging|, charging)?(?:, sir)?\\.?$").find(reply.trim())
        return when {
            timeMatch != null && language == Language.HINDI -> "अभी समय ${timeMatch.groupValues[1]} है, सर।"
            timeMatch != null && language == Language.HINGLISH -> "Sir, abhi time ${timeMatch.groupValues[1]} hai."
            dateMatch != null && language == Language.HINDI -> "आज की तारीख ${dateMatch.groupValues[1]} है, सर।"
            dateMatch != null && language == Language.HINGLISH -> "Sir, aaj ki date ${dateMatch.groupValues[1]} hai."
            batteryMatch != null && language == Language.HINDI -> "सर, बैटरी ${batteryMatch.groupValues[1]} प्रतिशत है।"
            batteryMatch != null && language == Language.HINGLISH -> "Sir, battery ${batteryMatch.groupValues[1]} percent hai."
            reply == "Always a pleasure, Sir." && language == Language.HINDI -> "आपकी मदद करके खुशी हुई, सर।"
            reply == "Always a pleasure, Sir." && language == Language.HINGLISH -> "Aapki help karke khushi hui, Sir."
            reply == "Welcome home, Sir. At your service." && language == Language.HINDI -> "घर वापसी पर स्वागत है, सर। मैं आपकी सेवा में तैयार हूँ।"
            reply == "Welcome home, Sir. At your service." && language == Language.HINGLISH -> "Welcome home, Sir. Main aapki help ke liye ready hoon."
            reply == "Flashlight on." && language == Language.HINDI -> "टॉर्च चालू कर दी है, सर।"
            reply == "Flashlight off." && language == Language.HINDI -> "टॉर्च बंद कर दी है, सर।"
            reply == "Flashlight on." && language == Language.HINGLISH -> "Sir, flashlight on kar di hai."
            reply == "Flashlight off." && language == Language.HINGLISH -> "Sir, flashlight off kar di hai."
            else -> localize(reply, language)
        }
    }

    fun localize(text: String, language: Language): String {
        val englishToHindi = mapOf(
            "The answer is " to "जवाब है ",
            "Hello Sir, I am online and ready to assist you." to "नमस्ते सर, मैं ऑनलाइन हूँ और आपकी मदद के लिए तैयार हूँ।",
            "I am functioning perfectly within normal parameters, Sir." to "सर, मेरे सभी सिस्टम सामान्य रूप से काम कर रहे हैं।",
            "I can tell you the time, date, do basic calculations, or you can ask me anything if internet is on." to "मैं समय और तारीख बता सकता हूँ, सामान्य गणना कर सकता हूँ। इंटरनेट होने पर आप मुझसे और सवाल भी पूछ सकते हैं।",
            "I couldn't answer that offline. Add an API key in Settings to enable AI." to "मैं इसका जवाब ऑफ़लाइन नहीं दे पाया। AI चालू करने के लिए Settings में API key जोड़ें।",
            "I'm offline right now, so I can't use AI." to "अभी इंटरनेट नहीं है, इसलिए मैं AI इस्तेमाल नहीं कर सकता।"
        )
        if (language == Language.ENGLISH) return text
        if (language == Language.HINGLISH) {
            return when (text) {
                "Hello Sir, I am online and ready to assist you." -> "Hello Sir, main online hoon aur aapki help ke liye ready hoon."
                "I am functioning perfectly within normal parameters, Sir." -> "Sir, mere saare systems normal parameters par perfectly kaam kar rahe hain."
                "I couldn't answer that offline. Add an API key in Settings to enable AI." -> "Sir, offline main iska answer nahi de paaya. AI enable karne ke liye Settings mein API key add karein."
                "I'm offline right now, so I can't use AI." -> "Sir, abhi internet offline hai, isliye AI use nahi kar sakta."
                else -> text
            }
        }
        return englishToHindi[text] ?: text
    }
}
