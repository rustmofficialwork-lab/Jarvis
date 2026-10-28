package com.jarvisassistant.app

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.pow

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
        val match = Regex("""[\d\.\s\+\-\*\/\%\^\(\)]+""").find(text)
        val exp = match?.value?.trim()
        return if (exp != null && exp.length > 2 && exp.any { it.isDigit() }) exp else null
    }

    // Internal visibility lets the JVM unit tests exercise the parser directly.
    internal fun calculate(expression: String): Double? {
        return try {
            ExpressionParser(expression).parse()
        } catch (_: Exception) {
            null
        }
    }

    /** Small, bounded arithmetic parser: parentheses, precedence, unary signs and powers. */
    private class ExpressionParser(private val input: String) {
        private var index = 0

        fun parse(): Double {
            require(input.isNotBlank() && input.length <= 256)
            val result = parseExpression()
            skipSpaces()
            require(index == input.length)
            return checked(result)
        }

        private fun parseExpression(): Double {
            var value = parseTerm()
            while (true) {
                skipSpaces()
                value = when {
                    consume('+') -> checked(value + parseTerm())
                    consume('-') -> checked(value - parseTerm())
                    else -> return checked(value)
                }
            }
        }

        private fun parseTerm(): Double {
            var value = parseUnary()
            while (true) {
                skipSpaces()
                value = when {
                    consume('*') -> checked(value * parseUnary())
                    consume('/') -> {
                        val divisor = parseUnary()
                        require(divisor != 0.0) { "Division by zero" }
                        checked(value / divisor)
                    }
                    consume('%') -> {
                        val divisor = parseUnary()
                        require(divisor != 0.0) { "Modulo by zero" }
                        checked(value % divisor)
                    }
                    else -> return checked(value)
                }
            }
        }

        private fun parseUnary(): Double {
            skipSpaces()
            return when {
                consume('+') -> parseUnary()
                consume('-') -> checked(-parseUnary())
                else -> parsePower()
            }
        }

        private fun parsePower(): Double {
            var value = parsePrimary()
            skipSpaces()
            if (consume('^')) {
                value = checked(value.pow(parseUnary()))
            }
            return checked(value)
        }

        private fun parsePrimary(): Double {
            skipSpaces()
            if (consume('(')) {
                val value = parseExpression()
                skipSpaces()
                require(consume(')')) { "Missing closing parenthesis" }
                return value
            }

            val start = index
            var decimalSeen = false
            while (index < input.length) {
                when (val ch = input[index]) {
                    in '0'..'9' -> index++
                    '.' -> {
                        require(!decimalSeen) { "Invalid number" }
                        decimalSeen = true
                        index++
                    }
                    else -> break
                }
            }
            require(index > start) { "Expected a number" }
            return input.substring(start, index).toDouble()
        }

        private fun skipSpaces() {
            while (index < input.length && input[index].isWhitespace()) index++
        }

        private fun consume(char: Char): Boolean {
            if (index >= input.length || input[index] != char) return false
            index++
            return true
        }

        private fun checked(value: Double): Double {
            require(value.isFinite()) { "Result is not finite" }
            return value
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
