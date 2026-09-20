[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

function Show-State([string]$Name, [string]$Status, [string]$Detail) {
    [PSCustomObject]@{ component = $Name; status = $Status; detail = $Detail }
}

$rows = @()
$rows += Show-State 'RVC venv' ($(if (Test-Path $python) { 'PASS' } else { 'WAITING' })) $python

$seedRepo = Join-Path $projectRoot 'tools\external\seed-vc'
$rows += Show-State 'Seed-VC source' ($(if (Test-Path (Join-Path $seedRepo 'inference.py')) { 'PASS' } else { 'WAITING' })) $seedRepo
$seedPython = Join-Path $projectRoot 'tools\venvs\seed-vc\Scripts\python.exe'
$rows += Show-State 'Seed-VC isolated Python' ($(if (Test-Path $seedPython) { 'PASS' } else { 'WAITING' })) $seedPython
foreach ($checkpoint in @(
    'models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
    'models\seed-vc\checkpoints\offline-v1\DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth'
)) {
    $checkpointPath = Join-Path $projectRoot $checkpoint
    $rows += Show-State "Seed-VC checkpoint $(Split-Path $checkpoint -Leaf)" ($(if (Test-Path $checkpointPath) { 'PASS' } else { 'WAITING' })) $checkpointPath
}

$referenceDir = Join-Path $projectRoot 'dataset\reference-voices'
foreach ($voice in @('voice-female-f1.wav', 'voice-male-m1.wav')) {
    $path = Join-Path $referenceDir $voice
    $rows += Show-State "Reference $voice" ($(if (Test-Path $path) { 'PASS' } else { 'WAITING' })) $path
}

$cosyDir = Join-Path $projectRoot 'models\speech-reconstruction\cosyvoice'
$breezeDir = Join-Path $projectRoot 'models\speech-reconstruction\breeze-tts-2'
$cosyPython = Join-Path $projectRoot 'tools\venvs\cosyvoice-wsl\bin\python'
$rows += Show-State 'CosyVoice WSL Python' ($(if (Test-Path $cosyPython) { 'PASS' } else { 'WAITING' })) $cosyPython
$cosyWeights = @(Get-ChildItem -LiteralPath $cosyDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in @('.safetensors', '.bin', '.pt') })
$breezeWeights = @(Get-ChildItem -LiteralPath $breezeDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in @('.safetensors', '.bin', '.pt') })
$cosyReady = (Test-Path (Join-Path $cosyDir 'config.json')) -and ($cosyWeights.Count -gt 0)
$breezeReady = (Test-Path (Join-Path $breezeDir 'config.json')) -and ($breezeWeights.Count -gt 0)
$rows += Show-State 'CosyVoice model' ($(if ($cosyReady) { 'PASS' } else { 'PLANNED' })) "$cosyDir (weights=$($cosyWeights.Count))"
$rows += Show-State 'Breeze TTS 2 model' ($(if ($breezeReady) { 'PASS' } else { 'PLANNED' })) "$breezeDir (weights=$($breezeWeights.Count))"

$rows | Format-Table -AutoSize
Write-Output '狀態意義：PASS=指定檔案或環境已存在；WAITING=可建立但尚未下載/安裝或 runtime gate 未完成；PLANNED=需獨立環境與上游條件。這不是端到端語音品質驗收。'
