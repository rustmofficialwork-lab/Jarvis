$ErrorActionPreference = "Stop"

Write-Host "JARVIS Offline AI setup" -ForegroundColor Cyan
Write-Host "This installs Ollama (if needed) and downloads the Llama 3.2 3B model."
Write-Host "The model download is approximately 2 GB; keep an internet connection during setup."

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

& $ollamaExe pull llama3.2:3b
if ($LASTEXITCODE -ne 0) {
    throw "The Llama 3.2 3B model download failed. Check your internet connection and rerun this script."
}

Write-Host ""
Write-Host "Offline AI is ready. JARVIS will start Ollama automatically when needed and use it whenever cloud AI is unavailable." -ForegroundColor Green
