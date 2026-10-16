## JARVIS 5.0.0 — Rebrand Release
 JARVIS. This release contains only the rename plus the
compile-blocker and logic bug fixes listed below.

### Rename summary
- Package: `com.jarvisassistant.app`
- App name: JARVIS
- Wake word default: JARVIS
- Prefs/Keystore namespace: jarvis*`
- Theme: Theme.Jarvis`
- Foreground service channel: jarvis_assistant`
- Broadcast actions: com.jarvisassistant.app.JARVIS_WAKE`

### Bug fixes included
1. `MainActivity` — `withoutWakePrefix` undefined variable in `type ...` handler.
2. `MainActivity` — missing `proactiveMode` / `onProactiveMode` args in `JarvisApp(...)` call.
3. `JarvisRecoveryStore` — referenced non-existent `step.confirmationReason` (now `step.rationale`).
4. `JarvisRecoveryStore` — no more `null` passed to non-nullable `rationale`.
5. Tests — mixed `org.junit.*` and `kotlin.test.*` imports; unified to `kotlin.test.*`.
6. `CommandNormalizer` — removed duplicate `"स्क्रीनशॉट लो"` key.
7. `MainActivity` — replaced 5 identical diagnostics messages with distinct, meaningful ones.
8. `JarvisVoiceEngine` — wake-word Hindi aliases  `जार्विस` / `जारविस`.
9. `JarvisTaskStoreTest` — replaced a meaningless assertion with real model tests.
10. `SecureVault` — Keystore alias bumped to `jarvis.local-data.v1` (old encrypted data intentionally not migrated; see file header).

### Build
```bash
./gradlew clean testDebugUnitTest :app:assembleDebug
