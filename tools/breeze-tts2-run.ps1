[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$TextFile,
    [Parameter(Mandatory = $true)] [string]$Output,
    [string]$ReferenceAudio = '',
    [string]$ReferenceTextFile = '',
    [string]$Instruction = '',
    [double]$CfgScale = 1.0,
    [int]$Seed = 42,
    [switch]$FastAll,
    [ValidateSet('eager', 'flash_attention_2')][string]$AttentionImplementation = 'eager',
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
$wslEnv = @("PYTHONPATH=$breezeRepo")
$defaultWslPath = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
$localSoxRoot = Join-Path $projectRoot 'artifacts\sox-local'
if (Test-Path -LiteralPath (Join-Path $localSoxRoot 'usr\bin\sox')) {
    # SoX 可能以無 sudo 的 .deb extraction 存在；只注入這個被 gitignore 的
    # local runtime，避免改動 WSL 系統套件或把 binary 放進 repository。
    $soxBin = Convert-ToWslPath (Join-Path $localSoxRoot 'usr\bin')
    $soxLib = Convert-ToWslPath (Join-Path $localSoxRoot 'usr\lib\x86_64-linux-gnu')
    $wslEnv += ("PATH={0}:{1}" -f $soxBin, $defaultWslPath)
    $wslEnv += ("LD_LIBRARY_PATH={0}:/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu" -f $soxLib)
    Write-Output "Breeze project-local SoX: $soxBin/sox"
}

$arguments = @(
    $runnerPath,
    '--model-dir', $modelPath,
    '--text-file', $textPath,
    '--output', $outputPath,
    '--cfg-scale', $CfgScale.ToString([Globalization.CultureInfo]::InvariantCulture),
    '--seed', $Seed.ToString(),
    '--attention-implementation', $AttentionImplementation
)
if ($FastAll) { $arguments += '--fast-all' }
if ($Instruction) { $arguments += @('--instruction', $Instruction) }
if ($ReferenceAudio) {
    if (-not $ReferenceTextFile) { throw 'ReferenceAudio 需要同時提供 ReferenceTextFile' }
    $arguments += @('--reference-audio', (Convert-ToWslPath $ReferenceAudio))
    $arguments += @('--reference-text-file', (Convert-ToWslPath $ReferenceTextFile))
}

& wsl.exe -d $Distro -- env @wslEnv $pythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Breeze TTS 2 inference failed with exit=$LASTEXITCODE"
}
