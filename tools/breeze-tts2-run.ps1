[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$TextFile,
    [Parameter(Mandatory = $true)] [string]$Output,
    [string]$ReferenceAudio = '',
    [string]$ReferenceTextFile = '',
    [string]$Instruction = '',
    [double]$CfgScale = 1.0,
    [int]$Seed = 42,
    [string]$Distro = 'Ubuntu'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

function Convert-ToWslPath([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        $resolved = (Resolve-Path -LiteralPath $Path).Path
    } else {
        $parent = Split-Path -Parent $Path
        if (-not $parent) { $parent = '.' }
        $resolved = Join-Path (Resolve-Path -LiteralPath $parent).Path (Split-Path -Leaf $Path)
    }
    $drive = $resolved.Substring(0, 1).ToLowerInvariant()
    return "/mnt/$drive" + ($resolved.Substring(2) -replace '\\', '/')
}

$textPath = Convert-ToWslPath $TextFile
$outputParent = Split-Path -Parent $Output
if (-not $outputParent) { $outputParent = '.' }
New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
$outputPath = Convert-ToWslPath (Join-Path (Resolve-Path -LiteralPath $outputParent).Path (Split-Path -Leaf $Output))
$modelPath = Convert-ToWslPath (Join-Path $projectRoot 'models\speech-reconstruction\breeze-tts-2')
$runnerPath = Convert-ToWslPath (Join-Path $projectRoot 'tools\breeze-tts2-infer.py')
$pythonPath = '/mnt/d/AetherTune/tools/venvs/breeze-tts-wsl/bin/python'
$breezeRepo = '/mnt/d/AetherTune/tools/external/breeze-tts'

$arguments = @(
    $runnerPath,
    '--model-dir', $modelPath,
    '--text-file', $textPath,
    '--output', $outputPath,
    '--cfg-scale', $CfgScale.ToString([Globalization.CultureInfo]::InvariantCulture),
    '--seed', $Seed.ToString()
)
if ($Instruction) { $arguments += @('--instruction', $Instruction) }
if ($ReferenceAudio) {
    if (-not $ReferenceTextFile) { throw 'ReferenceAudio 需要同時提供 ReferenceTextFile' }
    $arguments += @('--reference-audio', (Convert-ToWslPath $ReferenceAudio))
    $arguments += @('--reference-text-file', (Convert-ToWslPath $ReferenceTextFile))
}

& wsl.exe -d $Distro -- env "PYTHONPATH=$breezeRepo" $pythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Breeze TTS 2 inference failed with exit=$LASTEXITCODE"
}
