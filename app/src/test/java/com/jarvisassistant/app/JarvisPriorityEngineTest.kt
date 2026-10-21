package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class JarvisPriorityEngineTest {
    @Test fun offAlwaysIgnores() {
        val d = JarvisPriorityEngine.score(JarvisPriorityEngine.Candidate("meeting", 100, 100), JarvisProactiveEngine.Mode.OFF, 12)
        assertEquals(JarvisPriorityEngine.Level.IGNORE, d.level)
    }

    @Test fun urgentMeetingCanBecomeCritical() {
        val d = JarvisPriorityEngine.score(JarvisPriorityEngine.Candidate("meeting", 100, 95, minutesUntil = 3, important = true), JarvisProactiveEngine.Mode.HIGH, 12)
        assertEquals(JarvisPriorityEngine.Level.CRITICAL, d.level)
        assertTrue(d.score >= 85)
    }

    @Test fun lowModeFiltersOrdinaryNoise() {
        val d = JarvisPriorityEngine.score(JarvisPriorityEngine.Candidate("info", 20, 20), JarvisProactiveEngine.Mode.LOW, 12)
        assertEquals(JarvisPriorityEngine.Level.IGNORE, d.level)
    }

    @Test fun quietHoursReduceNonImportantScore() {
        val day = JarvisPriorityEngine.score(JarvisPriorityEngine.Candidate("info", 70, 70), JarvisProactiveEngine.Mode.NORMAL, 12)
        val night = JarvisPriorityEngine.score(JarvisPriorityEngine.Candidate("info", 70, 70), JarvisProactiveEngine.Mode.NORMAL, 2)
        assertTrue(night.score < day.score)
    }
}

class JarvisProactivePlannerTest {
    @Test fun plannerIncludesDueTasks() {
        val now = 1_000_000L
        val task = JarvisTaskStore.Task(1L, "submit report", now + 30 * 60_000L, false)
        val suggestions = JarvisProactivePlanner.plan(now, 80, true, null, listOf(task))
        assertTrue(suggestions.any { it.key == "task_1" })
    }
}
