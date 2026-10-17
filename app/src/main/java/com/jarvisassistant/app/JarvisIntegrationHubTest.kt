package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class JarvisIntegrationHubTest {
    @Test fun listsCoreProviders() {
        val providers = JarvisIntegrationHub.list().map { it.provider }
        assertTrue(JarvisIntegrationHub.Provider.GMAIL in providers)
        assertTrue(JarvisIntegrationHub.Provider.GOOGLE_CALENDAR in providers)
        assertTrue(JarvisIntegrationHub.Provider.WHATSAPP in providers)
    }

    @Test fun statusIsExplicitlyControlled() {
        JarvisIntegrationHub.setStatus(JarvisIntegrationHub.Provider.GMAIL, JarvisIntegrationHub.Status.CONNECTED)
        assertEquals(JarvisIntegrationHub.Status.CONNECTED, JarvisIntegrationHub.status(JarvisIntegrationHub.Provider.GMAIL))
    }
}
