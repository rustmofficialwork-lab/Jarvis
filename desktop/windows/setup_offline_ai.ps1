$ErrorActionPreference = "Stop"

$Model = "qwen3.5:4b"
$Repo = "rustmofficialwork-lab/Jarvis"
$ReleaseTag = "offline-ai-qwen3.5-4b"
$BundleModels = Join-Path $PSScriptRoot "offline-ai-bundle\models"
$DefaultModels = if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { Join-Path $HOME ".ollama\models" }

Write-Host "JARVIS Offline AI setup" -ForegroundColor Cyan
Write-Host "Model: $Model"

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExe = if ($ollamaCommand) { $ollamaCommand.Source } else { $null }
if (-not $ollamaExe) {
    $localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME "AppData\Local" }
    $programFiles = if ($env:ProgramFiles) { $env:ProgramFiles } else { "C:\Program Files" }
    $candidates = @((Join-Path $localAppData "Programs\Ollama\ollama.exe"), (Join-Path $programFiles "Ollama\ollama.exe"), "C:\Program Files\Ollama\ollama.exe")
    $ollamaExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $ollamaExe) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw "Ollama is not installed and winget is unavailable. Install Ollama, then rerun this setup." }
    winget install --id Ollama.Ollama --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Ollama installation failed (exit code $LASTEXITCODE)." }
    $localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME "AppData\Local" }
    $programFiles = if ($env:ProgramFiles) { $env:ProgramFiles } else { "C:\Program Files" }
    $candidates = @((Join-Path $localAppData "Programs\Ollama\ollama.exe"), (Join-Path $programFiles "Ollama\ollama.exe"), "C:\Program Files\Ollama\ollama.exe")
    $ollamaExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $ollamaExe) {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) { $ollamaExe = $ollamaCommand.Source }
}
if (-not $ollamaExe) { throw "Ollama installation could not be located. Restart Windows and rerun setup." }

$serverReady = $false
try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null; $serverReady = $true } catch {
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
}
if (-not $serverReady) {
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        Start-Sleep -Seconds 2
        try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null; $serverReady = $true; break } catch {}
    }
}
if (-not $serverReady) { throw "Ollama did not start. Restart Windows and rerun setup." }

$installed = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
$latestModel = $Model + ":latest"
$hasModel = @($installed.models | Where-Object { $_.name -eq $Model -or $_.name -eq $latestModel }).Count -gt 0

if (-not $hasModel) {
    $bundleManifest = Join-Path $BundleModels "manifests\registry.ollama.ai\library\qwen3.5\4b"
    if (Test-Path -LiteralPath $bundleManifest -PathType Leaf) {
        $blobDir = Join-Path $BundleModels "blobs"
        if (-not (Test-Path $blobDir -PathType Container)) { throw "Bundled model blobs are missing." }
        New-Item -ItemType Directory -Force -Path $DefaultModels | Out-Null
        Copy-Item -Path (Join-Path $BundleModels "*") -Destination $DefaultModels -Recurse -Force
        Write-Host "Using model bundled with the installer." -ForegroundColor Green
    } else {
        Write-Host "Downloading the JARVIS Qwen3.5 4B release assets..." -ForegroundColor Cyan
        $api = "https://api.github.com/repos/$Repo/releases/tags/$ReleaseTag"
        $release = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "JARVIS-Offline-AI-Setup"; "Accept" = "application/vnd.github+json" }
        $assetMap = @{}
        foreach ($asset in $release.assets) { $assetMap[$asset.name] = $asset.browser_download_url }
        if (-not $assetMap.ContainsKey("qwen35-index.json") -or -not $assetMap.ContainsKey("qwen35-manifest.json")) {
            throw "The JARVIS model release is missing required index or manifest assets."
        }

        $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("jarvis-qwen-download-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $tempRoot | Out-Null
        try {
            $indexPath = Join-Path $tempRoot "qwen35-index.json"
            $manifestTemp = Join-Path $tempRoot "qwen35-manifest.json"
            Invoke-WebRequest -Uri $assetMap["qwen35-index.json"] -OutFile $indexPath -UseBasicParsing
            Invoke-WebRequest -Uri $assetMap["qwen35-manifest.json"] -OutFile $manifestTemp -UseBasicParsing
            $index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
            if ($index.model -ne $Model) { throw "Release model index does not match $Model." }

            $blobRoot = Join-Path $DefaultModels "blobs"
            $manifestDest = Join-Path $DefaultModels "manifests\registry.ollama.ai\library\qwen3.5\4b"
            New-Item -ItemType Directory -Force -Path $blobRoot, (Split-Path -Parent $manifestDest) | Out-Null
            foreach ($blob in $index.blobs) {
                if ($blob.digest -notmatch '^sha256:[0-9a-f]{64}$') { throw "Invalid digest in release index." }
                $blobName = $blob.digest.Replace(":", "-")
                $finalBlob = Join-Path $blobRoot $blobName
                $partialBlob = Join-Path $tempRoot ($blobName + ".assembled")
                $output = [IO.File]::Create($partialBlob)
                try {
                    foreach ($partName in $blob.parts) {
                        if (-not $assetMap.ContainsKey([string]$partName)) { throw "Release is missing model part: $partName" }
                        $partPath = Join-Path $tempRoot ([string]$partName)
                        Invoke-WebRequest -Uri $assetMap[[string]$partName] -OutFile $partPath -UseBasicParsing
                        $input = [IO.File]::OpenRead($partPath)
                        try { $input.CopyTo($output) } finally { $input.Dispose(); Remove-Item -LiteralPath $partPath -Force }
                    }
                } finally { $output.Dispose() }
                $actualHash = (Get-FileHash -LiteralPath $partialBlob -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actualHash -ne $blob.digest.Substring(7)) { throw "Downloaded model blob failed SHA-256 verification: $blobName" }
                if ((Get-Item -LiteralPath $partialBlob).Length -ne [long]$blob.size) { throw "Downloaded model blob has an incorrect size: $blobName" }
                Move-Item -LiteralPath $partialBlob -Destination $finalBlob -Force
            }
            Move-Item -LiteralPath $manifestTemp -Destination $manifestDest -Force
            Write-Host "Qwen3.5 4B downloaded and SHA-256 verified." -ForegroundColor Green
        } finally { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
    }

    # Refresh Ollama model discovery before using the network fallback.
    $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
    if (@($tags.models | Where-Object { $_.name -eq $Model -or $_.name -eq $latestModel }).Count -eq 0) {
        & $ollamaExe pull $Model
        if ($LASTEXITCODE -ne 0) { throw "Ollama could not register the local model or download the registry fallback." }
    }
}
Write-Host ""
Write-Host "Offline AI setup completed. JARVIS uses the local Qwen3.5 4B model." -ForegroundColor Green
