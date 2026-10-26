package com.jarvisassistant.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Encrypted, bounded, user-controlled long-term memory. */
class JarvisMemoryManager(private val context: Context) {
    private val prefs = context.getSharedPreferences("jarvis_long_memory", Context.MODE_PRIVATE)
    private val key = "items"
    private val maxItems = 200

    enum class Kind(val wire: String) {
        PREFERENCE("preference"), PERSON("person"), PROJECT("project"), EPISODIC("episodic"), FACT("fact"), PROFILE("profile"), USER("user");
        companion object { fun fromWire(value: String): Kind = values().firstOrNull { it.wire.equals(value, true) } ?: FACT }
    }

    data class Memory(val id: String, val text: String, val kind: String = Kind.FACT.wire, val createdAt: Long = System.currentTimeMillis(), val updatedAt: Long = createdAt)

    @Synchronized fun list(): List<Memory> = readItems()
    @Synchronized fun list(kind: String): List<Memory> = readItems().filter { it.kind.equals(kind, true) }
    @Synchronized fun search(query: String): List<Memory> {
        val q = query.trim().lowercase()
        if (q.isBlank()) return emptyList()
        return readItems().filter { it.text.lowercase().contains(q) || it.kind.lowercase().contains(q) }
    }

    @Synchronized fun remember(text: String, kind: String = Kind.FACT.wire) {
        val clean = text.trim().take(500)
        if (clean.isBlank()) return
        val normalizedKind = Kind.fromWire(kind).wire
        val now = System.currentTimeMillis()
        val existing = readItems().filterNot { it.text.equals(clean, true) }
        val items = (existing + Memory(java.util.UUID.randomUUID().toString(), clean, normalizedKind, now, now)).takeLast(maxItems)
        writeItems(items)
    }

    @Synchronized fun forget(query: String): Int {
        val q = query.trim().lowercase()
        if (q.isBlank()) return 0
        val old = readItems()
        val kept = old.filterNot { it.text.lowercase().contains(q) || it.id == query.trim() }
        writeItems(kept)
        return old.size - kept.size
    }

    @Synchronized fun forgetId(id: String): Boolean {
        val old = readItems()
        val kept = old.filterNot { it.id == id }
        writeItems(kept)
        return kept.size != old.size
    }

    @Synchronized fun clear() { prefs.edit().remove(key).apply() }
    /**
     * Build a compact, query-relevant memory context for the AI request.
     * This avoids sending every saved personal fact on every turn. If no terms
     * overlap, only a small recent subset is used rather than the full vault.
     */
    @Synchronized fun contextFor(query: String, maxChars: Int = 2_000, fallbackItems: Int = 5): String {
        val items = readItems()
        if (items.isEmpty() || maxChars <= 0) return ""
        val stopWords = setOf(
            "the", "and", "for", "that", "this", "with", "you", "your", "what", "when",
            "where", "how", "please", "about", "from", "have", "hai", "ho", "ka", "ki",
            "ke", "ko", "me", "mein", "mujhe", "batao", "kya", "aur", "theek"
        )
        val terms = Regex("[\\p{L}\\p{N}]{2,}")
            .findAll(query.lowercase(java.util.Locale.ROOT))
            .map { it.value }
            .filterNot { it in stopWords }
            .toSet()
        val scored = items.map { memory ->
            val body = (memory.text + " " + memory.kind).lowercase(java.util.Locale.ROOT)
            val score = terms.count { term -> body.contains(term) }
            memory to score
        }
        val relevant = scored.filter { it.second > 0 }
            .sortedWith(compareByDescending<Pair<Memory, Int>> { it.second }.thenByDescending { it.first.updatedAt })
            .map { it.first }
        val selected = if (relevant.isNotEmpty()) relevant.take(12)
            else items.sortedByDescending { it.updatedAt }.take(fallbackItems.coerceAtLeast(0))
        val output = StringBuilder()
        for (item in selected) {
            val line = "- [${item.kind}] ${item.text}\n"
            if (output.length + line.length > maxChars) break
            output.append(line)
        }
        return output.toString().trim()
    }

    fun context(maxChars: Int = 4_000): String = list().asReversed().joinToString("\n") { "- [${it.kind}] ${it.text}" }.take(maxChars)

    private fun readItems(): List<Memory> {
        val raw = SecureVault.decrypt(prefs.getString(key, "").orEmpty())
        return try {
            val a = JSONArray(raw)
            (0 until a.length()).mapNotNull { i ->
                a.optJSONObject(i)?.let {
                    val text = it.optString("text").trim()
                    if (text.isBlank()) null else Memory(
                        id = it.optString("id").ifBlank { java.util.UUID.randomUUID().toString() },
                        text = text,
                        kind = Kind.fromWire(it.optString("kind", "fact")).wire,
                        createdAt = it.optLong("createdAt", System.currentTimeMillis()),
                        updatedAt = it.optLong("updatedAt", it.optLong("createdAt", System.currentTimeMillis()))
                    )
                }
            }.takeLast(maxItems)
        } catch (_: Exception) { emptyList() }
    }

    private fun writeItems(items: List<Memory>) {
        val a = JSONArray().apply {
            items.takeLast(maxItems).forEach {
                put(JSONObject().put("id", it.id).put("text", it.text).put("kind", it.kind).put("createdAt", it.createdAt).put("updatedAt", it.updatedAt))
            }
        }
        prefs.edit().putString(key, SecureVault.encrypt(a.toString())).apply()
    }
}
