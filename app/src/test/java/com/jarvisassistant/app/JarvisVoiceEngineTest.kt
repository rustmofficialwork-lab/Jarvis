package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.assertEquals
import java.util.Locale

class JarvisVoiceEngineTest {
    @Test fun jarvisWakeAliasesIncludeHindiForms() {
        val aliases = JarvisVoiceEngine.wakeAliases("JARVIS")
        assertTrue(aliases.contains("JARVIS"))
        assertTrue(aliases.contains("jarvis"))
        assertTrue(aliases.contains("जार्विस"))
        assertTrue(aliases.contains("जारविस"))
    }

    @Test fun wakeMatchingUsesWordBoundaries() {
        assertTrue(JarvisVoiceEngine.containsWakeWord("JARVIS", "JARVIS"))
        assertTrue(JarvisVoiceEngine.containsWakeWord("JARVIS what time is it", "JARVIS"))
        assertTrue(JarvisVoiceEngine.containsWakeWord("जार्विस समय बताओ", "JARVIS"))
        assertFalse(JarvisVoiceEngine.containsWakeWord("jarvislike", "JARVIS"))
    }

    @Test fun autoTtsUsesDeviceLocale() {
        assertEquals(Locale("hi", "IN"), JarvisVoiceEngine.ttsLocale("auto", Locale("hi", "IN")))
    }

    @Test fun blankWakeWordFallsBackToJarvis() {
        assertTrue(JarvisVoiceEngine.containsWakeWord("JARVIS hello", ""))
    }
}
