package com.jarvisassistant.app

import android.content.Context

/** Vision entry points: camera capture, on-device OCR, and Accessibility-based UI text. */
object JarvisVision {
    fun openCamera(context: Context): Boolean = JarvisProductivity.openCamera(context)
    fun accessibilityAvailable(): Boolean = JarvisAccessibilityService.active != null
    fun currentFocusedText(): String = JarvisAccessibilityService.active?.readFocusedText().orEmpty()
    fun ocrAvailable(): Boolean = true
}
