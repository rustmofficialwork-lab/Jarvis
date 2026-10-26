<<<<<<< HEAD
# Jarvis
=======
# 🤖 JARVIS - AI Android Assistant

**JARVIS** is an advanced, proactive AI assistant built natively for Android using Kotlin. It is designed to act as an intelligent agent that can listen, see, plan, and execute tasks seamlessly on your device.

> **Version:** 5.0.0 (Rebrand Release)

## ✨ Key Features

Based on the modular architecture, JARVIS includes:

*   🎙️ **Voice Engine:** Advanced speech recognition and command normalization (`JarvisVoiceEngine.kt`).
*   👁️ **Vision Engine:** Visual context understanding and image processing (`JarvisVisionEngine.kt`).
*   🧠 **Agent Runtime & Context:** Intelligent decision-making using memory and context engines (`JarvisAgentRuntime.kt`, `JarvisContextEngine.kt`).
*   ⚡ **Proactive Planner:** Anticipates user needs and schedules tasks (`JarvisProactivePlanner.kt`).
*   ♿ **Accessibility Service:** Deep system integration to automate tasks across the UI (`JarvisAccessibilityService.kt`).
*   🔐 **Security Center:** Built-in cybersecurity audits and secure data storage (`CybersecurityAudit.kt`, `SecureVault.kt`).
*   🛠️ **Tool System & Integration:** Extendable architecture to connect with other services (`JarvisToolSystem`).

## 📂 Project Structure

The project follows standard Android Gradle conventions:
```text
app/src/main/java/com/jarvisassistant.app/  -> Main Kotlin Source Code
app/src/main/res/                           -> XML Layouts, Strings, Configs
app/src/test/java/com/jarvisassistant.app/  -> Unit Tests for Engines & Runtimes

## Autonomous agent flow

The app now routes explicit agent requests and multi-tool goals through `JarvisAgent` -> `JarvisAgentRuntime` -> `JarvisAgentExecutor`. The runtime is bounded to 8 steps, retries null/failed tool results, pauses at tools marked for confirmation, and supports `confirm` / `cancel agent` in the main chat. Research and weather tools return real provider output; calculator uses the offline command engine; other registered Android actions are delegated to the shared command router only after any required confirmation. Tool results that cannot be obtained are reported as failures rather than successful execution.

Examples: `agent research latest Android security and weather in Gwalior`, `plan and execute research about solar energy`, or `research ... and weather in Bhopal`. Sensitive operations may ask for `confirm`; say `cancel agent` to abort. Agent orchestration is implemented, but Android build/device tests must be run in Android Studio before treating it as release-ready.


### Connectivity and language behavior
- The main HUD shows a live `ONLINE` / `OFFLINE` indicator based on Android's validated network connection.
- Local commands and basic calculations continue to work without internet; AI fallback is only attempted while online.
- AI prompts include a per-turn language instruction for Hindi (Devanagari), English, or Hinglish (Roman script), based on the user's message.
- Common offline replies and spoken output follow the detected user language when the device has the corresponding text-to-speech voice installed.


## Final validation notes

- Network status uses Android's validated active network; online-dependent research and weather agent steps fail safely when offline.
- Agent execution preserves ordered plan steps, requires confirmation for configured high-impact tools, treats common router permission/error responses as failures, and allows cancellation state to be updated while a tool is running.
- AI replies receive an explicit per-turn Hindi, English, or Hinglish language instruction. Deterministic offline replies are localized for supported common commands; this is not a full offline translation model.
- General AI responses still require internet connectivity and a valid provider endpoint/API key. Android speech recognition and TTS language availability depend on installed device language packs.
- Build/test status: source-level checks and ZIP/XML integrity checks are performed in this environment. A full Gradle Android build and JUnit run require downloading Gradle 8.7 and Android dependencies; if the build host has no network, those checks cannot complete here. Do not treat the project as device-certified until built and tested on an Android device.
>>>>>>> 5b258fd (Initial commit)
