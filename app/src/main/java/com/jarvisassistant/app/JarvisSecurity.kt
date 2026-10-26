package com.jarvisassistant.app

/** Central risk/confirmation policy. High-risk actions must be confirmed immediately before execution. */
object JarvisSecurity {
    enum class Risk { LOW, MEDIUM, HIGH }

    data class Decision(
        val risk: Risk,
        val reason: String,
        val requiresConfirmation: Boolean
    )

    fun assess(command: String): Decision {
        val t = CommandNormalizer.normalize(command).trim()
        return when {
            Regex("""^(?:call|dial)\b""", RegexOption.IGNORE_CASE).containsMatchIn(t) ->
                Decision(Risk.HIGH, "placing a phone call", true)
            Regex("""^(?:text|sms|message)\b""", RegexOption.IGNORE_CASE).containsMatchIn(t) ->
                Decision(Risk.HIGH, "sending or preparing a message", true)
            listOf("purchase", "buy ", "buy", "pay ", "pay", "transfer ", "transfer", "send money", "upi", "payment", "पेमेंट", "पैसे भेज", "खरीद").any { t.contains(it) } ->
                Decision(Risk.HIGH, "a financial or purchase action", true)
            listOf("delete ", "delete", "remove all", "clear all", "wipe ", "wipe", "डिलीट", "हटा दो", "मिटा दो", "साफ कर दो").any { t.contains(it) } ->
                Decision(Risk.HIGH, "destructive data action", true)
            t == "lock phone" || t == "lock my phone" ->
                Decision(Risk.HIGH, "locking the device", true)
            listOf("open", "search", "weather", "calculate", "battery", "time", "date").any { t.startsWith(it) } ->
                Decision(Risk.LOW, "a read-only or reversible action", false)
            else -> Decision(Risk.MEDIUM, "an action that may change device state", false)
        }
    }

    fun isConfirmation(text: String): Boolean {
        val t = CommandNormalizer.normalize(text).lowercase()
        return t in setOf("yes", "yeah", "yep", "confirm", "confirmed", "do it", "haan", "ha", "हाँ", "कर दो", "करो")
    }

    fun isRejection(text: String): Boolean {
        val t = CommandNormalizer.normalize(text).lowercase()
        return t in setOf("no", "nope", "cancel", "cancel it", "nah", "nahi", "नहीं", "मत करो", "रद्द करो")
    }
}
