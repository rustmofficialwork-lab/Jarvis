package com.jarvisassistant.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Pure model test for [JarvisTaskStore.Task].
 *
 * Note: The full store requires an Android [android.content.Context],
 * so pure JVM unit tests cover the data model only. End-to-end store
 * behavior is verified via instrumentation tests.
 */
class JarvisTaskStoreTest {
    @Test fun taskDefaultsAreSane() {
        val task = JarvisTaskStore.Task(id = 1L, text = "submit report")
        assertEquals(1L, task.id)
        assertEquals("submit report", task.text)
        assertNull(task.dueAt)
        assertFalse(task.done)
    }

    @Test fun completeFlipsDoneFlag() {
        val task = JarvisTaskStore.Task(id = 5L, text = "call mom", dueAt = null, done = false)
        val completed = task.copy(done = true)
        assertTrue(completed.done)
        assertEquals(5L, completed.id)
        assertEquals("call mom", completed.text)
    }

    @Test fun dueAtIsPreservedWhenProvided() {
        val dueAt = 1_700_000_000_000L
        val task = JarvisTaskStore.Task(id = 7L, text = "meeting", dueAt = dueAt, done = false)
        assertEquals(dueAt, task.dueAt)
    }
}
