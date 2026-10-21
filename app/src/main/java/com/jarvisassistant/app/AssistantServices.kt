package com.jarvisassistant.app

import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.io.ByteArrayOutputStream
import java.io.StringReader
import java.util.concurrent.atomic.AtomicBoolean
import javax.xml.parsers.DocumentBuilderFactory
import org.xml.sax.InputSource

data class ResearchSource(val title: String, val url: String, val excerpt: String)
data class ChatTurn(val user: String, val assistant: String, val sources: List<ResearchSource> = emptyList())
data class AssistantAnswer(val text: String, val sources: List<ResearchSource> = emptyList())

/**
 * Uses the widely implemented OpenAI Chat Completions wire format. The base URL and model
 * are user-configurable, so the app does not bind a source-level credential or one vendor.
 */
object AiProvider {
    fun answer(
        endpoint: String,
        model: String,
        apiKey: String,
        prompt: String,
        recentTurns: List<ChatTurn>,
        memory: String,
        research: List<ResearchSource>,
        researchWasRequested: Boolean,
        seriousMode: Boolean,
        cybersecurityMode: Boolean,
        cancelled: () -> Boolean = { false }
    ): String {
        require(apiKey.isNotBlank()) { "Add an API key in Settings to use online AI." }
        val url = URL(endpoint.trim())
        require(url.protocol == "https") { "The AI endpoint must use HTTPS." }

        val system = buildString {
            append("You are JARVIS, a helpful personal Android assistant. Address the user as Master when natural, not in every sentence. ")
            append("Be clear about uncertainty and never claim a phone action succeeded unless the app reports that it did. ")
            append("Do not invent web research or citations. ")
            if (seriousMode) append("Serious Mode is active: be focused, direct and concise. ")
            if (cybersecurityMode) {
                append("Cybersecurity Mode is active: provide defensive, authorized guidance only; ask for clear authorization and scope before discussing tests against a real target. ")
                append("Do not assist credential theft, stealth, malware, bypasses, exploitation or destructive actions. ")
            }
            if (memory.isNotBlank()) append("\nUser-approved local memory (may be used for personalization):\n$memory\n")
            if (researchWasRequested) {
                append("\nThe user asked for current information. Use only the retrieved research below, cite claims with source URLs in Markdown, ")
                append("and say plainly if the results do not support a reliable answer. Do not imply that a search worked if it returned no results.\n")
                append("Research quality: ${JarvisResearchEngine.compare(research)}\n")
                append("Retrieved sources (use only these URLs for citations):\n")
                append(
                    research.joinToString("\n") { JarvisResearchEngine.citationLine(it) + " — " + it.excerpt }
                        .ifBlank { "No research results were retrieved. Explain that current information could not be verified." }
                )
            }
        }

        val messages = JSONArray().put(JSONObject().put("role", "system").put("content", system))
        recentTurns.takeLast(8).forEach { turn ->
            messages.put(JSONObject().put("role", "user").put("content", turn.user))
            messages.put(JSONObject().put("role", "assistant").put("content", turn.assistant))
        }
        messages.put(JSONObject().put("role", "user").put("content", prompt))
        val isResponsesApi = url.path.endsWith("/responses", ignoreCase = true)
        val body = if (isResponsesApi) {
            JSONObject()
                .put("model", model.trim())
                .put("instructions", system)
                .put("input", prompt)
                .put("stream", false)
                .toString()
        } else {
            JSONObject()
                .put("model", model.trim())
                .put("messages", messages)
                .put("stream", false)
                .toString()
        }

        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 15_000
            readTimeout = 45_000
            doOutput = true
            setRequestProperty("Authorization", "Bearer $apiKey")
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", "application/json")
        }
        try {
            if (cancelled()) throw java.util.concurrent.CancellationException("request cancelled")
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val response = if (stream == null) "" else {
                val out = ByteArrayOutputStream()
                stream.use { input ->
                    val buffer = ByteArray(8192)
                    while (true) {
                        if (cancelled()) throw java.util.concurrent.CancellationException("request cancelled")
                        val n = input.read(buffer)
                        if (n < 0) break
                        out.write(buffer, 0, n)
                    }
                }
                out.toString(Charsets.UTF_8.name())
            }
            if (status !in 200..299) {
                val detail = try {
                    JSONObject(response).optJSONObject("error")?.optString("message").orEmpty()
                } catch (_: Exception) { "" }
                return "The AI provider returned HTTP $status${if (detail.isNotBlank()) ": $detail" else "."}"
            }
            val json = JSONObject(response)
            val answer = if (isResponsesApi) {
                json.optString("output_text").ifBlank {
                    val output = json.optJSONArray("output") ?: JSONArray()
                    (0 until output.length()).flatMap { i ->
                        val content = output.optJSONObject(i)?.optJSONArray("content") ?: JSONArray()
                        (0 until content.length()).mapNotNull { j -> content.optJSONObject(j)?.optString("text")?.takeIf { it.isNotBlank() } }
                    }.joinToString("\n")
                }
            } else {
                val content = json.optJSONArray("choices")
                    ?.optJSONObject(0)
                    ?.optJSONObject("message")
                    ?.opt("content")
                when (content) {
                is String -> content
                is JSONArray -> (0 until content.length()).mapNotNull { i ->
                    content.optJSONObject(i)?.optString("text")?.takeIf(String::isNotBlank)
                }.joinToString("\n")
                    else -> ""
                }
            }
            return answer.ifBlank { "The AI provider returned an empty response." }
        } finally {
            connection.disconnect()
        }
    }
}

/**
 * Lightweight public search through DuckDuckGo's Instant Answer API. This is an
 * information-retrieval aid, not a general web crawler; empty results stay empty.
 */
object InternetResearch {
    private val currentInfoTerms = listOf(
        "latest", "current", "today", "right now", "this week", "this month",
        "news", "price of", "weather", "recent", "look up", "search online",
        "research", "search", "look up", "as of ", "who is the current", "what happened", "खोज", "आज", "अभी", "ताज़ा", "लेटेस्ट", "समाचार", "न्यूज़", "खबर", "कीमत", "मौसम", "कौन है"
    )

    fun shouldSearch(prompt: String): Boolean {
        val lower = prompt.lowercase()
        return currentInfoTerms.any(lower::contains)
    }

    fun search(query: String, cancelled: () -> Boolean = { false }): List<ResearchSource> {
        val url = URL("https://api.duckduckgo.com/?q=${Uri.encode(query)}&format=json&no_html=1&skip_disambig=1")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8_000
            readTimeout = 12_000
            setRequestProperty("User-Agent", "JARVIS-Android/1.0")
            setRequestProperty("Accept", "application/json")
        }
        try {
            if (cancelled()) return emptyList()
            if (connection.responseCode !in 200..299) return emptyList()
            val json = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            val sources = LinkedHashMap<String, ResearchSource>()
            fun add(title: String, link: String, excerpt: String) {
                if (link.startsWith("https://") && excerpt.isNotBlank() && sources.size < 5) {
                    sources.putIfAbsent(link, ResearchSource(title.ifBlank { link }, link, excerpt.take(500)))
                }
            }
            add(json.optString("Heading"), json.optString("AbstractURL"), json.optString("AbstractText"))
            collectTopics(json.optJSONArray("RelatedTopics"), sources, 3)
            // Deliberately mix independent sources instead of letting one provider fill the list.
            if (!cancelled()) searchWikipedia(query, sources, 5)
            if (!cancelled()) searchNewsRss(query, sources, 8)
            return JarvisResearchEngine.rank(sources.values.toList(), 8).map { it.source }
        } catch (_: Exception) {
            return emptyList()
        } finally {
            connection.disconnect()
        }
    }

    private fun searchWikipedia(query: String, found: LinkedHashMap<String, ResearchSource>, limit: Int = 5) {
        try {
            val api = URL("https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=${Uri.encode(query)}&format=json&srlimit=3")
            val c = api.openConnection() as HttpURLConnection
            c.connectTimeout = 6000; c.readTimeout = 9000
            c.setRequestProperty("User-Agent", "JARVIS-Android/2.0")
            if (c.responseCode !in 200..299) { c.disconnect(); return }
            val json = JSONObject(c.inputStream.bufferedReader().use { it.readText() })
            val hits = json.optJSONObject("query")?.optJSONArray("search") ?: JSONArray()
            for (i in 0 until hits.length()) {
                val item = hits.optJSONObject(i) ?: continue
                val title = item.optString("title")
                val url = "https://en.wikipedia.org/wiki/${Uri.encode(title.replace(' ', '_'))}"
                val snippet = item.optString("snippet").replace(Regex("<[^>]+>"), "")
                if (snippet.isNotBlank()) found.putIfAbsent(url, ResearchSource(title, url, snippet.take(500)))
                if (found.size >= limit) break
            }
            c.disconnect()
        } catch (_: Exception) { }
    }

    private fun searchNewsRss(query: String, found: LinkedHashMap<String, ResearchSource>, limit: Int = 8) {
        try {
            val rss = URL("https://news.google.com/rss/search?q=${Uri.encode(query)}&hl=en-IN&gl=IN&ceid=IN:en")
            val c = rss.openConnection() as HttpURLConnection
            c.connectTimeout = 6000
            c.readTimeout = 9000
            c.setRequestProperty("User-Agent", "JARVIS-Android/2.1")
            if (c.responseCode !in 200..299) { c.disconnect(); return }
            c.inputStream.use { input ->
                val factory = DocumentBuilderFactory.newInstance().apply {
                    setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
                    setFeature("http://xml.org/sax/features/external-general-entities", false)
                    setFeature("http://xml.org/sax/features/external-parameter-entities", false)
                    isExpandEntityReferences = false
                }
                val doc = factory.newDocumentBuilder().parse(InputSource(input))
                val items = doc.getElementsByTagName("item")
                for (i in 0 until minOf(items.length, 5)) {
                    val node = items.item(i)
                    fun text(tag: String): String = node.childNodes.let { children ->
                        (0 until children.length).asSequence()
                            .map { children.item(it) }
                            .firstOrNull { it.nodeName == tag }?.textContent?.trim().orEmpty()
                    }
                    val title = text("title")
                    val link = text("link")
                    val date = text("pubDate")
                    if (title.isNotBlank() && link.startsWith("https://")) {
                        found.putIfAbsent(link, ResearchSource(title, link, if (date.isBlank()) "News result" else "Published $date"))
                    }
                    if (found.size >= limit) break
                }
            }
            c.disconnect()
        } catch (_: Exception) { }
    }

    private fun collectTopics(items: JSONArray?, found: LinkedHashMap<String, ResearchSource>, limit: Int = 5) {
        if (items == null || found.size >= limit) return
        for (i in 0 until items.length()) {
            if (found.size >= limit) break
            val item = items.optJSONObject(i) ?: continue
            val nested = item.optJSONArray("Topics")
            if (nested != null) {
                collectTopics(nested, found, limit)
            } else {
                val text = item.optString("Text")
                val firstUrl = item.optString("FirstURL")
                val title = text.substringBefore(" - ").ifBlank { firstUrl }
                addSource(found, title, firstUrl, text)
            }
        }
    }

    private fun addSource(
        found: LinkedHashMap<String, ResearchSource>,
        title: String,
        link: String,
        excerpt: String
    ) {
        if (link.startsWith("https://") && excerpt.isNotBlank() && found.size < 8) {
            found.putIfAbsent(link, ResearchSource(title.ifBlank { link }, link, excerpt.take(500)))
        }
    }
}
