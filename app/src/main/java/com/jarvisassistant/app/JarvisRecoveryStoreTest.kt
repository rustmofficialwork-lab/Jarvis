package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals

class JarvisRecoveryStoreTest {
    @Test fun runtimeStateCanBeRestoredWithoutChangingStatus() {
        val plan = JarvisAgent.Plan("demo", listOf(JarvisAgent.Step(JarvisToolSystem.Tool.CALCULATOR, "calculate 2+2", false, "demo")))
        val state = JarvisAgentRuntime.State("demo", plan, nextIndex = 0, status = JarvisAgentRuntime.Status.WAITING_CONFIRMATION)
        JarvisAgentRuntime.restore(state)
        assertEquals(JarvisAgentRuntime.Status.WAITING_CONFIRMATION, JarvisAgentRuntime.current()?.status)
        assertEquals(0, JarvisAgentRuntime.current()?.nextIndex)
    }
}
