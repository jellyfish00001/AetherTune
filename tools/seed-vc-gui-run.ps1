#Requires -Version 7.2
[CmdletBinding()]
param(
    [string]$Python = '.\tools\venvs\seed-vc\Scripts\python.exe',
    [string]$Repo = '.\tools\external\seed-vc',
    [string]$Checkpoint = '.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
    [string]$Config = '.\tools\external\seed-vc\configs\presets\config_dit_mel_seed_uvit_xlsr_tiny.yml',
    [string]$SessionRoot = '.\artifacts\seed-vc\gui-session',
    [string]$ModelScopeVadCache,
    [string]$AssetManifest = '.\tools\seed-vc-assets.json',
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
. (Join-Path $PSScriptRoot 'seed-vc-gui-device-selection.ps1')
. (Join-Path $PSScriptRoot 'seed-vc-assets.ps1')
$resolvedPython = [IO.Path]::GetFullPath($Python)
$resolvedRepo = [IO.Path]::GetFullPath($Repo)
$resolvedCheckpoint = [IO.Path]::GetFullPath($Checkpoint)
$resolvedConfig = [IO.Path]::GetFullPath($Config)
$resolvedSession = [IO.Path]::GetFullPath($SessionRoot)
$manifestPath = [IO.Path]::GetFullPath($AssetManifest)
$guiPath = Join-Path $resolvedRepo 'real-time-gui.py'
$hifiganConfig = Join-Path $resolvedRepo 'configs\hifigan.yml'
$missing = [System.Collections.Generic.List[string]]::new()
$manifest = $null
try { $manifest = Read-SeedVcAssetManifest -Path $manifestPath }
catch { $missing.Add($_.Exception.Message) }
$expectedRevision = if ($manifest) { [string]$manifest.seed_vc_source.revision } else { $null }
$cacheNames = if ($manifest) { @($manifest.huggingface_repositories | ForEach-Object { [string]$_.cache_directory }) } else { @() }

if (-not (Test-Path -LiteralPath $resolvedPython -PathType Leaf)) { $missing.Add("Seed-VC Python missing: $resolvedPython") }
if (-not (Test-Path -LiteralPath $resolvedRepo -PathType Container)) { $missing.Add("Seed-VC source missing: $resolvedRepo") }
else {
    $actualRevision = (& git -C $resolvedRepo rev-parse HEAD 2>$null | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or $actualRevision -ne $expectedRevision) {
        $missing.Add("Seed-VC source revision must be $expectedRevision (actual: $actualRevision)")
    }
}
if (-not (Test-Path -LiteralPath $guiPath -PathType Leaf)) { $missing.Add("Official GUI missing: $guiPath") }
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
if ($ModelScopeVadCache) { $vadModelPath = [IO.Path]::GetFullPath($ModelScopeVadCache) }
elseif ($env:MODELSCOPE_CACHE) { $vadModelPath = Join-Path ([IO.Path]::GetFullPath($env:MODELSCOPE_CACHE)) 'hub\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch' }
else { $vadModelPath = Join-Path $env:USERPROFILE '.cache\modelscope\hub\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch' }
if ($manifest) {
    foreach ($finding in Get-SeedVcAssetManifestFindings -Manifest $manifest -ProjectRoot $projectRoot -SeedVcRepo $resolvedRepo -ModelScopeVadPath $vadModelPath -RealtimeCheckpointOverride $resolvedCheckpoint) {
        $missing.Add($finding)
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
            $defaultIds = @($runtime.defaults)
            $defaultInputId = if ($defaultIds.Count -gt 0 -and $null -ne $defaultIds[0]) { [int]$defaultIds[0] } else { -1 }
            $defaultOutputId = if ($defaultIds.Count -gt 1 -and $null -ne $defaultIds[1]) { [int]$defaultIds[1] } else { -1 }
            $hostApiNames = @($runtime.hostapis | ForEach-Object { [string]$_.name })
            $devicePair = Resolve-SeedVcDevicePair `
                -DeviceRows $devices `
                -HostApiNames $hostApiNames `
                -DefaultInputIndex $defaultInputId `
                -DefaultOutputIndex $defaultOutputId `
                -InputDeviceName $InputDeviceName `
                -SavedInputDeviceName ([string]$savedSettings.sg_input_device) `
                -OutputDeviceName $OutputDeviceName `
                -SavedOutputDeviceName ([string]$savedSettings.sg_output_device) `
                -RequestedHostApi $HostApi `
                -SavedHostApi ([string]$savedSettings.sg_hostapi)
            $selectedInputPreflight = $devicePair.Input
            $selectedOutputPreflight = $devicePair.Output
        }
        catch { $missing.Add("Seed-VC runtime/device preflight failed: $($_.Exception.Message)") }
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
    profile_scope = if ($manifest) { $manifest.supported_profile_scope } else { $null }
    offline_v1_helper_completeness = if ($manifest) { $manifest.offline_v1_helper_completeness } else { $null }
    revision = $expectedRevision
    asset_manifest = $manifestPath
    clean_machine_bootstrap_status = if ($manifest) { $manifest.clean_machine_bootstrap_status }
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

$sessionConfigDir = Join-Path $resolvedSession 'configs'
$inUseConfigDir = Join-Path $sessionConfigDir 'inuse'
$sessionConfigPath = Join-Path $inUseConfigDir 'config.json'
$baseConfigPath = Join-Path $sessionConfigDir 'config.json'
$sessionHifiganPath = Join-Path $sessionConfigDir 'hifigan.yml'
$sessionCheckpoints = Join-Path $resolvedSession 'checkpoints'
$sessionModelScope = Join-Path $resolvedSession 'modelscope'
$cacheRoot = Join-Path $resolvedRepo 'checkpoints'
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
$inputIndex = if ($defaults.Count -gt 0 -and $null -ne $defaults[0]) { [int]$defaults[0] } else { -1 }
$outputIndex = if ($defaults.Count -gt 1 -and $null -ne $defaults[1]) { [int]$defaults[1] } else { -1 }
$hostApiNames = @($runtime.hostapis | ForEach-Object { [string]$_.name })
$devicePair = Resolve-SeedVcDevicePair `
    -DeviceRows $devices `
    -HostApiNames $hostApiNames `
    -DefaultInputIndex $inputIndex `
    -DefaultOutputIndex $outputIndex `
    -InputDeviceName $InputDeviceName `
    -SavedInputDeviceName ([string]$configData.sg_input_device) `
    -OutputDeviceName $OutputDeviceName `
    -SavedOutputDeviceName ([string]$configData.sg_output_device) `
    -RequestedHostApi $HostApi `
    -SavedHostApi ([string]$configData.sg_hostapi)
$inputDevice = $devicePair.Input
$outputDevice = $devicePair.Output
$resolvedHostApi = $devicePair.HostApi

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
