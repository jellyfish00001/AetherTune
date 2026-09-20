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

foreach ($path in @($Source, $Target)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "找不到音檔：$path"
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $Repo 'inference.py') -PathType Leaf)) {
    throw "找不到 Seed-VC inference.py：$Repo；請先依 backends/seed-vc/README.md 建立獨立環境與 repo。"
}
if (-not (Test-Path -LiteralPath $Checkpoint -PathType Leaf)) {
    throw "找不到 checkpoint：$Checkpoint；請先下載官方 Seed-VC offline-v1 checkpoint。"
}
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    throw "找不到 Seed-VC config：$Config"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "找不到 Seed-VC Python environment：$Python；請先執行 tools\seed-vc-setup.ps1"
}

$resolvedOutput = [IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null
$resolvedSource = [IO.Path]::GetFullPath($Source)
$resolvedTarget = [IO.Path]::GetFullPath($Target)
$resolvedRepo = [IO.Path]::GetFullPath($Repo)
$resolvedCheckpoint = [IO.Path]::GetFullPath($Checkpoint)
$resolvedConfig = [IO.Path]::GetFullPath($Config)
$resolvedPython = [IO.Path]::GetFullPath($Python)

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
finally {
    Pop-Location
}

$outputFiles = @(Get-ChildItem -LiteralPath $resolvedOutput -Filter '*.wav' -File -ErrorAction SilentlyContinue | ForEach-Object {
    [ordered]@{
        relative_path = $_.FullName.Substring($projectRoot.Length + 1)
        bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
})
if ($outputFiles.Count -eq 0) {
    throw "Seed-VC inference completed but no WAV output was found: $resolvedOutput"
}

$manifest = [ordered]@{
    status = 'PASS'
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
$manifestPath = Join-Path $resolvedOutput 'seed-vc-run.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output "Seed-VC manifest: $manifestPath"
