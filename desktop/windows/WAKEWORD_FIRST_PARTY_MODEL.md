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
