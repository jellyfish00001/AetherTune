[CmdletBinding()]
param(
    [string]$Python310,
    [string]$Environment = '.\tools\venvs\seed-vc',
    [string]$SeedVcRepo = '.\tools\external\seed-vc',
    [string]$RealtimeCheckpoint = '.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
    [string]$RealtimeConfig = '.\tools\external\seed-vc\configs\presets\config_dit_mel_seed_uvit_xlsr_tiny.yml',
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Resolve-ProjectPath([string]$Path) {
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path $projectRoot $Path))
}

function Find-Python310 {
    $candidates = @()
    if ($Python310) {
        $provided = Resolve-ProjectPath $Python310
        if (Test-Path -LiteralPath $provided -PathType Leaf) {
            $candidates += [pscustomobject]@{ Exe = $provided; Prefix = @() }
        } else {
            Write-Output "BLOCKED Python 3.10 path does not exist: $provided"
        }
    } else {
        foreach ($name in @('python3.10', 'python')) {
            $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($command -and $command.Source) {
                $candidates += [pscustomobject]@{ Exe = $command.Source; Prefix = @() }
            }
        }
        $launcher = Get-Command 'py' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($launcher -and $launcher.Source) {
            $candidates += [pscustomobject]@{ Exe = $launcher.Source; Prefix = @('-3.10') }
        }
    }

    foreach ($candidate in $candidates) {
        try {
            $versionArgs = @($candidate.Prefix) + @('-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            $version = (& $candidate.Exe @versionArgs 2>$null | Select-Object -Last 1).ToString().Trim()
            if ($LASTEXITCODE -eq 0 -and $version -eq '3.10') { return $candidate }
        } catch { }
    }
    return $null
}

$repo = Resolve-ProjectPath $SeedVcRepo
$requirements = Join-Path $repo 'requirements.txt'
$gui = Join-Path $repo 'real-time-gui.py'
$configFile = Resolve-ProjectPath $RealtimeConfig
$checkpoint = Resolve-ProjectPath $RealtimeCheckpoint
$environmentRoot = Resolve-ProjectPath $Environment
$environmentPython = Join-Path $environmentRoot 'Scripts\python.exe'

$pythonCandidate = Find-Python310
$inventory = @(
    [pscustomobject]@{ Kind = 'SETUP_REQUIRED'; Name = 'Python 3.10 base interpreter'; Path = if ($pythonCandidate) { $pythonCandidate.Exe } else { '<not found: supply -Python310 or install Python 3.10>' }; Exists = [bool]$pythonCandidate },
    [pscustomobject]@{ Kind = 'SETUP_REQUIRED'; Name = 'Seed-VC upstream source'; Path = $repo; Exists = (Test-Path -LiteralPath $gui -PathType Leaf) },
    [pscustomobject]@{ Kind = 'SETUP_REQUIRED'; Name = 'Seed-VC requirements.txt'; Path = $requirements; Exists = (Test-Path -LiteralPath $requirements -PathType Leaf) },
    [pscustomobject]@{ Kind = 'GUI_REQUIRED'; Name = 'realtime-tiny checkpoint'; Path = $checkpoint; Exists = (Test-Path -LiteralPath $checkpoint -PathType Leaf) },
    [pscustomobject]@{ Kind = 'GUI_REQUIRED'; Name = 'realtime-tiny config'; Path = $configFile; Exists = (Test-Path -LiteralPath $configFile -PathType Leaf) },
    [pscustomobject]@{ Kind = 'RUNTIME_CACHE'; Name = 'XLS-R content encoder'; Path = (Join-Path $repo 'checkpoints\models--facebook--wav2vec2-xls-r-300m\snapshots'); Pattern = 'pytorch_model.bin'; Exists = $false },
    [pscustomobject]@{ Kind = 'RUNTIME_CACHE'; Name = 'FunASR CampPlus speaker encoder'; Path = (Join-Path $repo 'checkpoints\models--funasr--campplus\snapshots'); Pattern = 'campplus_cn_common.bin'; Exists = $false },
    [pscustomobject]@{ Kind = 'RUNTIME_CACHE'; Name = 'HiFT vocoder'; Path = (Join-Path $repo 'checkpoints\models--FunAudioLLM--CosyVoice-300M\snapshots'); Pattern = 'hift.pt'; Exists = $false },
    [pscustomobject]@{ Kind = 'RUNTIME_CACHE'; Name = 'FunASR VAD cache'; Path = (Join-Path $env:USERPROFILE '.cache\modelscope\hub\models\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch'); Pattern = 'configuration.json'; Exists = $false }
)

foreach ($item in @($inventory | Where-Object { $_.Kind -eq 'RUNTIME_CACHE' })) {
    $foundAsset = if (Test-Path -LiteralPath $item.Path -PathType Container) {
        Get-ChildItem -LiteralPath $item.Path -Filter $item.Pattern -File -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1
    } else { $null }
    $item.Exists = [bool]$foundAsset
    $item.Path = if ($foundAsset) { $foundAsset.FullName } else { Join-Path $item.Path "**\$($item.Pattern)" }
}

Write-Output 'Seed-VC asset preflight (read-only; no download, install, or audio-device changes):'
foreach ($item in $inventory) {
    $state = if ($item.Exists) { 'PASS' } else { if ($item.Kind -eq 'RUNTIME_CACHE') { 'WAITING' } else { 'MISSING' } }
    Write-Output ("{0} [{1}] {2} :: {3}" -f $state, $item.Kind, $item.Name, $item.Path)
}

$setupMissing = @($inventory | Where-Object { $_.Kind -eq 'SETUP_REQUIRED' -and -not $_.Exists })
$guiMissing = @($inventory | Where-Object { $_.Kind -eq 'GUI_REQUIRED' -and -not $_.Exists })
$runtimeMissing = @($inventory | Where-Object { $_.Kind -eq 'RUNTIME_CACHE' -and -not $_.Exists })
if ($setupMissing.Count -gt 0) {
    Write-Output 'BLOCKED: setup prerequisites are missing. No pip command was run.'
    Write-Output '取得官方 Seed-VC source、requirements.txt 與 Python 3.10 後重跑；本腳本不會 clone repo 或下載 checkpoints。'
    exit 2
}

if ($guiMissing.Count -gt 0) {
    Write-Output 'WAITING: GUI model assets are incomplete. Setup can prepare the isolated venv, but GUI launch remains blocked until these files are supplied locally.'
    Write-Output '請先依 docs/seed-vc-assets.md 取得並核對 realtime-tiny checkpoint/config；不會自動下載大型權重。'
}
if ($PreflightOnly) {
    if ($guiMissing.Count -gt 0 -or $runtimeMissing.Count -gt 0) { exit 3 }
    exit 0
}

if (-not (Test-Path -LiteralPath $environmentPython -PathType Leaf)) {
    Write-Output "建立 Seed-VC Python environment：$environmentRoot"
    $venvArgs = @($pythonCandidate.Prefix) + @('-m', 'venv', $environmentRoot)
    & $pythonCandidate.Exe @venvArgs
    if ($LASTEXITCODE -ne 0) { throw "建立 venv 失敗，exit=$LASTEXITCODE" }
}

Write-Output '更新 pip/setuptools/wheel'
& $environmentPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "更新 packaging tools 失敗，exit=$LASTEXITCODE" }

Write-Output '安裝與目前專案 GPU runtime 對齊的 Torch CUDA 12.8'
& $environmentPython -m pip install --index-url 'https://download.pytorch.org/whl/cu128' `
    'torch==2.7.1+cu128' 'torchaudio==2.7.1+cu128' 'torchvision==0.22.1+cu128'
if ($LASTEXITCODE -ne 0) { throw "安裝 Torch CUDA runtime 失敗，exit=$LASTEXITCODE" }

$packages = Get-Content -LiteralPath $requirements -Encoding UTF8 |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith('#') -and $_ -notmatch '^--' -and $_ -notmatch '^(torch|torchvision|torchaudio)(\s|=|$)' }

Write-Output '安裝 Seed-VC 其他官方依賴（略過 requirements.txt 內舊 Torch pin）'
& $environmentPython -m pip install @packages
if ($LASTEXITCODE -ne 0) { throw "安裝 Seed-VC 依賴失敗，exit=$LASTEXITCODE" }

& $environmentPython -c "import torch, torchaudio, torchvision, munch, dac, funasr; print('Seed-VC imports PASS'); print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw "Seed-VC import smoke test 失敗，exit=$LASTEXITCODE" }

Write-Output "Seed-VC environment ready: $environmentPython"
if ($guiMissing.Count -gt 0) { Write-Output 'WAITING: install is complete, but GUI cannot start until the local checkpoint and config are supplied.' }
if ($runtimeMissing.Count -gt 0) { Write-Output 'WAITING: runtime cache files are incomplete; GUI launch remains blocked until each required local asset exists.' }
