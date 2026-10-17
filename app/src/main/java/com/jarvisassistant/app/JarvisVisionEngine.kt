package com.jarvisassistant.app

import android.content.Context
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.util.concurrent.atomic.AtomicBoolean

/** Local vision pipeline: image selection/capture + on-device OCR. */
object JarvisVisionEngine {
    data class OcrResult(val text: String, val blocks: Int)

    fun recognizeText(context: Context, uri: Uri, onResult: (Result<OcrResult>) -> Unit) {
        val finished = AtomicBoolean(false)
        try {
            val image = InputImage.fromFilePath(context, uri)
            val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
            recognizer.process(image)
                .addOnSuccessListener { result ->
                    if (finished.compareAndSet(false, true)) {
                        onResult(Result.success(OcrResult(result.text.trim(), result.textBlocks.size)))
                    }
                }
                .addOnFailureListener { error ->
                    if (finished.compareAndSet(false, true)) onResult(Result.failure(error))
                }
                .addOnCompleteListener { recognizer.close() }
        } catch (error: Exception) {
            if (finished.compareAndSet(false, true)) onResult(Result.failure(error))
        }
    }
}
