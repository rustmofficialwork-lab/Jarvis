# First-party JARVIS wake-word model: data collection

The current desktop build still uses a publisher-hosted ONNX model. That model cannot be silently bundled or redistributed by this project under the publisher's current download/license flow. Do not describe the wake-word feature as self-contained yet.

A first-party model must be trained and validated from properly labeled audio before the app can switch away from the existing detector. A model file must not be fabricated or checked in without a real training run and evaluation.

## Collecting a local development dataset

Run these commands from `desktop/windows` on the Windows development PC:

```powershell
py wakeword_dataset_recorder.py --label positive --count 30
py wakeword_dataset_recorder.py --label negative --count 30
```

- Positive: say only "Jarvis" once per clip, naturally, after the countdown.
- Negative: do not say "Jarvis"; capture ordinary room noise and unrelated speech.
- Use a quiet room for some clips and normal everyday background sound for others.
- Keep clips from different recording sessions separated when evaluating so validation does not simply reuse training audio.
- Record only your own voice or voices for which you have permission. The recorder stores WAV files locally and does not upload them.

The recorder uses 16 kHz, mono, 16-bit PCM and 1.5-second clips. It supports `--device-index` to select a microphone. The dataset is written under `wakeword_dataset/positive` and `wakeword_dataset/negative` by default.

## Release gate (not yet complete)

Before replacing the current detector, the project still needs:

1. A reproducible training pipeline and a documented model architecture.
2. Separate train, validation, and held-out test splits.
3. Evaluation for missed detections and false activations per hour in quiet and noisy conditions.
4. A trained ONNX artifact with a recorded SHA-256 hash and model/version metadata.
5. Runtime integration and installer bundling of that first-party artifact.
6. Windows microphone testing on more than one device.

Do not claim the custom model is complete until all release gates pass. The existing publisher model remains the active implementation until then.

## Owner-only activation requirement

The requested behavior is stricter than ordinary wake-word detection: JARVIS should accept "Jarvis" only when the enrolled owner says it. The runtime therefore needs two independent gates:

1. Wake-word detection decides whether the word "Jarvis" was spoken.
2. Speaker verification decides whether the voice matches the locally enrolled owner profile.

A positive wake-word clip is not, by itself, a reliable speaker identity model. Do not treat a keyword classifier score as proof of speaker identity, and do not claim owner-only activation until impostor-speaker testing has been completed.

### Speaker-profile design and privacy gates

- Enrollment must be an explicit user action with clear microphone consent.
- Store the derived speaker profile locally in the user's AppData, not in the repository or cloud. Provide a clear delete/reset action.
- Prefer a documented, license-compatible speaker-embedding model that can be bundled with the installer and run offline. Verify its redistribution terms before bundling; do not silently download model weights at first launch.
- Compare embeddings with a calibrated threshold and reject uncertain matches. A threshold must be measured against held-out owner and non-owner recordings, not guessed.
- Evaluate false accepts and false rejects across different sessions, microphone distances, room noise, and more than one non-owner speaker.
- Voice matching is not strong authentication: recordings and voice imitation can spoof it. Do not use it as the sole gate for sensitive actions or account access.

### Additional owner-enrollment data needed

The current positive/negative dataset recorder is for wake-word classification, not complete speaker verification. A later enrollment flow must collect multiple short owner utterances across separate sessions and retain a separate held-out owner set. Evaluation also needs consented non-owner samples that are never mixed into the owner's enrollment profile. Keep all samples local and make deletion straightforward.

## Current implementation boundary

The current Windows listener activates immediately after the publisher wake-word model crosses its threshold. It does not yet run a speaker-verification gate. The current "Set up wake word" flow also still requires the publisher-hosted ONNX model and downloads shared openWakeWord runtime assets. Therefore neither first-party offline wake-word setup nor owner-only activation is complete. Do not label the current listener as owner-voice-only.
