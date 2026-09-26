[CmdletBinding()]
param(
    [string]$Python310,
    [string]$Environment = '.\tools\venvs\seed-vc',
    [string]$Repo = '.\tools\external\seed-vc',
    [string]$ModelScopeVadCache,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$expectedRevision = '51383efd921027683c89e5348211d93ff12ac2a8'
$repoPath = [IO.Path]::GetFullPath($Repo)
$envRoot = [IO.Path]::GetFullPath($Environment)
$envPython = Join-Path $envRoot 'Scripts\python.exe'
$missing = [System.Collections.Generic.List[string]]::new()

function Resolve-Python310Path {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (Test-Path -LiteralPath $RequestedPath -PathType Leaf) {
            return [IO.Path]::GetFullPath($RequestedPath)
        }
        return $null
    }

    # 先從既有 venv 的 pyvenv.cfg 找 base interpreter；這比假設安裝目錄可靠。
    $venvCfg = Join-Path (Split-Path -Parent $PSScriptRoot) 'tools\venvs\seed-vc\pyvenv.cfg'
    if (Test-Path -LiteralPath $venvCfg -PathType Leaf) {
        $homeLine = Get-Content -LiteralPath $venvCfg -Encoding UTF8 | Where-Object { $_ -match '^home\s*=' } | Select-Object -First 1
        if ($homeLine -match '^home\s*=\s*(.+)$') {
            $fromVenv = Join-Path $Matches[1].Trim() 'python.exe'
            if (Test-Path -LiteralPath $fromVenv -PathType Leaf) { return [IO.Path]::GetFullPath($fromVenv) }
        }
    }

    # 從目前登入者的安裝根目錄探索，不把某個 Windows 帳號名稱寫進專案。
    $localPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'
    if (Test-Path -LiteralPath $localPython -PathType Leaf) { return [IO.Path]::GetFullPath($localPython) }

    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $candidate = & $launcher.Source -3.10 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) {
            $candidatePath = [string]($candidate | Select-Object -Last 1)
            if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
                return [IO.Path]::GetFullPath($candidatePath)
            }
        }
    }
    return $null
}

$resolvedPython = Resolve-Python310Path -RequestedPath $Python310
if (-not $resolvedPython) {
    $missing.Add('Python 3.10 x64 executable (install it or pass -Python310 <python.exe>)')
}

$repoFiles = @(
    'inference.py',
    'real-time-gui.py',
    'requirements.txt',
    'configs\presets\config_dit_mel_seed_uvit_whisper_small_wavenet.yml',
    'configs\presets\config_dit_mel_seed_uvit_xlsr_tiny.yml',
    'configs\hifigan.yml'
)
foreach ($relativePath in $repoFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoPath $relativePath))) {
        $missing.Add("Seed-VC required file/cache is missing: $relativePath")
    }
}
foreach ($projectAsset in @(
    'models\seed-vc\checkpoints\offline-v1\DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth',
    'models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $projectAsset) -PathType Leaf)) {
        $missing.Add("Project-local Seed-VC checkpoint is missing: $projectAsset; setup will not download it")
    }
}

$hfAssetMap = @{
    'models--facebook--wav2vec2-xls-r-300m' = @('pytorch_model.bin', 'config.json', 'preprocessor_config.json')
    'models--funasr--campplus' = @('campplus_cn_common.bin')
    'models--FunAudioLLM--CosyVoice-300M' = @('hift.pt')
}
foreach ($repoName in $hfAssetMap.Keys) {
    $cachePath = Join-Path (Join-Path $repoPath 'checkpoints') $repoName
    $refPath = Join-Path $cachePath 'refs\main'
    if (-not (Test-Path -LiteralPath $refPath -PathType Leaf)) {
        $missing.Add("Pinned local Hugging Face cache reference is missing: $repoName\refs\main")
        continue
    }
    $snapshotId = (Get-Content -LiteralPath $refPath -Raw -Encoding UTF8).Trim()
    if (-not $snapshotId -or $snapshotId -notmatch '^[0-9a-fA-F]{7,64}$') {
        $missing.Add("Invalid Hugging Face snapshot reference in $repoName\refs\main")
        continue
    }
    foreach ($assetName in $hfAssetMap[$repoName]) {
        $assetPath = Join-Path (Join-Path (Join-Path $cachePath 'snapshots') $snapshotId) $assetName
        if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf) -or (Get-Item -LiteralPath $assetPath -ErrorAction SilentlyContinue).Length -le 0) {
            $missing.Add("Required cached model file is missing/empty: $repoName\snapshots\$snapshotId\$assetName")
        }
    }
}

if ($ModelScopeVadCache) { $vadModelPath = [IO.Path]::GetFullPath($ModelScopeVadCache) }
elseif ($env:MODELSCOPE_CACHE) { $vadModelPath = Join-Path ([IO.Path]::GetFullPath($env:MODELSCOPE_CACHE)) 'hub\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch' }
else { $vadModelPath = Join-Path $env:USERPROFILE '.cache\modelscope\hub\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch' }
foreach ($vadAsset in @('model.pt', 'config.yaml', 'configuration.json', 'am.mvn')) {
    $vadFile = Join-Path $vadModelPath $vadAsset
    if (-not (Test-Path -LiteralPath $vadFile -PathType Leaf) -or (Get-Item -LiteralPath $vadFile -ErrorAction SilentlyContinue).Length -le 0) {
        $missing.Add("Required local ModelScope VAD asset is missing/empty: $vadFile")
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $repoPath '.git'))) {
    $missing.Add('Seed-VC source checkout is missing its .git metadata; setup will not clone or change third-party source')
}
else {
    $actualRevision = (& git -C $repoPath rev-parse HEAD 2>$null | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or $actualRevision -ne $expectedRevision) {
        $missing.Add("Seed-VC revision must be $expectedRevision (actual: $actualRevision); review and pin the source manually")
    }
}

$pythonProbe = $null
if ($resolvedPython) {
    $pythonProbeText = & $resolvedPython -c "import json,sys; p={'version':list(sys.version_info[:3]),'bits':__import__('struct').calcsize('P')*8}; import tkinter; t=tkinter.Tcl(); p['tcl']=t.eval('info patchlevel'); t.call('package','require','Tk'); p['tk']='available'; print(json.dumps(p))" 2>&1
    $pythonProbeExit = $LASTEXITCODE
    if ($pythonProbeExit -eq 0) {
        try {
            $pythonProbe = [string]($pythonProbeText | Select-Object -Last 1) | ConvertFrom-Json
            if ($pythonProbe.version[0] -ne 3 -or $pythonProbe.version[1] -ne 10) {
                $missing.Add("Python must be 3.10.x (found $($pythonProbe.version -join '.'))")
            }
            if ($pythonProbe.bits -ne 64) { $missing.Add('Python must be 64-bit') }
        }
        catch { $missing.Add('Python 3.10 Tcl/Tk preflight returned unreadable output') }
    }
    else {
        $detail = ($pythonProbeText | ForEach-Object { $_.ToString() }) -join ' '
        $missing.Add("Python 3.10 Tcl/Tk is unavailable: $detail")
    }
}

$preflight = [ordered]@{
    status = if ($missing.Count -eq 0) { 'PASS' } else { 'BLOCKED' }
    source = $repoPath
    expected_revision = $expectedRevision
    python = $resolvedPython
    python_probe = $pythonProbe
    modelscope_vad_path = $vadModelPath
    modelscope_vad_model_sha256 = if (Test-Path -LiteralPath (Join-Path $vadModelPath 'model.pt') -PathType Leaf) { (Get-FileHash -LiteralPath (Join-Path $vadModelPath 'model.pt') -Algorithm SHA256).Hash } else { $null }
    environment = $envRoot
    would_download_models = $false
    missing = @($missing)
}
Write-Output ($preflight | ConvertTo-Json -Depth 6)
if ($missing.Count -gt 0) {
    throw "Seed-VC preflight blocked before pip changes. Resolve every listed prerequisite, then rerun."
}
if ($PreflightOnly) { return }

if (-not (Test-Path -LiteralPath $envPython -PathType Leaf)) {
    Write-Output "建立獨立 Seed-VC Python environment：$envRoot"
    & $resolvedPython -m venv $envRoot
    if ($LASTEXITCODE -ne 0) { throw "建立 venv 失敗，exit=$LASTEXITCODE" }
}

Write-Output '更新 packaging tools'
& $envPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "更新 packaging tools 失敗，exit=$LASTEXITCODE" }

Write-Output '安裝 Torch CUDA 12.8 runtime（不下載 Seed-VC checkpoint）'
& $envPython -m pip install --index-url 'https://download.pytorch.org/whl/cu128' `
    'torch==2.7.1+cu128' 'torchaudio==2.7.1+cu128' 'torchvision==0.22.1+cu128'
if ($LASTEXITCODE -ne 0) { throw "安裝 Torch CUDA runtime 失敗，exit=$LASTEXITCODE" }

$requirementsPath = Join-Path $repoPath 'requirements.txt'
$packages = Get-Content -LiteralPath $requirementsPath -Encoding UTF8 |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith('#') -and $_ -notmatch '^--' -and $_ -notmatch '^(torch|torchvision|torchaudio)(\s|=|$)' }

Write-Output '安裝 Seed-VC requirements.txt 內的其餘相依套件'
& $envPython -m pip install @packages
if ($LASTEXITCODE -ne 0) { throw "安裝 Seed-VC 依賴失敗，exit=$LASTEXITCODE" }

& $envPython -c "import torch, torchaudio, torchvision, munch, dac, funasr, tkinter; t=tkinter.Tcl(); t.call('package','require','Tk'); print('Seed-VC imports and Tcl/Tk PASS'); print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw "Seed-VC import/Tcl-Tk smoke test 失敗，exit=$LASTEXITCODE" }

Write-Output "Seed-VC environment ready: $envPython"
