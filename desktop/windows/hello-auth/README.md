# JARVIS Windows Hello helper

This small native helper asks Windows to verify the currently signed-in user,
using the verification method configured by Windows (Windows Hello face/PIN,
fingerprint, or another supported device). It does not read, export, or store
biometric templates.

A successful result means Windows verified the user. It does not reveal which
verification modality was used and is not a face-recognition API. Windows does
not expose the enrolled face template or a reusable face-match result to this
unpackaged desktop application.

The helper is built by the Windows CI workflow and bundled with the desktop app.
