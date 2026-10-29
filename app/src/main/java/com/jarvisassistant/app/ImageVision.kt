package com.jarvisassistant.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Base64
import java.io.ByteArrayOutputStream

/**
 * Converts a user-selected image to a bounded JPEG data URL for vision-capable
 * OpenAI-compatible APIs. The image stays in memory and is not saved to disk.
 */
object ImageVision {
    private const val MAX_EDGE = 1280
    private const val JPEG_QUALITY = 82

    fun encode(context: Context, uri: Uri): String {
        val resolver = context.contentResolver
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
            ?: throw IllegalArgumentException("Could not open the selected image.")
        require(bounds.outWidth > 0 && bounds.outHeight > 0) { "The selected file is not a supported image." }

        var sample = 1
        while (bounds.outWidth / sample > MAX_EDGE * 2 || bounds.outHeight / sample > MAX_EDGE * 2) {
            sample *= 2
        }
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        val decoded = resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
            ?: throw IllegalArgumentException("Could not decode the selected image.")

        val bitmap = if (decoded.width > MAX_EDGE || decoded.height > MAX_EDGE) {
            val ratio = minOf(MAX_EDGE.toFloat() / decoded.width, MAX_EDGE.toFloat() / decoded.height)
            Bitmap.createScaledBitmap(
                decoded,
                (decoded.width * ratio).toInt().coerceAtLeast(1),
                (decoded.height * ratio).toInt().coerceAtLeast(1),
                true
            ).also { if (it !== decoded) decoded.recycle() }
        } else decoded

        val bytes = ByteArrayOutputStream().use { output ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, output)
            output.toByteArray()
        }
        if (bitmap !== decoded) bitmap.recycle() else decoded.recycle()
        require(bytes.isNotEmpty()) { "Could not prepare the selected image." }
        require(bytes.size <= 2_000_000) { "Image is too large after compression. Choose a smaller image." }
        return "data:image/jpeg;base64," + Base64.encodeToString(bytes, Base64.NO_WRAP)
    }
}
