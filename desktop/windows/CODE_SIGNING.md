# Windows artifact code signing

The Windows workflow can sign the portable app's native binaries and the Inno Setup installer after packaging. Signing is optional until the project owner configures a valid code-signing certificate.

## GitHub Actions configuration

In the repository's Actions secrets, add:

- `WINDOWS_SIGNING_CERT_BASE64`: the Base64-encoded PFX certificate bundle containing the authorized code-signing certificate and private key.
- `WINDOWS_SIGNING_CERT_PASSWORD`: the PFX password.

Keep both values private. Never commit a PFX file, private key, certificate password, or decoded certificate to the repository. Use a certificate issued for the publisher identity that should appear in Windows signature details.

The workflow decodes the PFX only into the temporary GitHub Actions runner directory, signs packaged `.exe`, `.dll`, and `.pyd` files plus `JARVIS-Setup-x64.exe`, applies a SHA-256 timestamp, verifies each signature, and removes the temporary PFX.

If either secret is missing, the workflow deliberately skips signing and uploads unsigned artifacts. A successful unsigned build must not be described as a signed release. The rolling release checksums are generated after the signing step, so they match the final published files.

## Local verification

On Windows with the Windows SDK installed:

```powershell
signtool verify /pa /v .\JARVIS-Setup-x64.exe
```

A valid signature confirms publisher integrity; it does not prove that the application is free of bugs or that Windows SmartScreen reputation is already established.
