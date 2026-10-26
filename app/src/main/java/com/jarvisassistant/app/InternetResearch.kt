package com.jarvisassistant.app

import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

object InternetResearch {
    private const val TAG = "InternetResearch"

    data class SearchResult(
        val title: String,
        val url: String,
        val excerpt: String
    )

    // JarvisAgent.kt ise use karta hai
    fun shouldSearch(query: String): Boolean {
        val lower = query.lowercase()
        val keywords = listOf(
            "search", "who is", "what is", "news", "weather", "latest",
            "kya hai", "kaun hai", "research", "tell me about", "find",
            "current", "today", "aaj ka", "khabar"
        )
        return keywords.any { lower.contains(it) }
    }

    // AiProvider.kt ise use karta hai (DuckDuckGo API)
    fun search(query: String): List<SearchResult> {
        if (query.isBlank()) return emptyList()
        val results = mutableListOf<SearchResult>()

        try {
            val encodedQuery = URLEncoder.encode(query, "UTF-8")
            val searchUrl = URL("https://api.duckduckgo.com/?q=$encodedQuery&format=json&no_html=1")
            val connection = searchUrl.openConnection() as HttpURLConnection

            try {
                connection.requestMethod = "GET"
                connection.connectTimeout = 10000
                connection.readTimeout = 15000
                connection.setRequestProperty("User-Agent", "JARVIS-Android/1.0")

                if (connection.responseCode in 200..299) {
                    val response = connection.inputStream.bufferedReader().use { it.readText() }
                    val json = JSONObject(response)

                    val abstractText = json.optString("AbstractText", "")
                    val abstractUrl = json.optString("AbstractURL", "")
                    val heading = json.optString("Heading", query)

                    if (abstractText.isNotBlank() && abstractUrl.isNotBlank()) {
                        results.add(SearchResult(heading, abstractUrl, abstractText))
                    }

                    val related = json.optJSONArray("RelatedTopics")
                    addRelatedTopics(related, results)
                }
            } finally {
                connection.disconnect()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Search failed: ${e.message}")
        }

        return results.distinctBy { it.url }.take(10)
    }

    private fun addRelatedTopics(topics: JSONArray?, results: MutableList<SearchResult>) {
        if (topics == null) return
        for (i in 0 until topics.length()) {
            val item = topics.optJSONObject(i) ?: continue

            val nested = item.optJSONArray("Topics")
            if (nested != null) {
                addRelatedTopics(nested, results)
                continue
            }

            val text = item.optString("Text", "")
            val firstUrl = item.optString("FirstURL", "")

            if (text.isNotBlank() && firstUrl.isNotBlank()) {
                results.add(SearchResult(text.take(100), firstUrl, text))
            }
        }
    }
}
