package com.jarvisassistant.app

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.graphics.Bitmap
import android.os.Build
import java.io.File
import java.io.FileOutputStream
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * User-enabled, visible Android accessibility integration. It only reads the currently focused input text
 * when explicitly requested by the app and performs explicit commands requested by the user;
 * it does not continuously store screen content.
 */
class JarvisAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() {
        super.onServiceConnected()
        active = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit

    override fun onDestroy() {
        if (active === this) active = null
        super.onDestroy()
    }

    fun readFocusedText(): String {
        val node = rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        return node?.text?.toString().orEmpty().take(2000)
    }

    fun captureScreenshot(output: File, callback: (Boolean, File?) -> Unit) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) { callback(false, null); return }
        takeScreenshot(
            android.view.Display.DEFAULT_DISPLAY,
            mainExecutor,
            object : TakeScreenshotCallback {
                override fun onSuccess(result: ScreenshotResult) {
                    runCatching {
                        output.parentFile?.mkdirs()
                        FileOutputStream(output).use { stream ->
                            result.hardwareBuffer.let { buffer ->
                                val bitmap = Bitmap.wrapHardwareBuffer(buffer, result.colorSpace)
                                    ?: throw IllegalStateException("Screenshot bitmap unavailable")
                                bitmap.compress(Bitmap.CompressFormat.PNG, 90, stream)
                                bitmap.recycle()
                                buffer.close()
                            }
                        }
                    }.onSuccess { callback(true, output) }
                        .onFailure { callback(false, null) }
                }
                override fun onFailure(errorCode: Int) { callback(false, null) }
            }
        )
    }

    fun performCommand(command: String, x: Float = 0f, y: Float = 0f, text: String = ""): Boolean {
        return when (command) {
            "back" -> performGlobalAction(GLOBAL_ACTION_BACK)
            "home" -> performGlobalAction(GLOBAL_ACTION_HOME)
            "tap" -> dispatchTouch(x, y, x, y)
            "scroll-up" -> dispatchTouch(
                resources.displayMetrics.widthPixels / 2f,
                resources.displayMetrics.heightPixels * 0.78f,
                resources.displayMetrics.widthPixels / 2f,
                resources.displayMetrics.heightPixels * 0.28f
            )
            "scroll-down" -> dispatchTouch(
                resources.displayMetrics.widthPixels / 2f,
                resources.displayMetrics.heightPixels * 0.28f,
                resources.displayMetrics.widthPixels / 2f,
                resources.displayMetrics.heightPixels * 0.78f
            )
            "type" -> {
                val node = rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
                    ?: return false
                val args = Bundle().apply {
                    putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
                }
                node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
            }
            else -> false
        }
    }

    private fun dispatchTouch(x1: Float, y1: Float, x2: Float, y2: Float): Boolean {
        val path = Path().apply {
            moveTo(x1.coerceAtLeast(0f), y1.coerceAtLeast(0f))
            lineTo(x2.coerceAtLeast(0f), y2.coerceAtLeast(0f))
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, if (x1 == x2 && y1 == y2) 80 else 420))
            .build()
        return dispatchGesture(gesture, null, null)
    }

    companion object {
        @Volatile var active: JarvisAccessibilityService? = null
            private set
    }
}
