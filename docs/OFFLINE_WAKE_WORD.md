# Offline wake-word engine

## Implementation

JARVIS can use Picovoice Porcupine's built-in **JARVIS** keyword for on-device wake-word detection. Porcupine owns microphone capture while waiting for the keyword; after detection, JARVIS stops and releases Porcupine before starting Android `SpeechRecognizer` for the actual command.

The app uses `ai.picovoice:porcupine-android:4.0.2`. Wake-word inference is performed on-device, but the SDK AccessKey must be configured and may require internet for SDK key validation. No AccessKey is stored in this repository.

## Configure the AccessKey

1. Create an AccessKey in the [Picovoice Console](https://console.picovoice.ai/).
2. Add this line to your **user-level** Gradle properties file (normally `~/.gradle/gradle.properties`), not to a tracked repository file:

   ```properties
   PICOVOICE_ACCESS_KEY=your_actual_access_key
   ```

   Alternatively, set the `PICOVOICE_ACCESS_KEY` environment variable when building.
3. Sync and build the Android project, install it, grant microphone permission, and start the foreground JARVIS service.

If no key is configured or Porcupine initialization fails, the service logs a warning and falls back to the previous Android `SpeechRecognizer` wake-word path. In that fallback mode, silence retry delay is 2 seconds; microphone indicator flicker can still occur.

## Runtime behavior and limitations

- Porcupine listens for its built-in `JARVIS` keyword. Saying “Hey Jarvis” should trigger when the spoken keyword is detected; the built-in model is for “JARVIS”, not a custom phrase-specific “Hey Jarvis” model.
- On detection, Porcupine is stopped and deleted before command speech recognition starts, avoiding simultaneous microphone ownership.
- Pausing or stopping the service releases Porcupine resources.
- Android's microphone privacy indicator remains visible whenever the foreground service is actively using the microphone. The goal is to avoid rapid session restarts, not to hide the indicator.
- This source change has not been built or tested on a physical device in this environment. Validate Gradle sync, SDK initialization, foreground-service behavior, wake-word accuracy, and battery usage on-device.