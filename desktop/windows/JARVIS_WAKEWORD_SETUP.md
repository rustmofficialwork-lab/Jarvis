# Single-word "Jarvis" wake word model

JARVIS uses the community-published openWakeWord model named **Jarvis**.

## Install the model once

1. Open the official model page: https://openwakeword.com/library/422
2. Sign in on that page and download the **ONNX** file named:
   `Jarvis_20260313_215039.onnx`
3. On Windows, create this folder if it does not exist:
   `%APPDATA%\JARVISDesktop\wakewords\`
4. Place the downloaded ONNX file in that folder. The final path must be:
   `%APPDATA%\JARVISDesktop\wakewords\Jarvis_20260313_215039.onnx`
5. Start JARVIS, enable Voice Listening, and say **"Jarvis"**.

The detector runs locally after the model and openWakeWord feature files have been downloaded.
The first setup requires internet access. The speech-to-text stage still uses the project's
existing Google recognition with Vosk fallback behavior.

## Model and license

The model page reports 87.3% recall with background noise and room reverb, and 0.00 false
activations/hour on its benchmark at threshold 0.5. These are publisher-reported benchmark
figures, not a guarantee for every microphone or room.

The model is offered for personal and non-commercial use by default. Review the model page's
license terms before redistributing it or using it commercially. The model binary is not
included in this repository; download it from the official page above.
