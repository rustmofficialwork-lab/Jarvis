package com.maxassistant.app

import android.content.Context
import java.io.File

/** Small bounded encrypted file store; avoids putting a growing transcript in SharedPreferences. */
class HistoryStore(context: Context) {
    private val file = File(context.filesDir, "history.v2.enc")

    fun read(): String {
        if (!file.exists()) return "[]"
        return runCatching { SecureVault.decrypt(file.readText(Charsets.UTF_8)).ifBlank { "[]" } }
            .getOrDefault("[]")
    }

    fun write(json: String) {
        val payload = SecureVault.encrypt(json)
        val tmp = File(file.parentFile, "${file.name}.tmp")
        tmp.writeText(payload, Charsets.UTF_8)
        if (!tmp.renameTo(file)) {
            file.writeText(payload, Charsets.UTF_8)
            tmp.delete()
        }
    }

    fun clear() {
        file.delete()
    }
}
