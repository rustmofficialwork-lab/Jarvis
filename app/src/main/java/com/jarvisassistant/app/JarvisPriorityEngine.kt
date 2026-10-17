package com.jarvisassistant.app

/** Pure decision layer for proactive notifications. No device side effects. */
object JarvisPriorityEngine {
    enum class Level { IGNORE, LOW, NORMAL, HIGH, CRITICAL }

    data class Candidate(
        val kind: String,
        val urgency: Int,
        val relevance: Int,
        val confidence: Int = 100,
        val minutesUntil: Int? = null,
        val important: Boolean = false
    )

    data class Decision(val level: Level, val score: Int, val reason: String)

    fun score(candidate: Candidate, mode: JarvisProactiveEngine.Mode, nowHour: Int): Decision {
        if (mode == JarvisProactiveEngine.Mode.OFF) return Decision(Level.IGNORE, 0, "proactive mode is off")
        val quiet = nowHour >= 23 || nowHour < 7
        var score = (candidate.urgency.coerceIn(0, 100) * 45 +
                candidate.relevance.coerceIn(0, 100) * 30 +
                candidate.confidence.coerceIn(0, 100) * 25) / 100
        if (candidate.minutesUntil != null) {
            score += when {
                candidate.minutesUntil <= 5 -> 30
                candidate.minutesUntil <= 15 -> 20
                candidate.minutesUntil <= 30 -> 12
                candidate.minutesUntil <= 60 -> 5
                else -> 0
            }
        }
        if (candidate.important) score += 20
        if (quiet && !candidate.important) score -= 25
        score = score.coerceIn(0, 100)
        val threshold = when (mode) {
            JarvisProactiveEngine.Mode.LOW -> 85
            JarvisProactiveEngine.Mode.NORMAL -> 60
            JarvisProactiveEngine.Mode.HIGH -> 40
            JarvisProactiveEngine.Mode.OFF -> 101
        }
        val level = when {
            score < threshold -> Level.IGNORE
            candidate.important && score >= 85 -> Level.CRITICAL
            score >= 80 -> Level.HIGH
            score >= 60 -> Level.NORMAL
            else -> Level.LOW
        }
        return Decision(level, score, "score=$score threshold=$threshold")
    }
}
