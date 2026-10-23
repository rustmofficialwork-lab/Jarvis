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

    // 1. Focused Text padhna
    fun readFocusedText(): String {
        val node = rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        return node?.text?.toString().orEmpty().take(2000)
    }

    // 2. NAYA: Poori screen ka text padhna (AI ko context dene ke liye)
    fun readScreenContent(): String {
        val root = rootInActiveWindow ?: return ""
        val sb = StringBuilder()
        traverseNode(root, sb)
        return sb.toString().trim().take(4000)
    }

    private fun traverseNode(node: AccessibilityNodeInfo?, sb: StringBuilder) {
        if (node == null) return
        if (!node.text.isNullOrBlank()) {
            sb.append(node.text).append("\n")
        }
        for (i in 0 until node.childCount) {
            traverseNode(node.getChild(i), sb)
        }
    }

    // 3. NAYA: Text ke naam par click karna
    fun clickByText(targetText: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val nodes = root.findAccessibilityNodeInfosByText(targetText)
        
        for (node in nodes) {
            if (node.isClickable) {
                return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            } else {
                // Agar node clickable nahi hai, toh uske parent ko check karo
                var parent = node.parent
                while (parent != null) {
                    if (parent.isClickable) {
                        return parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    }
                    parent = parent.parent
                }
            }
        }
        return false
    }

    // 4. Screenshot lena
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

    // 5. UPDATED: Naye Global Actions add kiye hain
    fun performCommand(command: String, x: Float = 0f, y: Float = 0f, text: String = ""): Boolean {
        return when (command) {
            "back" -> performGlobalAction(GLOBAL_ACTION_BACK)
            "home" -> performGlobalAction(GLOBAL_ACTION_HOME)
            "recents" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
            "notifications" -> performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
            "power-menu" -> performGlobalAction(GLOBAL_ACTION_POWER_DIALOG)
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

    fun performTap(x: Float, y: Float) {
        performCommand("tap", x, y)
    }

    fun inputText(text: String) {
        performCommand("type", text = text)
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
