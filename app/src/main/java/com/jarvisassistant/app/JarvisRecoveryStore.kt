package com.jarvisassistant.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Encrypted, bounded persistence for resumable JARVIS agent jobs. */
class JarvisRecoveryStore(context: Context) {
    private val prefs = context.getSharedPreferences("jarvis_recovery", Context.MODE_PRIVATE)
    private val key = "agent_state"

    fun save(state: JarvisAgentRuntime.State?) {
        if (state == null) { clear(); return }
        val json = JSONObject().apply {
            put("goal", state.goal.take(1000))
            put("nextIndex", state.nextIndex)
            put("retries", state.retries)
            put("status", state.status.name)
            put("savedAt", System.currentTimeMillis())
            put("steps", JSONArray().apply {
                state.plan.steps.take(8).forEach { step ->
                    put(JSONObject().apply {
                        put("tool", step.tool.name)
                        put("command", step.command.take(800))
                        put("requiresConfirmation", step.requiresConfirmation)
                        put("reason", step.rationale.take(300))
                    })
                }
            })
            put("events", JSONArray().apply {
                state.events.takeLast(20).forEach { event ->
                    put(JSONObject().apply {
                        put("stepIndex", event.stepIndex)
                        put("status", event.status.name)
                        put("message", event.message.take(300))
                    })
                }
            })
        }
        prefs.edit().putString(key, SecureVault.encrypt(json.toString())).apply()
    }

    fun load(): JarvisAgentRuntime.State? {
        val raw = SecureVault.decrypt(prefs.getString(key, "").orEmpty())
        if (raw.isBlank()) return null
        return try {
            val json = JSONObject(raw)
            val stepsJson = json.optJSONArray("steps") ?: return null
            val steps = buildList {
                for (i in 0 until minOf(stepsJson.length(), 8)) {
                    val item = stepsJson.getJSONObject(i)
                    val tool = JarvisToolSystem.Tool.valueOf(item.getString("tool"))
                    add(JarvisAgent.Step(
                        tool = tool,
                        command = item.optString("command").take(800),
                        requiresConfirmation = item.optBoolean("requiresConfirmation"),
                        rationale = item.optString("reason").take(300)
                    ))
                }
            }
            if (steps.isEmpty()) return null
            val eventsJson = json.optJSONArray("events")
            val events = buildList {
                if (eventsJson != null) for (i in 0 until minOf(eventsJson.length(), 20)) {
                    val item = eventsJson.getJSONObject(i)
                    add(JarvisAgentRuntime.Event(item.optInt("stepIndex"), JarvisAgentRuntime.Status.valueOf(item.getString("status")), item.optString("message").take(300)))
                }
            }
            JarvisAgentRuntime.State(
                goal = json.optString("goal").take(1000),
                plan = JarvisAgent.Plan(json.optString("goal").take(1000), steps),
                nextIndex = json.optInt("nextIndex").coerceIn(0, steps.size),
                retries = json.optInt("retries").coerceAtLeast(0).coerceAtMost(2),
                status = JarvisAgentRuntime.Status.valueOf(json.optString("status", JarvisAgentRuntime.Status.FAILED.name)),
                events = events
            )
        } catch (_: Exception) { null }
    }

    fun clear() { prefs.edit().remove(key).apply() }

    companion object {
        fun isRecoverable(state: JarvisAgentRuntime.State?): Boolean =
            state != null && state.status in setOf(JarvisAgentRuntime.Status.RUNNING, JarvisAgentRuntime.Status.WAITING_CONFIRMATION)
    }
}
