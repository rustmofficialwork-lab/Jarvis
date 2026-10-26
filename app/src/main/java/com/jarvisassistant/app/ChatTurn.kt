
package com.jarvisassistant.app

data class ChatTurn(
    val prompt: String,
    val reply: String,
    val attachments: List<String> = emptyList()
)
