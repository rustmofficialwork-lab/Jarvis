# Local owner voice verification

## What JARVIS does

The voice setup wizard has an explicit **Enroll owner voice (local)** action. It records eight prompted 3-second clips after microphone consent and explicit confirmation. The raw WAV clips are temporary and are deleted after the profile is created.

JARVIS downloads the pinned ECAPA-TDNN ONNX speaker-embedding model during that explicit enrollment step. The model runs on the PC through ONNX Runtime. The derived voice embedding is stored in Windows Credential Manager through the existing keyring integration; raw recordings are not uploaded and are not retained by the enrollment flow.

At runtime, the wake listener keeps a short rolling audio buffer in memory. When the wake-word model fires, JARVIS compares the buffer's speaker embedding with the locally enrolled profile. A non-match or missing profile is rejected before the command-capture pipeline opens.

## Setup

1. Open JARVIS Voice Setup and grant microphone permission.
2. Complete **Check microphone**.
3. Select **Enroll owner voice (local)** and confirm that you are enrolling your own voice.
4. Read the prompts naturally while JARVIS records the eight samples.
5. Complete the wake-word test and finish setup.

If the optional download helper is needed, run from `desktop/windows`:

```powershell
py -m pip install -r voice_identity_requirements.txt
```

To reset the profile, run:

```powershell
py owner_voice_setup.py --reset --confirm
```

Re-enroll after changing the microphone substantially or if verification becomes unreliable.

## Privacy and security limits

- Voice samples and the derived profile are biometric information. Enroll only your own voice, keep Windows access protected, and delete the profile when no longer needed.
- Raw enrollment WAV clips are temporary; the derived embedding is stored in the OS credential vault.
- The ECAPA model is a general speaker-embedding model trained on VoxCeleb, not a model trained specifically on the owner. The initial cosine threshold is a conservative starting point from the model family, not a threshold calibrated to every microphone or user.
- Voice matching is not liveness detection. A recording, voice imitation, or other spoofing may pass. It is a convenience gate only and must never be used as the sole protection for payments, accounts, passwords, or other sensitive actions.
- A failed or uncertain comparison rejects activation. If the microphone or room changes, re-enroll and evaluate before relying on it.

Model reference: https://huggingface.co/kenrunio/transcriber-speaker-onnx (Apache-2.0 ONNX conversion of SpeechBrain ECAPA-TDNN). Model card documents 16 kHz mono input and 192-dimensional embeddings.
