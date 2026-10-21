package com.jarvisassistant.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat

/** Single source of truth for the user-facing "What can you do?" response. */
object JarvisCapabilities {
    fun describe(context: Context): String {
        val mic = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        val camera = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        val accessibility = JarvisAccessibilityService.active != null
        val admin = (context.getSystemService(Context.DEVICE_POLICY_SERVICE) as android.app.admin.DevicePolicyManager)
            .isAdminActive(android.content.ComponentName(context, JarvisDeviceAdminReceiver::class.java))

        return buildString {
            append("I can currently:\n")
            append("✓ Answer questions and use the configured AI provider\n")
            append("✓ Search current web information and show sources\n")
            append("✓ Use temporary in-session conversation context, encrypted long-term memory and local tasks\n")
            append("✓ Set alarms/reminders, maintain local tasks, and open Calendar, Maps, Camera, Email, Drive, YouTube, Spotify, WhatsApp and Telegram\n")
            append("✓ Control supported phone settings, volume, media, brightness, clipboard and flashlight\n")
            append("✓ Open installed apps and use supported Accessibility actions\n✓ Read recent notifications after explicit Notification Access approval\n✓ Capture Android 11+ screenshots after explicit Accessibility approval")
            if (mic) append("\n✓ Use voice input")
            if (accessibility) append("\n✓ Read the currently focused UI text through Accessibility")
            if (admin) append("\n✓ Lock the phone with the enabled device-admin permission")
            if (!camera) append("\n\nCamera/flashlight control: permission not currently granted")
            append("\n\nI cannot currently:\n")
            append("✗ Send WhatsApp messages automatically\n")
            append("✗ Make purchases or money transfers\n")
            append("✗ Perform unrestricted background device control\n")
            append("✗ Run unrestricted security scans or exploit tests")
            append("\n\n✓ Use a priority engine for proactive battery/calendar alerts")
            append("\n✓ Use a local agent planner that decomposes multi-step goals into safe tools")
            append("\n✓ Require confirmation before high-risk phone, SMS, payment-like or external-control actions")
        }
    }
}
