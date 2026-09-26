#Requires -Version 7.0
$ErrorActionPreference = 'Stop'

$setupScript = Join-Path $PSScriptRoot 'seed-vc-setup.ps1'
$pwsh = Get-Command 'pwsh.exe' -ErrorAction Stop
$fixtureRoot = Join-Path $env:TEMP ("aethertune-seed-vc-setup-preflight-" + [Guid]::NewGuid().ToString('N'))
$fixtureTools = Join-Path $fixtureRoot 'tools'
$fixtureScript = Join-Path $fixtureTools 'seed-vc-setup.ps1'
$repoPath = Join-Path $fixtureRoot 'external\seed-vc'
$fixtureEnvironment = Join-Path $fixtureTools 'venvs\seed-vc-normal-start'
$missingPythonEnvironment = Join-Path $fixtureTools 'venvs\seed-vc-missing-python'
$modelScopePath = Join-Path $fixtureRoot 'fixture-modelscope-vad'
$shimRoot = Join-Path $fixtureRoot 'shims'
$pythonShim = Join-Path $shimRoot 'python310.cmd'
$gitShim = Join-Path $shimRoot 'git.cmd'
$missingPython = Join-Path $fixtureRoot 'not-installed\python.exe'

$null = New-Item -ItemType Directory -Force -Path $fixtureTools, $repoPath, $modelScopePath, $shimRoot
Copy-Item -LiteralPath $setupScript -Destination $fixtureScript

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
    'inference.py',
    'real-time-gui.py',
    'requirements.txt',
    'configs\presets\config_dit_mel_seed_uvit_whisper_small_wavenet.yml',
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
$null = New-Item -ItemType File -Path $offlineCheckpoint
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
# 唯一預期缺項是空 Hifi-GAN config 與兩個無效 checkpoint；它們必須先阻止任何 venv/pip mutation。
$normalRun = Invoke-SetupFixture -PythonPath $pythonShim -EnvironmentPath $fixtureEnvironment
if ($normalRun.ExitCode -eq 0 -or $normalRun.Report.status -cne 'BLOCKED') {
    throw "Synthetic normal setup should exit nonzero with BLOCKED; exit=$($normalRun.ExitCode) status=$($normalRun.Report.status)"
}
if ($normalRun.Report.python_probe.bits -ne 64 -or ($normalRun.Report.python_probe.version -join '.') -ne '3.10.11' -or
    $normalRun.Report.python_probe.tcl -cne '8.6.12' -or $normalRun.Report.python_probe.tk -cne 'available') {
    throw 'Local Python shim did not satisfy the expected Python 3.10 x64/Tcl/Tk probe.'
}

$requiredMissing = @(
    'Seed-VC required file/cache is missing, not a regular file, or empty: configs\hifigan.yml',
    'Project-local Seed-VC checkpoint is missing, not a regular file, or empty: models\seed-vc\checkpoints\offline-v1\DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth',
    'Project-local Seed-VC checkpoint is missing, not a regular file, or empty: models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth'
)
if (@($normalRun.Report.missing).Count -ne $requiredMissing.Count) {
    throw "Normal setup reported unexpected preflight findings: $($normalRun.Report.missing -join ' | ')"
}
foreach ($expected in $requiredMissing) {
    $matchingFindings = @($normalRun.Report.missing | Where-Object { $_.StartsWith($expected, [StringComparison]::Ordinal) })
    if ($matchingFindings.Count -ne 1) { throw "Expected a single precise BLOCKED finding: $expected" }
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

Write-Output "PASS Seed-VC setup preflight regression: normal setup with valid Python/Tcl/Tk shim is blocked only by empty source/checkpoint files before venv/pip; separate missing-Python case is BLOCKED; synthetic fixture only; normal_exit=$($normalRun.ExitCode), missing_python_exit=$($missingPythonRun.ExitCode); fixture=$fixtureRoot"
