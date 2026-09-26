#Requires -Version 7.0
$ErrorActionPreference = 'Stop'

$setupScript = Join-Path $PSScriptRoot 'seed-vc-setup.ps1'
$pwsh = Get-Command 'pwsh.exe' -ErrorAction Stop
$windowsPowerShell = Get-Command 'powershell.exe' -ErrorAction Stop
$fixtureRoot = Join-Path $env:TEMP ("aethertune-seed-vc-setup-preflight-" + [Guid]::NewGuid().ToString('N'))
$fixtureTools = Join-Path $fixtureRoot 'tools'
$fixtureScript = Join-Path $fixtureTools 'seed-vc-setup.ps1'
$fixtureAssetsHelper = Join-Path $fixtureTools 'seed-vc-assets.ps1'
$fixtureAssetManifest = Join-Path $fixtureTools 'seed-vc-assets.json'
$repoPath = Join-Path $fixtureRoot 'external\seed-vc'
$fixtureEnvironment = Join-Path $fixtureTools 'venvs\seed-vc-normal-start'
$missingPythonEnvironment = Join-Path $fixtureTools 'venvs\seed-vc-missing-python'
$modelScopePath = Join-Path $fixtureRoot 'fixture-modelscope-vad'
$shimRoot = Join-Path $fixtureRoot 'shims'
$pythonShim = Join-Path $shimRoot 'python310.cmd'
$gitShim = Join-Path $shimRoot 'git.cmd'
$missingPython = Join-Path $fixtureRoot 'not-installed\python.exe'

$null = New-Item -ItemType Directory -Force -Path $fixtureTools, $repoPath, $modelScopePath, $shimRoot
$ps51SmokeScript = Join-Path $fixtureRoot 'ps51-setup-smoke.ps1'
Set-Content -LiteralPath $ps51SmokeScript -Encoding ascii -Value @'
param(
    [Parameter(Mandatory)][string]$SetupPath,
    [Parameter(Mandatory)][string]$AssetsHelperPath,
    [Parameter(Mandatory)][string]$ManifestPath
)
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($SetupPath, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Output $_.Message }
    exit 1
}
. $AssetsHelperPath
$manifest = Read-SeedVcAssetManifest -Path $ManifestPath
if ($manifest.seed_vc_source.required_files.Count -ne 4 -or $manifest.checkpoints.Count -ne 2 -or
    $manifest.huggingface_repositories.Count -ne 3 -or $manifest.model_scope_fsmn_vad.files.Count -ne 4) {
    Write-Output 'Seed-VC manifest collection counts did not match the registered contract.'
    exit 1
}
Write-Output 'PASS Windows PowerShell 5.1 setup parser and asset manifest loader.'
'@
$ps51SmokeOutput = @(& $windowsPowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $ps51SmokeScript `
    $setupScript (Join-Path $PSScriptRoot 'seed-vc-assets.ps1') (Join-Path $PSScriptRoot 'seed-vc-assets.json') 2>&1)
$ps51SmokeExit = $LASTEXITCODE
if ($ps51SmokeExit -ne 0 -or ($ps51SmokeOutput -join ' ') -notmatch 'PASS Windows PowerShell 5\.1 setup parser and asset manifest loader') {
    throw "Windows PowerShell 5.1 setup/manifest smoke failed; exit=$ps51SmokeExit; output=$($ps51SmokeOutput -join ' ')"
}

Copy-Item -LiteralPath $setupScript -Destination $fixtureScript
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'seed-vc-assets.ps1') -Destination $fixtureAssetsHelper
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'seed-vc-assets.json') -Destination $fixtureAssetManifest

# 只回傳 setup probe 所需的 Python 3.10/Tcl/Tk JSON，不執行任何安裝命令。
$pythonShimBody = @'
@echo off
echo {"version":[3,10,11],"bits":64,"tcl":"8.6.12","tk":"available"}
exit /b 0
'@
Set-Content -LiteralPath $pythonShim -Value $pythonShimBody -Encoding ascii

# 固定 revision 僅供隔離 fixture 通過 source gate；不呼叫真實 Git repository。
$gitShimBody = @'
@echo off
if /i "%~1"=="-C" if /i "%~3"=="rev-parse" if /i "%~4"=="HEAD" (
  echo 51383efd921027683c89e5348211d93ff12ac2a8
  exit /b 0
)
echo BLOCKED: unexpected synthetic git invocation %* 1>&2
exit /b 2
'@
Set-Content -LiteralPath $gitShim -Value $gitShimBody -Encoding ascii

# 建立純文字的虛構前置項目；沒有模型內容、安裝、pip 或第三方 repo 下載。
$repoFiles = @(
    'real-time-gui.py',
    'requirements.txt',
    'configs\presets\config_dit_mel_seed_uvit_xlsr_tiny.yml',
    'configs\hifigan.yml'
)
foreach ($relativePath in $repoFiles) {
    $path = Join-Path $repoPath $relativePath
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path)
    if ($relativePath -ceq 'configs\hifigan.yml') { $null = New-Item -ItemType File -Path $path }
    else { Set-Content -LiteralPath $path -Value 'synthetic fixture only' -Encoding utf8 }
}
$null = New-Item -ItemType Directory -Force -Path (Join-Path $repoPath '.git')

$offlineCheckpoint = Join-Path $fixtureRoot 'models\seed-vc\checkpoints\offline-v1\DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth'
$realtimeCheckpoint = Join-Path $fixtureRoot 'models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth'
$null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $offlineCheckpoint), (Split-Path -Parent $realtimeCheckpoint)
# The offline-v1 checkpoint and Whisper preset are deliberately absent: setup only gates realtime-tiny.
$null = New-Item -ItemType Directory -Path $realtimeCheckpoint

$hfAssets = @{
    'models--facebook--wav2vec2-xls-r-300m' = @('pytorch_model.bin', 'config.json', 'preprocessor_config.json')
    'models--funasr--campplus' = @('campplus_cn_common.bin')
    'models--FunAudioLLM--CosyVoice-300M' = @('hift.pt')
}
foreach ($repoName in $hfAssets.Keys) {
    $cachePath = Join-Path (Join-Path $repoPath 'checkpoints') $repoName
    $snapshotId = 'abcdef0123456789'
    $refPath = Join-Path $cachePath 'refs\main'
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $refPath)
    Set-Content -LiteralPath $refPath -Value $snapshotId -Encoding ascii
    foreach ($assetName in $hfAssets[$repoName]) {
        $assetPath = Join-Path (Join-Path (Join-Path $cachePath 'snapshots') $snapshotId) $assetName
        $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $assetPath)
        Set-Content -LiteralPath $assetPath -Value 'synthetic fixture only' -Encoding ascii
    }
}
foreach ($vadName in @('model.pt', 'config.yaml', 'configuration.json', 'am.mvn')) {
    Set-Content -LiteralPath (Join-Path $modelScopePath $vadName) -Value 'synthetic fixture only' -Encoding ascii
}

function Invoke-SetupFixture {
    param(
        [Parameter(Mandatory)][string]$PythonPath,
        [Parameter(Mandatory)][string]$EnvironmentPath,
        [switch]$PreflightOnly
    )

    $argumentList = @(
        '-NoProfile', '-File', $fixtureScript,
        '-Python310', $PythonPath,
        '-Environment', $EnvironmentPath,
        '-Repo', $repoPath,
        '-ModelScopeVadCache', $modelScopePath
    )
    if ($PreflightOnly) { $argumentList += '-PreflightOnly' }

    $previousPath = $env:PATH
    try {
        $env:PATH = $shimRoot + [IO.Path]::PathSeparator + $previousPath
        $childOutput = @(& $pwsh.Source @argumentList 2>&1)
        $childExitCode = $LASTEXITCODE
    }
    finally { $env:PATH = $previousPath }

    $outputText = ($childOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    $jsonMatch = [regex]::Match($outputText, '(?s)\{\s*"status"\s*:.*?"missing"\s*:\s*\[.*?\]\s*\}')
    if (-not $jsonMatch.Success) { throw "Setup preflight did not emit its JSON report. Output: $outputText" }
    $report = $jsonMatch.Value | ConvertFrom-Json
    return [pscustomobject]@{ ExitCode = $childExitCode; OutputText = $outputText; Report = $report }
}

# 第一個呼叫走一般 setup 路徑（不傳 -PreflightOnly），Python probe 和固定 revision 由本機 shim 回答。
# realtime-tiny 的 Hifi-GAN config 與 checkpoint 無效時必須先阻止 mutation；缺席的 offline-v1 不應成為 finding。
$normalRun = Invoke-SetupFixture -PythonPath $pythonShim -EnvironmentPath $fixtureEnvironment
if ($normalRun.ExitCode -eq 0 -or $normalRun.Report.status -cne 'BLOCKED') {
    throw "Synthetic normal setup should exit nonzero with BLOCKED; exit=$($normalRun.ExitCode) status=$($normalRun.Report.status)"
}
if ($normalRun.Report.python_probe.bits -ne 64 -or ($normalRun.Report.python_probe.version -join '.') -ne '3.10.11' -or
    $normalRun.Report.python_probe.tcl -cne '8.6.12' -or $normalRun.Report.python_probe.tk -cne 'available') {
    throw 'Local Python shim did not satisfy the expected Python 3.10 x64/Tcl/Tk probe.'
}

$expectedFindingPrefixes = @(
    'Seed-VC required source file is missing, not regular, or empty: configs/hifigan.yml',
    'Seed-VC realtime-tiny checkpoint is missing or not a regular file:',
    'Hugging Face local snapshot revision mismatch for facebook/wav2vec2-xls-r-300m:',
    'Hugging Face local snapshot revision mismatch for funasr/campplus:',
    'Hugging Face local snapshot revision mismatch for FunAudioLLM/CosyVoice-300M:',
    'ModelScope FSMN-VAD model.pt (local-observed hash; upstream revision/license UNKNOWN) size mismatch:',
    'ModelScope FSMN-VAD config.yaml (local-observed hash; upstream revision/license UNKNOWN) size mismatch:',
    'ModelScope FSMN-VAD configuration.json (local-observed hash; upstream revision/license UNKNOWN) size mismatch:',
    'ModelScope FSMN-VAD am.mvn (local-observed hash; upstream revision/license UNKNOWN) size mismatch:'
)
if (@($normalRun.Report.missing).Count -ne $expectedFindingPrefixes.Count) {
    throw "Synthetic normal setup should report exactly $($expectedFindingPrefixes.Count) findings and no unrelated failures; found $(@($normalRun.Report.missing).Count): $(@($normalRun.Report.missing) -join ' | ')"
}
foreach ($expected in $expectedFindingPrefixes) {
    $matchingFindings = @($normalRun.Report.missing | Where-Object { $_.StartsWith($expected, [StringComparison]::Ordinal) })
    if ($matchingFindings.Count -ne 1) { throw "Expected a single precise BLOCKED finding: $expected" }
}
if (@($normalRun.Report.missing | Where-Object { $_ -match '(?i)offline-v1|whisper|bigvgan' }).Count -gt 0) {
    throw "Realtime setup gate must not require offline-v1/Whisper/BigVGAN helper assets: $(@($normalRun.Report.missing) -join ' | ')"
}
if (Test-Path -LiteralPath $fixtureEnvironment) {
    throw "Normal setup created the Seed-VC environment before resolving empty assets: $fixtureEnvironment"
}
if ($normalRun.OutputText -match '(?i)pip install|更新 packaging tools|建立獨立 Seed-VC Python environment') {
    throw 'Normal setup reached an environment creation or pip installation message before blocking.'
}

# 第二個呼叫隔離驗證 missing-Python 訊息；此分支可用 -PreflightOnly，且不影響第一個 mutation gate 證據。
$missingPythonRun = Invoke-SetupFixture -PythonPath $missingPython -EnvironmentPath $missingPythonEnvironment -PreflightOnly
if ($missingPythonRun.ExitCode -eq 0 -or $missingPythonRun.Report.status -cne 'BLOCKED') {
    throw "Missing-Python preflight should exit nonzero with BLOCKED; exit=$($missingPythonRun.ExitCode) status=$($missingPythonRun.Report.status)"
}
if (@($missingPythonRun.Report.missing | Where-Object { $_ -like 'Python 3.10 x64 executable*' }).Count -ne 1) {
    throw 'Synthetic missing Python prerequisite was not reported.'
}
if (Test-Path -LiteralPath $missingPythonEnvironment) {
    throw "Missing-Python preflight created the Seed-VC environment: $missingPythonEnvironment"
}

Write-Output "PASS Seed-VC setup preflight regression: Windows PowerShell 5.1 setup parser/manifest loader PASS; realtime-tiny setup blocks on its synthetic Hifi-GAN/realtime checkpoint issues while missing offline-v1/Whisper/BigVGAN assets add no findings before venv/pip; separate missing-Python case is BLOCKED; synthetic fixture only; normal_exit=$($normalRun.ExitCode), missing_python_exit=$($missingPythonRun.ExitCode); fixture=$fixtureRoot"
