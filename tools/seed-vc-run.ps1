[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$Source,
    [Parameter(Mandatory = $true)] [string]$Target,
    [string]$OutputDir = '.\artifacts\seed-vc',
    [string]$Repo = '.\tools\external\seed-vc',
    [string]$Checkpoint = '.\models\seed-vc\checkpoints\offline-v1\DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth',
    [string]$Config = '.\tools\external\seed-vc\configs\presets\config_dit_mel_seed_uvit_whisper_small_wavenet.yml',
    [string]$Python = '.\tools\venvs\seed-vc\Scripts\python.exe',
    [switch]$Fp16
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Resolve-ProjectPath([string]$Path) {
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path $projectRoot $Path))
}

function Save-Manifest([System.Collections.IDictionary]$Value, [string]$Path) {
    $tempPath = "$Path.tmp"
    $json = $Value | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($tempPath, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tempPath -Destination $Path -Force
}

$resolvedSource = Resolve-ProjectPath $Source
$resolvedTarget = Resolve-ProjectPath $Target
$resolvedOutputRoot = Resolve-ProjectPath $OutputDir
$resolvedRepo = Resolve-ProjectPath $Repo
$resolvedCheckpoint = Resolve-ProjectPath $Checkpoint
$resolvedConfig = Resolve-ProjectPath $Config
$resolvedPython = Resolve-ProjectPath $Python
$wavCheck = Join-Path $PSScriptRoot 'seed-vc-wav-check.py'

foreach ($file in @($resolvedSource, $resolvedTarget, $resolvedCheckpoint, $resolvedConfig, $resolvedPython, $wavCheck)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "找不到必要檔案：$file" }
}
if (-not (Test-Path -LiteralPath (Join-Path $resolvedRepo 'inference.py') -PathType Leaf)) {
    throw "找不到 Seed-VC inference.py：$resolvedRepo；請先依 docs/seed-vc-assets.md 準備 official source。"
}

$resolvedSource = (Resolve-Path -LiteralPath $resolvedSource).Path
$resolvedTarget = (Resolve-Path -LiteralPath $resolvedTarget).Path
$sourceHash = (Get-FileHash -LiteralPath $resolvedSource -Algorithm SHA256).Hash
$targetHash = (Get-FileHash -LiteralPath $resolvedTarget -Algorithm SHA256).Hash
$checkpointHash = (Get-FileHash -LiteralPath $resolvedCheckpoint -Algorithm SHA256).Hash
$runId = [Guid]::NewGuid().ToString('N')
$startedAt = [DateTimeOffset]::UtcNow
$resolvedRunDir = Join-Path $resolvedOutputRoot $runId
New-Item -ItemType Directory -Path $resolvedRunDir -ErrorAction Stop | Out-Null
$manifestPath = Join-Path $resolvedRunDir 'seed-vc-run.json'

$manifest = [ordered]@{
    schema_version = 'aethertune-seed-vc-run/v2'
    run_id = $runId
    status = 'RUNNING'
    started_at_utc = $startedAt.ToString('o')
    backend = 'seed-vc'
    profile = 'offline-v1'
    python = $resolvedPython
    source = [ordered]@{ path = $resolvedSource; sha256 = $sourceHash }
    target = [ordered]@{ path = $resolvedTarget; sha256 = $targetHash }
    checkpoint = [ordered]@{ path = $resolvedCheckpoint; sha256 = $checkpointHash }
    config = $resolvedConfig
    fp16 = [bool]$Fp16
    output_directory = $resolvedRunDir
    output_validation = [ordered]@{ status = 'WAITING'; finite = $false; non_zero = $false }
}
Save-Manifest $manifest $manifestPath

$inferenceArgs = @(
    'inference.py', '--source', $resolvedSource, '--target', $resolvedTarget,
    '--output', $resolvedRunDir, '--checkpoint', $resolvedCheckpoint,
    '--config', $resolvedConfig, '--f0-condition', 'False'
)
if ($Fp16) { $inferenceArgs += @('--fp16', 'True') }

Write-Output "Seed-VC run id: $runId"
Write-Output "Seed-VC source SHA256: $sourceHash"
Write-Output "Seed-VC target SHA256: $targetHash"
Write-Output "Seed-VC checkpoint SHA256: $checkpointHash"
Write-Output "執行官方 Seed-VC inference.py；本次全新輸出資料夾：$resolvedRunDir"

Push-Location $resolvedRepo
try {
    try {
        $inferenceText = @(& $resolvedPython @inferenceArgs 2>&1 | ForEach-Object { $_.ToString() })
        $inferenceExitCode = $LASTEXITCODE
        $inferenceText | ForEach-Object { Write-Output $_ }
        if ($inferenceExitCode -ne 0) { throw "Seed-VC inference failed with exit code $inferenceExitCode" }

        $wavFiles = @(Get-ChildItem -LiteralPath $resolvedRunDir -Filter '*.wav' -File | Sort-Object FullName)
        if ($wavFiles.Count -eq 0) { throw "Seed-VC inference created no WAV in this run directory: $resolvedRunDir" }

        $outputFiles = @()
        foreach ($wavFile in $wavFiles) {
            if ($wavFile.LastWriteTimeUtc -lt $startedAt.UtcDateTime.AddSeconds(-1)) {
                throw "Output file predates this run and cannot be accepted: $($wavFile.FullName)"
            }
            $validationJson = & $resolvedPython $wavCheck $wavFile.FullName
            if ($LASTEXITCODE -ne 0) { throw "WAV signal gate failed for $($wavFile.FullName): $validationJson" }
            $validation = $validationJson | ConvertFrom-Json
            if ($validation.status -ne 'PASS' -or -not $validation.finite -or -not $validation.non_zero) {
                throw "WAV signal gate did not return finite non-zero PASS: $($wavFile.FullName)"
            }
            $outputFiles += [ordered]@{
                path = $wavFile.FullName
                bytes = $wavFile.Length
                sha256 = (Get-FileHash -LiteralPath $wavFile.FullName -Algorithm SHA256).Hash
                metrics = $validation
            }
        }

        $torchRuntime = (& $resolvedPython -c "import torch; print(torch.__version__ + ' cuda=' + str(torch.version.cuda) + ' available=' + str(torch.cuda.is_available()))" | Select-Object -Last 1).ToString()
        if ($LASTEXITCODE -ne 0) { throw '無法讀取 Torch runtime identity。' }
        $manifest.status = 'PASS'
        $manifest.completed_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
        $manifest.torch_runtime = $torchRuntime
        $manifest.inference_log = $inferenceText
        $manifest.output_files = $outputFiles
        $manifest.output_validation = [ordered]@{ status = 'PASS'; finite = $true; non_zero = $true }
        Save-Manifest $manifest $manifestPath
        Write-Output "Seed-VC manifest: $manifestPath"
        Write-Output "Seed-VC output validation: PASS ($($outputFiles.Count) new WAV file(s), finite and non-zero)"
    } catch {
        $manifest.status = 'FAIL'
        $manifest.completed_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
        $manifest.error = $_.Exception.Message
        Save-Manifest $manifest $manifestPath
        Write-Output "Seed-VC failure manifest: $manifestPath"
        throw
    }
} finally {
    Pop-Location
}
