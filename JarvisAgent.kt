package com.jarvisassistant.app

/**
 * Local deterministic agent planner. It decomposes common goals into safe tool steps.
 * Planning never executes a tool; high-risk steps are explicitly marked for confirmation.
 */
object JarvisAgent {
    data class Step(
        val tool: JarvisToolSystem.Tool,
        val command: String,
        val requiresConfirmation: Boolean,
        val rationale: String
    )

    data class Plan(
        val goal: String,
        val steps: List<Step>,
        val needsOnlineReasoning: Boolean = false
    )

    fun plan(input: String): Plan {
        val normalized = CommandNormalizer.normalize(input).trim()
        val lower = normalized.lowercase()
        val steps = mutableListOf<Step>()

        fun add(tool: JarvisToolSystem.Tool, reason: String, confirmation: Boolean = JarvisToolSystem.needsConfirmation(tool), command: String = normalized) {
            steps += Step(tool, command, confirmation, reason)
        }

        if (InternetResearch.shouldSearch(lower) || lower.contains("research") || lower.contains("search")) {
            add(JarvisToolSystem.Tool.WEB_RESEARCH, "Retrieve current information before answering")
        }
        if (lower.contains("weather") || lower.contains("मौसम")) {
            add(JarvisToolSystem.Tool.WEATHER, "Read current weather information")
        }
        if (lower.contains("calculate") || lower.contains("calculator") || looksLikeArithmetic(lower)) {
            add(JarvisToolSystem.Tool.CALCULATOR, "Evaluate the requested calculation")
        }
        if (lower.contains("calendar") || lower.contains("meeting") || lower.contains("schedule")) {
            add(JarvisToolSystem.Tool.CALENDAR, "Read or open calendar information", command = "open calendar")
        }
        if (lower.contains("remind") || lower.contains("reminder") || lower.contains("याद")) {
            add(JarvisToolSystem.Tool.REMINDER, "Create or open a reminder flow")
        }
        if (lower.contains("map") || lower.contains("navigate") || lower.contains("directions")) {
            add(JarvisToolSystem.Tool.MAPS, "Open navigation for the requested destination", command = extractMapsCommand(normalized) ?: "open maps")
        }
        if (lower.contains("email") || lower.contains("mail")) {
            add(JarvisToolSystem.Tool.EMAIL, "Open the email composer", command = "open email")
        }
        if (lower.contains("camera") || lower.contains("photo")) {
            add(JarvisToolSystem.Tool.CAMERA, "Open the Android camera", command = "open camera")
        }
        if (lower.contains("screenshot") || lower.contains("screen")) {
            add(JarvisToolSystem.Tool.SCREEN, "Use supported screen/accessibility actions")
        }
        if (lower.startsWith("open ")) {
            add(JarvisToolSystem.Tool.APP_LAUNCH, "Open the requested installed app", false)
        }
        if (Regex("\\b(call|dial)\\b").containsMatchIn(lower)) {
            add(JarvisToolSystem.Tool.PHONE, "A phone call has external side effects")
        }
        if (Regex("\\b(sms|text message|message)\\b").containsMatchIn(lower)) {
            add(JarvisToolSystem.Tool.SMS, "A message can affect another person")
        }
        if (lower.contains("smart home") || lower.contains("turn on the light") || lower.contains("turn off the light")) {
            add(JarvisToolSystem.Tool.SMART_HOME, "Smart-home control changes an external device")
        }

        val deduped = steps.distinctBy { it.tool }
        return Plan(
            goal = input,
            steps = deduped,
            needsOnlineReasoning = deduped.isEmpty() || looksComplex(lower)
        )
    }

    private fun extractMapsCommand(text: String): String? {
        val m = Regex("^(?:map|maps|navigate to|directions to)\\s+(.+)$", RegexOption.IGNORE_CASE).find(text)
        return m?.let { "maps ${it.groupValues[1].trim()}" }
    }

    private fun looksLikeArithmetic(text: String): Boolean =
        text.matches(Regex(".*\\d\\s*[+*/%^-]\\s*\\d.*"))

    private fun looksComplex(text: String): Boolean =
        listOf("then", "after that", "and then", "compare", "find the best", "plan a", "research and").any(text::contains)
}
