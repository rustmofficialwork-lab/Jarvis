# Single-word "Jarvis" wake-word model

JARVIS uses the community-published openWakeWord model named **Jarvis**.

## One-time setup

1. Start JARVIS and activate Voice Listening, or choose **Set up wake word** in Settings.
2. JARVIS opens the model publisher's page. Sign in there if the publisher requests it, review the license, and download the ONNX model.
3. Leave the downloaded filename unchanged. JARVIS watches the Windows **Downloads** folder, validates the ONNX file, and copies it to the app's wake-word folder automatically.
4. Once JARVIS reports that the model is installed, enable Voice Listening again and say **"Jarvis"**.

Expected model filename:

`Jarvis_20260313_215039.onnx`

Expected installed path:

`%APPDATA%\JARVISDesktop\wakewords\Jarvis_20260313_215039.onnx`

You do not need to manually create the folder, rename the file, or copy it into the app-data directory. The setup assistant waits up to ten minutes for the download to finish. If your browser saves downloads somewhere other than the standard Downloads folder, move the file there and choose **Set up wake word** again.

## Internet and offline behavior

Internet is needed for the publisher's one-time model download and for openWakeWord's shared feature/VAD runtime files on first activation. JARVIS stores these shared assets under `%APPDATA%\\JARVISDesktop\\wakeword_runtime\\models` so standard Windows users do not need write access to the installation folder. JARVIS requests these shared assets without downloading openWakeWord's unrelated pretrained wake-word model catalog. After those files are cached, wake-word detection runs locally on the PC and does not send microphone audio to a wake-word cloud service. Speech-to-text uses the project's existing online recognition with its local Vosk fallback.

The app does not silently fetch or redistribute the custom model because the publisher gates downloads behind its own page and its default model terms are personal/non-commercial. The user must complete the publisher's download step and review those terms.

## Microphone diagnostics

To list available Windows microphone/input devices:

```powershell
py wakeword_mic_test.py --list-devices
```

The list shows each input device's PyAudio index. To test a particular microphone, pass that index:

```powershell
py wakeword_mic_test.py --device-index 2
```

Replace `2` with the index shown for the microphone you want to test. If no index is supplied, the Windows/PyAudio default input is used.

The local diagnostic runs three short phases: quiet room, five spoken "Jarvis" attempts, and ordinary background noise. It reports peak confidence and activation counts. It does not save or upload audio. Repeat it with the microphone, distance, room and speaker volume you normally use. A spot-check is not a guarantee of zero false activations or perfect recall.

The live detector now requires confidence at or above 0.5 for two consecutive 80 ms audio frames, plus its existing two-second cooldown. This filters isolated confidence spikes without changing the model's published threshold.

## Model and license

The model page reports 87.3% recall with background noise and room reverb, and 0.00 false activations/hour on its benchmark at threshold 0.5. These are publisher-reported benchmark figures, not a guarantee for every microphone or room. JARVIS' two-frame activation rule also differs from the publisher's benchmark procedure.

The model is offered for personal and non-commercial use by default. Review the model page's license terms before using it commercially. The model binary is not included in this repository; download it from the publisher.
