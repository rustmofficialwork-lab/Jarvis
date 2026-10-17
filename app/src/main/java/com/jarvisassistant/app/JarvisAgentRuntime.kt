package com.jarvisassistant.app

/**
 * Stateful execution coordinator for multi-step agent plans.
 * It never bypasses JarvisToolSystem confirmation metadata and is bounded to prevent runaway loops.
 */
object JarvisAgentRuntime {
    enum class Status { IDLE, RUNNING, WAITING_CONFIRMATION, COMPLETED, FAILED, CANCELLED }

    data class Event(val stepIndex: Int, val status: Status, val message: String)

    data class State(
        val goal: String,
        val plan: JarvisAgent.Plan,
        val nextIndex: Int = 0,
        val retries: Int = 0,
        val status: Status = Status.IDLE,
        val events: List<Event> = emptyList()
    )

    data class Result(
        val state: State,
        val needsConfirmation: Boolean = false,
        val confirmationReason: String? = null
    )

    private const val MAX_STEPS = 8
    private const val MAX_RETRIES_PER_STEP = 2
    private var state: State? = null

    @Synchronized fun snapshot(): State? = state

    @Synchronized fun restore(restored: State?): State? {
        state = restored
        return state
    }

    @Synchronized fun current(): State? = state

    @Synchronized fun start(plan: JarvisAgent.Plan, executor: (JarvisAgent.Step) -> String?): Result {
        if (plan.steps.size > MAX_STEPS) {
            val failed = State(plan.goal, plan, status = Status.FAILED,
                events = listOf(Event(-1, Status.FAILED, "Plan exceeds the $MAX_STEPS-step safety limit.")))
            state = failed
            return Result(failed)
        }
        state = State(plan.goal, plan, status = Status.RUNNING)
        return runUntilBlocked(executor)
    }

    @Synchronized fun confirmAndContinue(executor: (JarvisAgent.Step) -> String?): Result {
        val current = state ?: return Result(
            State("", JarvisAgent.Plan("", emptyList()), status = Status.FAILED,
                events = listOf(Event(-1, Status.FAILED, "No agent run is waiting for confirmation.")))
        )
        if (current.status != Status.WAITING_CONFIRMATION) return Result(current)
        state = current.copy(status = Status.RUNNING, events = current.events + Event(current.nextIndex, Status.RUNNING, "Confirmation received; continuing."))
        return runUntilBlocked(executor)
    }

    @Synchronized fun cancel(): State? {
        val current = state ?: return null
        val cancelled = current.copy(status = Status.CANCELLED,
            events = current.events + Event(current.nextIndex, Status.CANCELLED, "Agent run cancelled."))
        state = cancelled
        return cancelled
    }

    private fun runUntilBlocked(executor: (JarvisAgent.Step) -> String?): Result {
        var current = state ?: return Result(State("", JarvisAgent.Plan("", emptyList()), status = Status.FAILED))
        while (current.nextIndex < current.plan.steps.size) {
            val step = current.plan.steps[current.nextIndex]
            if (step.requiresConfirmation) {
                current = current.copy(
                    status = Status.WAITING_CONFIRMATION,
                    events = current.events + Event(current.nextIndex, Status.WAITING_CONFIRMATION, "Confirmation required for ${step.tool.name}."))
                state = current
                return Result(current, true, JarvisToolSystem.describe(step.tool))
            }
            var attempt = 0
            var output: String? = null
            while (attempt <= MAX_RETRIES_PER_STEP && output == null) {
                attempt++
                output = try { executor(step) } catch (_: Exception) { null }
                if (output == null && attempt <= MAX_RETRIES_PER_STEP) {
                    current = current.copy(retries = attempt,
                        events = current.events + Event(current.nextIndex, Status.RUNNING, "Retrying ${step.tool.name} ($attempt/$MAX_RETRIES_PER_STEP)."))
                }
            }
            if (output == null) {
                current = current.copy(status = Status.FAILED,
                    events = current.events + Event(current.nextIndex, Status.FAILED, "${step.tool.name} failed after retries."))
                state = current
                return Result(current)
            }
            current = current.copy(
                nextIndex = current.nextIndex + 1,
                retries = 0,
                events = current.events + Event(current.nextIndex, Status.RUNNING, output.take(240)))
            state = current
        }
        current = current.copy(status = Status.COMPLETED,
            events = current.events + Event(current.nextIndex, Status.COMPLETED, "Agent goal completed."))
        state = current
        return Result(current)
    }
}
