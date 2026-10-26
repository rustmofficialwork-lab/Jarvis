package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class JarvisNetworkResilienceTest {
    @Test fun retryDelayIsBoundedAndExponential() {
        assertEquals(1000L, JarvisNetworkResilience.retryDelayMillis(0))
        assertEquals(2000L, JarvisNetworkResilience.retryDelayMillis(1))
        assertEquals(30000L, JarvisNetworkResilience.retryDelayMillis(5))
        assertTrue(JarvisNetworkResilience.retryDelayMillis(99) <= 30000L)
    }

    @Test fun transientFailureClassifierRecognizesNetworkErrors() {
        assertTrue(JarvisNetworkResilience.isTransientNetworkFailure(java.net.UnknownHostException("offline")))
        assertTrue(JarvisNetworkResilience.isTransientNetworkFailure(java.net.SocketTimeoutException("timeout")))
    }
}
