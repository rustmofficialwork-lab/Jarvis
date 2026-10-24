
package com.jarvisassistant.app

import java.util.Locale
import kotlin.math.pow

/**
 * Basic offline assistant engine.
 * No internet or external library required.
 */
object OfflineAssistantEngine {

    /**
     * Handles supported offline commands.
     * Returns null when the command is not supported.
     */
    fun handleCommand(input: String): String? {
        val query = input.trim()

        if (query.isEmpty()) {
            return "Please kuch bolo. / कृपया कुछ पूछें।"
        }

        val normalized = query.lowercase(Locale.ROOT)

        // Help commands
        if (
            normalized in listOf(
                "help", "madad", "help me",
                "what can you do", "tum kya kar sakte ho",
                "kya kar sakte ho", "commands",
                "offline help"
            )
        ) {
            return helpResponse()
        }

        // Basic greetings
        if (
            normalized in listOf(
                "hi", "hello", "hey", "namaste",
                "namaskar", "hii", "jarvis"
            )
        ) {
            return "Hello! Main Jarvis hoon. Batao, kya help chahiye?"
        }

        // Offline identity
        if (
            normalized in listOf(
                "who are you", "tum kaun ho",
                "apna naam batao", "your name"
            )
        ) {
            return "Main Jarvis hoon, tumhara assistant. Abhi offline mode mein hoon."
        }

        // Offline capability/status
        if (
            normalized in listOf(
                "are you online", "internet hai",
                "offline mode", "offline ho",
                "can you work offline"
            )
        ) {
            return "Main offline mode mein basic commands aur calculations kar sakta hoon. Advanced AI answers ke liye internet chahiye."
        }

        // Extract a calculation from common phrases.
        val expression = extractExpression(query)

        if (expression != null) {
            val result = calculate(expression)

            if (result != null && result.isFinite()) {
                return "Answer: ${formatNumber(result)}"
            }

            return "Calculation samajh nahi aayi. Example: 25 * (4 + 2)"
        }

        // Unknown commands must be handled by the caller.
        return null
    }

    /**
     * Returns a calculation result, or null for invalid expressions.
     *
     * Supports:
     * +, -, *, /, %, ^ and parentheses.
     * Example: 2 + 3 * (4 - 1) = 11
     * Example: 50% = 0.5
     */
    fun calculate(expression: String): Double? {
        return try {
            val parser = ExpressionParser(expression)
            parser.parse()
        } catch (_: Exception) {
            null
        }
    }

    private fun extractExpression(input: String): String? {
        var text = input.trim()

        val prefixes = listOf(
            "calculate", "calculation", "compute",
            "solve", "what is", "what's",
            "kitna hota hai", "kitna hoga",
            "kitna hai", "jod do", "plus",
            "jarvis calculate", "hisab karo",
            "hisaab karo", "ganana karo"
        )

        val lower = text.lowercase(Locale.ROOT)

        for (prefix in prefixes.sortedByDescending { it.length }) {
            if (lower.startsWith(prefix + " ")) {
                text = text.substring(prefix.length).trim()
                break
            }
        }

        // Only allow calculator characters and spaces.
        if (text.isEmpty()) return null

        if (!text.any { it.isDigit() }) return null

        if (!text.all {
                it.isDigit() ||
                it in "+-*/%^(). " ||
                it == ','
            }
        ) {
            return null
        }

        // Accept decimal comma only when there is no decimal point.
        text = if (',' in text && '.' !in text) {
            text.replace(',', '.')
        } else {
            text.replace(",", "")
        }

        return text
    }

    private fun formatNumber(number: Double): String {
        if (!number.isFinite()) return "Invalid result"

        val rounded = String.format(Locale.US, "%.8f", number)
            .trimEnd('0')
            .trimEnd('.')

        return if (rounded == "-0") "0" else rounded
    }

    private fun helpResponse(): String {
        return """
            Main offline mode mein ye kaam kar sakta hoon:

            • Calculations: 25 * (4 + 2)
            • Percentages: 50%
            • Powers: 2 ^ 5
            • Greetings: Hello, Namaste
            • Basic help aur assistant information

            Main offline mode mein har general knowledge question ka jawab nahi de sakta. Advanced AI ke liye internet connection chahiye.
        """.trimIndent()
    }

    private class ExpressionParser(
        private val source: String
    ) {
        private var position = 0

        fun parse(): Double {
            val result = parseExpression()
            skipSpaces()

            require(position == source.length) {
                "Unexpected character"
            }

            require(result.isFinite()) {
                "Invalid numeric result"
            }

            return result
        }

        // expression = term (('+' | '-') term)*
        private fun parseExpression(): Double {
            var value = parseTerm()

            while (true) {
                skipSpaces()

                value = when {
                    consume('+') -> value + parseTerm()
                    consume('-') -> value - parseTerm()
                    else -> return value
                }
            }
        }

        // term = unary (('*' | '/') unary)*
        private fun parseTerm(): Double {
            var value = parseUnary()

            while (true) {
                skipSpaces()

                value = when {
                    consume('*') -> value * parseUnary()

                    consume('/') -> {
                        val divisor = parseUnary()
                        require(divisor != 0.0) {
                            "Division by zero"
                        }
                        value / divisor
                    }

                    else -> return value
                }

                require(value.isFinite()) {
                    "Result out of range"
                }
            }
        }

        private fun parseUnary(): Double {
            skipSpaces()

            return when {
                consume('+') -> parseUnary()
                consume('-') -> -parseUnary()
                else -> parsePower()
            }
        }

        // Power is right-associative: 2^3^2 = 2^(3^2)
        private fun parsePower(): Double {
            var value = parsePrimary()

            skipSpaces()

            if (consume('^')) {
                val exponent = parseUnary()
                value = value.pow(exponent)

                require(value.isFinite()) {
                    "Invalid power"
                }
            }

            return value
        }

        private fun parsePrimary(): Double {
            skipSpaces()

            val value = if (consume('(')) {
                val inner = parseExpression()
                skipSpaces()

                require(consume(')')) {
                    "Missing closing parenthesis"
                }

                inner
            } else {
                parseNumber()
            }

            skipSpaces()

            // A postfix percentage: 50% = 0.5
            return if (consume('%')) {
                value / 100.0
            } else {
                value
            }
        }

        private fun parseNumber(): Double {
            skipSpaces()

            val start = position
            var hasDigit = false

            while (
                position < source.length &&
                source[position].isDigit()
            ) {
                position++
                hasDigit = true
            }

            if (
                position < source.length &&
                source[position] == '.'
            ) {
                position++

                while (
                    position < source.length &&
                    source[position].isDigit()
                ) {
                    position++
                    hasDigit = true
                }
            }

            require(hasDigit) {
                "Number expected"
            }

            return source.substring(start, position).toDouble()
        }

        private fun consume(char: Char): Boolean {
            if (
                position < source.length &&
                source[position] == char
            ) {
                position++
                return true
            }

            return false
        }

        private fun skipSpaces() {
            while (
                position < source.length &&
                source[position].isWhitespace()
            ) {
                position++
            }
        }
    }
}
