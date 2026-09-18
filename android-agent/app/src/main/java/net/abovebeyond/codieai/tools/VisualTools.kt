package net.abovebeyond.codieai.tools

import android.content.Context
import android.graphics.BitmapFactory
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.label.ImageLabeling
import com.google.mlkit.vision.label.defaults.ImageLabelerOptions
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

object VisualTools {
    fun ocr(context: Context, name: String): String {
        val bitmap = decodeWorkspaceBitmap(context, name)
        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        try {
            val image = InputImage.fromBitmap(bitmap, 0)
            val latch = CountDownLatch(1)
            val result = AtomicReference<String>()
            val error = AtomicReference<Throwable>()

            recognizer.process(image)
                .addOnSuccessListener { text ->
                    result.set(text.text.ifBlank { "No text recognized." })
                    latch.countDown()
                }
                .addOnFailureListener {
                    error.set(it)
                    latch.countDown()
                }

            require(latch.await(30, TimeUnit.SECONDS)) { "OCR timed out" }
            error.get()?.let { throw it }
            return result.get().orEmpty().take(20_000)
        } finally {
            recognizer.close()
            bitmap.recycle()
        }
    }

    fun labels(context: Context, name: String): String {
        val bitmap = decodeWorkspaceBitmap(context, name)
        val labeler = ImageLabeling.getClient(
            ImageLabelerOptions.Builder()
                .setConfidenceThreshold(0.45f)
                .build()
        )

        try {
            val image = InputImage.fromBitmap(bitmap, 0)
            val latch = CountDownLatch(1)
            val result = AtomicReference<String>()
            val error = AtomicReference<Throwable>()

            labeler.process(image)
                .addOnSuccessListener { labels ->
                    val sorted = labels
                        .sortedByDescending { it.confidence }
                        .take(20)

                    result.set(
                        if (sorted.isEmpty()) {
                            "No image labels recognized."
                        } else {
                            buildString {
                                append("Image labels:")
                                sorted.forEach { label ->
                                    append("\n- ")
                                        .append(label.text)
                                        .append(" confidence=")
                                        .append(String.format("%.3f", label.confidence))
                                }
                            }
                        }
                    )
                    latch.countDown()
                }
                .addOnFailureListener {
                    error.set(it)
                    latch.countDown()
                }

            require(latch.await(30, TimeUnit.SECONDS)) { "Image labeling timed out" }
            error.get()?.let { throw it }
            return result.get().orEmpty()
        } finally {
            labeler.close()
            bitmap.recycle()
        }
    }

    private fun decodeWorkspaceBitmap(context: Context, name: String): android.graphics.Bitmap {
        val file = WorkspaceTools.file(context, name)
        require(file.isFile) { "Workspace image not found: " + name }
        require(file.length() <= 15_000_000L) { "Image file is too large" }

        val options = BitmapFactory.Options().apply {
            inPreferredConfig = android.graphics.Bitmap.Config.ARGB_8888
        }

        val bitmap = BitmapFactory.decodeFile(file.absolutePath, options)
            ?: throw IllegalArgumentException("Unsupported or invalid image file: " + name)

        val pixels = bitmap.width.toLong() * bitmap.height.toLong()
        require(pixels <= 20_000_000L) { "Image dimensions are too large" }
        return bitmap
    }
}
