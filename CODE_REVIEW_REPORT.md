# JARVIS source review report

Review date: 2026-10-18

## Checks completed
- ZIP archive integrity: passed (`unzip -t` / Python `ZipFile.testzip`).
- Android manifest resource references: all references checked by the static script resolved.
- XML files under `app/src/main`: parsed successfully.
- Legacy `MAXX` text scan in source/resources: no matches.
- TODO/FIXME scan in Kotlin sources: no matches.
- Confirmed that chat transcript data is kept in Activity memory for the current session, and old transcript keys/files are cleared during initialization; long-term memory remains a separate encrypted store.
- Reviewed weather API wiring and added common Hinglish city prompt patterns plus a unit label fix.

## Not verified
- Gradle unit tests and APK assembly could not run in this environment. `./gradlew --no-daemon testDebugUnitTest assembleDebug` stopped while downloading Gradle 8.7 because `services.gradle.org` could not be resolved (`UnknownHostException`).
- No Android device/emulator smoke test was available.
- Therefore this report does not claim a successful Kotlin compile, passing test suite, or installable APK.

## Known integration limits
- Google services need OAuth/client configuration and user consent.
- Smart-home operation requires a real provider/device integration.
- Full offline LLM inference requires a packaged on-device model/runtime.
- A dedicated low-power wake-word model is not confirmed.
- Weather requires internet access and the Open-Meteo endpoints to be reachable.

## Safety note
The app includes Accessibility, notification-listener, microphone, camera, and device-admin capabilities. Enable only permissions that are necessary and understood. High-risk actions should require explicit user confirmation.


## Patch follow-up (2026-10-21)
- Added query-relevant memory context selection and wired it into AI requests.
- Added Hindi/Hinglish command aliases and real unit tests for `CommandNormalizer`.
- Fixed a source-set issue: the file named `CommandNormalizerTest.kt` had contained a duplicate copy of `SecureVault` rather than tests.
- Set the Gradle wrapper script executable bit.
- Re-ran `bash gradlew --no-daemon testDebugUnitTest assembleDebug`; execution is still blocked before Gradle starts because `services.gradle.org` DNS/network access is unavailable. Compilation, tests, and APK assembly remain unverified.
