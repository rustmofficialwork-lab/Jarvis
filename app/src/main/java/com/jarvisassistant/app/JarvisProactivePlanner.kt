package com.jarvisassistant.app

/** Pure planning layer for proactive suggestions. It never performs side effects. */
object JarvisProactivePlanner {
    data class Suggestion(val key: String, val title: String, val body: String, val candidate: JarvisPriorityEngine.Candidate)

    fun plan(
        nowMillis: Long,
        batteryPercent: Int,
        charging: Boolean,
        nextEvent: JarvisContextEngine.CalendarEvent?,
        tasks: List<JarvisTaskStore.Task>
    ): List<Suggestion> {
        val out = mutableListOf<Suggestion>()
        if (!charging && batteryPercent in 0..20) {
            out += Suggestion("battery", "JARVIS", "Battery is $batteryPercent%. You may want to charge your phone.",
                JarvisPriorityEngine.Candidate("battery", 100 - batteryPercent, 85, 100, important = batteryPercent <= 5))
        }
        nextEvent?.let { e ->
            val minutes = ((e.beginMillis - nowMillis) / 60000L).toInt().coerceAtLeast(0)
            if (minutes <= 60) out += Suggestion("calendar_${e.id}_${e.beginMillis}", "JARVIS Calendar", "${e.title} starts in about $minutes minutes.",
                JarvisPriorityEngine.Candidate("calendar", 100 - (minutes * 3).coerceAtMost(90), 95, 100, minutes, minutes <= 5))
        }
        tasks.filter { !it.done && it.dueAt != null && it.dueAt >= nowMillis && it.dueAt <= nowMillis + 24L * 60L * 60L * 1000L }
            .sortedBy { it.dueAt }
            .take(3)
            .forEach { task ->
                val minutes = ((task.dueAt!! - nowMillis) / 60000L).toInt().coerceAtLeast(0)
                out += Suggestion("task_${task.id}", "JARVIS Task", "Task due in about $minutes minutes: ${task.text}",
                    JarvisPriorityEngine.Candidate("task", 100 - (minutes / 14).coerceAtMost(80), 88, 100, minutes, minutes <= 10))
            }
        return out.sortedByDescending { it.candidate.urgency * 45 + it.candidate.relevance * 30 }
    }
}
