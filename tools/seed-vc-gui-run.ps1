[CmdletBinding()]
param(
    [string]$Python = '.\tools\venvs\seed-vc\Scripts\python.exe',
    [string]$Repo = '.\tools\external\seed-vc',
    [string]$Checkpoint = '.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
    [string]$Config = '.\tools\external\seed-vc\configs\presets\config_dit_mel_seed_uvit_xlsr_tiny.yml',
    [string]$Reference,
    [string]$HostApi,
    [string]$InputDevice,
    [string]$OutputDevice,
    [switch]$ListDevices,
    [switch]$AllowNetworkAssets
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Resolve-PathFromRoot([string]$Path) {
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path $projectRoot $Path))
}

$pythonPath = Resolve-PathFromRoot $Python
$repoPath = Resolve-PathFromRoot $Repo
$checkpointPath = Resolve-PathFromRoot $Checkpoint
$configPath = Resolve-PathFromRoot $Config
$helperPath = Join-Path $PSScriptRoot 'seed-vc-gui-config.py'

foreach ($required in @(
    [pscustomobject]@{ Name = 'Seed-VC Python environment'; Path = $pythonPath },
    [pscustomobject]@{ Name = 'Seed-VC official GUI'; Path = (Join-Path $repoPath 'real-time-gui.py') },
    [pscustomobject]@{ Name = 'realtime-tiny checkpoint'; Path = $checkpointPath },
    [pscustomobject]@{ Name = 'realtime-tiny config'; Path = $configPath },
    [pscustomobject]@{ Name = 'device selection helper'; Path = $helperPath }
)) {
    if (-not (Test-Path -LiteralPath $required.Path -PathType Leaf)) {
        Write-Output "BLOCKED: missing $($required.Name): $($required.Path)"
        Write-Output '先依 docs/seed-vc-assets.md 準備本機檔案；GUI launcher 不會下載主要 checkpoint。'
        exit 2
    }
}

if ($ListDevices) {
    & $pythonPath $helperPath --repo $repoPath --list-devices
    exit $LASTEXITCODE
}

$cacheAssets = @(
    [pscustomobject]@{ Name = 'XLS-R content encoder'; Pattern = 'pytorch_model.bin'; Root = (Join-Path $repoPath 'checkpoints\models--facebook--wav2vec2-xls-r-300m\snapshots') },
    [pscustomobject]@{ Name = 'FunASR CampPlus speaker encoder'; Pattern = 'campplus_cn_common.bin'; Root = (Join-Path $repoPath 'checkpoints\models--funasr--campplus\snapshots') },
    [pscustomobject]@{ Name = 'HiFT vocoder'; Pattern = 'hift.pt'; Root = (Join-Path $repoPath 'checkpoints\models--FunAudioLLM--CosyVoice-300M\snapshots') },
    [pscustomobject]@{ Name = 'FunASR VAD model'; Pattern = 'configuration.json'; Root = (Join-Path $env:USERPROFILE '.cache\modelscope\hub\models\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch') }
)
$missingCache = @()
foreach ($asset in $cacheAssets) {
    $found = if (Test-Path -LiteralPath $asset.Root -PathType Container) {
        Get-ChildItem -LiteralPath $asset.Root -Filter $asset.Pattern -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    } else { $null }
    if ($found) {
        Write-Output "PASS cached runtime asset [$($asset.Name)]: $($found.FullName)"
    } else {
        Write-Output "WAITING cached runtime asset [$($asset.Name)]: $($asset.Root)\$($asset.Pattern)"
        $missingCache += $asset.Name
    }
}
if ($missingCache.Count -gt 0 -and -not $AllowNetworkAssets) {
    Write-Output 'BLOCKED: offline-by-default policy prevents the upstream GUI from downloading missing auxiliary models.'
    Write-Output '先依 docs/seed-vc-assets.md 人工準備並核對本機 cache；只有明確同意執行時才可加 -AllowNetworkAssets。主要 realtime-tiny checkpoint 不會由此參數下載。'
    exit 2
}

$cudaCheck = & $pythonPath -c "import torch; print('cuda=' + str(torch.cuda.is_available()) + ' devices=' + str(torch.cuda.device_count()))"
if ($LASTEXITCODE -ne 0) { throw "Seed-VC Torch preflight failed, exit=$LASTEXITCODE" }
Write-Output "GPU preflight: $cudaCheck"
if (-not ($cudaCheck -match 'cuda=True\s+devices=[1-9]')) {
    Write-Output 'BLOCKED: this GUI launcher requires an available CUDA device at cuda:0.'
    exit 2
}

$configArgs = @('--repo', $repoPath)
if ($HostApi) { $configArgs += @('--host-api', $HostApi) }
if ($InputDevice) { $configArgs += @('--input-device', $InputDevice) }
if ($OutputDevice) { $configArgs += @('--output-device', $OutputDevice) }
if ($Reference) { $configArgs += @('--reference-audio', (Resolve-PathFromRoot $Reference)) }
& $pythonPath $helperPath @configArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($AllowNetworkAssets) {
    Remove-Item Env:HF_HUB_OFFLINE -ErrorAction SilentlyContinue
    Remove-Item Env:TRANSFORMERS_OFFLINE -ErrorAction SilentlyContinue
    Write-Output 'Network model access enabled for this GUI process by explicit -AllowNetworkAssets.'
} else {
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    Write-Output 'Hugging Face/Transformers offline mode is enabled; no large checkpoint auto-download is allowed.'
}

Push-Location $repoPath
try {
    Write-Output '啟動 Seed-VC 官方 realtime GUI：FP32、CUDA device 0。GUI 使用所選實體輸入裝置，不會注入 WAV。'
    & $pythonPath 'real-time-gui.py' '--checkpoint-path' $checkpointPath '--config-path' $configPath '--fp16' 'False' '--gpu' '0'
    if ($LASTEXITCODE -ne 0) { throw "Seed-VC realtime GUI exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
