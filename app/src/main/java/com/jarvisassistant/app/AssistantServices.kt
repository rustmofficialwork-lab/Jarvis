package com.jarvisassistant.app

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// AI Search ke liye data classes
data class ResearchSource(
    val title: String,
    val url: String,
    val excerpt: String
)

data class AssistantAnswer(
    val text: String,
    val sources: List<ResearchSource> = emptyList()
)

// Bina internet ke basic commands aur calculation ke liye
object OfflineAssistantEngine {
    fun handleCommand(prompt: String): String? {
        val lower = prompt.lowercase(Locale.ROOT).trim()
        val language = JarvisLanguage.detect(prompt)

        // Math calculation check
        val expression = extractExpression(lower)
        if (expression != null) {
            val result = calculate(expression)
            if (result != null && !isInfinite(result)) {
                val answer = "The answer is ${formatNumber(result)}."
                return when (language) {
                    JarvisLanguage.Language.HINDI -> "जवाब है ${formatNumber(result)}।"
                    JarvisLanguage.Language.HINGLISH -> "Answer hai ${formatNumber(result)}."
                    JarvisLanguage.Language.ENGLISH -> answer
                }
            }
        }

        return when {
            lower.contains("help") || lower.contains("madad") || lower.contains("मदद") -> localizedHelp(language)
            lower.contains("hello") || lower.contains("hi jarvis") || lower.contains("namaste") || lower.contains("नमस्ते") ->
                JarvisLanguage.localize("Hello Sir, I am online and ready to assist you.", language)
            lower.contains("how are you") || lower.contains("kaise ho") || lower.contains("कैसे हो") ->
                JarvisLanguage.localize("I am functioning perfectly within normal parameters, Sir.", language)
            lower.contains("time") || lower.contains("samay") || lower.contains("waqt") || lower.contains("समय") || lower.contains("वक्त") -> {
                val time = SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date())
                when (language) {
                    JarvisLanguage.Language.HINDI -> "अभी समय $time है, सर।"
                    JarvisLanguage.Language.HINGLISH -> "Sir, abhi time $time hai."
                    JarvisLanguage.Language.ENGLISH -> "The current time is $time."
                }
            }
            lower.contains("date") || lower.contains("tareekh") || lower.contains("तारीख") -> {
                val date = SimpleDateFormat("EEEE, d MMMM yyyy", Locale.getDefault()).format(Date())
                when (language) {
                    JarvisLanguage.Language.HINDI -> "आज की तारीख $date है, सर।"
                    JarvisLanguage.Language.HINGLISH -> "Sir, aaj ki date $date hai."
                    JarvisLanguage.Language.ENGLISH -> "Today is $date."
                }
            }
            lower.contains("who are you") || lower.contains("tum kaun ho") || lower.contains("तुम कौन हो") -> when (language) {
                JarvisLanguage.Language.HINDI -> "मैं JARVIS हूँ, आपका personal AI assistant, सर।"
                JarvisLanguage.Language.HINGLISH -> "Sir, main JARVIS hoon, aapka personal AI assistant."
                JarvisLanguage.Language.ENGLISH -> "I am JARVIS, your personal AI assistant developed to help you."
            }
            else -> null
        }
    }

    private fun localizedHelp(language: JarvisLanguage.Language): String = when (language) {
        JarvisLanguage.Language.HINDI -> "मैं समय, तारीख और सामान्य गणना बता सकता हूँ। इंटरनेट होने पर मैं AI से दूसरे सवालों के जवाब भी दे सकता हूँ।"
        JarvisLanguage.Language.HINGLISH -> "Sir, main time, date aur basic calculations kar sakta hoon. Internet ho to AI se aur questions ke answers bhi de sakta hoon."
        JarvisLanguage.Language.ENGLISH -> "I can tell you the time, date, do basic calculations, or you can ask me anything if internet is on."
    }

    private fun extractExpression(text: String): String? {
        val match = Regex("""[\d\.\s\+\-\*\/\%]+""").find(text)
        val exp = match?.value?.trim()
        return if (exp != null && exp.length > 2 && exp.any { it.isDigit() }) exp else null
    }

    private fun calculate(expression: String): Double? {
        return try {
            val tokens = expression.replace(" ", "")
            if (tokens.contains("+")) return tokens.split("+").let { it[0].toDouble() + it[1].toDouble() }
            if (tokens.contains("-")) return tokens.split("-").let { it[0].toDouble() - it[1].toDouble() }
            if (tokens.contains("*")) return tokens.split("*").let { it[0].toDouble() * it[1].toDouble() }
            if (tokens.contains("/")) return tokens.split("/").let { it[0].toDouble() / it[1].toDouble() }
            null
        } catch (e: Exception) {
            null
        }
    }

    private fun isInfinite(value: Double): Boolean {
        return value.isInfinite() || value.isNaN()
    }

    private fun formatNumber(value: Double): String {
        return if (value % 1.0 == 0.0) value.toInt().toString() else String.format(Locale.US, "%.2f", value)
    }
}

// Agent ke tools aur unki permission (confirmation) check karne ke liye
object JarvisToolSystem {
    enum class Tool {
        WEB_RESEARCH, WEATHER, CALCULATOR, CALENDAR, REMINDER,
        MAPS, EMAIL, CAMERA, SCREEN, APP_LAUNCH, PHONE, SMS, SMART_HOME
    }

    fun needsConfirmation(tool: Tool): Boolean {
        return when (tool) {
            Tool.PHONE, Tool.SMS, Tool.SMART_HOME, Tool.EMAIL -> true
            else -> false
        }
    }
}
