package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals

class JarvisDiagnosticsTest {
    @Test fun entryFieldsAreBounded() {
        val e = JarvisDiagnostics.Entry(1L, "category", "INFO", "message")
        assertEquals("category", e.category)
        assertEquals("INFO", e.level)
        assertEquals("message", e.message)
    }
}
