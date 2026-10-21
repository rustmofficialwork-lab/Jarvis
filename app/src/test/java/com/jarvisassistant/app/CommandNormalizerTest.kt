package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals

class CommandNormalizerTest {
    @Test fun normalizesHindiTimeCommand() {
        assertEquals("time", CommandNormalizer.normalize("समय क्या है"))
    }

    @Test fun normalizesHinglishVolumeCommands() {
        assertEquals("volume up", CommandNormalizer.normalize("JARVIS volume badha do"))
        assertEquals("volume down", CommandNormalizer.normalize("volume kam kar do"))
    }

    @Test fun normalizesHinglishAppAndSearchCommands() {
        assertEquals("open whatsapp", CommandNormalizer.normalize("WhatsApp kholo"))
        assertEquals("search online", CommandNormalizer.normalize("internet par search karo"))
    }

    @Test fun normalizesMemoryPhrases() {
        assertEquals("remember", CommandNormalizer.normalize("ye yaad rakhna"))
        assertEquals("remind me", CommandNormalizer.normalize("mujhe yaad dilana"))
    }
}
