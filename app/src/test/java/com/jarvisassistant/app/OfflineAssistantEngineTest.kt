package com.jarvisassistant.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OfflineAssistantEngineTest {

    @Test
    fun greetingCommandWorks() {
        val result = OfflineAssistantEngine.handleCommand("hello")

        assertNotNull(result)
        assertTrue(result!!.isNotBlank())
    }

    @Test
    fun hindiGreetingCommandWorks() {
        val result = OfflineAssistantEngine.handleCommand("namaste")

        assertNotNull(result)
        assertTrue(result!!.isNotBlank())
    }

    @Test
    fun helpCommandWorks() {
        val result = OfflineAssistantEngine.handleCommand("help")

        assertNotNull(result)
        assertTrue(result!!.isNotBlank())
    }

    @Test
    fun additionWorks() {
        assertEquals(
            4.0,
            OfflineAssistantEngine.calculate("2+2")!!,
            0.0001
        )
    }

    @Test
    fun multiplicationWorks() {
        assertEquals(
            12.0,
            OfflineAssistantEngine.calculate("3*4")!!,
            0.0001
        )
    }

    @Test
    fun parenthesesWork() {
        assertEquals(
            20.0,
            OfflineAssistantEngine.calculate("(2+3)*4")!!,
            0.0001
        )
    }

    @Test
    fun powerWorks() {
        assertEquals(
            8.0,
            OfflineAssistantEngine.calculate("2^3")!!,
            0.0001
        )
    }

    @Test
    fun divisionByZeroReturnsNull() {
        assertNull(OfflineAssistantEngine.calculate("5/0"))
    }

    @Test
    fun invalidExpressionReturnsNull() {
        assertNull(OfflineAssistantEngine.calculate("hello world"))
    }

    @Test
    fun unknownCommandReturnsNull() {
        assertNull(
            OfflineAssistantEngine.handleCommand(
                "open a spaceship"
            )
        )
    }
}
