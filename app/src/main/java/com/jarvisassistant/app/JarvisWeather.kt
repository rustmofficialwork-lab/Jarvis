package com.jarvisassistant.app

import android.net.Uri
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

/** Live weather via Open-Meteo's public geocoding and forecast APIs (no API key required). */
object JarvisWeather {
    fun answer(prompt: String, cancelled: () -> Boolean = { false }): String {
        val city = extractCity(prompt)
            ?: return "Weather ke liye city ka naam batayein, jaise: 'weather in Bhopal'."
        return try {
            val geoUrl = URL("https://geocoding-api.open-meteo.com/v1/search?name=${Uri.encode(city)}&count=1&language=en&format=json")
            val geo = getJson(geoUrl, cancelled)
            val place = geo.optJSONArray("results")?.optJSONObject(0)
                ?: return "Mujhe '$city' nahi mila. City ka naam dobara check karein."
            val latitude = place.optDouble("latitude", Double.NaN)
            val longitude = place.optDouble("longitude", Double.NaN)
            if (!latitude.isFinite() || !longitude.isFinite()) return "'$city' ke coordinates nahi mile."
            val name = place.optString("name", city)
            val region = listOf(place.optString("admin1"), place.optString("country")).filter { it.isNotBlank() }.joinToString(", ")
            val forecastUrl = URL("https://api.open-meteo.com/v1/forecast?latitude=$latitude&longitude=$longitude&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m&timezone=auto")
            val forecast = getJson(forecastUrl, cancelled)
            val current = forecast.optJSONObject("current") ?: return "Weather provider ne current weather nahi diya."
            val units = forecast.optJSONObject("current_units")
            val temp = current.optDouble("temperature_2m", Double.NaN)
            val feels = current.optDouble("apparent_temperature", Double.NaN)
            val humidity = current.optInt("relative_humidity_2m", -1)
            val wind = current.optDouble("wind_speed_10m", Double.NaN)
            val rain = current.optDouble("precipitation", Double.NaN)
            val code = current.optInt("weather_code", -1)
            buildString {
                append("Current weather in ").append(name)
                if (region.isNotBlank()) append(", ").append(region)
                append(": ").append(weatherDescription(code)).append(".")
                if (temp.isFinite()) append(" Temperature ").append(temp).append(units?.optString("temperature_2m", "°C") ?: "°C").append(".")
                if (feels.isFinite()) append(" Feels like ").append(feels).append(units?.optString("apparent_temperature", "°C") ?: "°C").append(".")
                if (humidity >= 0) append(" Humidity ").append(humidity).append("%.")
                if (wind.isFinite()) append(" Wind ").append(wind).append(" ").append(units?.optString("wind_speed_10m", "km/h") ?: "km/h").append(".")
                if (rain.isFinite()) append(" Precipitation ").append(rain).append(" mm.")
                append("\nSource: Open-Meteo (live API).")
            }
        } catch (_: java.util.concurrent.CancellationException) {
            "Weather request cancelled."
        } catch (e: Exception) {
            "Live weather abhi nahi mil paaya (${e.message ?: "network error"}). Internet check karke dobara try karein."
        }
    }

    fun extractCity(prompt: String): String? {
        // Avoid treating generic questions as city names (e.g. "what is the weather today").
        val normalized = prompt.trim().replace(Regex("\\s+"), " ")
        if (Regex("(?i)^(?:what is|what's|tell me|how is|how's)\\s+(?:the\\s+)?(?:weather|forecast|mausam)(?:\\s+(?:today|now|currently|right now))?[?.! ]*$").matches(normalized)) return null
        val match = Regex("(?i)\\b(?:weather|forecast|mausam|मौसम)(?:\\s+(?:today|now|ka|ki|for))?\\s+(?:in|at|for|of)\\s+([\\p{L}][\\p{L} .'-]{1,60})").find(prompt)
            ?: Regex("(?i)\\b(?:in|at)\\s+([\\p{L}][\\p{L} .'-]{1,60})\\s+(?:weather|forecast|mausam|मौसम)").find(prompt)
            ?: Regex("(?i)^\\s*([\\p{L}][\\p{L} .'-]{1,50}?)\\s+(?:ka|ki|mein)\\s+(?:weather|forecast|mausam|मौसम)(?:\\s+(?:batao|bataiye|today|now|kya hai))?[?.! ]*$").find(prompt)
            ?: Regex("(?i)^\\s*([\\p{L}][\\p{L} .'-]{1,50}?)\\s+(?:weather|forecast|mausam|मौसम)(?:\\s+(?:batao|bataiye|today|now|kya hai))?[?.! ]*$").find(prompt)
        return match?.groupValues?.get(1)?.trim()?.trimEnd('?', '.', '!')
            ?.replace(Regex("(?i)\\s+(today|tomorrow|now|currently|right now|batao|bataiye|kya hai)$"), "")
            ?.takeIf { it.isNotBlank() }
    }

    private fun getJson(url: URL, cancelled: () -> Boolean): JSONObject {
        if (cancelled()) throw java.util.concurrent.CancellationException()
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8_000
            readTimeout = 10_000
            setRequestProperty("User-Agent", "JARVIS-Android/1.0")
            setRequestProperty("Accept", "application/json")
        }
        try {
            val status = connection.responseCode
            if (status !in 200..299) throw IllegalStateException("weather provider HTTP $status")
            if (cancelled()) throw java.util.concurrent.CancellationException()
            return JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
        } finally { connection.disconnect() }
    }

    private fun weatherDescription(code: Int): String = when (code) {
        0 -> "Clear sky"
        1 -> "Mainly clear"
        2 -> "Partly cloudy"
        3 -> "Overcast"
        45, 48 -> "Foggy"
        51, 53, 55 -> "Drizzle"
        56, 57 -> "Freezing drizzle"
        61, 63, 65 -> "Rain"
        66, 67 -> "Freezing rain"
        71, 73, 75, 77 -> "Snow"
        80, 81, 82 -> "Rain showers"
        85, 86 -> "Snow showers"
        95 -> "Thunderstorm"
        96, 99 -> "Thunderstorm with hail"
        else -> "Conditions unavailable"
    }
}
