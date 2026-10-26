package com.jarvisassistant.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Small encrypted local task list for JARVIS productivity commands. */
class JarvisTaskStore(context: Context) {
    data class Task(val id: Long, val text: String, val dueAt: Long? = null, val done: Boolean = false)
    
    // RENAMED: "jarvis_tasks" -> "jarvis_tasks"
    private val prefs = context.getSharedPreferences("jarvis_tasks", Context.MODE_PRIVATE)
    private val key = "items"
    private val maxItems = 200

    @Synchronized fun list(includeDone: Boolean = false): List<Task> {
        val raw = SecureVault.decrypt(prefs.getString(key, "").orEmpty())
        return runCatching {
            val a = JSONArray(raw)
            (0 until a.length()).mapNotNull { i ->
                a.optJSONObject(i)?.let { o -> Task(o.optLong("id"), o.optString("text"), o.optLong("due", 0L).takeIf { it > 0 }, o.optBoolean("done")) }
            }.filter { includeDone || !it.done }
        }.getOrDefault(emptyList())
    }

    @Synchronized fun add(text: String, dueAt: Long? = null): Task {
        val existing = list(true)
        // Keep IDs unique even when several tasks are created within the same millisecond.
        val id = maxOf(System.currentTimeMillis(), (existing.maxOfOrNull { it.id } ?: 0L) + 1L)
        val task = Task(id, text.trim().take(300), dueAt)
        val items = existing.takeLast(maxItems - 1) + task
        save(items)
        return task
    }

    @Synchronized fun complete(id: Long): Boolean {
        val items = list(true)
        val changed = items.any { it.id == id && !it.done }
        if (changed) save(items.map { if (it.id == id) it.copy(done = true) else it })
        return changed
    }

    @Synchronized fun delete(id: Long): Boolean {
        val items = list(true)
        val filtered = items.filterNot { it.id == id }
        if (filtered.size != items.size) save(filtered) else return false
        return true
    }

    @Synchronized fun clearDone() = save(list(true).filterNot { it.done })

    private fun save(items: List<Task>) {
        val a = JSONArray().apply { 
            items.forEach { 
                put(JSONObject().put("id", it.id).put("text", it.text).put("due", it.dueAt ?: 0L).put("done", it.done)) 
            } 
        }
        prefs.edit().putString(key, SecureVault.encrypt(a.toString())).apply()
    }
}
