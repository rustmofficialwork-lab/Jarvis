package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.assertEquals

class JarvisSecurityTest {
    @Test fun callRequiresConfirmation() {
        assertTrue(JarvisSecurity.assess("call 9999999999").requiresConfirmation)
        assertEquals(JarvisSecurity.Risk.HIGH, JarvisSecurity.assess("call 9999999999").risk)
    }

    @Test fun messageRequiresConfirmation() {
        assertTrue(JarvisSecurity.assess("send sms 9999999999").requiresConfirmation)
    }

    @Test fun normalSearchDoesNotRequireConfirmation() {
        assertFalse(JarvisSecurity.assess("search latest Android news").requiresConfirmation)
    }

    @Test fun hindiConfirmationIsAccepted() {
        assertTrue(JarvisSecurity.isConfirmation("haan"))
        assertTrue(JarvisSecurity.isRejection("nahi"))
    }
}
