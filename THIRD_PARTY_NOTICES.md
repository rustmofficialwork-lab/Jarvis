# Third-party runtime notices

JARVIS bundles the following browser-side runtime libraries in its Windows build:

- **Three.js 0.160.0** — Copyright © 2010–2023 Three.js Authors. Licensed under the MIT License. Source: https://github.com/mrdoob/three.js
- **MediaPipe Tasks Vision 0.10.14** — Copyright 2019–2024 The MediaPipe Authors. Licensed under the Apache License, Version 2.0. Source: https://www.npmjs.com/package/@mediapipe/tasks-vision

The Windows build copies the upstream Three.js license and the Apache License, Version 2.0, into the installed application's `vendor/licenses` directory. The MediaPipe Hand Landmarker task model is also bundled under `vendor/mediapipe/models/hand_landmarker.task` so gesture control can start without a first-use model download. Review the upstream MediaPipe model documentation and terms for the exact model revision distributed with each build. The separate Face Detector model remains downloaded on first face-presence activation.
