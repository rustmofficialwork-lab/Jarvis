# JARVIS feature status and required setup

## Implemented in this revision
- Live weather lookup through Open-Meteo geocoding + current conditions APIs; no API key required. The user must name a city (for example, `weather in Bhopal`).
- Weather requests are handled in the background worker, with cancellation, connection/read timeouts, HTTP status checks, and clear error messages.
- Chat transcripts are session-only. Startup removes the old encrypted transcript file and the legacy `history` preference; long-term user-approved memory remains separate.
- Unit tests added for common weather-city extraction prompts.

## Requires external setup or device testing
- Gmail / Google Calendar / Contacts / Drive OAuth: needs a registered OAuth client, consent configuration, and secure token lifecycle. Do not hardcode client secrets or claim an account is connected before authorization succeeds.
- Smart-home control: needs a chosen provider (for example Home Assistant or Matter ecosystem), endpoint, pairing/credentials, and explicit confirmation rules. No generic API can control arbitrary devices.
- Fully offline generative AI: needs a selected on-device model, license review, model asset download, device RAM/storage checks, and an inference runtime. Current offline support is basic local commands, not a complete offline LLM.
- Dedicated low-power wake-word detection: current wake listener uses Android speech recognition and may rely on OS/network speech services; it is not a dedicated always-on wake-word model.

## Verification limitation
The Gradle wrapper could not download Gradle 8.7 in this environment because DNS/network access to services.gradle.org was unavailable. Therefore, this source package is not represented as a verified APK build. Run `./gradlew testDebugUnitTest assembleDebug` on a machine with Android SDK and network access to verify compilation and tests.


## Follow-up hardening applied in this patch
- Long-term memory context is now query-aware: `JarvisMemoryManager.contextFor()` ranks saved items by overlap with the current request and sends only a bounded subset to the AI provider. If there is no match, it sends only a small recent subset rather than the entire memory vault.
- `MainActivity` now uses `contextFor(prompt)` for provider context, reducing unnecessary personal-data disclosure and prompt size.
- Added common Hinglish aliases for remembering information, setting reminders, opening common apps, and starting web search.
- Replaced a mislabeled test source: `CommandNormalizerTest.kt` previously contained a duplicate `SecureVault` object, which would conflict with the main source set. It now contains actual command-normalization unit tests.
- Marked the Gradle wrapper script executable for normal Unix/Linux usage.

## Still incomplete / requires credentials or real-device validation
- The AI API is configurable, but requires a valid HTTPS endpoint, model name, and provider API key entered by the user. No free unlimited AI API is bundled.
- Current web research uses DuckDuckGo Instant Answer API, which is not a full general-purpose search engine; coverage may be sparse. A dedicated search provider is a future integration.
- The integrations hub opens provider pages and tracks in-memory status; it does not complete OAuth or connect accounts. The `CONNECTED` status must only be set after real auth is implemented.
- Long-term memory is encrypted in app-private preferences, but a device backup/migration strategy and robust per-memory editing UX need further work.
- Full offline generative AI and dedicated low-power wake-word detection are not implemented.
- The patch has not been verified by Gradle compilation or on-device tests because Gradle 8.7 cannot be downloaded in this network-restricted environment.
