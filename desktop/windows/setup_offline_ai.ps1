$ErrorActionPreference = "Stop"

$Model = "qwen3.5:4b"
$Repo = "rustmofficialwork-lab/Jarvis"
$ReleaseTag = "offline-ai-qwen3.5-4b"
$BundleRoot = Join-Path $PSScriptRoot "offline-ai-bundle"
$BundleModels = Join-Path $BundleRoot "models"
$DefaultModels = $BundleModels
$env:OLLAMA_MODELS = $DefaultModels
$env:OLLAMA_HOST = "127.0.0.1:11435"

Write-Host "JARVIS Offline AI setup" -ForegroundColor Cyan
Write-Host "Model: $Model"

$bundledOllama = Join-Path $BundleRoot "ollama\ollama.exe"
if (-not (Test-Path -LiteralPath $bundledOllama -PathType Leaf)) { $bundledOllama = Get-ChildItem -Path (Join-Path $BundleRoot "ollama") -Filter "ollama.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName }
$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExe = if ($bundledOllama -and (Test-Path -LiteralPath $bundledOllama)) { $bundledOllama } elseif ($ollamaCommand) { $ollamaCommand.Source } else { $null }
if (-not $ollamaExe) {
    $localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME "AppData\Local" }
    $programFiles = if ($env:ProgramFiles) { $env:ProgramFiles } else { "C:\Program Files" }
    $candidates = @((Join-Path $localAppData "Programs\Ollama\ollama.exe"), (Join-Path $programFiles "Ollama\ollama.exe"), "C:\Program Files\Ollama\ollama.exe")
    $ollamaExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $ollamaExe) { throw "The offline JARVIS package is missing its bundled Ollama runtime. Re-download the complete installer." }

$serverReady = $false
# Run JARVIS Ollama on its own loopback port and model store. Never terminate
# another Ollama instance that may belong to the user or a different application.
Start-Sleep -Milliseconds 300
try { Invoke-RestMethod -Uri "http://127.0.0.1:11435/api/tags" -TimeoutSec 2 | Out-Null; $serverReady = $true } catch {
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
}
if (-not $serverReady) {
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        Start-Sleep -Seconds 2
        try { Invoke-RestMethod -Uri "http://127.0.0.1:11435/api/tags" -TimeoutSec 2 | Out-Null; $serverReady = $true; break } catch {}
    }
}
if (-not $serverReady) { throw "Ollama did not start. Restart Windows and rerun setup." }

$installed = Invoke-RestMethod -Uri "http://127.0.0.1:11435/api/tags" -TimeoutSec 10
$latestModel = $Model + ":latest"
$hasModel = @($installed.models | Where-Object { $_.name -eq $Model -or $_.name -eq $latestModel }).Count -gt 0

if (-not $hasModel) {
    $bundleManifest = Join-Path $BundleModels "manifests\registry.ollama.ai\library\qwen3.5\4b"
    if (Test-Path -LiteralPath $bundleManifest -PathType Leaf) {
        $blobDir = Join-Path $BundleModels "blobs"
        if (-not (Test-Path $blobDir -PathType Container)) { throw "Bundled model blobs are missing." }
        Write-Host "Using Qwen3.5 4B bundled inside the JARVIS installer." -ForegroundColor Green
    } else {
        throw "The complete Qwen3.5 4B model is missing from this installer. Download the Full Offline Setup again."
    }

    # Ask Ollama to rescan the model store before using the registry fallback.
    $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11435/api/tags" -TimeoutSec 10
    if (@($tags.models | Where-Object { $_.name -eq $Model -or $_.name -eq $latestModel }).Count -eq 0) {
        & $ollamaExe list | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "Ollama could not inspect its local model store." }
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11435/api/tags" -TimeoutSec 10
    }
    if (@($tags.models | Where-Object { $_.name -eq $Model -or $_.name -eq $latestModel }).Count -eq 0) {
        throw "Bundled Qwen3.5 4B was not registered by Ollama. The installer package is incomplete."
    }
}

# Verify a real local inference; file presence alone is not a successful setup.
$body = @{ model = $Model; stream = $false; messages = @(@{ role = "user"; content = "Reply with exactly: JARVIS MODEL READY" }); options = @{ num_predict = 24; temperature = 0 } } | ConvertTo-Json -Depth 6
try {
    $reply = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:11435/api/chat" -ContentType "application/json" -Body $body -TimeoutSec 180
    if (-not $reply.message.content -or -not $reply.message.content.Trim()) { throw "Ollama returned an empty response." }
} catch {
    throw "Qwen3.5 4B files are present, but the model did not complete a local inference test: $($_.Exception.Message)"
}
Write-Host ""
Write-Host "Offline AI setup completed. Qwen3.5 4B passed a local inference test." -ForegroundColor Green
