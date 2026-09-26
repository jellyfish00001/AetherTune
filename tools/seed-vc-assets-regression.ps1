# Isolated contract regression for manifest-driven setup and GUI preflight gates.
# All assets are small synthetic files under one unique TEMP directory; no real cache,
# weights, venv, model runtime, GUI window, or audio device is touched.
#Requires -Version 7.2
$ErrorActionPreference = 'Stop'

$toolRoot = $PSScriptRoot
$pwsh = (Get-Command 'pwsh.exe' -ErrorAction Stop).Source
$fixtureRoot = Join-Path $env:TEMP ("aethertune-seed-vc-assets-" + [Guid]::NewGuid().ToString('N'))
$fixtureTools = Join-Path $fixtureRoot 'tools'
$repoPath = Join-Path $fixtureRoot 'external\seed-vc'
$modelScopePath = Join-Path $fixtureRoot 'modelscope-vad'
$shimRoot = Join-Path $fixtureRoot 'shims'
$setupEnvironment = Join-Path $fixtureRoot 'venvs\setup'
$pythonShim = Join-Path $shimRoot 'python310.cmd'
$gitShim = Join-Path $shimRoot 'git.cmd'
$missingPython = Join-Path $fixtureRoot 'missing\python.exe'
$manifestPath = Join-Path $fixtureTools 'seed-vc-assets.json'
$guiConfig = Join-Path $repoPath 'fixture-gui-config.yml'

$null = New-Item -ItemType Directory -Force -Path $fixtureTools, $repoPath, $modelScopePath, $shimRoot
foreach ($name in @('seed-vc-setup.ps1', 'seed-vc-gui-run.ps1', 'seed-vc-gui-bootstrap.py', 'seed-vc-assets.ps1', 'seed-vc-gui-overlay.ps1', 'seed-vc-gui-device-selection.ps1')) {
    Copy-Item -LiteralPath (Join-Path $toolRoot $name) -Destination (Join-Path $fixtureTools $name)
}

Set-Content -LiteralPath $pythonShim -Encoding ascii -Value @'
@echo off
echo %*| findstr /i /c:"sounddevice as sd" >nul
if not errorlevel 1 goto gui_probe
echo %*| findstr /i /c:"seed-vc-gui-bootstrap.py" >nul
if not errorlevel 1 goto bootstrap
echo {"version":[3,10,11],"bits":64,"tcl":"8.6.12","tk":"available"}
exit /b 0
:gui_probe
echo {"python":"3.10.11","cuda_available":true,"cuda_count":1,"gpu0":"Synthetic GPU","hostapis":[{"name":"Synthetic DirectSound"}],"devices":[{"index":0,"name":"Synthetic Input","hostapi":0,"max_input_channels":1,"max_output_channels":0},{"index":1,"name":"Synthetic Output","hostapi":0,"max_input_channels":0,"max_output_channels":2}],"defaults":[0,1]}
exit /b 0
:bootstrap
if not defined AETHERTUNE_GUI_BOOTSTRAP_MARKER exit /b 19
> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo GUI_BOOTSTRAP_LAUNCH_REACHED
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo cwd=%CD%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo repo=%AETHERTUNE_SEED_VC_REPO%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo gui=%AETHERTUNE_SEED_VC_GUI%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo checkpoint=%AETHERTUNE_SEED_VC_CHECKPOINT%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo config=%AETHERTUNE_SEED_VC_CONFIG%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo vad=%AETHERTUNE_SEED_VC_VAD_PATH%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo modelscope=%MODELSCOPE_CACHE%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo hf_home=%HF_HOME%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo hf_cache=%HF_HUB_CACHE%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo hf_offline=%HF_HUB_OFFLINE%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo transformers_offline=%TRANSFORMERS_OFFLINE%
>> "%AETHERTUNE_GUI_BOOTSTRAP_MARKER%" echo pythonpath=%PYTHONPATH%
exit /b 0
'@
Set-Content -LiteralPath $gitShim -Encoding ascii -Value @'
@echo off
if /i "%~1"=="-C" if /i "%~3"=="rev-parse" if /i "%~4"=="HEAD" (
  echo 51383efd921027683c89e5348211d93ff12ac2a8
  exit /b 0
)
echo BLOCKED: unexpected synthetic git invocation %* 1>&2
exit /b 2
'@

function Write-SyntheticAsset {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Content)
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path)
    [IO.File]::WriteAllBytes($Path, [Text.Encoding]::UTF8.GetBytes($Content))
}

function Register-SyntheticAsset {
    param([Parameter(Mandatory)][System.Collections.IDictionary]$Record, [Parameter(Mandatory)][string]$Path)
    $bytes = [Text.Encoding]::UTF8.GetBytes("synthetic:$($Record.path)")
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path)
    [IO.File]::WriteAllBytes($Path, $bytes)
    $Record.size_bytes = [long]$bytes.Length
    $Record.sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
}

$manifest = Get-Content -LiteralPath (Join-Path $toolRoot 'seed-vc-assets.json') -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
$sourceFiles = @($manifest.seed_vc_source.required_files)
foreach ($relative in $sourceFiles) {
    $content = if ($relative -ceq 'configs/presets/config_dit_mel_seed_uvit_xlsr_tiny.yml') {
        "vocoder:`n  type: hifigan`nspeech_tokenizer:`n  type: xlsr`n"
    }
    elseif ($relative -ceq 'configs/hifigan.yml') { "synthetic hifigan config`n" }
    else { "synthetic source file: $relative`n" }
    Write-SyntheticAsset -Path (Join-Path $repoPath $relative) -Content $content
}
Write-SyntheticAsset -Path $guiConfig -Content "vocoder:`n  type: hifigan`nspeech_tokenizer:`n  type: xlsr`n"
$null = New-Item -ItemType Directory -Force -Path (Join-Path $repoPath '.git')

foreach ($checkpoint in $manifest.checkpoints) {
    Register-SyntheticAsset -Record $checkpoint -Path (Join-Path $fixtureRoot $checkpoint.path)
}
foreach ($repository in $manifest.huggingface_repositories) {
    $cacheRoot = Join-Path (Join-Path $repoPath 'checkpoints') $repository.cache_directory
    $null = New-Item -ItemType Directory -Force -Path (Join-Path $cacheRoot 'refs')
    Set-Content -LiteralPath (Join-Path $cacheRoot 'refs\main') -Value $repository.expected_local_revision -Encoding ascii
    foreach ($asset in $repository.files) {
        $assetPath = Join-Path (Join-Path (Join-Path $cacheRoot 'snapshots') $repository.expected_local_revision) $asset.path
        Register-SyntheticAsset -Record $asset -Path $assetPath
    }
}
foreach ($asset in $manifest.model_scope_fsmn_vad.files) {
    Register-SyntheticAsset -Record $asset -Path (Join-Path $modelScopePath $asset.path)
}
Set-Content -LiteralPath $manifestPath -Value ($manifest | ConvertTo-Json -Depth 12) -Encoding utf8
$baseManifestJson = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8

function Invoke-BlockedPreflight {
    param([Parameter(Mandatory)][ValidateSet('setup', 'gui')][string]$Kind,
        [Parameter(Mandatory)][string]$CaseName)

    $caseManifest = Join-Path $fixtureRoot "$CaseName.manifest.json"
    $resetManifest = $baseManifestJson | ConvertFrom-Json -AsHashtable
    foreach ($checkpoint in $resetManifest.checkpoints) {
        Register-SyntheticAsset -Record $checkpoint -Path (Join-Path $fixtureRoot $checkpoint.path)
    }
    foreach ($repository in $resetManifest.huggingface_repositories) {
        $cacheRoot = Join-Path (Join-Path $repoPath 'checkpoints') $repository.cache_directory
        Set-Content -LiteralPath (Join-Path $cacheRoot 'refs\main') -Value $repository.expected_local_revision -Encoding ascii
        foreach ($asset in $repository.files) {
            Register-SyntheticAsset -Record $asset -Path (Join-Path (Join-Path (Join-Path $cacheRoot 'snapshots') $repository.expected_local_revision) $asset.path)
        }
    }
    foreach ($asset in $resetManifest.model_scope_fsmn_vad.files) {
        Register-SyntheticAsset -Record $asset -Path (Join-Path $modelScopePath $asset.path)
    }
    Set-Content -LiteralPath $manifestPath -Value ($resetManifest | ConvertTo-Json -Depth 12) -Encoding utf8
    Copy-Item -LiteralPath $manifestPath -Destination $caseManifest -Force
    $caseRepo = $repoPath
    $caseVad = $modelScopePath
    $caseEnvironment = Join-Path $fixtureRoot "venvs\$CaseName"
    $caseSession = Join-Path $fixtureRoot "sessions\$CaseName"

    switch ($CaseName) {
        'missing-asset' {
            Remove-Item -LiteralPath (Join-Path (Join-Path (Join-Path (Join-Path $repoPath 'checkpoints') 'models--funasr--campplus') 'snapshots\e4b6ede7ce16997aff4ae69fbca1f0175e2afede') 'campplus_cn_common.bin')
        }
        'wrong-snapshot-revision' {
            Set-Content -LiteralPath (Join-Path (Join-Path (Join-Path $repoPath 'checkpoints') 'models--funasr--campplus') 'refs\main') -Value ('b' * 40) -Encoding ascii
        }
        'wrong-hash' {
            $tampered = Join-Path (Join-Path (Join-Path (Join-Path $repoPath 'checkpoints') 'models--funasr--campplus') 'snapshots\e4b6ede7ce16997aff4ae69fbca1f0175e2afede') 'campplus_cn_common.bin'
            $expectedLength = (Get-Item -LiteralPath $tampered).Length
            [IO.File]::WriteAllBytes($tampered, [byte[]](1..$expectedLength))
        }
        'wrong-source-revision' {
            $bad = Get-Content -LiteralPath $caseManifest -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
            $bad.seed_vc_source.revision = 'b' * 40
            Set-Content -LiteralPath $caseManifest -Value ($bad | ConvertTo-Json -Depth 12) -Encoding utf8
        }
        'wrong-model-revision' {
            $bad = Get-Content -LiteralPath $caseManifest -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
            $bad.checkpoints[0].model_repo_revision = 'b' * 40
            Set-Content -LiteralPath $caseManifest -Value ($bad | ConvertTo-Json -Depth 12) -Encoding utf8
        }
        'invalid-json' { Set-Content -LiteralPath $caseManifest -Value '{"schema_version":' -Encoding utf8 }
        'invalid-schema' {
            $bad = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
            $bad.model_scope_fsmn_vad.license_status = 'Apache-2.0'
            Set-Content -LiteralPath $caseManifest -Value ($bad | ConvertTo-Json -Depth 12) -Encoding utf8
        }
        'omitted-source-requirement' {
            $bad = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
            $bad.seed_vc_source.required_files = @($bad.seed_vc_source.required_files | Where-Object { $_ -cne 'requirements.txt' })
            Set-Content -LiteralPath $caseManifest -Value ($bad | ConvertTo-Json -Depth 12) -Encoding utf8
        }
        'omitted-hf-dependency' {
            $bad = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
            $xlsr = @($bad.huggingface_repositories | Where-Object { $_.repo_id -ceq 'facebook/wav2vec2-xls-r-300m' })[0]
            $xlsr.files = @($xlsr.files | Where-Object { $_.path -cne 'preprocessor_config.json' })
            Set-Content -LiteralPath $caseManifest -Value ($bad | ConvertTo-Json -Depth 12) -Encoding utf8
        }
    }

    if ($Kind -eq 'setup') {
        $scriptPath = Join-Path $fixtureTools 'seed-vc-setup.ps1'
        $args = @('-NoProfile','-File',$scriptPath,'-Python310',$pythonShim,'-Environment',$caseEnvironment,
            '-Repo',$caseRepo,'-ModelScopeVadCache',$caseVad,'-AssetManifest',$caseManifest)
    }
    else {
        $scriptPath = Join-Path $fixtureTools 'seed-vc-gui-run.ps1'
        $args = @('-NoProfile','-File',$scriptPath,'-Python',$pythonShim,'-Repo',$caseRepo,
            '-Config',$guiConfig,'-SessionRoot',$caseSession,'-ModelScopeVadCache',$caseVad,
            '-AssetManifest',$caseManifest)
    }

    $previousPath = $env:PATH
    try {
        $env:PATH = $shimRoot + [IO.Path]::PathSeparator + $previousPath
        $output = @(& $pwsh @args 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally { $env:PATH = $previousPath }
    $outputText = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    $match = [regex]::Match($outputText, '(?s)\{\s*"status"\s*:.*?"missing"\s*:\s*\[.*?\]\s*\}')
    if (-not $match.Success) { throw "$Kind $CaseName did not emit a structured BLOCKED report. Output: $outputText" }
    $report = $match.Value | ConvertFrom-Json
    if ($exitCode -eq 0 -or $report.status -cne 'BLOCKED') { throw "$Kind $CaseName should be nonzero/BLOCKED; exit=$exitCode status=$($report.status)" }
    if ($outputText -match '(?i)pip install|更新 packaging tools|建立獨立 Seed-VC Python environment|Official GUI opens|Start VC') {
        throw "$Kind $CaseName reached a mutation/install/GUI-start message before blocking."
    }
    if ($Kind -eq 'setup' -and (Test-Path -LiteralPath $caseEnvironment)) { throw "Setup created venv before blocking: $caseEnvironment" }
    if ($Kind -eq 'gui' -and (Test-Path -LiteralPath $caseSession)) { throw "GUI created session overlay before blocking: $caseSession" }
    return [pscustomobject]@{ Kind=$Kind; Case=$CaseName; ExitCode=$exitCode; Output=$outputText; Report=$report }
}

function Invoke-RealtimeProfileScopeSmoke {
    $offlineCheckpoint = Join-Path $fixtureRoot 'models\seed-vc\checkpoints\offline-v1\DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth'
    $offlinePreset = Join-Path $repoPath 'configs\presets\config_dit_mel_seed_uvit_whisper_small_wavenet.yml'
    $offlineInference = Join-Path $repoPath 'inference.py'
    $offlineCheckpointFull = [IO.Path]::GetFullPath($offlineCheckpoint)
    $fixtureFull = [IO.Path]::GetFullPath($fixtureRoot).TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    if (-not $offlineCheckpointFull.StartsWith($fixtureFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside this isolated fixture: $offlineCheckpointFull"
    }
    if (Test-Path -LiteralPath $offlineCheckpointFull) { Remove-Item -LiteralPath $offlineCheckpointFull -Force }
    if (Test-Path -LiteralPath $offlinePreset) { throw "Realtime-only source fixture unexpectedly contains offline preset: $offlinePreset" }
    if (Test-Path -LiteralPath $offlineInference) { throw "Realtime-only source fixture unexpectedly contains offline inference entry point: $offlineInference" }

    $setupEnvironment = Join-Path $fixtureRoot 'venvs\realtime-scope-smoke'
    $setupArguments = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-setup.ps1'),
        '-Python310',$pythonShim,'-Environment',$setupEnvironment,'-Repo',$repoPath,
        '-ModelScopeVadCache',$modelScopePath,'-AssetManifest',$manifestPath,'-PreflightOnly')
    $previousPath = $env:PATH
    try {
        $env:PATH = $shimRoot + [IO.Path]::PathSeparator + $previousPath
        $setupOutput = @(& $pwsh @setupArguments 2>&1)
        $setupExit = $LASTEXITCODE
    }
    finally { $env:PATH = $previousPath }
    $setupText = ($setupOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    $setupJson = [regex]::Match($setupText, '(?s)\{\s*"status"\s*:.*?"missing"\s*:\s*\[.*?\]\s*\}')
    if (-not $setupJson.Success) { throw "Realtime-only setup smoke did not emit structured preflight JSON: $setupText" }
    $setupReport = $setupJson.Value | ConvertFrom-Json
    if ($setupExit -ne 0 -or $setupReport.status -cne 'PASS' -or $setupReport.profile_scope -cne 'realtime-tiny' -or
        $setupReport.offline_v1_helper_completeness -cne 'WAITING' -or @($setupReport.missing).Count -ne 0) {
        throw "Setup must pass its realtime-only preflight with offline-v1 absent; exit=$setupExit report=$($setupJson.Value) output=$setupText"
    }
    if (Test-Path -LiteralPath $setupEnvironment) { throw "PreflightOnly created a venv: $setupEnvironment" }

    $successSession = Join-Path $fixtureRoot 'sessions\realtime-scope-smoke'
    $marker = Join-Path $fixtureRoot 'fake-gui-bootstrap.marker'
    $guiArguments = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-gui-run.ps1'),
        '-Python',$pythonShim,'-Repo',$repoPath,
        '-Checkpoint',(Join-Path $fixtureRoot 'models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth'),
        '-Config',$guiConfig,'-SessionRoot',$successSession,'-ModelScopeVadCache',$modelScopePath,
        '-AssetManifest',$manifestPath,'-InputDeviceName','Synthetic Input','-OutputDeviceName','Synthetic Output',
        '-HostApi','Synthetic DirectSound')
    $previousMarker = $env:AETHERTUNE_GUI_BOOTSTRAP_MARKER
    try {
        $env:PATH = $shimRoot + [IO.Path]::PathSeparator + $previousPath
        $env:AETHERTUNE_GUI_BOOTSTRAP_MARKER = $marker
        $guiOutput = @(& $pwsh @guiArguments 2>&1)
        $guiExit = $LASTEXITCODE
    }
    finally {
        $env:PATH = $previousPath
        $env:AETHERTUNE_GUI_BOOTSTRAP_MARKER = $previousMarker
    }
    $guiText = ($guiOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    if ($guiExit -ne 0) { throw "Realtime-only GUI fixture should reach the intercepted bootstrap; exit=$guiExit output=$guiText" }
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw 'Fake Python did not intercept the GUI bootstrap invocation.' }

    $resolvedSession = [IO.Path]::GetFullPath($successSession)
    $resolvedRepo = [IO.Path]::GetFullPath($repoPath)
    $resolvedCheckpoint = Join-Path $fixtureRoot 'models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth'
    $resolvedConfig = [IO.Path]::GetFullPath($guiConfig)
    $expectedMarkerLines = @(
        'GUI_BOOTSTRAP_LAUNCH_REACHED',
        "cwd=$resolvedSession",
        "repo=$resolvedRepo",
        "gui=$(Join-Path $resolvedRepo 'real-time-gui.py')",
        "checkpoint=$resolvedCheckpoint",
        "config=$resolvedConfig",
        "vad=$([IO.Path]::GetFullPath($modelScopePath))",
        "modelscope=$(Join-Path $resolvedSession 'modelscope')",
        "hf_home=$(Join-Path $resolvedSession 'hf-home')",
        "hf_cache=$(Join-Path $resolvedSession 'checkpoints')",
        'hf_offline=1',
        'transformers_offline=1',
        "pythonpath=$resolvedRepo"
    )
    $markerLines = @(Get-Content -LiteralPath $marker -Encoding UTF8)
    foreach ($expectedLine in $expectedMarkerLines) {
        if ($markerLines -cnotcontains $expectedLine) { throw "Intercepted GUI bootstrap did not receive expected isolated launch setting: $expectedLine; marker=$($markerLines -join ' | ')" }
    }

    $sessionConfig = Join-Path $resolvedSession 'configs\inuse\config.json'
    $sessionHifigan = Join-Path $resolvedSession 'configs\hifigan.yml'
    if (-not (Test-Path -LiteralPath $sessionConfig -PathType Leaf) -or -not (Test-Path -LiteralPath $sessionHifigan -PathType Leaf)) {
        throw 'GUI normal path did not materialize the isolated session config and Hifi-GAN config.'
    }
    $settings = Get-Content -LiteralPath $sessionConfig -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    if ($settings.sg_hostapi -cne 'Synthetic DirectSound' -or $settings.sg_input_device -cne 'Synthetic Input' -or
        $settings.sg_output_device -cne 'Synthetic Output') {
        throw "GUI session config did not persist the unique synthetic endpoints: $sessionConfig"
    }
    foreach ($repository in $manifest.huggingface_repositories) {
        $linkPath = Join-Path (Join-Path $resolvedSession 'checkpoints') $repository.cache_directory
        $targetPath = [IO.Path]::GetFullPath((Join-Path (Join-Path $repoPath 'checkpoints') $repository.cache_directory))
        $entry = Get-Item -LiteralPath $linkPath -Force -ErrorAction Stop
        $resolvedLink = [IO.DirectoryInfo]::new($linkPath).ResolveLinkTarget($true)
        if ($entry.LinkType -cne 'Junction' -or $null -eq $resolvedLink -or
            [IO.Path]::GetFullPath($resolvedLink.FullName) -ine $targetPath) {
            throw "Realtime GUI did not create a verified cache junction: $linkPath -> $($resolvedLink.FullName)"
        }
    }
    if (Test-Path -LiteralPath $offlineCheckpointFull) { throw 'Realtime-only GUI smoke unexpectedly restored the offline-v1 checkpoint.' }
    return [pscustomobject]@{ SetupExit=$setupExit; GuiExit=$guiExit; Session=$successSession; Marker=$marker }
}

$profileScopeSmoke = Invoke-RealtimeProfileScopeSmoke

$results = @()
foreach ($caseName in @('missing-asset','wrong-snapshot-revision','wrong-hash','wrong-source-revision','wrong-model-revision','invalid-json','invalid-schema','omitted-source-requirement','omitted-hf-dependency')) {
    foreach ($kind in @('setup','gui')) {
        $results += Invoke-BlockedPreflight -Kind $kind -CaseName $caseName
    }
}

# Prove each injected condition is present in both entry-point reports.
$expectedFragments = @{
    'missing-asset' = 'is missing or not a regular file'
    'wrong-snapshot-revision' = 'snapshot revision mismatch'
    'wrong-hash' = 'SHA-256 mismatch'
    'wrong-source-revision' = 'source revision must remain'
    'wrong-model-revision' = 'model provenance must remain'
    'invalid-json' = 'invalid JSON'
    'invalid-schema' = 'license UNKNOWN'
    'omitted-source-requirement' = 'Seed-VC source.required_files set mismatch'
    'omitted-hf-dependency' = 'Hugging Face facebook/wav2vec2-xls-r-300m.files set mismatch'
}
foreach ($result in $results) {
    if ($result.Output -notmatch [regex]::Escape($expectedFragments[$result.Case])) {
        throw "$($result.Kind) $($result.Case) did not report its exact manifest/asset failure."
    }
}

Write-Output "PASS Seed-VC asset manifest regression: 18 isolated negative setup/GUI cases blocked before venv, pip, session overlay, GUI window, or audio stream; realtime-only setup preflight and GUI reached an intercepted bootstrap with offline-v1 checkpoint, offline preset, and offline inference.py absent, verified config/junction/env overlay; no real GUI/audio; fixture=$fixtureRoot"
