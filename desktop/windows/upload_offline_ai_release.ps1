$ErrorActionPreference = "Stop"

# Upload the already-installed Ollama Qwen3.5 4B model directly from its model store.
# Large blobs are streamed into temporary <=1.8 GB parts for GitHub Release's asset limit.
$Repo = "rustmofficialwork-lab/Jarvis"
$Tag = "offline-ai-qwen3.5-4b"
$Model = "qwen3.5:4b"
$ChunkBytes = 400MB
$Store = if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { Join-Path $HOME ".ollama\models" }
$ManifestRelative = "manifests\registry.ollama.ai\library\qwen3.5\4b"
$ManifestPath = Join-Path $Store $ManifestRelative

 $ghCommand = Get-Command gh.exe -ErrorAction SilentlyContinue
if (-not $ghCommand) { $ghCommand = Get-Command gh -ErrorAction SilentlyContinue }
if (-not $ghCommand) {
    $knownGhPath = Join-Path $env:ProgramFiles "GitHub CLI\gh.exe"
    if (Test-Path -LiteralPath $knownGhPath -PathType Leaf) { $ghPath = $knownGhPath }
    else { throw "GitHub CLI (gh.exe) was not found. Install GitHub CLI, then reopen PowerShell." }
} else { $ghPath = $ghCommand.Source }
& $ghPath auth status | Out-Null
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not signed in. Run: gh auth login" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "The installed $Model manifest was not found in: $Store"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$digests = @()
if ($manifest.config.digest) { $digests += [string]$manifest.config.digest }
foreach ($layer in @($manifest.layers)) { if ($layer.digest) { $digests += [string]$layer.digest } }
$digests = @($digests | Sort-Object -Unique)
if ($digests.Count -lt 2) { throw "Ollama manifest is incomplete." }

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("jarvis-qwen-upload-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
$assets = [System.Collections.Generic.List[string]]::new()
$index = [ordered]@{ model = $Model; manifest_asset = "qwen35-manifest.json"; blobs = @() }

try {
    Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $tempRoot "qwen35-manifest.json")
    $assets.Add((Join-Path $tempRoot "qwen35-manifest.json"))

    foreach ($digest in $digests) {
        if ($digest -notmatch '^sha256:[0-9a-f]{64}$') { throw "Unexpected blob digest: $digest" }
        $blobName = $digest.Replace(":", "-")
        $source = Join-Path (Join-Path $Store "blobs") $blobName
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing Ollama blob: $blobName" }
        $expectedHash = $digest.Substring(7)
        $actualHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) { throw "Integrity check failed for $blobName" }

        $info = Get-Item -LiteralPath $source
        $parts = @()
        $sourceStream = [IO.File]::OpenRead($source)
        try {
            $partNumber = 0
            while ($sourceStream.Position -lt $sourceStream.Length) {
                $partNumber++
                $partName = "qwen35-$blobName-part{0:D3}.bin" -f $partNumber
                $partPath = Join-Path $tempRoot $partName
                $output = [IO.File]::Create($partPath)
                try {
                    $buffer = New-Object byte[] (8MB)
                    $remaining = [Math]::Min([long]$ChunkBytes, $sourceStream.Length - $sourceStream.Position)
                    while ($remaining -gt 0) {
                        $read = $sourceStream.Read($buffer, 0, [int][Math]::Min($buffer.Length, $remaining))
                        if ($read -le 0) { throw "Unexpected end of blob while splitting $blobName" }
                        $output.Write($buffer, 0, $read)
                        $remaining -= $read
                    }
                } finally { $output.Dispose() }
                $assets.Add($partPath)
                $parts += $partName
            }
        } finally { $sourceStream.Dispose() }
        $index.blobs += [ordered]@{ digest = $digest; size = [long]$info.Length; parts = $parts }
    }

    $indexPath = Join-Path $tempRoot "qwen35-index.json"
    $index | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $indexPath -Encoding UTF8
    $assets.Add($indexPath)

    $releaseTagsJson = & $ghPath release list --repo $Repo --limit 100 --json tagName
    if ($LASTEXITCODE -ne 0) { throw "Could not list releases in $Repo. Check repository access." }
    $releaseTags = @($releaseTagsJson | ConvertFrom-Json | ForEach-Object { [string]$_.tagName })
    if ($releaseTags -notcontains $Tag) {
        & $ghPath release create $Tag --repo $Repo --title "JARVIS Qwen3.5 4B Offline Model" --notes "Official JARVIS offline model assets. Uploaded from the user's existing Ollama model store; SHA-256 verified."
        if ($LASTEXITCODE -ne 0) { throw "Could not create the GitHub Release." }
    }
    $uploadArgs = @("release", "upload", $Tag, "--repo", $Repo, "--clobber") + @($assets.ToArray())
    & $ghPath @uploadArgs
    if ($LASTEXITCODE -ne 0) { throw "GitHub Release asset upload failed." }
    Write-Host "Qwen3.5 4B assets uploaded and source blobs SHA-256 verified." -ForegroundColor Green
    Write-Host "Release: https://github.com/$Repo/releases/tag/$Tag"
} finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
