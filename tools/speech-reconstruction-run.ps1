[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$InputWav,
    [ValidateSet('cosyvoice', 'breeze-tts-2')] [string]$Backend = 'cosyvoice',
    [string]$OutputDir = '.\artifacts\speech-reconstruction',
    [string]$Output = '',
    [string]$TextFile = '',
    [string]$ReferenceAudio = '',
    [string]$ReferenceTextFile = '',
    [switch]$ReferenceTextVerified,
    [string]$Instruction = 'A natural, clear, warm speaking voice with a medium pace.',
    [string]$SttModel = 'small',
    [string]$Language = '',
    [string]$Distro = 'Ubuntu'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Convert-ToWslPath([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        $resolved = (Resolve-Path -LiteralPath $Path).Path
    } else {
        $parent = Split-Path -Parent $Path
        if (-not $parent) { $parent = '.' }
        $resolved = Join-Path (Resolve-Path -LiteralPath $parent).Path (Split-Path -Leaf $Path)
    }
    if ($resolved -notmatch '^[A-Za-z]:\\') {
        throw "Only Windows drive paths are supported: $Path"
    }
    $drive = $resolved.Substring(0, 1).ToLowerInvariant()
    return "/mnt/$drive" + ($resolved.Substring(2) -replace '\\', '/')
}

function Quote-Bash([string]$Value) {
    return "'" + ($Value -replace "'", "'\\''") + "'"
}

function Invoke-Wsl([string]$Command) {
    & wsl.exe -d $Distro -- bash -lc $Command
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed with exit=$LASTEXITCODE"
    }
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8)
}

if (-not (Test-Path -LiteralPath $InputWav -PathType Leaf)) {
    throw "找不到輸入音檔：$InputWav"
}
$inputPath = (Resolve-Path -LiteralPath $InputWav).Path
if ($ReferenceTextVerified -and -not $ReferenceTextFile) {
    throw '-ReferenceTextVerified 必須與 -ReferenceTextFile 一起提供'
}
$outputRoot = (New-Item -ItemType Directory -Force -Path $OutputDir).FullName
$inputItem = Get-Item -LiteralPath $inputPath
$stem = $inputItem.BaseName
if (-not $Output) {
    $Output = Join-Path $outputRoot "$stem-$Backend.wav"
} elseif (-not [System.IO.Path]::IsPathRooted($Output)) {
    if (Split-Path -Parent $Output) {
        $Output = Join-Path $projectRoot $Output
    } else {
        $Output = Join-Path $outputRoot $Output
    }
}
$outputPath = [System.IO.Path]::GetFullPath($Output)
$outputParent = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Force -Path $outputParent | Out-Null

# 未指定 reference 時，使用輸入音檔作為目標聲線；這適合快速 smoke test。
# ReferenceTextFile 只代表 reference audio 的 prompt transcript；TextFile 只代表要合成的目標文字。
$referencePath = $inputPath
if ($ReferenceAudio) {
    if (-not (Test-Path -LiteralPath $ReferenceAudio -PathType Leaf)) {
        throw "找不到 reference 音檔：$ReferenceAudio"
    }
    $referencePath = (Resolve-Path -LiteralPath $ReferenceAudio).Path
}

$sttVenvPython = '/mnt/d/AetherTune/tools/venvs/stt-wsl/bin/python'
$sttRunner = Convert-ToWslPath (Join-Path $projectRoot 'tools\stt-transcribe.py')
$sttRecords = @()

function Invoke-Stt([string]$AudioPath, [string]$Label) {
    $audioItem = Get-Item -LiteralPath $AudioPath
    $jsonPath = Join-Path $outputRoot "stt-$Label-$($audioItem.BaseName).json"
    $textPath = Join-Path $outputRoot "transcript-$Label-$($audioItem.BaseName).txt"
    $command = "set -e; $(Quote-Bash $sttVenvPython) $(Quote-Bash $sttRunner) --input $(Quote-Bash (Convert-ToWslPath $AudioPath)) --output $(Quote-Bash (Convert-ToWslPath $jsonPath)) --model $(Quote-Bash $SttModel)"
    if ($Language) { $command += " --language $(Quote-Bash $Language)" }
    $null = Invoke-Wsl $command
    $manifest = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $manifest.text) { throw "STT 沒有產生文字：$AudioPath" }
    Write-Utf8NoBom $textPath $manifest.text
    $script:sttRecords += [PSCustomObject]@{ label = $Label; audio = $AudioPath; json = $jsonPath; text = $textPath; language = $manifest.language; manual_review_required = $true }
    return $textPath
}

$ttsTextPath = $TextFile
if ($ttsTextPath) {
    if (-not (Test-Path -LiteralPath $ttsTextPath -PathType Leaf)) { throw "找不到 TTS 文字檔：$ttsTextPath" }
    $ttsTextPath = (Resolve-Path -LiteralPath $ttsTextPath).Path
} else {
    $ttsTextPath = Invoke-Stt $inputPath 'source'
}

$promptTextPath = $ReferenceTextFile
$referenceTextSource = 'stt_draft_reference_audio'
$referenceTextWasVerified = $false
if ($promptTextPath) {
    if (-not (Test-Path -LiteralPath $promptTextPath -PathType Leaf)) { throw "找不到 reference transcript：$promptTextPath" }
    $promptTextPath = (Resolve-Path -LiteralPath $promptTextPath).Path
    if ($ReferenceTextVerified) {
        $referenceTextSource = 'caller_provided_verified'
        $referenceTextWasVerified = $true
    } else {
        $referenceTextSource = 'caller_provided_unverified'
    }
} elseif ($referencePath -eq $inputPath -and -not $TextFile) {
    $promptTextPath = $ttsTextPath
    $referenceTextSource = 'stt_draft_reused_same_audio'
} else {
    $promptTextPath = Invoke-Stt $referencePath 'reference'
    $referenceTextSource = 'stt_draft_reference_audio'
}

if ($Backend -eq 'cosyvoice') {
    $modelWsl = Convert-ToWslPath (Join-Path $projectRoot 'models\speech-reconstruction\cosyvoice')
    $runnerWsl = Convert-ToWslPath (Join-Path $projectRoot 'tools\cosyvoice-infer.py')
    $referenceWsl = Convert-ToWslPath $referencePath
    $promptTextWsl = Convert-ToWslPath $promptTextPath
    $ttsTextWsl = Convert-ToWslPath $ttsTextPath
    $outputWsl = Convert-ToWslPath $outputPath
    $cosyPython = '/mnt/d/AetherTune/tools/venvs/cosyvoice-wsl/bin/python'
    $cosyRepo = '/mnt/d/AetherTune/tools/external/CosyVoice'
    $matchaRepo = '/mnt/d/AetherTune/tools/external/CosyVoice/third_party/Matcha-TTS'
    $command = "set -e; unset CUDA_VISIBLE_DEVICES; export PYTHONPATH=$(Quote-Bash $cosyRepo):$(Quote-Bash $matchaRepo); export HF_HUB_OFFLINE=1; $(Quote-Bash $cosyPython) -u $(Quote-Bash $runnerWsl) --model-dir $(Quote-Bash $modelWsl) --prompt-audio $(Quote-Bash $referenceWsl) --prompt-text-file $(Quote-Bash $promptTextWsl) --text-file $(Quote-Bash $ttsTextWsl) --output $(Quote-Bash $outputWsl) --fp16"
    Invoke-Wsl $command
} else {
    $breezeRunner = Join-Path $projectRoot 'tools\breeze-tts2-run.ps1'
    $breezeParameters = @{
        TextFile = $ttsTextPath
        Output = $outputPath
        Distro = $Distro
    }
    if ($ReferenceAudio -or $referencePath -eq $inputPath) {
        $breezeParameters.ReferenceAudio = $referencePath
        $breezeParameters.ReferenceTextFile = $promptTextPath
    } elseif ($Instruction) {
        $breezeParameters.Instruction = $Instruction
    }
    & $breezeRunner @breezeParameters
    if ($LASTEXITCODE -ne 0) { throw "Breeze TTS 2 wrapper failed with exit=$LASTEXITCODE" }
}

$workflowManifest = [ordered]@{
    status = 'PASS'
    backend = $Backend
    input_audio = $inputPath
    reference_audio = $referencePath
    tts_text_file = $ttsTextPath
    reference_text_file = $promptTextPath
    tts_text_source = if ($TextFile) { 'caller_text_file' } else { 'stt_draft_source_audio' }
    reference_text_source = $referenceTextSource
    reference_text_verified = $referenceTextWasVerified
    reference_audio_equals_input = ($referencePath -eq $inputPath)
    output = $outputPath
    stt = @($sttRecords)
    manual_review_required = (-not $referenceTextWasVerified)
    note = 'TextFile 是目標合成內容；ReferenceTextFile 是 reference audio 的 prompt transcript。只有明確指定 -ReferenceTextVerified 才會標示 caller_provided_verified；STT draft 或未核對的 caller text 仍需人工逐字確認。'
}
$workflowManifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ([System.IO.Path]::ChangeExtension($outputPath, '.workflow.json')) -Encoding UTF8
Write-Output ($workflowManifest | ConvertTo-Json -Depth 6)
