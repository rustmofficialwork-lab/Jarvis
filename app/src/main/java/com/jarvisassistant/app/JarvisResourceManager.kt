package com.jarvisassistant.app

import android.app.ActivityManager
import android.content.Context
import android.os.Debug

/** Lightweight, deterministic resource guard for foreground JARVIS work. */
object JarvisResourceManager {
    enum class Pressure { NORMAL, MODERATE, CRITICAL }

    data class Snapshot(
        val pressure: Pressure,
        val availableMemoryMb: Long,
        val totalMemoryMb: Long,
        val lowMemory: Boolean,
        val maxConcurrentJobs: Int = 1
    )

    fun snapshot(context: Context): Snapshot {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
        val info = ActivityManager.MemoryInfo()
        am?.getMemoryInfo(info)
        val available = info.availMem.coerceAtLeast(0L) / (1024L * 1024L)
        val total = info.totalMem.coerceAtLeast(0L) / (1024L * 1024L)
        val pressure = when {
            info.lowMemory || available < 96L -> Pressure.CRITICAL
            available < 192L -> Pressure.MODERATE
            else -> Pressure.NORMAL
        }
        return Snapshot(pressure, available, total, info.lowMemory)
    }

    fun shouldDeferWork(context: Context): Boolean = snapshot(context).pressure == Pressure.CRITICAL

    fun safeRequestLimitChars(): Int = 12_000

    fun heapUsedMb(): Long = Debug.getNativeHeapAllocatedSize() / (1024L * 1024L)

    fun status(context: Context): String {
        val s = snapshot(context)
        return "Resources: pressure=${s.pressure.name.lowercase()}, availableMemory=${s.availableMemoryMb}MB, " +
            "totalMemory=${s.totalMemoryMb}MB, heap=${heapUsedMb()}MB, maxConcurrentJobs=${s.maxConcurrentJobs}."
    }
}
