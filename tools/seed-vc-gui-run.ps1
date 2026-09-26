#Requires -Version 7.0
[CmdletBinding()]
param(
    [string]$Python = '.\tools\venvs\seed-vc\Scripts\python.exe',
    [string]$Repo = '.\tools\external\seed-vc',
    [string]$Checkpoint = '.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
    [string]$Config = '.\tools\external\seed-vc\configs\presets\config_dit_mel_seed_uvit_xlsr_tiny.yml',
    [string]$SessionRoot = '.\artifacts\seed-vc\gui-session',
    [string]$ModelScopeVadCache,
    [string]$InputDeviceName,
    [string]$OutputDeviceName,
    [string]$HostApi,
    [string]$ReferenceWav,
    [switch]$ClearReference,
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
. (Join-Path $PSScriptRoot 'seed-vc-gui-overlay.ps1')
$expectedRevision = '51383efd921027683c89e5348211d93ff12ac2a8'
$expectedCheckpointSha256 = 'C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88'
$resolvedPython = [IO.Path]::GetFullPath($Python)
$resolvedRepo = [IO.Path]::GetFullPath($Repo)
$resolvedCheckpoint = [IO.Path]::GetFullPath($Checkpoint)
$resolvedConfig = [IO.Path]::GetFullPath($Config)
$resolvedSession = [IO.Path]::GetFullPath($SessionRoot)
$guiPath = Join-Path $resolvedRepo 'real-time-gui.py'
$hifiganConfig = Join-Path $resolvedRepo 'configs\hifigan.yml'
$cacheRoot = Join-Path $resolvedRepo 'checkpoints'
$hfAssetMap = @{
    'models--facebook--wav2vec2-xls-r-300m' = @('pytorch_model.bin', 'config.json', 'preprocessor_config.json')
    'models--funasr--campplus' = @('campplus_cn_common.bin')
    'models--FunAudioLLM--CosyVoice-300M' = @('hift.pt')
}
$missing = [System.Collections.Generic.List[string]]::new()

if (-not (Test-Path -LiteralPath $resolvedPython -PathType Leaf)) { $missing.Add("Seed-VC Python missing: $resolvedPython") }
if (-not (Test-Path -LiteralPath $resolvedRepo -PathType Container)) { $missing.Add("Seed-VC source missing: $resolvedRepo") }
else {
    $actualRevision = (& git -C $resolvedRepo rev-parse HEAD 2>$null | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or $actualRevision -ne $expectedRevision) {
        $missing.Add("Seed-VC source revision must be $expectedRevision (actual: $actualRevision)")
    }
}
if (-not (Test-Path -LiteralPath $guiPath -PathType Leaf)) { $missing.Add("Official GUI missing: $guiPath") }
if (-not (Test-Path -LiteralPath $resolvedCheckpoint -PathType Leaf)) { $missing.Add("realtime-tiny checkpoint missing: $resolvedCheckpoint") }
elseif ((Get-FileHash -LiteralPath $resolvedCheckpoint -Algorithm SHA256).Hash -ne $expectedCheckpointSha256) {
    $missing.Add("realtime-tiny checkpoint hash does not match registered local asset $expectedCheckpointSha256")
}
if (-not (Test-Path -LiteralPath $resolvedConfig -PathType Leaf)) { $missing.Add("realtime-tiny config missing: $resolvedConfig") }
else {
    $configText = Get-Content -LiteralPath $resolvedConfig -Raw -Encoding UTF8
    if ($configText -notmatch '(?ms)vocoder:\s*\r?\n\s*type:\s*["'']?hifigan') {
        $missing.Add('realtime-tiny config must use the official Hifi-GAN vocoder profile')
    }
    if ($configText -notmatch '(?ms)speech_tokenizer:\s*\r?\n\s*type:\s*["'']?xlsr') {
        $missing.Add('realtime-tiny config must use the XLS-R speech tokenizer profile')
    }
}
if (-not (Test-Path -LiteralPath $hifiganConfig -PathType Leaf)) { $missing.Add("Hifi-GAN config missing: $hifiganConfig") }
$cacheNames = @($hfAssetMap.Keys)
foreach ($cacheName in $cacheNames) {
    $cachePath = Join-Path $cacheRoot $cacheName
    $refPath = Join-Path $cachePath 'refs\main'
    if (-not (Test-Path -LiteralPath $refPath -PathType Leaf)) {
        $missing.Add("Required local model cache reference missing (offline only): $cacheName\refs\main")
        continue
    }
    $snapshotId = (Get-Content -LiteralPath $refPath -Raw -Encoding UTF8).Trim()
    if (-not $snapshotId -or $snapshotId -notmatch '^[0-9a-fA-F]{7,64}$') {
        $missing.Add("Invalid local model snapshot reference: $cacheName\refs\main")
        continue
    }
    foreach ($assetName in $hfAssetMap[$cacheName]) {
        $assetPath = Join-Path (Join-Path (Join-Path $cachePath 'snapshots') $snapshotId) $assetName
        if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf) -or (Get-Item -LiteralPath $assetPath -ErrorAction SilentlyContinue).Length -le 0) {
            $missing.Add("Required local model asset missing/empty (offline only): $cacheName\snapshots\$snapshotId\$assetName")
        }
    }
}
if ($ModelScopeVadCache) { $vadModelPath = [IO.Path]::GetFullPath($ModelScopeVadCache) }
elseif ($env:MODELSCOPE_CACHE) { $vadModelPath = Join-Path ([IO.Path]::GetFullPath($env:MODELSCOPE_CACHE)) 'hub\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch' }
else { $vadModelPath = Join-Path $env:USERPROFILE '.cache\modelscope\hub\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch' }
foreach ($vadAsset in @('model.pt', 'config.yaml', 'configuration.json', 'am.mvn')) {
    $vadFile = Join-Path $vadModelPath $vadAsset
    if (-not (Test-Path -LiteralPath $vadFile -PathType Leaf) -or (Get-Item -LiteralPath $vadFile -ErrorAction SilentlyContinue).Length -le 0) {
        $missing.Add("Required local ModelScope VAD asset missing/empty (downloads disabled): $vadFile")
    }
}

$runtime = $null
$devices = @()
$selectedInputPreflight = $null
$selectedOutputPreflight = $null
$preflightSettingsPath = Join-Path $resolvedSession 'configs\inuse\config.json'
if (Test-Path -LiteralPath $resolvedPython -PathType Leaf) {
    $runtimeText = & $resolvedPython -c "import json,torch,sounddevice as sd,FreeSimpleGUI; print(json.dumps({'python':__import__('sys').version.split()[0],'cuda_available':torch.cuda.is_available(),'cuda_count':torch.cuda.device_count(),'gpu0':torch.cuda.get_device_name(0) if torch.cuda.is_available() and torch.cuda.device_count() else None,'hostapis':sd.query_hostapis(),'devices':[{ 'index':i,'name':d['name'],'hostapi':int(d['hostapi']),'max_input_channels':int(d['max_input_channels']),'max_output_channels':int(d['max_output_channels'])} for i,d in enumerate(sd.query_devices())],'defaults':list(sd.default.device)}))" 2>&1
    $runtimeExit = $LASTEXITCODE
    if ($runtimeExit -ne 0) { $missing.Add("Seed-VC runtime/device preflight failed: $($runtimeText -join ' ')") }
    else {
        try {
            $runtime = [string]($runtimeText | Select-Object -Last 1) | ConvertFrom-Json
            $devices = @($runtime.devices)
            if (-not $runtime.cuda_available -or $runtime.cuda_count -lt 1) { $missing.Add('Torch CUDA device 0 is unavailable; the GUI launcher does not fall back to CPU') }

            $savedSettings = @{}
            if (Test-Path -LiteralPath $preflightSettingsPath -PathType Leaf) {
                try { $savedSettings = Get-Content -LiteralPath $preflightSettingsPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable }
                catch { $missing.Add("Isolated Seed-VC settings are invalid JSON: $preflightSettingsPath") }
            }
            $inputWanted = if ($InputDeviceName) { $InputDeviceName } else { [string]$savedSettings.sg_input_device }
            $outputWanted = if ($OutputDeviceName) { $OutputDeviceName } else { [string]$savedSettings.sg_output_device }
            $defaultIds = @($runtime.defaults)
            $defaultInputId = if ($defaultIds.Count -gt 0 -and $null -ne $defaultIds[0]) { [int]$defaultIds[0] } else { -1 }
            $defaultOutputId = if ($defaultIds.Count -gt 1 -and $null -ne $defaultIds[1]) { [int]$defaultIds[1] } else { -1 }
            $inputCandidates = @($devices | Where-Object {
                $_.max_input_channels -gt 0 -and
                ((-not $inputWanted) -or ([string]$_.name -ceq $inputWanted)) -and
                ((-not $HostApi) -or ([string]$runtime.hostapis[[int]$_.hostapi].name -ceq $HostApi))
            })
            if (-not $inputWanted) { $inputCandidates = @($inputCandidates | Where-Object { [int]$_.index -eq $defaultInputId }) }
            if ($inputCandidates.Count -ne 1) {
                $missing.Add("Input endpoint selection is not unique (matches=$($inputCandidates.Count)); provide exact -InputDeviceName and -HostApi when needed")
            }
            else {
                $selectedInputPreflight = $inputCandidates[0]
                $derivedHostApi = [string]$runtime.hostapis[[int]$selectedInputPreflight.hostapi].name
                if ($HostApi -and $derivedHostApi -cne $HostApi) { $missing.Add("Input endpoint is not in Host API '$HostApi'") }
            }
            $effectiveHostApi = if ($HostApi) { $HostApi } elseif ($selectedInputPreflight) { [string]$runtime.hostapis[[int]$selectedInputPreflight.hostapi].name } else { '' }
            $outputCandidates = @($devices | Where-Object {
                $_.max_output_channels -gt 0 -and
                ((-not $outputWanted) -or ([string]$_.name -ceq $outputWanted)) -and
                ((-not $effectiveHostApi) -or ([string]$runtime.hostapis[[int]$_.hostapi].name -ceq $effectiveHostApi))
            })
            if (-not $outputWanted) { $outputCandidates = @($outputCandidates | Where-Object { [int]$_.index -eq $defaultOutputId }) }
            if ($outputCandidates.Count -ne 1) {
                $missing.Add("Output endpoint selection is not unique or does not share the input Host API (matches=$($outputCandidates.Count)); provide an exact compatible output endpoint")
            }
            else { $selectedOutputPreflight = $outputCandidates[0] }
            if ($selectedInputPreflight -and $selectedOutputPreflight) {
                $inputHostName = [string]$runtime.hostapis[[int]$selectedInputPreflight.hostapi].name
                $outputHostName = [string]$runtime.hostapis[[int]$selectedOutputPreflight.hostapi].name
                if ($inputHostName -cne $outputHostName) { $missing.Add("Input and output endpoints use different Host APIs: $inputHostName / $outputHostName") }
            }
        }
        catch { $missing.Add('Seed-VC runtime/device preflight returned unreadable JSON') }
    }
}

$referencePath = $null
if ($ReferenceWav) {
    if (-not (Test-Path -LiteralPath $ReferenceWav -PathType Leaf)) { $missing.Add("Reference WAV not found: $ReferenceWav") }
    else { $referencePath = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ReferenceWav).Path) }
}
if ($ReferenceWav -and $ClearReference) { $missing.Add('Use either -ReferenceWav or -ClearReference, not both') }

$preflight = [ordered]@{
    status = if ($missing.Count -eq 0) { 'PASS' } else { 'BLOCKED' }
    revision = $expectedRevision
    python = $resolvedPython
    runtime = $runtime
    checkpoint = $resolvedCheckpoint
    checkpoint_sha256 = if (Test-Path -LiteralPath $resolvedCheckpoint -PathType Leaf) { (Get-FileHash -LiteralPath $resolvedCheckpoint -Algorithm SHA256).Hash } else { $null }
    config = $resolvedConfig
    vocoder = 'Hifi-GAN'
    model_cache = 'local-only / offline'
    modelscope_vad_path = $vadModelPath
    modelscope_vad_model_sha256 = if (Test-Path -LiteralPath (Join-Path $vadModelPath 'model.pt') -PathType Leaf) { (Get-FileHash -LiteralPath (Join-Path $vadModelPath 'model.pt') -Algorithm SHA256).Hash } else { $null }
    selected_input = if ($selectedInputPreflight) { $selectedInputPreflight }
    selected_output = if ($selectedOutputPreflight) { $selectedOutputPreflight }
    missing = @($missing)
}
Write-Output ($preflight | ConvertTo-Json -Depth 8)
if ($missing.Count -gt 0) { throw 'Seed-VC GUI preflight blocked before opening the GUI.' }
if ($PreflightOnly) { return }

function Resolve-Device {
    param(
        [object[]]$DeviceRows,
        [string]$RequestedName,
        [string]$Direction,
        [int]$DefaultIndex,
        [string]$HostApiFilter
    )

    $channelField = if ($Direction -eq 'input') { 'max_input_channels' } else { 'max_output_channels' }
    $matches = @($DeviceRows | Where-Object {
        $_.$channelField -gt 0 -and
        ((-not $RequestedName) -or ([string]$_.name -ceq $RequestedName)) -and
        ((-not $HostApiFilter) -or ([string]$runtime.hostapis[[int]$_.hostapi].name -ceq $HostApiFilter))
    })
    if ($RequestedName -and $matches.Count -ne 1) {
        throw "Device name '$RequestedName' resolves to $($matches.Count) $Direction endpoints; use the exact unique name and -HostApi if needed."
    }
    if (-not $RequestedName) {
        $matches = @($matches | Where-Object { [int]$_.index -eq $DefaultIndex })
        if ($matches.Count -ne 1) {
            throw "No unique default $Direction endpoint is available. Pass -${Direction}DeviceName and, when needed, -HostApi."
        }
    }
    $device = $matches[0]
    $device | Add-Member -NotePropertyName hostapi_name -NotePropertyValue ([string]$runtime.hostapis[[int]$device.hostapi].name) -Force
    return $device
}

$sessionConfigDir = Join-Path $resolvedSession 'configs'
$inUseConfigDir = Join-Path $sessionConfigDir 'inuse'
$sessionConfigPath = Join-Path $inUseConfigDir 'config.json'
$baseConfigPath = Join-Path $sessionConfigDir 'config.json'
$sessionHifiganPath = Join-Path $sessionConfigDir 'hifigan.yml'
$sessionCheckpoints = Join-Path $resolvedSession 'checkpoints'
$sessionModelScope = Join-Path $resolvedSession 'modelscope'
$null = New-Item -ItemType Directory -Force -Path $inUseConfigDir, $sessionCheckpoints, (Join-Path $resolvedSession 'hf-home'), $sessionModelScope

Copy-Item -LiteralPath $hifiganConfig -Destination $sessionHifiganPath -Force
foreach ($cacheName in $cacheNames) {
    $targetCache = [IO.Path]::GetFullPath((Join-Path $cacheRoot $cacheName))
    $sessionCache = Join-Path $sessionCheckpoints $cacheName
    $null = Ensure-SeedVcCacheJunction -LinkPath $sessionCache -TargetPath $targetCache
}
$null = New-Item -ItemType Directory -Force -Path (Join-Path $sessionCheckpoints '.locks')

$configData = @{
    reference_audio_path = ''
    sg_hostapi = ''
    sg_wasapi_exclusive = $false
    sg_input_device = ''
    sg_output_device = ''
    sr_type = 'sr_model'
    sr_model = $true
    sr_device = $false
    diffusion_steps = 10.0
    inference_cfg_rate = 0.7
    max_prompt_length = 3.0
    block_time = 0.30
    crossfade_length = 0.04
    extra_time_ce = 5.0
    extra_time = 0.5
    extra_time_right = 0.02
}
if (Test-Path -LiteralPath $sessionConfigPath -PathType Leaf) {
    try { $configData = Get-Content -LiteralPath $sessionConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable }
    catch { throw "Isolated Seed-VC session settings are invalid JSON: $sessionConfigPath" }
}

$defaults = @($runtime.defaults)
$inputRequest = if ($InputDeviceName) { $InputDeviceName } else { [string]$configData.sg_input_device }
$outputRequest = if ($OutputDeviceName) { $OutputDeviceName } else { [string]$configData.sg_output_device }
$inputIndex = if ($defaults.Count -gt 0 -and $null -ne $defaults[0]) { [int]$defaults[0] } else { -1 }
$outputIndex = if ($defaults.Count -gt 1 -and $null -ne $defaults[1]) { [int]$defaults[1] } else { -1 }
$inputDevice = Resolve-Device -DeviceRows $devices -RequestedName $inputRequest -Direction input -DefaultIndex $inputIndex -HostApiFilter $HostApi
$resolvedHostApi = if ($HostApi) { $HostApi } else { $inputDevice.hostapi_name }
$outputDevice = Resolve-Device -DeviceRows $devices -RequestedName $outputRequest -Direction output -DefaultIndex $outputIndex -HostApiFilter $resolvedHostApi
if ($inputDevice.hostapi_name -cne $outputDevice.hostapi_name) {
    throw "Seed-VC GUI requires one Host API for both ends. Input=$($inputDevice.hostapi_name), output=$($outputDevice.hostapi_name); specify a compatible pair."
}
if ($HostApi -and $inputDevice.hostapi_name -cne $HostApi) { throw "Requested input endpoint is not part of Host API '$HostApi'." }

if ($InputDeviceName) { $configData.sg_input_device = [string]$inputDevice.name }
elseif (-not $configData.sg_input_device) { $configData.sg_input_device = [string]$inputDevice.name }
if ($OutputDeviceName) { $configData.sg_output_device = [string]$outputDevice.name }
elseif (-not $configData.sg_output_device) { $configData.sg_output_device = [string]$outputDevice.name }
$configData.sg_hostapi = [string]$inputDevice.hostapi_name
if ($referencePath) { $configData.reference_audio_path = $referencePath }
if ($ClearReference) { $configData.reference_audio_path = '' }
if ($configData.reference_audio_path) {
    if (-not (Test-Path -LiteralPath $configData.reference_audio_path -PathType Leaf)) {
        throw "Configured reference WAV no longer exists: $($configData.reference_audio_path); pass -ReferenceWav or -ClearReference."
    }
    $referenceHash = (Get-FileHash -LiteralPath $configData.reference_audio_path -Algorithm SHA256).Hash
}
else { $referenceHash = $null }

$settingsJson = $configData | ConvertTo-Json -Depth 5
Set-Content -LiteralPath $baseConfigPath -Value $settingsJson -Encoding UTF8
Set-Content -LiteralPath $sessionConfigPath -Value $settingsJson -Encoding UTF8

Write-Output "GUI settings are isolated under: $resolvedSession"
Write-Output "Input endpoint: $($inputDevice.hostapi_name) / $($inputDevice.name)"
Write-Output "Output endpoint: $($outputDevice.hostapi_name) / $($outputDevice.name)"
if ($referenceHash) { Write-Output "Reference SHA256: $referenceHash" }
else { Write-Output 'Reference: select one in the official GUI before starting conversion.' }
Write-Output 'Official GUI opens in FP32 on CUDA device 0. It does not inject audio or start a stream automatically.'
Write-Output 'Check the displayed input/output endpoints before pressing Start VC; synthetic GUI harness results are not microphone evidence.'

$previousLocation = Get-Location
$envNames = @('AETHERTUNE_SEED_VC_REPO','AETHERTUNE_SEED_VC_GUI','AETHERTUNE_SEED_VC_CHECKPOINT','AETHERTUNE_SEED_VC_CONFIG','AETHERTUNE_SEED_VC_VAD_PATH','MODELSCOPE_CACHE','HF_HOME','HF_HUB_CACHE','HUGGINGFACE_HUB_CACHE','TRANSFORMERS_CACHE','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','PYTHONPATH')
$oldEnv = @{}
foreach ($envName in $envNames) { $oldEnv[$envName] = [Environment]::GetEnvironmentVariable($envName, 'Process') }
try {
    $env:AETHERTUNE_SEED_VC_REPO = $resolvedRepo
    $env:AETHERTUNE_SEED_VC_GUI = $guiPath
    $env:AETHERTUNE_SEED_VC_CHECKPOINT = $resolvedCheckpoint
    $env:AETHERTUNE_SEED_VC_CONFIG = $resolvedConfig
    $env:AETHERTUNE_SEED_VC_VAD_PATH = $vadModelPath
    $env:MODELSCOPE_CACHE = $sessionModelScope
    $env:HF_HOME = Join-Path $resolvedSession 'hf-home'
    $env:HF_HUB_CACHE = $sessionCheckpoints
    $env:HUGGINGFACE_HUB_CACHE = $sessionCheckpoints
    $env:TRANSFORMERS_CACHE = $sessionCheckpoints
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    $env:PYTHONPATH = $resolvedRepo
    Set-Location $resolvedSession
    & $resolvedPython (Join-Path $PSScriptRoot 'seed-vc-gui-bootstrap.py')
    if ($LASTEXITCODE -ne 0) { throw "Official Seed-VC GUI exited with code $LASTEXITCODE" }
}
finally {
    Set-Location $previousLocation
    foreach ($envName in $envNames) { [Environment]::SetEnvironmentVariable($envName, $oldEnv[$envName], 'Process') }
}
