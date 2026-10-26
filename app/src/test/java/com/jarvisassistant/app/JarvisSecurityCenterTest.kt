package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertTrue

class JarvisSecurityCenterTest {
    @Test fun highRiskCallRequiresConfirmation() {
        val d = JarvisSecurity.assess("call mom")
        assertTrue(d.requiresConfirmation)
    }

    @Test fun destructiveActionRequiresConfirmation() {
        val d = JarvisSecurity.assess("delete all memories")
        assertTrue(d.requiresConfirmation)
    }
}
