$ErrorActionPreference = "Stop"

$Model = "qwen3.5:4b"
$BundleModels = Join-Path $PSScriptRoot "offline-ai-bundle\models"
$DefaultModels = Join-Path $HOME ".ollama\models"

Write-Host "JARVIS Offline AI setup" -ForegroundColor Cyan
Write-Host "Model: $Model"

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExe = if ($ollamaCommand) { $ollamaCommand.Source } else { $null }

if (-not $ollamaExe) {
    $localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME "AppData\Local" }
    $programFiles = if ($env:ProgramFiles) { $env:ProgramFiles } else { "C:\Program Files" }
    $candidates = @(
        (Join-Path $localAppData "Programs\Ollama\ollama.exe"),
        (Join-Path $programFiles "Ollama\ollama.exe"),
        "C:\Program Files\Ollama\ollama.exe"
    )
    $ollamaExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $ollamaExe) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Ollama is not installed and winget is unavailable. Install Ollama from https://ollama.com/download/windows, then run this script again."
    }
    winget install --id Ollama.Ollama --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Ollama installation failed (exit code $LASTEXITCODE)." }
    $localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME "AppData\Local" }
    $programFiles = if ($env:ProgramFiles) { $env:ProgramFiles } else { "C:\Program Files" }
    $candidates = @(
        (Join-Path $localAppData "Programs\Ollama\ollama.exe"),
        (Join-Path $programFiles "Ollama\ollama.exe"),
        "C:\Program Files\Ollama\ollama.exe"
    )
    $ollamaExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $ollamaExe) {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) { $ollamaExe = $ollamaCommand.Source }
}
if (-not $ollamaExe) {
    throw "Ollama installation could not be located. Restart PowerShell and run this script again."
}

# An optional release may ship Ollama's native model-store layout here.
$bundleManifest = Join-Path $BundleModels "manifests\registry.ollama.ai\library\qwen3.5\4b"
$hasBundle = Test-Path $bundleManifest -PathType Leaf
if ($hasBundle) {
    $blobDir = Join-Path $BundleModels "blobs"
    if (-not (Test-Path $blobDir -PathType Container)) {
        throw "The bundled Qwen3 model manifest exists but its blobs folder is missing."
    }
    New-Item -ItemType Directory -Force -Path $DefaultModels | Out-Null
    Copy-Item -Path (Join-Path $BundleModels "*") -Destination $DefaultModels -Recurse -Force
    Write-Host "Using the Qwen3.5 4B model bundled with this JARVIS installer." -ForegroundColor Green
} else {
    Write-Host "No offline model bundle is present; the official Ollama registry will be used." -ForegroundColor Yellow
    Write-Host "The first-time model download is approximately 3.3–4.0 GB."
}

$serverReady = $false
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
    $serverReady = $true
} catch {
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
}
if (-not $serverReady) {
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        Start-Sleep -Seconds 2
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
            $serverReady = $true
            break
        } catch {}
    }
}
if (-not $serverReady) {
    throw "Ollama did not start. Restart Windows, open Ollama, and run this script again."
}

$installed = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
$latestModel = $Model + ":latest"
$hasModel = @($installed.models | Where-Object { $_.name -eq $Model -or $_.name -eq $latestModel }).Count -gt 0
if (-not $hasModel) {
    if ($hasBundle) {
        throw "The bundled Qwen3 model was copied, but Ollama did not register it. Check the bundled manifest and blobs."
    }
    & $ollamaExe pull $Model
    if ($LASTEXITCODE -ne 0) {
        throw "The Qwen3.5 4B model download failed. Check your internet connection and rerun this script."
    }
}
Write-Host ""
Write-Host "Offline AI is ready. JARVIS will use the local Ollama model when cloud AI is unavailable." -ForegroundColor Green
