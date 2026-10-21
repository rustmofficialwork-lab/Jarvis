package com.jarvisassistant.app

import android.content.Context
import java.io.File

/** One-time cleanup helper for transcripts written by older app versions. */
class HistoryStore(context: Context) {
    private val file = File(context.filesDir, "history.v2.enc")
    fun clear() { file.delete() }
}
