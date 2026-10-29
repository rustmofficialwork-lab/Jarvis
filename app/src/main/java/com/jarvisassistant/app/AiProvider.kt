
package com.jarvisassistant.app

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object AiProvider {

    private const val SYSTEM_PROMPT = """
You are J.A.R.V.I.S., the user's personal AI butler, in the style of the Marvel films.
Address the user as "Sir". Tone: calm, polished, British, with subtle dry wit.
Support Hindi, English, and Hinglish. Match the exact language and script/style used in the latest user message; never default to English if the user speaks Hindi or Hinglish.
Replies are spoken aloud: keep them to 1-3 short sentences unless asked for detail, no markdown, lists or emojis.
Use crisp status lines like "Right away, Sir." or "Done, Sir." only for things that really happened.
Never claim an action succeeded unless it did; if something cannot be done, say so plainly and suggest an alternative.
"""

    fun answer(
        endpoint: String,
        model: String,
        apiKey: String,
        prompt: String,
        history: List<ChatTurn>,
        extraContext: String,
        attachments: List<String>,
        useSearch: Boolean,
        useVision: Boolean,
        useTools: Boolean,
        isCancelled: () -> Boolean
    ): String {

        require(apiKey.isNotBlank()) { "API key is missing." }
        val parsedEndpoint = try { URL(endpoint) } catch (_: Exception) {
            throw IllegalArgumentException("Endpoint URL is invalid.")
        }
        require(parsedEndpoint.protocol.equals("https", ignoreCase = true) &&
            !parsedEndpoint.host.isNullOrBlank() &&
            parsedEndpoint.userInfo == null) {
            "Endpoint must be a valid HTTPS URL without embedded credentials."
        }
        require(model.isNotBlank()) { "Model name is missing." }

        if (isCancelled()) {
            throw InterruptedException("Request cancelled.")
        }

        val messages = JSONArray()

        messages.put(
            JSONObject()
                .put("role", "system")
                .put("content", SYSTEM_PROMPT)
        )
        messages.put(
            JSONObject()
                .put("role", "system")
                .put("content", "Language policy for this turn: ${JarvisLanguage.aiInstruction(prompt)} Follow it throughout the answer.")
        )

        if (extraContext.isNotBlank()) {
            messages.put(
                JSONObject()
                    .put("role", "system")
                    .put("content", extraContext)
            )
        }

        if (useSearch) {
            val sources = try {
                InternetResearch.search(prompt)
            } catch (_: Exception) {
                emptyList()
            }

            if (sources.isNotEmpty()) {
                val researchText = buildString {
                    appendLine("Search results (verify claims against sources):")
                    sources.forEachIndexed { index, source ->
                        appendLine("${index + 1}. ${source.title}")
                        appendLine("URL: ${source.url}")
                        appendLine(source.excerpt)
                        appendLine()
                    }
                }

                messages.put(
                    JSONObject()
                        .put("role", "system")
                        .put("content", researchText)
                )
            }
        }

        history.takeLast(20).forEach { turn ->
            messages.put(
                JSONObject()
                    .put("role", "user")
                    .put("content", turn.prompt)
            )
            messages.put(
                JSONObject()
                    .put("role", "assistant")
                    .put("content", turn.reply)
            )
        }

        // Image attachments are in-memory data URLs produced by ImageVision.
        // Other attachment strings remain plain-text references; never imply they were read.
        val imageAttachments = attachments.filter { it.startsWith("data:image/") }.take(2)
        val textAttachments = attachments.filterNot { it.startsWith("data:image/") }
        val finalPrompt = buildString {
            append(prompt)

            if (textAttachments.isNotEmpty()) {
                appendLine()
                appendLine()
                appendLine("Attachment references supplied by the app:")
                textAttachments.forEachIndexed { index, attachment ->
                    appendLine("${index + 1}. $attachment")
                }
                appendLine("If an attachment's contents are not included, do not pretend you have read them.")
            }

            if (useVision && imageAttachments.isEmpty()) {
                appendLine()
                append("No image data was attached to this request. Ask the user to select an image rather than guessing.")
            }

            if (useTools) {
                appendLine()
                append("Do not claim to have executed app tools unless the app actually executed them.")
            }
        }

        val userMessage = JSONObject().put("role", "user")
        if (imageAttachments.isNotEmpty()) {
            val multimodalContent = JSONArray()
            multimodalContent.put(JSONObject().put("type", "text").put("text", finalPrompt))
            imageAttachments.forEach { imageDataUrl ->
                multimodalContent.put(
                    JSONObject()
                        .put("type", "image_url")
                        .put("image_url", JSONObject().put("url", imageDataUrl))
                )
            }
            userMessage.put("content", multimodalContent)
        } else {
            userMessage.put("content", finalPrompt)
        }
        messages.put(userMessage)

        if (isCancelled()) {
            throw InterruptedException("Request cancelled.")
        }

        val connection =
            URL(endpoint).openConnection() as HttpURLConnection

        try {
            connection.requestMethod = "POST"
            // Never forward an Authorization header through an untrusted redirect.
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 20000
            connection.readTimeout = 60000
            connection.doOutput = true

            connection.setRequestProperty(
                "Authorization",
                "Bearer $apiKey"
            )
            connection.setRequestProperty(
                "Content-Type",
                "application/json"
            )

            val body = JSONObject()
                .put("model", model)
                .put("messages", messages)
                .put("temperature", 0.7)
                .put("stream", false)

            connection.outputStream.use { output ->
                output.write(
                    body.toString().toByteArray(Charsets.UTF_8)
                )
            }

            if (isCancelled()) {
                throw InterruptedException("Request cancelled.")
            }

            val status = connection.responseCode
            val stream = if (status in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream
            }

            val response = stream?.bufferedReader()?.use {
                it.readText()
            }.orEmpty()

            if (status in 300..399) {
                throw IllegalStateException("API endpoint redirected the request; redirects are blocked for credential safety.")
            }
            if (status !in 200..299) {
                val errorMessage = try {
                    JSONObject(response)
                        .optJSONObject("error")
                        ?.optString("message")
                } catch (_: Exception) {
                    null
                }

                throw IllegalStateException(
                    "API error $status: " +
                    (errorMessage?.takeIf { it.isNotBlank() }
                        ?: response.take(250))
                )
            }

            val content = JSONObject(response)
                .getJSONArray("choices")
                .getJSONObject(0)
                .getJSONObject("message")
                .optString("content")
                .trim()

            if (content.isBlank()) {
                throw IllegalStateException(
                    "AI returned an empty response."
                )
            }

            return content
        } finally {
            connection.disconnect()
        }
    }
}
