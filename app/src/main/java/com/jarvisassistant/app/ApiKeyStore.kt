package com.jarvisassistant.app

import android.content.Context

/** Stores provider credentials encrypted with the app's Android Keystore-backed vault. */
object ApiKeyStore {
    private const val PREFS = "jarvis_secure_settings"
    private const val KEY = "api_key_v1"
    private const val LEGACY_KEY = "api_key"

    @Synchronized
    fun get(context: Context): String {
        val securePrefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val encrypted = securePrefs.getString(KEY, null)
        if (encrypted != null) {
            val decrypted = SecureVault.decrypt(encrypted)
            // Never silently fall back to an old plaintext copy after a secure value exists.
            // A blank result can mean a damaged payload or a Keystore key invalidation.
            return decrypted
        }

        // One-time migration from the legacy plaintext preference.
        val legacyPrefs = context.getSharedPreferences("jarvis", Context.MODE_PRIVATE)
        val legacy = legacyPrefs.getString(LEGACY_KEY, "").orEmpty()
        if (legacy.isNotBlank()) {
            val encryptedValue = SecureVault.encrypt(legacy)
            val saved = securePrefs.edit().putString(KEY, encryptedValue).commit()
            if (saved) {
                // Remove plaintext only after encrypted storage has been durably committed.
                legacyPrefs.edit().remove(LEGACY_KEY).commit()
                return legacy
            }
            // Preserve the legacy value if migration could not be committed.
            return legacy
        }
        return ""
    }

    @Synchronized
    fun set(context: Context, value: String) {
        val securePrefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val editor = securePrefs.edit()
        if (value.isBlank()) editor.remove(KEY)
        else editor.putString(KEY, SecureVault.encrypt(value))
        check(editor.commit()) { "Could not save API key securely." }
        // Remove any old plaintext copy after encrypted storage succeeds.
        context.getSharedPreferences("jarvis", Context.MODE_PRIVATE)
            .edit().remove(LEGACY_KEY).apply()
    }
}
