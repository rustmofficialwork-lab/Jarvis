package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class JarvisAgentTest {
    @Test fun callPlanIsHighRisk() {
        val plan = JarvisAgent.plan("call 9999999999")
        assertTrue(plan.steps.any { it.tool == JarvisToolSystem.Tool.PHONE && it.requiresConfirmation })
    }

    @Test fun multiIntentGoalProducesMultipleTools() {
        val plan = JarvisAgent.plan("research today's weather and then open maps")
        assertTrue(plan.steps.any { it.tool == JarvisToolSystem.Tool.WEB_RESEARCH })
        assertTrue(plan.steps.any { it.tool == JarvisToolSystem.Tool.WEATHER })
        assertTrue(plan.steps.any { it.tool == JarvisToolSystem.Tool.MAPS })
        assertTrue(plan.needsOnlineReasoning)
    }

    @Test fun lowRiskToolsDoNotRequireConfirmation() {
        val plan = JarvisAgent.plan("calculate 25 + 17")
        assertEquals(false, plan.steps.first().requiresConfirmation)
    }

    @Test fun openCameraDoesNotCreateDuplicateGenericAppLaunch() {
        val plan = JarvisAgent.plan("open camera")
        assertEquals(1, plan.steps.count { it.tool == JarvisToolSystem.Tool.CAMERA })
        assertEquals(0, plan.steps.count { it.tool == JarvisToolSystem.Tool.APP_LAUNCH })
    }

    @Test fun toolRiskPolicyMarksExternalActions() {
        assertTrue(JarvisToolSystem.needsConfirmation(JarvisToolSystem.Tool.PHONE))
        assertTrue(JarvisToolSystem.needsConfirmation(JarvisToolSystem.Tool.SMS))
        assertTrue(JarvisToolSystem.needsConfirmation(JarvisToolSystem.Tool.SMART_HOME))
    }
}
