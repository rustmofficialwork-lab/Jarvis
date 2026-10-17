package com.jarvisassistant.app

/** Central tool taxonomy and safety metadata used by the agent layer. */
object JarvisToolSystem {
    enum class Tool(val risk: Risk, val requiresNetwork: Boolean = false) {
        WEB_RESEARCH(Risk.LOW, true), CALCULATOR(Risk.LOW), WEATHER(Risk.LOW, true), MAPS(Risk.MEDIUM),
        CALENDAR(Risk.MEDIUM), REMINDER(Risk.MEDIUM), CONTACTS(Risk.MEDIUM), EMAIL(Risk.MEDIUM),
        FILES(Risk.MEDIUM), DRIVE(Risk.MEDIUM, true), YOUTUBE(Risk.LOW, true), SPOTIFY(Risk.LOW, true), WHATSAPP(Risk.MEDIUM), TELEGRAM(Risk.MEDIUM), CAMERA(Risk.MEDIUM), SCREEN(Risk.MEDIUM), APP_LAUNCH(Risk.LOW),
        PHONE(Risk.HIGH), SMS(Risk.HIGH), SMART_HOME(Risk.HIGH), SETTINGS(Risk.MEDIUM)
    }
    enum class Risk { LOW, MEDIUM, HIGH }

    fun needsConfirmation(tool: Tool): Boolean = tool.risk == Risk.HIGH

    fun describe(tool: Tool): String = when (tool) {
        Tool.WEB_RESEARCH -> "Current web research with retrieved sources"
        Tool.CALCULATOR -> "Local arithmetic evaluation"
        Tool.WEATHER -> "Current weather lookup"
        Tool.MAPS -> "Open maps/navigation"
        Tool.CALENDAR -> "Calendar read/open actions"
        Tool.REMINDER -> "Android reminder/alarm flow"
        Tool.CONTACTS -> "Contact lookup or selection"
        Tool.EMAIL -> "Open an email composer"
        Tool.FILES -> "Local file operations"
        Tool.DRIVE -> "Open Google Drive / Drive web"
        Tool.YOUTUBE -> "Open YouTube"
        Tool.SPOTIFY -> "Open Spotify"
        Tool.WHATSAPP -> "Open WhatsApp chat/share flow"
        Tool.TELEGRAM -> "Open Telegram chat/share flow"
        Tool.CAMERA -> "Open camera/capture flow"
        Tool.SCREEN -> "Supported screen/accessibility actions"
        Tool.APP_LAUNCH -> "Launch an installed app"
        Tool.PHONE -> "Phone call flow — confirmation required"
        Tool.SMS -> "SMS/message flow — confirmation required"
        Tool.SMART_HOME -> "External smart-home control — confirmation required"
        Tool.SETTINGS -> "Android settings flow"
    }
}
