# Third-party runtime notices

JARVIS bundles the following browser-side runtime libraries in its Windows build:

- **Three.js 0.160.0** — Copyright © 2010–2023 Three.js Authors. Licensed under the MIT License. Source: https://github.com/mrdoob/three.js
- **MediaPipe Tasks Vision 0.10.14** — Copyright 2019–2024 The MediaPipe Authors. Licensed under the Apache License, Version 2.0. Source: https://www.npmjs.com/package/@mediapipe/tasks-vision

The Windows build copies the upstream Three.js license and the Apache License, Version 2.0, into the installed application's `vendor/licenses` directory. The MediaPipe Hand Landmarker task model is also bundled under `vendor/mediapipe/models/hand_landmarker.task` so gesture control can start without a first-use model download. Review the upstream MediaPipe model documentation and terms for the exact model revision distributed with each build.


## Offline voice model notices

- **Vosk small speech models** — Alpha Cephei: `vosk-model-small-hi-0.22`, `vosk-model-small-en-in-0.4`, and `vosk-model-small-en-us-0.15`. The official Vosk model catalogue lists these models under the Apache License 2.0. The installer includes the Apache-2.0 license text beside the model files. Source: https://alphacephei.com/vosk/models
- **ECAPA-TDNN speaker encoder** — `kenrunio/transcriber-speaker-onnx`, pinned revision `4467ef1f92829ca0ff4bbdaa70d31f7d7d25c12c`, file `ecapa-any-length.onnx`. The project documentation identifies the ONNX conversion as Apache-2.0; the installer includes the upstream LICENSE file and verifies SHA-256 `700b63064ee98981186f59f247d28e56f7f6ab265d8b50ebb450db5a8ce21dc7`. Source: https://huggingface.co/kenrunio/transcriber-speaker-onnx

The bundled encoder does not contain or create a user's speaker profile. Owner enrollment is explicit, performed locally, and stores only the derived profile in Windows Credential Manager.
