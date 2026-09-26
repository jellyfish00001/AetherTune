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

$resolvedOutput = [IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null
$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$runStartedUtc = [DateTime]::UtcNow
$manifestPath = Join-Path $resolvedOutput 'seed-vc-run.json'

# Overwrite any previous run state before checking user inputs or model assets. A failed
# precondition must never leave an old PASS manifest as the apparent latest run.
$preflightManifest = [ordered]@{
    status = 'BLOCKED'
    run_id = $runId
    started_at_utc = $runStartedUtc.ToString('o')
    completed_at_utc = $null
    backend = 'seed-vc'
    profile = 'offline-v1'
    output_dir = $resolvedOutput
    failure = 'Preflight has not completed.'
}
$preflightManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

try {
    foreach ($path in @($Source, $Target)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "找不到音檔：$path"
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $Repo 'inference.py') -PathType Leaf)) {
        throw "找不到 Seed-VC inference.py：$Repo；請先依 backends/seed-vc/README.md 建立獨立環境與 repo。"
    }
    if (-not (Test-Path -LiteralPath $Checkpoint -PathType Leaf)) {
        throw "找不到 checkpoint：$Checkpoint；請先確認官方 Seed-VC offline-v1 checkpoint 已在本機。"
    }
    if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
        throw "找不到 Seed-VC config：$Config"
    }
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "找不到 Seed-VC Python environment：$Python；請先執行 tools\seed-vc-setup.ps1"
    }

    $resolvedSource = [IO.Path]::GetFullPath($Source)
    $resolvedTarget = [IO.Path]::GetFullPath($Target)
    $resolvedRepo = [IO.Path]::GetFullPath($Repo)
    $resolvedCheckpoint = [IO.Path]::GetFullPath($Checkpoint)
    $resolvedConfig = [IO.Path]::GetFullPath($Config)
    $resolvedPython = [IO.Path]::GetFullPath($Python)
}
catch {
    $preflightManifest.status = 'BLOCKED'
    $preflightManifest.completed_at_utc = [DateTime]::UtcNow.ToString('o')
    $preflightManifest.failure = $_.Exception.Message
    $preflightManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    throw
}

$beforeWavs = @{}
Get-ChildItem -LiteralPath $resolvedOutput -Filter '*.wav' -File -ErrorAction SilentlyContinue | ForEach-Object {
    $beforeWavs[$_.FullName] = [ordered]@{
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
}

$runningManifest = [ordered]@{
    status = 'RUNNING'
    run_id = $runId
    started_at_utc = $runStartedUtc.ToString('o')
    backend = 'seed-vc'
    profile = 'offline-v1'
    source_sha256 = (Get-FileHash -LiteralPath $resolvedSource -Algorithm SHA256).Hash
    target_sha256 = (Get-FileHash -LiteralPath $resolvedTarget -Algorithm SHA256).Hash
    checkpoint_sha256 = (Get-FileHash -LiteralPath $resolvedCheckpoint -Algorithm SHA256).Hash
    output_dir = $resolvedOutput
    python = $resolvedPython
}
$runningManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$args = @('inference.py', '--source', $resolvedSource, '--target', $resolvedTarget, '--output', $resolvedOutput, '--checkpoint', $resolvedCheckpoint, '--config', $resolvedConfig, '--f0-condition', 'False')
if ($Fp16) { $args += @('--fp16', 'True') }

Write-Output "Seed-VC source SHA256: $((Get-FileHash -LiteralPath $resolvedSource -Algorithm SHA256).Hash)"
Write-Output "Seed-VC target SHA256: $((Get-FileHash -LiteralPath $resolvedTarget -Algorithm SHA256).Hash)"
Write-Output "Seed-VC checkpoint SHA256: $((Get-FileHash -LiteralPath $resolvedCheckpoint -Algorithm SHA256).Hash)"
Write-Output "Seed-VC config: $resolvedConfig"
Write-Output "執行官方 Seed-VC inference.py；輸出資料夾：$resolvedOutput"

Push-Location $resolvedRepo
$inferenceText = @()
try {
    $inferenceText = @(& $resolvedPython @args 2>&1 | ForEach-Object { $_.ToString() })
    $inferenceExitCode = $LASTEXITCODE
    $inferenceText | ForEach-Object { Write-Output $_ }
    if ($inferenceExitCode -ne 0) { throw "Seed-VC inference failed with exit code $inferenceExitCode" }
}
catch {
    $failureManifest = [ordered]@{
        status = 'FAIL'
        run_id = $runId
        started_at_utc = $runStartedUtc.ToString('o')
        completed_at_utc = [DateTime]::UtcNow.ToString('o')
        backend = 'seed-vc'
        profile = 'offline-v1'
        failure = $_.Exception.Message
        inference_log = $inferenceText
    }
    $failureManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    throw
}
finally {
    Pop-Location
}

$changedWavs = @(Get-ChildItem -LiteralPath $resolvedOutput -Filter '*.wav' -File -ErrorAction SilentlyContinue | Where-Object {
    $old = $beforeWavs[$_.FullName]
    $newHash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    $createdOrChangedDuringRun = $_.LastWriteTimeUtc -ge $runStartedUtc
    $createdOrChangedDuringRun -and ((-not $old) -or ($old.sha256 -ne $newHash))
})
if ($changedWavs.Count -eq 0) {
    $failureManifest = [ordered]@{
        status = 'FAIL'
        run_id = $runId
        started_at_utc = $runStartedUtc.ToString('o')
        completed_at_utc = [DateTime]::UtcNow.ToString('o')
        backend = 'seed-vc'
        profile = 'offline-v1'
        failure = 'Inference exited successfully but created no new WAV or changed no WAV content; stale output is not accepted.'
        inference_log = $inferenceText
    }
    $failureManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    throw $failureManifest.failure
}

$validatorPython = $resolvedPython
if (-not (Test-Path -LiteralPath $validatorPython -PathType Leaf)) {
    $failureManifest = [ordered]@{
        status = 'WAITING'
        run_id = $runId
        started_at_utc = $runStartedUtc.ToString('o')
        completed_at_utc = [DateTime]::UtcNow.ToString('o')
        backend = 'seed-vc'
        profile = 'offline-v1'
        failure = 'Seed-VC Python is missing; new output cannot be checked with audio_output_validation.py.'
        inference_log = $inferenceText
    }
    $failureManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    throw $failureManifest.failure
}
$validationCode = "import json,sys; sys.path.insert(0,'tools'); from audio_output_validation import validate_wav_file; print(json.dumps(validate_wav_file(__import__('pathlib').Path(sys.argv[1]))))"
$outputFiles = @()
foreach ($wav in $changedWavs) {
    $validationText = & $validatorPython -c $validationCode $wav.FullName 2>&1
    $validationExit = $LASTEXITCODE
    if ($validationExit -ne 0) {
        $failureManifest = [ordered]@{
            status = 'FAIL'
            run_id = $runId
            started_at_utc = $runStartedUtc.ToString('o')
            completed_at_utc = [DateTime]::UtcNow.ToString('o')
            backend = 'seed-vc'
            profile = 'offline-v1'
            failure = "New WAV failed audio_output_validation.py: $($validationText -join ' ')"
            failed_wav = $wav.FullName
            inference_log = $inferenceText
        }
        $failureManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
        throw $failureManifest.failure
    }
    $outputValidation = [string]($validationText | Select-Object -Last 1) | ConvertFrom-Json
    $relativeOutput = if ($wav.FullName.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
        $wav.FullName.Substring($projectRoot.Length + 1)
    }
    else { $wav.FullName }
    $outputFiles += [ordered]@{
        relative_path = $relativeOutput
        bytes = $wav.Length
        sha256 = (Get-FileHash -LiteralPath $wav.FullName -Algorithm SHA256).Hash
        output_validation = $outputValidation
    }
}
if ($outputFiles.Count -eq 0) {
    throw "Seed-VC inference completed but the current run produced no validated WAV output: $resolvedOutput"
}

$manifest = [ordered]@{
    status = 'PASS'
    run_id = $runId
    started_at_utc = $runStartedUtc.ToString('o')
    completed_at_utc = [DateTime]::UtcNow.ToString('o')
    backend = 'seed-vc'
    profile = 'offline-v1'
    python = $resolvedPython
    torch_runtime = (& $resolvedPython -c "import torch; print(torch.__version__ + ' cuda=' + str(torch.version.cuda) + ' available=' + str(torch.cuda.is_available()))" | Select-Object -Last 1).ToString()
    source = [ordered]@{ path = $resolvedSource; sha256 = (Get-FileHash -LiteralPath $resolvedSource -Algorithm SHA256).Hash }
    target = [ordered]@{ path = $resolvedTarget; sha256 = (Get-FileHash -LiteralPath $resolvedTarget -Algorithm SHA256).Hash }
    checkpoint = [ordered]@{ path = $resolvedCheckpoint; sha256 = (Get-FileHash -LiteralPath $resolvedCheckpoint -Algorithm SHA256).Hash }
    config = $resolvedConfig
    output_files = $outputFiles
    inference_log = $inferenceText
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output "Seed-VC manifest: $manifestPath"
