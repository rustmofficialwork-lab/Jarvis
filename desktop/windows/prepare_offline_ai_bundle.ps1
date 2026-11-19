$ErrorActionPreference = "Stop"

# Export only Qwen3.5 4B and the blobs it references from the local Ollama store.
# Run after: ollama pull qwen3.5:4b
$Model = "qwen3.5:4b"
$Store = if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { Join-Path $HOME ".ollama\models" }
$ManifestRelative = "manifests\registry.ollama.ai\library\qwen3.5\4b"
$ManifestPath = Join-Path $Store $ManifestRelative
$BundleRoot = Join-Path $PSScriptRoot "offline-ai-bundle\models"

if (-not (Test-Path $ManifestPath -PathType Leaf)) {
    throw "Qwen3.5 4B is not installed in Ollama's model store. Run 'ollama pull $Model' first."
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$digests = @()
if ($manifest.config.digest) { $digests += [string]$manifest.config.digest }
foreach ($layer in @($manifest.layers)) {
    if ($layer.digest) { $digests += [string]$layer.digest }
}
$digests = @($digests | Sort-Object -Unique)
if ($digests.Count -lt 2) { throw "The Ollama manifest is incomplete; refusing to create a partial bundle." }

$destinationManifest = Join-Path $BundleRoot $ManifestRelative
$destinationBlobs = Join-Path $BundleRoot "blobs"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destinationManifest), $destinationBlobs | Out-Null
Copy-Item -LiteralPath $ManifestPath -Destination $destinationManifest -Force

foreach ($digest in $digests) {
    if ($digest -notmatch '^sha256:[0-9a-f]{64}$') {
        throw "Unexpected Ollama blob digest in manifest: $digest"
    }
    $blobName = $digest.Replace(":", "-")
    $sourceBlob = Join-Path (Join-Path $Store "blobs") $blobName
    $destinationBlob = Join-Path $destinationBlobs $blobName
    if (-not (Test-Path $sourceBlob -PathType Leaf)) {
        throw "Required model blob is missing: $blobName"
    }
    Copy-Item -LiteralPath $sourceBlob -Destination $destinationBlob -Force
    $actualHash = (Get-FileHash -LiteralPath $destinationBlob -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $digest.Substring(7)) {
        throw "Model blob integrity check failed: $blobName"
    }
}

Write-Host "Qwen3.5 4B bundle prepared successfully:" -ForegroundColor Green
Write-Host $BundleRoot
Write-Host "Include this folder in the Windows installer build. Keep it out of normal Git source history."
