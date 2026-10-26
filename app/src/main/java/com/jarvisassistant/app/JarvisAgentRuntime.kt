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
    @Volatile private var state: State? = null

    @Synchronized fun snapshot(): State? = state

    @Synchronized fun restore(restored: State?): State? {
        state = restored
        return state
    }

    @Synchronized fun current(): State? = state

    fun start(plan: JarvisAgent.Plan, executor: (JarvisAgent.Step) -> String?): Result {
        synchronized(this) {
            if (plan.steps.size > MAX_STEPS) {
                val failed = State(plan.goal, plan, status = Status.FAILED,
                    events = listOf(Event(-1, Status.FAILED, "Plan exceeds the $MAX_STEPS-step safety limit.")))
                state = failed
                return Result(failed)
            }
            state = State(plan.goal, plan, status = Status.RUNNING)
        }
        return runUntilBlocked(executor)
    }

    fun confirmAndContinue(executor: (JarvisAgent.Step) -> String?): Result {
        synchronized(this) {
            val current = state ?: return Result(
                State("", JarvisAgent.Plan("", emptyList()), status = Status.FAILED,
                    events = listOf(Event(-1, Status.FAILED, "No agent run is waiting for confirmation.")))
            )
            if (current.status != Status.WAITING_CONFIRMATION) return Result(current)
            val approvedSteps = current.plan.steps.toMutableList()
            if (current.nextIndex !in approvedSteps.indices) return Result(current)
            approvedSteps[current.nextIndex] = approvedSteps[current.nextIndex].copy(requiresConfirmation = false)
            state = current.copy(
                plan = current.plan.copy(steps = approvedSteps),
                status = Status.RUNNING,
                events = current.events + Event(current.nextIndex, Status.RUNNING, "Confirmation received; continuing.")
            )
        }
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
        while (true) {
            val current = synchronized(this) { state }
                ?: return Result(State("", JarvisAgent.Plan("", emptyList()), status = Status.FAILED))
            if (current.status == Status.CANCELLED) return Result(current)
            if (current.status != Status.RUNNING) return Result(current, current.status == Status.WAITING_CONFIRMATION,
                current.plan.steps.getOrNull(current.nextIndex)?.tool?.name)
            if (current.nextIndex >= current.plan.steps.size) {
                val completed = current.copy(status = Status.COMPLETED,
                    events = current.events + Event(current.nextIndex, Status.COMPLETED, "Agent goal completed."))
                synchronized(this) { if (state?.status != Status.CANCELLED) state = completed }
                return Result(synchronized(this) { state ?: completed })
            }
            val step = current.plan.steps[current.nextIndex]
            if (step.requiresConfirmation) {
                val waiting = current.copy(status = Status.WAITING_CONFIRMATION,
                    events = current.events + Event(current.nextIndex, Status.WAITING_CONFIRMATION, "Confirmation required for ${step.tool.name}."))
                synchronized(this) {
                    if (state?.status == Status.CANCELLED) return Result(state!!)
                    state = waiting
                }
                return Result(waiting, true, step.tool.name)
            }
            var attempt = 0
            var output: String? = null
            while (attempt <= MAX_RETRIES_PER_STEP && output == null) {
                if (synchronized(this) { state?.status == Status.CANCELLED }) return Result(synchronized(this) { state!! })
                attempt++
                output = try { executor(step) } catch (_: Exception) { null }
                if (output == null && attempt <= MAX_RETRIES_PER_STEP) {
                    synchronized(this) {
                        val latest = state
                        if (latest?.status == Status.CANCELLED) return Result(latest)
                        if (latest != null) state = latest.copy(retries = attempt,
                            events = latest.events + Event(current.nextIndex, Status.RUNNING, "Retrying ${step.tool.name} ($attempt/$MAX_RETRIES_PER_STEP)."))
                    }
                }
            }
            synchronized(this) {
                val latest = state ?: current
                if (latest.status == Status.CANCELLED) return Result(latest)
                if (output == null) {
                    val failed = latest.copy(status = Status.FAILED,
                        events = latest.events + Event(latest.nextIndex, Status.FAILED, "${step.tool.name} failed after retries."))
                    state = failed
                    return Result(failed)
                }
                state = latest.copy(nextIndex = latest.nextIndex + 1, retries = 0,
                    events = latest.events + Event(latest.nextIndex, Status.RUNNING, output.take(240)))
            }
        }
    }
}
