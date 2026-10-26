package com.jarvisassistant.app

import android.content.Context

/** Executes only registered, bounded tools. A null result means the action did not complete. */
object JarvisAgentExecutor {
    fun execute(context: Context, step: JarvisAgent.Step, wakeWord: String): String? {
        return when (step.tool) {
            JarvisToolSystem.Tool.WEB_RESEARCH -> {
                if (!JarvisNetworkResilience.isOnline(context)) return null
                val sources = InternetResearch.search(step.command)
                if (sources.isEmpty()) null else {
                    val ranked = JarvisResearchEngine.rank(sources.map { ResearchSource(it.title, it.url, it.excerpt) }, 5)
                    if (ranked.isEmpty()) null else buildString {
                        append("Research retrieved ").append(ranked.size).append(" source(s).\n")
                        ranked.forEachIndexed { index, item ->
                            append(index + 1).append(". ").append(item.source.title).append("\n")
                            append(item.source.excerpt.take(350)).append("\n")
                            append(item.source.url).append("\n")
                        }
                    }
                }
            }
            JarvisToolSystem.Tool.WEATHER -> {
                if (!JarvisNetworkResilience.isOnline(context)) return null
                val result = JarvisWeather.answer(step.command)
                if (result.startsWith("Live weather abhi nahi") ||
                    result.startsWith("Weather ke liye") ||
                    result.startsWith("Mujhe '") ||
                    result.startsWith("Weather provider") ||
                    result.contains("coordinates nahi mile")) null else result
            }
            JarvisToolSystem.Tool.CALCULATOR -> OfflineAssistantEngine.handleCommand(step.command)
            else -> {
                val result = JarvisCommandRouter.handle(context, step.command, wakeWord) ?: return null
                if (isFailureReply(result)) null else result
            }
        }
    }

    /** Router messages asking for permissions or reporting an error are not successful actions. */
    private fun isFailureReply(reply: String): Boolean {
        val value = reply.trim().lowercase(java.util.Locale.ROOT)
        return listOf(
            "grant ", "permission", "not found", "not active", "format:",
            "cannot ", "could not ", "failed", "unavailable", "error:",
            "please enable", "isn't available", "is not available"
        ).any(value::contains)
    }
}
