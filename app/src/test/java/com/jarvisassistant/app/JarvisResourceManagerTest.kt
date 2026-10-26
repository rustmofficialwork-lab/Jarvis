package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class JarvisResourceManagerTest {
    @Test fun requestLimitIsBounded() {
        assertTrue(JarvisResourceManager.safeRequestLimitChars() in 4000..16000)
    }

    @Test fun defaultConcurrencyIsSingle() {
        assertEquals(1, JarvisResourceManager.Snapshot(JarvisResourceManager.Pressure.NORMAL, 512, 1024, false).maxConcurrentJobs)
    }
}
