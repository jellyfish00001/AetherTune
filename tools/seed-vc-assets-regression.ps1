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
$foreignCwd = Join-Path $fixtureRoot 'foreign-cwd'
$setupEnvironment = Join-Path $fixtureRoot 'venvs\setup'
$pythonShim = Join-Path $shimRoot 'python310.cmd'
$gitShim = Join-Path $shimRoot 'git.cmd'
$missingPython = Join-Path $fixtureRoot 'missing\python.exe'
$manifestPath = Join-Path $fixtureTools 'seed-vc-assets.json'
$guiConfig = Join-Path $repoPath 'fixture-gui-config.yml'

$null = New-Item -ItemType Directory -Force -Path $fixtureTools, $repoPath, $modelScopePath, $shimRoot, $foreignCwd
. (Join-Path $toolRoot 'seed-vc-assets.ps1')
foreach ($name in @('seed-vc-setup.ps1', 'seed-vc-gui-run.ps1', 'seed-vc-gui-bootstrap.py', 'seed-vc-assets.ps1', 'seed-vc-gui-overlay.ps1', 'seed-vc-gui-device-selection.ps1')) {
    Copy-Item -LiteralPath (Join-Path $toolRoot $name) -Destination (Join-Path $fixtureTools $name)
}

Set-Content -LiteralPath $pythonShim -Encoding ascii -Value @'
@echo off
if defined AETHERTUNE_SEED_VC_PROCESS_CWD_MARKER (
  echo %CD%>"%AETHERTUNE_SEED_VC_PROCESS_CWD_MARKER%"
)
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

function Test-SeedVcProjectPathResolverBoundary {
    $absoluteInput = Join-Path $fixtureRoot 'absolute-path-preserved\asset.bin'
    $absoluteActual = Resolve-SeedVcProjectPath -Path $absoluteInput -ProjectRoot $foreignCwd
    if ($absoluteActual -ine [IO.Path]::GetFullPath($absoluteInput)) {
        throw "Fully qualified drive path was rebased: expected=$absoluteInput actual=$absoluteActual"
    }

    $uncInput = '\\seed-vc-test.invalid\share\asset.bin'
    $uncActual = Resolve-SeedVcProjectPath -Path $uncInput -ProjectRoot $foreignCwd
    if ($uncActual -ine [IO.Path]::GetFullPath($uncInput)) {
        throw "Fully qualified UNC path was rebased: expected=$uncInput actual=$uncActual"
    }

    $projectVolumeRoot = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($fixtureRoot))
    $rootRelativeInput = '\seed-vc-root-relative-probe\asset.bin'
    $rootRelativeExpected = [IO.Path]::GetFullPath((Join-Path $projectVolumeRoot 'seed-vc-root-relative-probe\asset.bin'))
    $rootRelativeActual = Resolve-SeedVcProjectPath -Path $rootRelativeInput -ProjectRoot $foreignCwd
    if ($rootRelativeActual -ine $rootRelativeExpected) {
        throw "Root-relative path was not anchored to the project volume: expected=$rootRelativeExpected actual=$rootRelativeActual"
    }

    $driveRelativeRejected = $false
    try { $null = Resolve-SeedVcProjectPath -Path 'C:seed-vc-drive-relative-probe\asset.bin' -ProjectRoot $fixtureRoot }
    catch { $driveRelativeRejected = $_.Exception.Message -match 'Drive-relative paths are unsupported' }
    if (-not $driveRelativeRejected) { throw 'Drive-relative paths must be rejected instead of depending on process cwd.' }
}

function Invoke-ForeignCwdRelativePathRegression {
    $setupEnvironment = Join-Path $fixtureRoot 'venvs\relative-path-setup'
    $referencePathSentinel = Join-Path $fixtureRoot 'reference-path-sentinel.wav'
    Write-SyntheticAsset -Path $referencePathSentinel -Content 'synthetic path sentinel; never decoded or played'
    $setupArguments = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-setup.ps1'),
        '-Python310','.\shims\python310.cmd','-Environment','.\venvs\relative-path-setup',
        '-Repo','.\external\seed-vc','-ModelScopeVadCache','.\modelscope-vad',
        '-AssetManifest','.\tools\seed-vc-assets.json','-PreflightOnly')
    $sessionRoot = Join-Path $fixtureRoot 'sessions\relative-path-gui'
    $guiArguments = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-gui-run.ps1'),
        '-Python','.\shims\python310.cmd','-Repo','.\external\seed-vc',
        '-Checkpoint','.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
        '-Config','.\external\seed-vc\fixture-gui-config.yml','-SessionRoot','.\sessions\relative-path-gui',
        '-ModelScopeVadCache','.\modelscope-vad','-AssetManifest','.\tools\seed-vc-assets.json',
        '-ReferenceWav','.\reference-path-sentinel.wav',
        '-InputDeviceName','Synthetic Input','-OutputDeviceName','Synthetic Output',
        '-HostApi','Synthetic DirectSound','-PreflightOnly')

    function Invoke-FixturePwshFromForeignCwd {
        param(
            [Parameter(Mandatory)][string[]]$Arguments,
            [Parameter(Mandatory)][string]$CwdMarker,
            [string]$BootstrapMarker
        )

        $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = $pwsh
        $startInfo.WorkingDirectory = $foreignCwd
        $startInfo.UseShellExecute = $false
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.Environment['PATH'] = $shimRoot + [IO.Path]::PathSeparator + $env:PATH
        $startInfo.Environment['AETHERTUNE_SEED_VC_PROCESS_CWD_MARKER'] = $CwdMarker
        if ($BootstrapMarker) { $startInfo.Environment['AETHERTUNE_GUI_BOOTSTRAP_MARKER'] = $BootstrapMarker }
        foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add($argument) }

        $process = [System.Diagnostics.Process]::Start($startInfo)
        if ($null -eq $process) { throw 'Could not start fixture pwsh process.' }
        try {
            $stdoutTask = $process.StandardOutput.ReadToEndAsync()
            $stderrTask = $process.StandardError.ReadToEndAsync()
            $process.WaitForExit()
            $stdout = $stdoutTask.GetAwaiter().GetResult()
            $stderr = $stderrTask.GetAwaiter().GetResult()
            $outputParts = @($stdout, $stderr) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
            return [pscustomobject]@{
                ExitCode = $process.ExitCode
                Output = ($outputParts -join [Environment]::NewLine)
            }
        }
        finally { $process.Dispose() }
    }

    $setupCwdMarker = Join-Path $fixtureRoot 'foreign-cwd-setup.marker'
    $guiCwdMarker = Join-Path $fixtureRoot 'foreign-cwd-gui.marker'
    $setupProcess = Invoke-FixturePwshFromForeignCwd -Arguments $setupArguments -CwdMarker $setupCwdMarker
    $guiProcess = Invoke-FixturePwshFromForeignCwd -Arguments $guiArguments -CwdMarker $guiCwdMarker
    $setupExit = $setupProcess.ExitCode
    $guiExit = $guiProcess.ExitCode

    $setupText = [string]$setupProcess.Output
    $guiText = [string]$guiProcess.Output
    $expectedWorkingDirectory = [IO.Path]::GetFullPath($foreignCwd)
    foreach ($markerPath in @($setupCwdMarker, $guiCwdMarker)) {
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) { throw "Synthetic Python shim did not record child process cwd: $markerPath" }
        $actualWorkingDirectory = [IO.Path]::GetFullPath((Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8).Trim())
        if ($actualWorkingDirectory -ine $expectedWorkingDirectory) {
            throw "Fixture child process did not run from the requested foreign cwd: expected=$expectedWorkingDirectory actual=$actualWorkingDirectory"
        }
    }
    $setupJson = [regex]::Match($setupText, '(?s)\{\s*"status"\s*:.*?"missing"\s*:\s*\[.*?\]\s*\}')
    $guiJson = [regex]::Match($guiText, '(?s)\{\s*"status"\s*:.*?"missing"\s*:\s*\[.*?\]\s*\}')
    if (-not $setupJson.Success) { throw "Foreign-CWD setup did not emit structured preflight JSON: $setupText" }
    if (-not $guiJson.Success) { throw "Foreign-CWD GUI did not emit structured preflight JSON: $guiText" }
    $setupReport = $setupJson.Value | ConvertFrom-Json
    $guiReport = $guiJson.Value | ConvertFrom-Json

    $expectedSetupPaths = @{
        source = Join-Path $fixtureRoot 'external\seed-vc'
        environment = $setupEnvironment
        asset_manifest = Join-Path $fixtureTools 'seed-vc-assets.json'
        python = $pythonShim
        modelscope_vad_path = $modelScopePath
    }
    foreach ($property in $expectedSetupPaths.Keys) {
        $expectedPath = [IO.Path]::GetFullPath([string]$expectedSetupPaths[$property])
        if ([IO.Path]::GetFullPath([string]$setupReport.$property) -ine $expectedPath) {
            throw "Foreign-CWD setup resolved $property incorrectly: expected=$expectedPath actual=$($setupReport.$property)"
        }
    }
    $expectedGuiPaths = @{
        python = $pythonShim
        session_root = $sessionRoot
        checkpoint = Join-Path $fixtureRoot 'models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth'
        config = Join-Path $repoPath 'fixture-gui-config.yml'
        requested_reference_audio_path = $referencePathSentinel
        asset_manifest = Join-Path $fixtureTools 'seed-vc-assets.json'
        modelscope_vad_path = $modelScopePath
    }
    foreach ($property in $expectedGuiPaths.Keys) {
        $expectedPath = [IO.Path]::GetFullPath([string]$expectedGuiPaths[$property])
        if ([IO.Path]::GetFullPath([string]$guiReport.$property) -ine $expectedPath) {
            throw "Foreign-CWD GUI resolved $property incorrectly: expected=$expectedPath actual=$($guiReport.$property)"
        }
    }
    if ($setupExit -ne 0 -or $setupReport.status -cne 'PASS' -or @($setupReport.missing).Count -ne 0) {
        throw "Foreign-CWD setup relative-path preflight should PASS; exit=$setupExit report=$($setupJson.Value) output=$setupText"
    }
    if ($guiExit -ne 0 -or $guiReport.status -cne 'PASS' -or @($guiReport.missing).Count -ne 0 -or
        [int]$guiReport.selected_input.index -ne 0 -or [int]$guiReport.selected_output.index -ne 1) {
        throw "Foreign-CWD GUI relative-path preflight should PASS and retain synthetic device selection; exit=$guiExit report=$($guiJson.Value) output=$guiText"
    }
    if (Test-Path -LiteralPath $setupEnvironment) { throw "Foreign-CWD setup preflight created a venv: $setupEnvironment" }
    if (Test-Path -LiteralPath $sessionRoot) { throw "Foreign-CWD GUI preflight created a session: $sessionRoot" }

    # 已保存的設定也可能含相對 reference 路徑；正常 GUI path 必須仍以 project root 解讀。
    $normalSessionRoot = Join-Path $fixtureRoot 'sessions\relative-path-gui-normal'
    $normalSessionConfig = Join-Path $normalSessionRoot 'configs\inuse\config.json'
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $normalSessionConfig)
    $savedSettings = @{
        reference_audio_path = '.\reference-path-sentinel.wav'
        sg_hostapi = 'Synthetic DirectSound'
        sg_input_device = 'Synthetic Input'
        sg_output_device = 'Synthetic Output'
    }
    Set-Content -LiteralPath $normalSessionConfig -Value ($savedSettings | ConvertTo-Json -Depth 5) -Encoding utf8
    $normalBootstrapMarker = Join-Path $fixtureRoot 'foreign-cwd-normal-gui-bootstrap.marker'
    $normalCwdMarker = Join-Path $fixtureRoot 'foreign-cwd-normal-gui.marker'
    $normalGuiArguments = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-gui-run.ps1'),
        '-Python','.\shims\python310.cmd','-Repo','.\external\seed-vc',
        '-Checkpoint','.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
        '-Config','.\external\seed-vc\fixture-gui-config.yml','-SessionRoot','.\sessions\relative-path-gui-normal',
        '-ModelScopeVadCache','.\modelscope-vad','-AssetManifest','.\tools\seed-vc-assets.json',
        '-InputDeviceName','Synthetic Input','-OutputDeviceName','Synthetic Output','-HostApi','Synthetic DirectSound')
    $normalGuiProcess = Invoke-FixturePwshFromForeignCwd -Arguments $normalGuiArguments `
        -CwdMarker $normalCwdMarker -BootstrapMarker $normalBootstrapMarker
    $normalGuiText = [string]$normalGuiProcess.Output
    if ($normalGuiProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $normalBootstrapMarker -PathType Leaf)) {
        throw "Foreign-CWD normal GUI path should reach the intercepted fake bootstrap; exit=$($normalGuiProcess.ExitCode) output=$normalGuiText"
    }
    if (-not (Test-Path -LiteralPath $normalCwdMarker -PathType Leaf)) { throw 'Normal GUI fake bootstrap did not record its working directory.' }
    $normalBootstrapCwd = [IO.Path]::GetFullPath((Get-Content -LiteralPath $normalCwdMarker -Raw -Encoding UTF8).Trim())
    if ($normalBootstrapCwd -ine [IO.Path]::GetFullPath($normalSessionRoot)) {
        throw "Foreign-CWD normal GUI did not use its resolved session root during bootstrap: expected=$normalSessionRoot actual=$normalBootstrapCwd"
    }
    $persistedSettings = Get-Content -LiteralPath $normalSessionConfig -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    $expectedReference = [IO.Path]::GetFullPath($referencePathSentinel)
    if ([IO.Path]::GetFullPath([string]$persistedSettings.reference_audio_path) -ine $expectedReference) {
        throw "Saved relative reference path was not anchored to the synthetic project root: expected=$expectedReference actual=$($persistedSettings.reference_audio_path)"
    }
    $bootstrapLines = @(Get-Content -LiteralPath $normalBootstrapMarker -Encoding UTF8)
    if ($bootstrapLines -notcontains 'GUI_BOOTSTRAP_LAUNCH_REACHED') {
        throw "Normal GUI path did not reach the fake bootstrap: $($bootstrapLines -join ' | ')"
    }
    return [pscustomobject]@{ SetupExit=$setupExit; GuiExit=$guiExit; WorkingDirectory=$foreignCwd }
}

$profileScopeSmoke = Invoke-RealtimeProfileScopeSmoke
$relativePathRegression = Invoke-ForeignCwdRelativePathRegression
Test-SeedVcProjectPathResolverBoundary

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

Write-Output "PASS Seed-VC asset manifest regression: 18 isolated negative setup/GUI cases blocked before venv, pip, session overlay, GUI window, or audio stream; realtime-only setup preflight and GUI reached an intercepted bootstrap with offline-v1 checkpoint, offline preset, and offline inference.py absent, verified config/junction/env overlay; foreign child process cwd and setup/GUI relative paths including saved reference paths were verified; fully-qualified drive/UNC paths and project-volume root-relative paths were checked, drive-relative paths rejected; no real GUI/audio; fixture=$fixtureRoot"
