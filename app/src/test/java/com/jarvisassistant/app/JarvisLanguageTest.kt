package com.jarvisassistant.app

import org.junit.Assert.assertEquals
import org.junit.Test

class JarvisLanguageTest {
    @Test fun detectsHindiScript() {
        assertEquals(JarvisLanguage.Language.HINDI, JarvisLanguage.detect("मुझे समय बताओ"))
    }

    @Test fun detectsHinglishRomanText() {
        assertEquals(JarvisLanguage.Language.HINGLISH, JarvisLanguage.detect("Aaj weather kaisa hai"))
    }

    @Test fun detectsEnglish() {
        assertEquals(JarvisLanguage.Language.ENGLISH, JarvisLanguage.detect("Please tell me the weather today"))
    }

    @Test fun localizesKnownTimeResponse() {
        assertEquals("Sir, abhi time 4:30 PM hai.", JarvisLanguage.localizeCommandReply("abhi time kya hai", "It is 4:30 PM, Sir."))
    }
}
