package com.jarvisassistant.app

import java.net.URI
import java.util.Locale

/** Deterministic research ranking and claim-safety layer. No network access here. */
object JarvisResearchEngine {
    data class RankedSource(
        val source: ResearchSource,
        val score: Int,
        val credibility: Int,
        val freshness: Int
    )

    fun rank(sources: List<ResearchSource>, max: Int = 8): List<RankedSource> {
        return sources
            .asSequence()
            .filter { it.url.startsWith("https://") && it.title.isNotBlank() && it.excerpt.isNotBlank() }
            .map { source ->
                val host = runCatching { URI(source.url).host.orEmpty().lowercase(Locale.ROOT) }.getOrDefault("")
                val credibility = credibility(host)
                val freshness = freshnessScore(source.excerpt)
                RankedSource(source, credibility + freshness + qualityScore(source), credibility, freshness)
            }
            .distinctBy { normalizeUrl(it.source.url) }
            .sortedByDescending { it.score }
            .take(max)
            .toList()
    }

    fun compare(sources: List<ResearchSource>): String {
        val ranked = rank(sources, 8)
        if (ranked.isEmpty()) return "No verifiable research sources were retrieved."
        val grouped = ranked.groupBy { host(it.source.url) }
        val independent = grouped.keys.size
        val lead = ranked.take(3).joinToString("; ") { it.source.title }
        return "Research quality: ${if (independent >= 3) "cross-checked" else "limited-source"}; " +
            "${ranked.size} usable sources from $independent domain(s). Top sources: $lead."
    }

    fun citationLine(source: ResearchSource): String = "- ${source.title}: ${source.url}"

    private fun credibility(host: String): Int = when {
        host.endsWith(".gov") || host.contains("gov.") -> 42
        host.endsWith(".edu") || host.contains(".ac.") -> 38
        host.contains("reuters.com") || host.contains("apnews.com") || host.contains("bbc.com") -> 36
        host.contains("wikipedia.org") -> 30
        host.contains("news.google.com") -> 20
        host.isBlank() -> 0
        else -> 18
    }

    private fun freshnessScore(text: String): Int {
        val lower = text.lowercase(Locale.ROOT)
        return when {
            listOf("published today", "today", "just now", "minutes ago", "hours ago").any(lower::contains) -> 24
            listOf("yesterday", "1 day ago", "2 days ago", "this week").any(lower::contains) -> 16
            listOf("2026", "2025").any(lower::contains) -> 10
            else -> 4
        }
    }

    private fun qualityScore(source: ResearchSource): Int {
        val title = source.title.trim()
        val excerpt = source.excerpt.trim()
        return (if (title.length >= 8) 4 else 0) + (if (excerpt.length >= 80) 6 else 2)
    }

    private fun host(url: String): String = runCatching { URI(url).host.orEmpty().lowercase(Locale.ROOT).removePrefix("www.") }.getOrDefault("")
    private fun normalizeUrl(url: String): String = url.trim().removeSuffix("/").lowercase(Locale.ROOT)
}
