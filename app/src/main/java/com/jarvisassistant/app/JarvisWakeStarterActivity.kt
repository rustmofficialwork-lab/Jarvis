package com.jarvisassistant.app

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.util.Log
import androidx.core.content.ContextCompat

/** No UI. Starts JarvisWakeService from a visible activity, then closes itself. */
class JarvisWakeStarterActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
            val intent = Intent(this, JarvisWakeService::class.java)
                .setAction(JarvisWakeService.ACTION_WAKE)
            ContextCompat.startForegroundService(this, intent)
        } catch (e: Exception) {
            Log.e("JarvisWakeStarter", "Could not start wake service", e)
        }
        finish()
    }
}
