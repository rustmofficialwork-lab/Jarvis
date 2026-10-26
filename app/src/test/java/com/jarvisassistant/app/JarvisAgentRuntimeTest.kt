package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

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

    @Test fun confirmationApprovesOnlyPendingStepAndContinues() {
        val plan = JarvisAgent.Plan("call", listOf(
            JarvisAgent.Step(JarvisToolSystem.Tool.PHONE, "call 123", true, "test"),
            JarvisAgent.Step(JarvisToolSystem.Tool.CALCULATOR, "calculate 1+1", false, "test")
        ))
        var calls = 0
        val waiting = JarvisAgentRuntime.start(plan) { calls++; "done" }
        assertTrue(waiting.needsConfirmation)
        assertEquals(0, calls)
        val result = JarvisAgentRuntime.confirmAndContinue { calls++; "done" }
        assertEquals(JarvisAgentRuntime.Status.COMPLETED, result.state.status)
        assertEquals(2, calls)
    }

    @Test fun cancelCanRunWhileToolIsExecuting() {
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val plan = JarvisAgent.Plan("slow", listOf(
            JarvisAgent.Step(JarvisToolSystem.Tool.CALCULATOR, "calculate 1+1", false, "test")
        ))
        val runner = Thread {
            JarvisAgentRuntime.start(plan) {
                entered.countDown()
                release.await(2, TimeUnit.SECONDS)
                "done"
            }
        }
        runner.start()
        assertTrue(entered.await(1, TimeUnit.SECONDS))
        val cancelled = JarvisAgentRuntime.cancel()
        assertEquals(JarvisAgentRuntime.Status.CANCELLED, cancelled?.status)
        release.countDown()
        runner.join(1000)
        assertEquals(JarvisAgentRuntime.Status.CANCELLED, JarvisAgentRuntime.current()?.status)
    }

    @Test fun cancelStopsRun() {
        val plan = JarvisAgent.Plan("demo", listOf(JarvisAgent.Step(JarvisToolSystem.Tool.CALCULATOR, "calculate 1+1", false, "test")))
        JarvisAgentRuntime.start(plan) { "2" }
        val cancelled = JarvisAgentRuntime.cancel()
        assertEquals(JarvisAgentRuntime.Status.CANCELLED, cancelled?.status)
    }
}
