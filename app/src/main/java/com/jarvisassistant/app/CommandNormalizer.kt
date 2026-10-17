package com.jarvisassistant.app

import java.util.Locale

/** Normalizes common English/Hindi/Hinglish phrases into the existing command vocabulary. */
object CommandNormalizer {
    private val aliases = linkedMapOf(
        "समय क्या है" to "time",
        "अभी कितने बजे हैं" to "time",
        "अभी कितने बजे है" to "time",
        "date क्या है" to "date",
        "आज की तारीख" to "date",
        "समय बताओ" to "time",
        "तारीख बताओ" to "date",
        "आवाज़ बढ़ाओ" to "volume up",
        "आवाज बढ़ाओ" to "volume up",
        "volume badhao" to "volume up",
        "volume badha do" to "volume up",
        "आवाज़ कम करो" to "volume down",
        "आवाज कम करो" to "volume down",
        "volume kam karo" to "volume down",
        "volume kam kar do" to "volume down",
        "म्यूट करो" to "mute",
        "फ्लैशलाइट चालू करो" to "turn on flashlight",
        "flashlight chalao" to "turn on flashlight",
        "torch chalao" to "turn on flashlight",
        "फ्लैशलाइट बंद करो" to "turn off flashlight",
        "flashlight band karo" to "turn off flashlight",
        "wifi खोलो" to "open wifi",
        "वाईफाई खोलो" to "open wifi",
        "bluetooth खोलो" to "open bluetooth",
        "ब्लूटूथ खोलो" to "open bluetooth",
        "सेटिंग्स खोलो" to "open settings",
        "settings kholo" to "open settings",
        "घर जाओ" to "home",
        "वापस जाओ" to "back",
        "पीछे जाओ" to "back",
        "अगला गाना" to "next song",
        "अगला गाना चलाओ" to "next song",
        "पिछला गाना" to "previous song",
        "गाना चलाओ" to "play music",
        "गाना रोक दो" to "pause music",
        "पॉज़ करो" to "pause music",
        "बैटरी कितनी है" to "battery status",
        "बैटरी कितने प्रतिशत है" to "battery percentage",
        "बैकग्राउंड सुनना शुरू करो" to "start background listening",
        "बैकग्राउंड सुनना बंद करो" to "stop background listening",
        "कैलेंडर एक्सेस चालू करो" to "enable calendar context",
        "कैलेंडर एक्सेस ऑन करो" to "enable calendar context",
        "कैलेंडर कॉन्टेक्स्ट चालू करो" to "enable calendar context",
        "कैलेंडर एक्सेस बंद करो" to "disable calendar context",
        "कैलेंडर कॉन्टेक्स्ट बंद करो" to "disable calendar context",
        "प्रोएक्टिव मोड बंद करो" to "proactive mode off",
        "प्रोएक्टिव मोड लो" to "proactive mode low",
        "प्रोएक्टिव मोड नॉर्मल" to "proactive mode normal",
        "प्रोएक्टिव मोड हाई" to "proactive mode high",
        "क्लिपबोर्ड पढ़ो" to "read clipboard",
        "क्लिपबोर्ड क्या है" to "read clipboard",
        "स्क्रीनशॉट लो" to "take screenshot",
        "नोटिफिकेशन पढ़ो" to "read notifications",
        "ब्राइटनेस 50" to "set brightness 50",
        "यादें दिखाओ" to "show memories",
        "तुम्हें क्या याद है" to "what do you remember",
        "याद में खोजो" to "search memory",
        "पसंद याद रखो" to "remember preference",
        "व्यक्ति याद रखो" to "remember person",
        "प्रोजेक्ट याद रखो" to "remember project",
        "सारी यादें मिटाओ" to "clear all memories",
        "एजेंट स्टेटस" to "agent status",
        "एजेंट कैंसल" to "agent cancel",
        "मदद करो" to "help",
        "कमांड बताओ" to "help",
        "क्या कर सकते हो" to "help",
        "सिस्टम हेल्थ" to "health",
        "डायग्नोस्टिक्स दिखाओ" to "diagnostics report",
        "नेटवर्क चेक करो" to "network status",
        "रिसोर्स स्टेटस" to "resource status",
        "परफॉर्मेंस चेक" to "performance status",
        "इंटीग्रेशन स्टेटस" to "integration status",
        "जॉब स्टेटस" to "agent status",
    )

    fun normalize(input: String, wakeWord: String = "JARVIS"): String {
        var value = input.trim().replace(Regex("\\s+"), " ")
        value = value.replace(Regex("(?i)^${Regex.escape(wakeWord.trim())}\\b\\s*[:,]?\\s*"), "")
        val lower = value.lowercase(Locale.ROOT)
        aliases.entries.firstOrNull { lower == it.key.lowercase(Locale.ROOT) }
            ?.let { return it.value }
        if (lower.startsWith("एजेंट चलाओ ") || lower.startsWith("एजेंट रन ")) {
            return "agent run " + value.substringAfter(' ').substringAfter(' ').trim().lowercase(Locale.ROOT)
        }
        if (lower.startsWith("एजेंट प्लान ")) {
            return "agent plan " + value.substringAfter(' ').trim().substringAfter(' ').trim().lowercase(Locale.ROOT)
        }
        return lower
    }
}
