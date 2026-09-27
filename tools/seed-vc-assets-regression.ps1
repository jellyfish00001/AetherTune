# Isolated contract regression for manifest-driven setup and GUI preflight gates.
# Synthetic assets live under one unique TEMP directory. The existing Seed-VC Python
# runtime is used only for import/Tcl/Tk checks; no checkpoint is loaded and no GUI or
# audio stream is opened.
#Requires -Version 7.2
[CmdletBinding()]
param([string]$PythonRuntime)

$ErrorActionPreference = 'Stop'

$toolRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $toolRoot
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
foreach ($name in @('seed-vc-setup.ps1', 'seed-vc-gui-run.ps1', 'seed-vc-gui-bootstrap.py', 'seed-vc-assets.ps1', 'seed-vc-gui-overlay.ps1', 'seed-vc-gui-device-selection.ps1')) {
    Copy-Item -LiteralPath (Join-Path $toolRoot $name) -Destination (Join-Path $fixtureTools $name)
}
. (Join-Path $toolRoot 'seed-vc-assets.ps1')

if ($PythonRuntime) { $resolvedTestPython = Resolve-SeedVcProjectPath -Path $PythonRuntime -ProjectRoot $projectRoot }
else { $resolvedTestPython = Resolve-SeedVcProjectPath -Path '.\tools\venvs\seed-vc\Scripts\python.exe' -ProjectRoot $projectRoot }
if (-not (Test-Path -LiteralPath $resolvedTestPython -PathType Leaf)) {
    throw "A real Seed-VC CPython runtime is required for the foreign-CWD import regression; pass -PythonRuntime <python.exe>. Resolved path: $resolvedTestPython"
}

Set-Content -LiteralPath $pythonShim -Encoding ascii -Value @'
@echo off
if defined AETHERTUNE_SEED_VC_PROCESS_CWD_MARKER echo %CD%>"%AETHERTUNE_SEED_VC_PROCESS_CWD_MARKER%"
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

function Invoke-ProcessFromWorkingDirectory {
    param(
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [System.Collections.IDictionary]$EnvironmentVariables = @{}
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Executable
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add($argument) }
    foreach ($name in $EnvironmentVariables.Keys) { $startInfo.Environment[[string]$name] = [string]$EnvironmentVariables[$name] }

    $process = [System.Diagnostics.Process]::Start($startInfo)
    if ($null -eq $process) { throw "Could not start process: $Executable" }
    try {
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $parts = @($stdout, $stderr) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        return [pscustomobject]@{ ExitCode=$process.ExitCode; Output=($parts -join [Environment]::NewLine) }
    }
    finally { $process.Dispose() }
}

function Test-SeedVcProjectPathResolverBoundary {
    $absoluteInput = Join-Path $fixtureRoot 'absolute-path-preserved\asset.bin'
    $absoluteActual = Resolve-SeedVcProjectPath -Path $absoluteInput -ProjectRoot $foreignCwd
    if ($absoluteActual -ine [IO.Path]::GetFullPath($absoluteInput)) { throw "Fully qualified drive path was rebased: $absoluteActual" }

    $uncInput = '\\seed-vc-test.invalid\share\asset.bin'
    $uncActual = Resolve-SeedVcProjectPath -Path $uncInput -ProjectRoot $foreignCwd
    if ($uncActual -ine [IO.Path]::GetFullPath($uncInput)) { throw "Fully qualified UNC path was rebased: $uncActual" }

    $volumeRoot = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($fixtureRoot))
    $rootRelative = '\seed-vc-root-relative-probe\asset.bin'
    $expectedRootRelative = [IO.Path]::GetFullPath((Join-Path $volumeRoot 'seed-vc-root-relative-probe\asset.bin'))
    $actualRootRelative = Resolve-SeedVcProjectPath -Path $rootRelative -ProjectRoot $foreignCwd
    if ($actualRootRelative -ine $expectedRootRelative) { throw "Root-relative path was not anchored to the project volume: $actualRootRelative" }

    foreach ($badPath in @('C:seed-vc-drive-relative-probe\asset.bin', '\\incomplete-unc')) {
        $rejected = $false
        try { $null = Resolve-SeedVcProjectPath -Path $badPath -ProjectRoot $fixtureRoot }
        catch { $rejected = $true }
        if (-not $rejected) { throw "Ambiguous path was accepted: $badPath" }
    }
}

function Invoke-RealPythonForeignCwdImportRegression {
    $sentinelMarker = Join-Path $fixtureRoot 'foreign-python-import.marker'
    $bootstrapMarker = Join-Path $fixtureRoot 'bootstrap-import-report.json'
    $pythonEnv = @{ AETHERTUNE_IMPORT_SENTINEL_MARKER=$sentinelMarker }
    Set-Content -LiteralPath (Join-Path $foreignCwd 'tkinter.py') -Encoding utf8 -Value @'
import os
from pathlib import Path
Path(os.environ["AETHERTUNE_IMPORT_SENTINEL_MARKER"]).write_text("tkinter")
raise RuntimeError("foreign CWD tkinter shadow imported")
'@
    Set-Content -LiteralPath (Join-Path $foreignCwd 'torch.py') -Encoding utf8 -Value @'
import os
from pathlib import Path
Path(os.environ["AETHERTUNE_IMPORT_SENTINEL_MARKER"]).write_text("torch")
raise RuntimeError("foreign CWD torch shadow imported")
'@

    $setupProbeCode = "import json,sys; p={'version':list(sys.version_info[:3]),'bits':__import__('struct').calcsize('P')*8}; import tkinter; t=tkinter.Tcl(); p['tcl']=t.eval('info patchlevel'); t.call('package','require','Tk'); p['tk']='available'; print(json.dumps(p))"
    $legacyTk = Invoke-ProcessFromWorkingDirectory -Executable $resolvedTestPython -Arguments @('-c',$setupProbeCode) -WorkingDirectory $foreignCwd -EnvironmentVariables $pythonEnv
    if ($legacyTk.ExitCode -eq 0 -or (Get-Content -LiteralPath $sentinelMarker -Raw -Encoding UTF8).Trim() -cne 'tkinter') {
        throw 'Real CPython fixture did not reproduce foreign-CWD tkinter shadowing without isolated mode.'
    }
    Remove-Item -LiteralPath $sentinelMarker -Force
    $isolatedTk = Invoke-ProcessFromWorkingDirectory -Executable $resolvedTestPython -Arguments @('-I','-B','-c',$setupProbeCode) -WorkingDirectory $foreignCwd -EnvironmentVariables $pythonEnv
    if ($isolatedTk.ExitCode -ne 0 -or $isolatedTk.Output -match [regex]::Escape($foreignCwd) -or (Test-Path -LiteralPath $sentinelMarker)) {
        throw "CPython -I -B did not isolate tkinter/Tcl/Tk from the foreign CWD; exit=$($isolatedTk.ExitCode) output=$($isolatedTk.Output)"
    }
    $setupProbeReport = ($isolatedTk.Output.Trim().Split([Environment]::NewLine) | Select-Object -Last 1) | ConvertFrom-Json
    if ($setupProbeReport.version[0] -ne 3 -or $setupProbeReport.version[1] -ne 10 -or $setupProbeReport.bits -ne 64 -or $setupProbeReport.tk -cne 'available') {
        throw "Real Seed-VC Python did not pass the exact isolated setup Tk probe: $($isolatedTk.Output)"
    }

    $actualSetupEnvironment = Join-Path $fixtureRoot 'venvs\real-cpython-setup-preflight'
    $actualSetupArgs = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-setup.ps1'),
        '-Python310',$resolvedTestPython,'-Environment',$actualSetupEnvironment,
        '-Repo',$repoPath,'-ModelScopeVadCache',$modelScopePath,'-AssetManifest',$manifestPath,'-PreflightOnly')
    $actualSetupEnv = @{ PATH=$shimRoot + [IO.Path]::PathSeparator + $env:PATH; PYTHONPATH=$foreignCwd; AETHERTUNE_IMPORT_SENTINEL_MARKER=$sentinelMarker }
    $actualSetupRun = Invoke-ProcessFromWorkingDirectory -Executable $pwsh -Arguments $actualSetupArgs -WorkingDirectory $foreignCwd -EnvironmentVariables $actualSetupEnv
    $actualSetupReport = Get-SeedVcPreflightReport -Output $actualSetupRun.Output -Label 'Real CPython setup preflight'
    if ($actualSetupRun.ExitCode -ne 0 -or $actualSetupReport.status -cne 'PASS' -or
        [string]$actualSetupReport.python -ine [string]$resolvedTestPython -or
        $actualSetupReport.python_probe.tk -cne 'available' -or
        (Test-Path -LiteralPath $sentinelMarker) -or (Test-Path -LiteralPath $actualSetupEnvironment)) {
        throw "Real CPython setup preflight did not pass in the foreign-CWD fixture without mutation: exit=$($actualSetupRun.ExitCode) report=$($actualSetupRun.Output)"
    }

    $legacyTorch = Invoke-ProcessFromWorkingDirectory -Executable $resolvedTestPython -Arguments @('-c','import torch; print(torch.__file__)') -WorkingDirectory $foreignCwd -EnvironmentVariables $pythonEnv
    if ($legacyTorch.ExitCode -eq 0 -or (Get-Content -LiteralPath $sentinelMarker -Raw -Encoding UTF8).Trim() -cne 'torch') {
        throw 'Real CPython fixture did not reproduce foreign-CWD torch shadowing without isolated mode.'
    }
    Remove-Item -LiteralPath $sentinelMarker -Force
    $isolatedTorch = Invoke-ProcessFromWorkingDirectory -Executable $resolvedTestPython -Arguments @('-I','-B','-c','import torch; print(torch.__file__)') -WorkingDirectory $foreignCwd -EnvironmentVariables $pythonEnv
    if ($isolatedTorch.ExitCode -ne 0 -or $isolatedTorch.Output -match [regex]::Escape($foreignCwd) -or (Test-Path -LiteralPath $sentinelMarker)) {
        throw "CPython -I did not isolate torch from the foreign CWD; exit=$($isolatedTorch.ExitCode) output=$($isolatedTorch.Output)"
    }

    $setupSource = Get-Content -LiteralPath (Join-Path $toolRoot 'seed-vc-setup.ps1') -Raw -Encoding UTF8
    $guiSource = Get-Content -LiteralPath (Join-Path $toolRoot 'seed-vc-gui-run.ps1') -Raw -Encoding UTF8
    $bootstrapSource = Get-Content -LiteralPath (Join-Path $toolRoot 'seed-vc-gui-bootstrap.py') -Raw -Encoding UTF8
    if ($setupSource -notmatch '(?m)& \$resolvedPython -I -B -c' -or
        $setupSource -notmatch '(?m)-3\.10 -I -B -c' -or
        $setupSource -notmatch '(?m)& \$envPython -I -B -c' -or
        $guiSource -notmatch '(?m)& \$resolvedPython -I -B -c' -or
        $guiSource -notmatch '(?m)& \$resolvedPython -I -B \(Join-Path .*seed-vc-gui-bootstrap\.py' -or
        $bootstrapSource -notmatch 'sys\.path\.insert\(0,\s*str\(repo_path\)\)') {
        throw 'Setup/GUI Python probes and GUI bootstrap must keep isolated import mode and explicitly add the pinned upstream repository path.'
    }

    $bootstrapRepo = Join-Path $fixtureRoot 'bootstrap-upstream'
    $bootstrapVad = Join-Path $fixtureRoot 'bootstrap-vad'
    $bootstrapCheckpoint = Join-Path $fixtureRoot 'bootstrap-checkpoint.pth'
    $bootstrapConfig = Join-Path $fixtureRoot 'bootstrap-config.yml'
    $probeModulePath = Join-Path $bootstrapRepo 'aether_seed_vc_import_probe.py'
    $fakeGuiPath = Join-Path $bootstrapRepo 'real-time-gui.py'
    $null = New-Item -ItemType Directory -Force -Path $bootstrapRepo, $bootstrapVad
    Set-Content -LiteralPath $probeModulePath -Encoding utf8 -Value 'FIXTURE_SOURCE = "explicit-upstream-path"'
    Set-Content -LiteralPath $fakeGuiPath -Encoding utf8 -Value @'
import json, os, sys, tkinter, torch
import aether_seed_vc_import_probe
from pathlib import Path
payload = {"tkinter": tkinter.__file__, "torch": torch.__file__, "probe": aether_seed_vc_import_probe.__file__, "sys_path0": sys.path[0]}
Path(os.environ["AETHERTUNE_SEED_VC_BOOTSTRAP_MARKER"]).write_text(json.dumps(payload))
'@
    Set-Content -LiteralPath $bootstrapCheckpoint -Value 'synthetic checkpoint marker' -Encoding ascii
    Set-Content -LiteralPath $bootstrapConfig -Value 'synthetic config marker' -Encoding ascii
    foreach ($vadFile in @('model.pt','config.yaml','configuration.json','am.mvn')) {
        Set-Content -LiteralPath (Join-Path $bootstrapVad $vadFile) -Value 'synthetic VAD marker' -Encoding ascii
    }
    $bootstrapEnv = @{
        AETHERTUNE_IMPORT_SENTINEL_MARKER=$sentinelMarker
        AETHERTUNE_SEED_VC_REPO=$bootstrapRepo
        AETHERTUNE_SEED_VC_GUI=$fakeGuiPath
        AETHERTUNE_SEED_VC_CHECKPOINT=$bootstrapCheckpoint
        AETHERTUNE_SEED_VC_CONFIG=$bootstrapConfig
        AETHERTUNE_SEED_VC_VAD_PATH=$bootstrapVad
        AETHERTUNE_SEED_VC_BOOTSTRAP_MARKER=$bootstrapMarker
        PYTHONPATH=$foreignCwd
    }
    $bootstrapRun = Invoke-ProcessFromWorkingDirectory -Executable $resolvedTestPython -Arguments @('-I','-B',(Join-Path $toolRoot 'seed-vc-gui-bootstrap.py')) -WorkingDirectory $foreignCwd -EnvironmentVariables $bootstrapEnv
    if ($bootstrapRun.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $bootstrapMarker -PathType Leaf) -or (Test-Path -LiteralPath $sentinelMarker)) {
        throw "Isolated GUI bootstrap did not complete the synthetic import probe; exit=$($bootstrapRun.ExitCode) output=$($bootstrapRun.Output)"
    }
    $bootstrapReport = Get-Content -LiteralPath $bootstrapMarker -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([IO.Path]::GetFullPath($bootstrapReport.probe) -ine [IO.Path]::GetFullPath($probeModulePath) -or
        [IO.Path]::GetFullPath($bootstrapReport.sys_path0) -ine [IO.Path]::GetFullPath($bootstrapRepo) -or
        $bootstrapReport.torch -match [regex]::Escape($foreignCwd) -or
        $bootstrapReport.tkinter -match [regex]::Escape($foreignCwd)) {
        throw "GUI bootstrap import roots were not isolated and explicit: $bootstrapMarker"
    }

    return [pscustomobject]@{ TkExit=$isolatedTk.ExitCode; TorchExit=$isolatedTorch.ExitCode; BootstrapExit=$bootstrapRun.ExitCode; Python=$resolvedTestPython }
}

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
        'transformers_offline=1'
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

<# HEAD-era path harness is superseded by the generalized phase 2 foreign-CWD regression below.
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

#>
function Get-SeedVcPreflightReport {
    param(
        [Parameter(Mandatory)][string]$Output,
        [Parameter(Mandatory)][string]$Label
    )

    $jsonMatch = [regex]::Match($Output, '(?s)\{\s*"status"\s*:.*?"missing"\s*:\s*\[.*?\]\s*\}')
    if (-not $jsonMatch.Success) { throw "$Label did not emit structured preflight JSON: $Output" }
    return ($jsonMatch.Value | ConvertFrom-Json)
}

function Invoke-ForeignCwdPowerShell {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$CwdMarker,
        [hashtable]$AdditionalEnvironment = @{}
    )

    $environment = @{ PATH = $shimRoot + [IO.Path]::PathSeparator + $env:PATH; AETHERTUNE_SEED_VC_PROCESS_CWD_MARKER = $CwdMarker }
    foreach ($name in $AdditionalEnvironment.Keys) { $environment[$name] = [string]$AdditionalEnvironment[$name] }
    return Invoke-ProcessFromWorkingDirectory -Executable $pwsh -Arguments $Arguments -WorkingDirectory $foreignCwd -EnvironmentVariables $environment
}

function Invoke-ForeignCwdPathRegression {
    $referenceSentinel = Join-Path $fixtureRoot 'reference-path-sentinel.wav'
    Write-SyntheticAsset -Path $referenceSentinel -Content 'synthetic path sentinel; never decoded or played'
    $setupEnvironment = Join-Path $fixtureRoot 'venvs\foreign-cwd-setup'
    $setupMarker = Join-Path $fixtureRoot 'foreign-cwd-setup.marker'
    $setupArgs = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-setup.ps1'),
        '-Python310','.\shims\python310.cmd','-Environment','.\venvs\foreign-cwd-setup',
        '-Repo','.\external\seed-vc','-ModelScopeVadCache','.\modelscope-vad',
        '-AssetManifest','.\tools\seed-vc-assets.json','-PreflightOnly')
    $setupRun = Invoke-ForeignCwdPowerShell -Arguments $setupArgs -CwdMarker $setupMarker
    $setupReport = Get-SeedVcPreflightReport -Output $setupRun.Output -Label 'Foreign-CWD setup'
    $expectedSetupPaths = @{
        source = Join-Path $fixtureRoot 'external\seed-vc'
        environment = $setupEnvironment
        asset_manifest = Join-Path $fixtureTools 'seed-vc-assets.json'
        python = $pythonShim
        modelscope_vad_path = $modelScopePath
    }
<# Keep phase 2's exit, CWD, and no-mutation assertions for setup.
    foreach ($property in $expectedSetupPaths.Keys) {
        $expectedPath = [IO.Path]::GetFullPath([string]$expectedSetupPaths[$property])
        if ([IO.Path]::GetFullPath([string]$setupReport.$property) -ine $expectedPath) {
            throw "Foreign-CWD setup resolved $property incorrectly: expected=$expectedPath actual=$($setupReport.$property)"
        }
    }
#>
    if ($setupRun.ExitCode -ne 0 -or $setupReport.status -cne 'PASS' -or @($setupReport.missing).Count -ne 0) {
        throw "Foreign-CWD setup relative-path preflight should PASS; exit=$($setupRun.ExitCode) report=$($setupRun.Output)"
    }
    foreach ($property in $expectedSetupPaths.Keys) {
        if ([IO.Path]::GetFullPath([string]$setupReport.$property) -ine [IO.Path]::GetFullPath([string]$expectedSetupPaths[$property])) {
            throw "Foreign-CWD setup resolved $property incorrectly: $($setupReport.$property)"
        }
    }
    if ([IO.Path]::GetFullPath((Get-Content -LiteralPath $setupMarker -Raw -Encoding UTF8).Trim()) -ine [IO.Path]::GetFullPath($foreignCwd)) {
        throw 'Setup preflight changed the caller working directory before invoking Python.'
    }
    if (Test-Path -LiteralPath $setupEnvironment) { throw "Foreign-CWD setup preflight created a venv: $setupEnvironment" }

    $sessionRoot = Join-Path $fixtureRoot 'sessions\foreign-cwd-gui-preflight'
    $guiMarker = Join-Path $fixtureRoot 'foreign-cwd-gui.marker'
    $guiArgs = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-gui-run.ps1'),
        '-Python','.\shims\python310.cmd','-Repo','.\external\seed-vc',
        '-Checkpoint','.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
        '-Config','.\external\seed-vc\fixture-gui-config.yml','-SessionRoot','.\sessions\foreign-cwd-gui-preflight',
        '-ModelScopeVadCache','.\modelscope-vad','-AssetManifest','.\tools\seed-vc-assets.json',
        '-ReferenceWav','.\reference-path-sentinel.wav',
        '-InputDeviceName','Synthetic Input','-OutputDeviceName','Synthetic Output',
        '-HostApi','Synthetic DirectSound','-PreflightOnly')
    $guiRun = Invoke-ForeignCwdPowerShell -Arguments $guiArgs -CwdMarker $guiMarker
    $guiReport = Get-SeedVcPreflightReport -Output $guiRun.Output -Label 'Foreign-CWD GUI'
    $expectedGuiPaths = @{
        python = $pythonShim
        session_root = $sessionRoot
        checkpoint = Join-Path $fixtureRoot 'models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth'
        config = Join-Path $repoPath 'fixture-gui-config.yml'
<# HEAD-era GUI assertions are superseded by the phase 2 requested/effective-reference checks.
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
#>
        effective_reference = $referenceSentinel
        asset_manifest = Join-Path $fixtureTools 'seed-vc-assets.json'
        modelscope_vad_path = $modelScopePath
    }
    if ($guiRun.ExitCode -ne 0 -or $guiReport.status -cne 'PASS' -or @($guiReport.missing).Count -ne 0 -or
        [int]$guiReport.selected_input.index -ne 0 -or [int]$guiReport.selected_output.index -ne 1) {
        throw "Foreign-CWD GUI preflight should PASS with the synthetic endpoint pair; exit=$($guiRun.ExitCode) report=$($guiRun.Output)"
    }
    foreach ($property in $expectedGuiPaths.Keys) {
        if ([IO.Path]::GetFullPath([string]$guiReport.$property) -ine [IO.Path]::GetFullPath([string]$expectedGuiPaths[$property])) {
            throw "Foreign-CWD GUI resolved $property incorrectly: $($guiReport.$property)"
        }
    }
    if ($guiReport.requested_reference -cne '.\reference-path-sentinel.wav' -or
        $guiReport.reference_source -cne 'command-line' -or
        [IO.Path]::GetFullPath((Get-Content -LiteralPath $guiMarker -Raw -Encoding UTF8).Trim()) -ine [IO.Path]::GetFullPath($foreignCwd)) {
        throw 'GUI preflight did not preserve the caller CWD and requested/effective reference distinction.'
    }
    if (Test-Path -LiteralPath $sessionRoot) { throw "Foreign-CWD GUI preflight created a session overlay: $sessionRoot" }

    Test-SeedVcProjectPathResolverBoundary
    return [pscustomobject]@{ SetupExit=$setupRun.ExitCode; GuiExit=$guiRun.ExitCode; WorkingDirectory=$foreignCwd }
}

function Invoke-GuiReferencePreflightCase {
    param(
        [Parameter(Mandatory)][string]$CaseName,
        [Parameter(Mandatory)][System.Collections.IDictionary]$SavedSettings,
        [Parameter(Mandatory)][bool]$ExpectedPass,
        [AllowEmptyString()][string]$ExpectedEffectiveReference,
        [AllowEmptyString()][string]$ExpectedSource,
        [string[]]$ReferenceArguments = @()
    )

    $sessionRoot = Join-Path $fixtureRoot "sessions\reference-$CaseName"
    $settingsPath = Join-Path $sessionRoot 'configs\inuse\config.json'
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $settingsPath)
    Set-Content -LiteralPath $settingsPath -Value ($SavedSettings | ConvertTo-Json -Depth 8) -Encoding utf8
    $beforeHash = (Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash
    $cwdMarker = Join-Path $fixtureRoot "reference-$CaseName-cwd.marker"
    $arguments = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-gui-run.ps1'),
        '-Python','.\shims\python310.cmd','-Repo','.\external\seed-vc',
        '-Checkpoint','.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
        '-Config','.\external\seed-vc\fixture-gui-config.yml','-SessionRoot',".\sessions\reference-$CaseName",
        '-ModelScopeVadCache','.\modelscope-vad','-AssetManifest','.\tools\seed-vc-assets.json',
        '-InputDeviceName','Synthetic Input','-OutputDeviceName','Synthetic Output','-HostApi','Synthetic DirectSound') + $ReferenceArguments + @('-PreflightOnly')
    $run = Invoke-ForeignCwdPowerShell -Arguments $arguments -CwdMarker $cwdMarker
    $report = Get-SeedVcPreflightReport -Output $run.Output -Label "Reference case $CaseName"
    $expectedStatus = if ($ExpectedPass) { 'PASS' } else { 'BLOCKED' }
    $expectedExit = if ($ExpectedPass) { 0 } else { $null }
    if ($report.status -cne $expectedStatus -or ($ExpectedPass -and $run.ExitCode -ne $expectedExit) -or (-not $ExpectedPass -and $run.ExitCode -eq 0)) {
        throw "Reference case $CaseName expected $expectedStatus; exit=$($run.ExitCode) report=$($run.Output)"
    }
    if ([string]$report.effective_reference -cne [string]$ExpectedEffectiveReference -or [string]$report.reference_source -cne [string]$ExpectedSource) {
        throw "Reference case $CaseName selected the wrong effective reference/source: effective=$($report.effective_reference) source=$($report.reference_source)"
    }
    if ([IO.Path]::GetFullPath((Get-Content -LiteralPath $cwdMarker -Raw -Encoding UTF8).Trim()) -ine [IO.Path]::GetFullPath($foreignCwd)) {
        throw "Reference case $CaseName did not preserve foreign caller CWD."
    }
    if ((Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash -cne $beforeHash) {
        throw "Blocked/readonly reference preflight mutated saved settings for $CaseName."
    }
    foreach ($forbidden in @('checkpoints','modelscope','hf-home','configs\config.json','configs\hifigan.yml')) {
        if (Test-Path -LiteralPath (Join-Path $sessionRoot $forbidden)) {
            throw "Reference preflight mutated session overlay path $forbidden in case $CaseName."
        }
    }
    return [pscustomobject]@{ Case=$CaseName; ExitCode=$run.ExitCode; Status=$report.status; EffectiveReference=$report.effective_reference; Source=$report.reference_source }
}

$realPythonImportRegression = Invoke-RealPythonForeignCwdImportRegression
$foreignCwdPathRegression = Invoke-ForeignCwdPathRegression

$referenceSentinel = Join-Path $fixtureRoot 'reference-path-sentinel.wav'
Write-SyntheticAsset -Path $referenceSentinel -Content 'synthetic reference marker; never decoded or played'
$referenceCases = @(
    (Invoke-GuiReferencePreflightCase -CaseName 'missing-saved' -SavedSettings @{ reference_audio_path='.\missing-reference.wav' } -ExpectedPass $false -ExpectedEffectiveReference '' -ExpectedSource ''),
    (Invoke-GuiReferencePreflightCase -CaseName 'relative-saved' -SavedSettings @{ reference_audio_path='.\reference-path-sentinel.wav' } -ExpectedPass $true -ExpectedEffectiveReference $referenceSentinel -ExpectedSource 'saved'),
    (Invoke-GuiReferencePreflightCase -CaseName 'cli-overrides-missing-saved' -SavedSettings @{ reference_audio_path='.\missing-reference.wav' } -ExpectedPass $true -ExpectedEffectiveReference $referenceSentinel -ExpectedSource 'command-line' -ReferenceArguments @('-ReferenceWav','.\reference-path-sentinel.wav')),
    (Invoke-GuiReferencePreflightCase -CaseName 'clear-overrides-missing-saved' -SavedSettings @{ reference_audio_path='.\missing-reference.wav' } -ExpectedPass $true -ExpectedEffectiveReference '' -ExpectedSource 'cleared' -ReferenceArguments @('-ClearReference')),
    (Invoke-GuiReferencePreflightCase -CaseName 'cli-takes-precedence-over-clear' -SavedSettings @{ reference_audio_path='.\missing-reference.wav' } -ExpectedPass $true -ExpectedEffectiveReference $referenceSentinel -ExpectedSource 'command-line' -ReferenceArguments @('-ReferenceWav','.\reference-path-sentinel.wav','-ClearReference')),
    (Invoke-GuiReferencePreflightCase -CaseName 'drive-relative-saved' -SavedSettings @{ reference_audio_path='C:seed-vc-relative.wav' } -ExpectedPass $false -ExpectedEffectiveReference '' -ExpectedSource ''),
    (Invoke-GuiReferencePreflightCase -CaseName 'malformed-saved-reference-type' -SavedSettings @{ reference_audio_path=@{ path='.\reference-path-sentinel.wav' } } -ExpectedPass $false -ExpectedEffectiveReference '' -ExpectedSource '')
)
$malformedSession = Join-Path $fixtureRoot 'sessions\reference-malformed-json'
$malformedSettings = Join-Path $malformedSession 'configs\inuse\config.json'
$null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $malformedSettings)
Set-Content -LiteralPath $malformedSettings -Value '{"reference_audio_path":' -Encoding utf8
$malformedMarker = Join-Path $fixtureRoot 'reference-malformed-json-cwd.marker'
$malformedArgs = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-gui-run.ps1'),
    '-Python','.\shims\python310.cmd','-Repo','.\external\seed-vc',
    '-Checkpoint','.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
    '-Config','.\external\seed-vc\fixture-gui-config.yml','-SessionRoot','.\sessions\reference-malformed-json',
    '-ModelScopeVadCache','.\modelscope-vad','-AssetManifest','.\tools\seed-vc-assets.json',
    '-InputDeviceName','Synthetic Input','-OutputDeviceName','Synthetic Output','-HostApi','Synthetic DirectSound','-PreflightOnly')
$malformedRun = Invoke-ForeignCwdPowerShell -Arguments $malformedArgs -CwdMarker $malformedMarker
$malformedReport = Get-SeedVcPreflightReport -Output $malformedRun.Output -Label 'Malformed saved settings'
if ($malformedRun.ExitCode -eq 0 -or $malformedReport.status -cne 'BLOCKED' -or
    ($malformedReport.missing -join ' ') -notmatch 'settings are invalid JSON') {
    throw "Malformed saved settings must block before overlay mutation; exit=$($malformedRun.ExitCode) report=$($malformedRun.Output)"
}
foreach ($forbidden in @('checkpoints','modelscope','hf-home','configs\config.json','configs\hifigan.yml')) {
    if (Test-Path -LiteralPath (Join-Path $malformedSession $forbidden)) { throw "Malformed settings created session overlay path $forbidden." }
}

$normalReferenceSession = Join-Path $fixtureRoot 'sessions\reference-normal-launch'
$normalReferenceSettings = Join-Path $normalReferenceSession 'configs\inuse\config.json'
$null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $normalReferenceSettings)
Set-Content -LiteralPath $normalReferenceSettings -Value (@{ reference_audio_path='.\reference-path-sentinel.wav'; sg_hostapi='Synthetic DirectSound'; sg_input_device='Synthetic Input'; sg_output_device='Synthetic Output' } | ConvertTo-Json -Depth 5) -Encoding utf8
$normalReferenceBootstrap = Join-Path $fixtureRoot 'reference-normal-bootstrap.marker'
$normalReferenceCwd = Join-Path $fixtureRoot 'reference-normal-cwd.marker'
$normalReferenceArgs = @('-NoProfile','-File',(Join-Path $fixtureTools 'seed-vc-gui-run.ps1'),
    '-Python','.\shims\python310.cmd','-Repo','.\external\seed-vc',
    '-Checkpoint','.\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth',
    '-Config','.\external\seed-vc\fixture-gui-config.yml','-SessionRoot','.\sessions\reference-normal-launch',
    '-ModelScopeVadCache','.\modelscope-vad','-AssetManifest','.\tools\seed-vc-assets.json',
    '-InputDeviceName','Synthetic Input','-OutputDeviceName','Synthetic Output','-HostApi','Synthetic DirectSound')
$normalReferenceRun = Invoke-ForeignCwdPowerShell -Arguments $normalReferenceArgs -CwdMarker $normalReferenceCwd -AdditionalEnvironment @{ AETHERTUNE_GUI_BOOTSTRAP_MARKER=$normalReferenceBootstrap }
if ($normalReferenceRun.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $normalReferenceBootstrap -PathType Leaf)) {
    throw "Normal GUI launch with a saved relative reference should reach the intercepted bootstrap; exit=$($normalReferenceRun.ExitCode) output=$($normalReferenceRun.Output)"
}
$normalReferencePersisted = Get-Content -LiteralPath $normalReferenceSettings -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
if ([IO.Path]::GetFullPath([string]$normalReferencePersisted.reference_audio_path) -ine [IO.Path]::GetFullPath($referenceSentinel)) {
    throw "Normal GUI launch did not persist the same resolved saved reference: $($normalReferencePersisted.reference_audio_path)"
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

Write-Output "PASS Seed-VC Phase 1 regression: 18 manifest-negative setup/GUI cases blocked before mutation; project-root paths and foreign caller CWD verified; $($referenceCases.Count) saved/CLI/clear/malformed-reference cases plus malformed JSON blocked or resolved before overlay writes; actual Seed-VC CPython 3.10.11 reproduced tkinter.py/torch.py CWD shadowing, exact Tk setup probe passed with -I -B, real setup preflight passed in the foreign CWD, and isolated GUI bootstrap imported a synthetic module from its explicit upstream path; GUI bootstrap/cache overlay used fixtures only and did not start model inference, GUI window, or audio."
