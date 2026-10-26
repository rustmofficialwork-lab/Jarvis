package com.jarvisassistant.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class JarvisWeatherTest {
    @Test fun extractsCityFromCommonEnglishPrompts() {
        assertEquals("Bhopal", JarvisWeather.extractCity("weather in Bhopal"))
        assertEquals("New Delhi", JarvisWeather.extractCity("what is the weather in New Delhi today?"))
        assertEquals("Mumbai", JarvisWeather.extractCity("forecast for Mumbai"))
        assertEquals("Bhopal", JarvisWeather.extractCity("Bhopal ka mausam batao"))
        assertEquals("Delhi", JarvisWeather.extractCity("Delhi weather"))
    }

    @Test fun asksForCityWhenMissing() {
        assertNull(JarvisWeather.extractCity("what is the weather today"))
    }
}
