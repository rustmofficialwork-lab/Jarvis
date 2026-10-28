# Offline wake-word engine: implementation notes

## Current status

The wake listener currently uses Android's `SpeechRecognizer` to recognize speech and then checks the returned text for “Jarvis”. This is **not** a dedicated offline wake-word detector. The silence retry delay has been increased to the existing 2-second minimum to reduce rapid recognizer recreation, privacy-indicator flicker, and battery churn.

## Requirements for a real offline wake-word detector

A dedicated keyword engine needs an actual acoustic model for the requested phrase and a compatible Android runtime. The repository does not currently include a “Hey Jarvis” model.

Before enabling an engine, choose and supply one of:

- **Picovoice Porcupine**: Android SDK, an access key configured locally (never committed), and a custom keyword model file for “Hey Jarvis”.
- **An open-source on-device keyword-spotting model/runtime**: compatible model files, license review, and Android integration.

A generic built-in keyword or a text-matching rule is not a substitute for a trained “Hey Jarvis” acoustic model. Do not enable a placeholder engine that would silently fail at runtime.

## Next integration steps

1. Add the selected engine/runtime and model-loading lifecycle.
2. Route the microphone audio to the wake-word engine continuously while the foreground microphone service is active.
3. Start `SpeechRecognizer` only after a wake-word hit, for the actual user command.
4. Release audio resources on pause/stop, handle Android microphone permission and foreground-service restrictions, and test on physical devices.
5. Verify that the selected runtime and model are genuinely offline; test with mobile data and Wi-Fi disabled.

## Validation caveat

This branch change is a retry-loop mitigation only. It does not yet implement true offline “Hey Jarvis” detection, and no Android build or device test has been run in this environment.
