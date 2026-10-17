package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class JarvisResearchEngineTest {
    private fun source(title: String, url: String, excerpt: String) = ResearchSource(title, url, excerpt)

    @Test fun secureSourcesAreRankedAndDeduplicated() {
        val items = listOf(
            source("Wikipedia", "https://en.wikipedia.org/wiki/Android", "Android reference published today"),
            source("Government", "https://example.gov/report", "Official report published today with detailed findings"),
            source("Duplicate", "https://example.gov/report/", "same")
        )
        val ranked = JarvisResearchEngine.rank(items)
        assertEquals(2, ranked.size)
        assertTrue(ranked.first().source.url.contains("example.gov"))
    }

    @Test fun comparisonReportsIndependentDomains() {
        val result = JarvisResearchEngine.compare(listOf(
            source("A", "https://a.gov/x", "Official report published today"),
            source("B", "https://reuters.com/x", "News published today"),
            source("C", "https://en.wikipedia.org/wiki/X", "Reference")
        ))
        assertTrue(result.contains("cross-checked"))
        assertTrue(result.contains("3 domain(s)"))
    }

    @Test fun httpSourcesAreRejected() {
        val ranked = JarvisResearchEngine.rank(listOf(source("Bad", "http://example.com", "text")))
        assertTrue(ranked.isEmpty())
    }
}
