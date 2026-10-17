package com.jarvisassistant.app

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * App-private authenticated encryption backed by a non-exportable Android Keystore key.
 * The encrypted values can be copied from preferences, but cannot be decrypted off-device
 * without the key held by this installation's Keystore.
 *
 * ⚠️ MIGRATION NOTE: If you are upgrading from the old "maxx.local-data.v1" alias,
 * existing encrypted data will be unreadable. Either:
 *   (a) Bump the alias and force a fresh install (recommended for a rename release), or
 *   (b) Keep the old alias for one release to allow lazy re-encryption.
 */
object SecureVault {
    private const val STORE = "AndroidKeyStore"
    // ✅ RENAMED: "maxx.local-data.v1" → "jarvis.local-data.v1"
    private const val KEY_ALIAS = "jarvis.local-data.v1"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"

    @Synchronized
    fun encrypt(plainText: String): String {
        if (plainText.isEmpty()) return ""
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val encrypted = cipher.doFinal(plainText.toByteArray(Charsets.UTF_8))
        val payload = cipher.iv + encrypted
        return Base64.encodeToString(payload, Base64.NO_WRAP)
    }

    @Synchronized
    fun decrypt(encoded: String): String {
        if (encoded.isEmpty()) return ""
        return try {
            val payload = Base64.decode(encoded, Base64.NO_WRAP)
            require(payload.size > 12) { "Invalid encrypted payload" }
            val iv = payload.copyOfRange(0, 12)
            val ciphertext = payload.copyOfRange(12, payload.size)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, iv))
            String(cipher.doFinal(ciphertext), Charsets.UTF_8)
        } catch (_: Exception) {
            ""
        }
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance(STORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, STORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }
}
