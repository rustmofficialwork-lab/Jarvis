package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class JarvisAgentRuntimeTest {
    @Test fun retriesThenCompletes() {
        val plan = JarvisAgent.Plan("demo", listOf(JarvisAgent.Step(JarvisToolSystem.Tool.CALCULATOR, "calculate 1+1", false, "test")))
        var calls = 0
        val result = JarvisAgentRuntime.start(plan) {
            calls++
            if (calls < 2) null else "2"
        }
        assertEquals(JarvisAgentRuntime.Status.COMPLETED, result.state.status)
        assertEquals(2, calls)
    }

    @Test fun highRiskStopsBeforeExecution() {
        val plan = JarvisAgent.Plan("call", listOf(JarvisAgent.Step(JarvisToolSystem.Tool.PHONE, "call 123", true, "test")))
        var calls = 0
        val result = JarvisAgentRuntime.start(plan) { calls++; "sent" }
        assertEquals(JarvisAgentRuntime.Status.WAITING_CONFIRMATION, result.state.status)
        assertTrue(result.needsConfirmation)
        assertEquals(0, calls)
    }

    @Test fun cancelStopsRun() {
        val plan = JarvisAgent.Plan("demo", listOf(JarvisAgent.Step(JarvisToolSystem.Tool.CALCULATOR, "calculate 1+1", false, "test")))
        JarvisAgentRuntime.start(plan) { "2" }
        val cancelled = JarvisAgentRuntime.cancel()
        assertEquals(JarvisAgentRuntime.Status.CANCELLED, cancelled?.status)
    }
}
