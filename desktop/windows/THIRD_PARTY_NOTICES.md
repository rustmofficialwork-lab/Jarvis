# Third-party runtime notices

JARVIS bundles the following browser-side runtime libraries in its Windows build:

- **Three.js 0.160.0** — Copyright © 2010–2023 Three.js Authors. Licensed under the MIT License. Source: https://github.com/mrdoob/three.js
- **MediaPipe Tasks Vision 0.10.14** — Copyright 2019–2024 The MediaPipe Authors. Licensed under the Apache License, Version 2.0. Source: https://www.npmjs.com/package/@mediapipe/tasks-vision

The Windows build copies the upstream Three.js license and the Apache License, Version 2.0, into the installed application's `vendor/licenses` directory. MediaPipe model files are fetched separately at first camera-feature activation and are not included in this notice as bundled assets.
