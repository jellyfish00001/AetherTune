#Requires -Version 5.1
<#
.SYNOPSIS
  E2E 延遲一行編排：雙虛擬線 baseline 相加、routing precheck、自動 request、streaming engine、彙總 artifacts。

.NOTES
  `-Profile pc2-virtual`（預設）或 `cable-voicemeeter`；`-RequestOnly`／`-SelfTest` 不接實機音訊。
  pc2-virtual 不使用 `verify_wiring.ps1`（CABLE／Voicemeeter 專用）。
#>
[CmdletBinding()]
param(
    [string]$Root = '',
    [string]$Python = '',
    [ValidateSet('pc2-virtual', 'cable-voicemeeter', 'custom')]
    [string]$Profile = 'pc2-virtual',
    [ValidateSet('none', 'meanvc2', 'xvc', 'seed-vc', 'rvc', 'all')]
    [string]$Engine = 'none',
    [string]$In = '',
    [string]$Out = '',
    [string]$EngineIn = '',
    [string]$EngineOut = '',
    [string]$LineAOut = '',
    [string]$LineAIn = '',
    [string]$LineBOut = '',
    [string]$LineBIn = '',
    [string]$HostApi = 'Windows WASAPI',
    [string]$Request = '',
    [string]$Reference = '',
    [ValidateSet('click', 'chirp')]
    [string]$Signal = 'chirp',
    [int]$Pulses = 8,
    [double]$IntervalMs = 1000,
    [double]$MaxDelayMs = 900,
    [int]$LoadTimeoutSec = 300,
    [string]$ResultsDir = '',
    [switch]$SelfTest,
    [switch]$RequestOnly,
    [switch]$SkipPrecheck
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    param([string]$Candidate)
    if ($Candidate -and (Test-Path -LiteralPath $Candidate)) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }
    $scriptDir = $PSScriptRoot
    if (-not $scriptDir) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $scriptDir '..')).Path
}

function Resolve-PythonExe {
    param(
        [string]$RootPath,
        [string]$Explicit,
        [switch]$AllowMissing
    )
    if ($Explicit) {
        if (-not (Test-Path -LiteralPath $Explicit)) {
            if ($AllowMissing) { return $null }
            Write-Error "Python not found: $Explicit"
            exit 2
        }
        return (Resolve-Path -LiteralPath $Explicit).Path
    }
  if ($AllowMissing) {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        return $null
    }
    $venvPy = Join-Path $RootPath '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPy) {
        return (Resolve-Path -LiteralPath $venvPy).Path
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    Write-Error '找不到 python；請以 -Python 指定含 sounddevice／numpy 的直譯器（本腳本不自動安裝）。'
    exit 2
}

function Get-ProfileDefaults {
    param([string]$Name)
    switch ($Name) {
        'pc2-virtual' {
            return @{
                Out       = 'Steam Streaming Microphone'
                In        = 'Voice Changer Virtual Aud'
                EngineIn  = 'Steam Streaming Microphone'
                EngineOut = 'Voice Changer Virtual Aud'
                LineAOut  = 'Steam Streaming Microphone'
                LineAIn   = 'Steam Streaming Microphone'
                LineBOut  = 'Voice Changer Virtual Aud'
                LineBIn   = 'Voice Changer Virtual Aud'
                HostApi   = 'Windows WASAPI'
            }
        }
        'cable-voicemeeter' {
            return @{
                Out       = 'CABLE Input'
                In        = 'Voicemeeter Out B1'
                EngineIn  = 'CABLE Output'
                EngineOut = 'Voicemeeter Input'
                LineAOut  = 'CABLE Input'
                LineAIn   = 'CABLE Output'
                LineBOut  = 'Voicemeeter Input'
                LineBIn   = 'Voicemeeter Out B1'
                HostApi   = 'Windows WASAPI'
            }
        }
        default { return @{} }
    }
}

function Test-PythonImportsSounddevice {
    param([string]$Py)
    if (-not $Py) { return $false }
    $code = "import importlib.util; print('ok' if importlib.util.find_spec('sounddevice') and importlib.util.find_spec('soundfile') else 'no')"
    try {
        $out = & $Py -c $code 2>$null
        return ($LASTEXITCODE -eq 0 -and ($out | Select-Object -Last 1) -eq 'ok')
    } catch { return $false }
}

function New-AutoEngineRequest {
    param(
        [string]$RootPath,
        [string]$EngineId,
        [string]$EngineInName,
        [string]$EngineOutName,
        [string]$HostApiName,
        [string]$ReferencePath
    )
    $manifestPath = Join-Path $RootPath "contracts\engines\$EngineId.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "找不到 manifest: $manifestPath"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $parameters = @{}
    foreach ($p in $manifest.parameters) {
        $parameters[$p.name] = $p.default
    }
    return [ordered]@{
        reference       = $ReferencePath
        input           = $EngineInName
        output          = $EngineOutName
        host_api        = $HostApiName
        parameters      = $parameters
        postfx          = @{
            enabled                 = $false
            wet                     = 0.3
            low_db                  = 0.0
            mid_db                  = 0.0
            high_db                 = 0.0
            compressor_threshold_db = -18.0
            compressor_ratio        = 3.0
            reverb_mix              = 0.12
            output_gain_db          = 0.0
        }
        noise_reduction = @{ enabled = $false; strength_db = 12.0 }
        monitor         = @{ enabled = $false }
    }
}

function Merge-BaselineSummaries {
    param([object[]]$Parts)
    $keys = @('min_ms', 'p50_ms', 'p95_ms', 'max_ms', 'mean_ms', 'e2e_first_packet_ms')
    $merged = @{}
    foreach ($key in $keys) {
        $sum = 0.0
        $ok = $true
        foreach ($part in $Parts) {
            if (-not $part) { $ok = $false; break }
            $s = if ($part.summary) { $part.summary } else { $part }
            $v = $s.$key
            if ($null -eq $v) { $ok = $false; break }
            $sum += [double]$v
        }
        if ($ok) { $merged[$key] = $sum }
    }
    $detected = 0
    $count = 0
    foreach ($part in $Parts) {
        $s = if ($part.summary) { $part.summary } else { $part }
        if ($s.detected) { $detected += [int]$s.detected }
        if ($s.count) { $count += [int]$s.count }
    }
    if ($count -gt 0) {
        $merged['detected'] = $detected
        $merged['count'] = $count
    }
    return $merged
}

function Write-CombinedBaselineReport {
    param(
        [string]$Path,
        [object]$LineAReport,
        [object]$LineBReport,
        [hashtable]$MergedSummary,
        [hashtable]$Meta
    )
    $payload = [ordered]@{
        schema           = 'aethertune-e2e-latency/v1'
        mode             = 'loopback_baseline'
        baseline_kind    = 'dual_line_sum'
        summary          = $MergedSummary
        line_a           = $LineAReport
        line_b           = $LineBReport
        baseline_meta    = $Meta
    }
    ($payload | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $Path -Encoding UTF8
    return $Path
}

function Invoke-RoutingPrecheck {
    param(
        [string]$ProbeScript,
        [string]$PrecheckDir,
        [string]$LineAOutFrag,
        [string]$LineAInFrag,
        [string]$LineBOutFrag,
        [string]$LineBInFrag,
        [string]$Py,
        [string]$LoopbackPy
    )
    $issues = New-Object System.Collections.Generic.List[string]
    $lineAJson = Join-Path $PrecheckDir 'precheck-lineA.json'
    $codeA = & pwsh -NoProfile -File $ProbeScript -Out $LineAOutFrag -In $LineAInFrag -Label 'lineA' -Crosstalk `
        -CrosstalkOut $LineAOutFrag -CrosstalkIn $LineBInFrag -OutJson $lineAJson
    if ($LASTEXITCODE -ne 0) { $issues.Add("lineA winmm probe FAIL (exit $codeA)") }

    $lineBJson = Join-Path $PrecheckDir 'precheck-lineB.json'
    $codeB = & pwsh -NoProfile -File $ProbeScript -Out $LineBOutFrag -In $LineBInFrag -Label 'lineB' -Crosstalk `
        -CrosstalkOut $LineBOutFrag -CrosstalkIn $LineAInFrag -OutJson $lineBJson
    if ($LASTEXITCODE -ne 0) { $issues.Add("lineB winmm probe FAIL (exit $codeB)") }

    if ($Py -and $LoopbackPy -and (Test-PythonImportsSounddevice -Py $Py)) {
        foreach ($pair in @(
            @{ label = 'lineA-sd'; out = $LineAOutFrag; inp = $LineAInFrag },
            @{ label = 'lineB-sd'; out = $LineBOutFrag; inp = $LineBInFrag }
        )) {
            # 證據寫入 precheck 目錄，不落在呼叫端 cwd 的 artifacts/。
            $sdWav = Join-Path $PrecheckDir "$($pair.label)-loopback.wav"
            $sdCode = & $Py -u -B $LoopbackPy --seconds 1.5 --output-fragment $pair.out --input-fragment $pair.inp --out $sdWav 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                $issues.Add("$($pair.label) sounddevice loopback exit $sdCode")
            }
        }
    }
    return @{ ok = ($issues.Count -eq 0); reasons = $issues; artifacts = @($lineAJson, $lineBJson) }
}

function Get-GitHead {
    param([string]$RootPath)
    try {
        $out = & git -C $RootPath rev-parse HEAD 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return [string]$out.Trim() }
    } catch { }
    return $null
}

function Read-BenchReport {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    return ($raw | ConvertFrom-Json)
}

function Invoke-E2EBench {
    param(
        [string]$Py,
        [string]$BenchScript,
        [string[]]$ExtraArgs
    )
    $argList = @('-u', '-B', $BenchScript) + $ExtraArgs
    & $Py @argList | ForEach-Object { Write-Host $_ }
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    return [int]$code
}

function New-SummaryRow {
    param(
        [string]$EngineId,
        [string]$Mode,
        [string]$RunDir,
        [object]$Report,
        [int]$ExitCode,
        [hashtable]$Devices
    )
    $status = 'BLOCKED'
    $summary = $null
    $compare = $null
    $verdict = $null
    if ($Report) {
        $summary = $Report.summary
        $verdict = $Report.target_verdict
        $compare = $Report.compare
        if ($verdict -eq 'BLOCKED') {
            $status = 'BLOCKED'
        } elseif ($ExitCode -eq 3) {
            $status = 'BLOCKED'
        } elseif ($ExitCode -ne 0) {
            $status = 'BLOCKED'
        } else {
            $status = $verdict
        }
    } elseif ($ExitCode -eq 3) {
        $status = 'BLOCKED'
    }
    return [ordered]@{
        engine                   = $EngineId
        mode                     = $Mode
        status                   = $status
        target_verdict           = $verdict
        min_ms                   = if ($summary) { $summary.min_ms } else { $null }
        p50_ms                   = if ($summary) { $summary.p50_ms } else { $null }
        p95_ms                   = if ($summary) { $summary.p95_ms } else { $null }
        max_ms                   = if ($summary) { $summary.max_ms } else { $null }
        e2e_first_packet_ms      = if ($summary) { $summary.e2e_first_packet_ms } else { $null }
        engine_minus_baseline_ms = if ($compare) { $compare.engine_minus_baseline_ms } else { $null }
        run_dir                  = $RunDir
        devices                  = $Devices
        bench_exit_code          = $ExitCode
        blocked_reason           = if ($Devices.blocked_reason) { $Devices.blocked_reason } else { $null }
        baseline_line_a          = if ($Devices.baseline_line_a) { $Devices.baseline_line_a } else { $null }
        baseline_line_b          = if ($Devices.baseline_line_b) { $Devices.baseline_line_b } else { $null }
        baseline_sum             = if ($Devices.baseline_sum) { $Devices.baseline_sum } else { $null }
    }
}

function Format-MsCell {
    param($Value)
    if ($null -eq $Value) { return 'n/a' }
    return ('{0:N2} ms' -f [double]$Value)
}

function Write-ConsoleTable {
    param([object[]]$Rows)
    Write-Host ''
    Write-Host ('{0,-14} {1,-22} {2,-8} {3,-10} {4,-10} {5,-10} {6,-10}' -f 'engine', 'mode', 'status', 'min', 'p50', 'p95', 'max')
    foreach ($r in $Rows) {
        Write-Host ('{0,-14} {1,-22} {2,-8} {3,-10} {4,-10} {5,-10} {6,-10}' -f `
            $r.engine, $r.mode, $r.status, `
            (Format-MsCell $r.min_ms), (Format-MsCell $r.p50_ms), (Format-MsCell $r.p95_ms), (Format-MsCell $r.max_ms))
    }
    Write-Host ''
}

function Write-SummaryArtifacts {
    param(
        [string]$OutDir,
        [string]$Stamp,
        [object[]]$Rows,
        [hashtable]$Meta
    )
    $jsonPath = Join-Path $OutDir "$Stamp-summary.json"
    $mdPath = Join-Path $OutDir "$Stamp-summary.md"
    $payload = [ordered]@{
        timestamp_local = $Stamp
        git_commit      = $Meta.git_commit
        python          = $Meta.python
        root            = $Meta.root
        self_test       = [bool]$Meta.self_test
        profile         = $Meta.profile
        rows            = $Rows
    }
    ($payload | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("# E2E latency summary ($Stamp)")
    [void]$sb.AppendLine('')
    [void]$sb.AppendLine("| engine | mode | status | min | p50 | p95 | max | e2e_first | Δ baseline | run_dir |")
    [void]$sb.AppendLine("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    foreach ($r in $Rows) {
        $delta = if ($null -ne $r.engine_minus_baseline_ms) { Format-MsCell $r.engine_minus_baseline_ms } else { '—' }
        [void]$sb.AppendLine("| $($r.engine) | $($r.mode) | $($r.status) | $(Format-MsCell $r.min_ms) | $(Format-MsCell $r.p50_ms) | $(Format-MsCell $r.p95_ms) | $(Format-MsCell $r.max_ms) | $(Format-MsCell $r.e2e_first_packet_ms) | $delta | ``$($r.run_dir)`` |")
    }
    [void]$sb.AppendLine('')
    [void]$sb.AppendLine("git: ``$($Meta.git_commit)`` | python: ``$($Meta.python)``")
    $sb.ToString() | Set-Content -LiteralPath $mdPath -Encoding UTF8
    return @{ json = $jsonPath; md = $mdPath }
}

function Merge-EngineRequest {
    param(
        [string]$RootPath,
        [string]$RequestPath,
        [string]$EngineInName,
        [string]$EngineOutName,
        [string]$HostApiName,
        [string]$DestPath
    )
    if (-not $RequestPath -or -not (Test-Path -LiteralPath $RequestPath)) {
        Write-Error "engine 模式需要可讀的 -Request JSON（含 reference 等欄位）。"
        exit 2
    }
    $raw = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8
    $obj = $raw | ConvertFrom-Json
    if ($null -eq $obj) {
        Write-Error 'Request JSON 必須是 object。'
        exit 2
    }
    $obj | Add-Member -NotePropertyName input -NotePropertyValue $EngineInName -Force
    $obj | Add-Member -NotePropertyName output -NotePropertyValue $EngineOutName -Force
    $obj | Add-Member -NotePropertyName host_api -NotePropertyValue $HostApiName -Force
    ($obj | ConvertTo-Json -Depth 30) | Set-Content -LiteralPath $DestPath -Encoding UTF8
}

function Start-RunnerAndWaitRunning {
    param(
        [string]$Py,
        [string]$RootPath,
        [string]$EngineId,
        [string]$RequestPath,
        [string]$StdoutLog,
        [int]$TimeoutSec
    )
    $runner = Join-Path $RootPath 'services\engines\runner_service.py'
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Py
    $psi.Arguments = "-u -B `"$runner`" --root `"$RootPath`" --engine $EngineId --request `"$RequestPath`""
    $psi.WorkingDirectory = $RootPath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $stdout = $proc.StandardOutput
    $stdin = $proc.StandardInput
    $artifactPath = $null
    $running = $false
    $failed = $false
    $failReason = ''
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $logWriter = New-Object System.IO.StreamWriter($StdoutLog, $false, [System.Text.UTF8Encoding]::new($false))
    $stdin.WriteLine('{"command":"start"}')
    $stdin.Flush()
    while (-not $running -and -not $failed -and -not $proc.HasExited) {
        if ((Get-Date) -gt $deadline) {
            $failed = $true
            $failReason = "LOAD_TIMEOUT after ${TimeoutSec}s"
            break
        }
        $line = $stdout.ReadLine()
        if ($null -eq $line) {
            Start-Sleep -Milliseconds 50
            continue
        }
        $logWriter.WriteLine($line)
        $logWriter.Flush()
        if ($line.StartsWith('{')) {
            try {
                $ev = $line | ConvertFrom-Json
                if ($ev.type -eq 'artifact' -and $ev.path) {
                    $artifactPath = [string]$ev.path
                }
                $val = $null
                if ($ev.PSObject.Properties.Match('value').Count -gt 0) { $val = $ev.value }
                if ($val -eq 'RUNNING') { $running = $true; break }
                if ($val -eq 'ERROR') {
                    $failed = $true
                    $failReason = if ($ev.reason) { [string]$ev.reason } else { 'engine ERROR' }
                    break
                }
            } catch { }
        }
    }
    if ($failed) {
        try {
            $stdin.WriteLine('{"command":"stop"}')
            $stdin.Flush()
        } catch { }
        Stop-RunnerProcess -Process $proc -Stdin $stdin -LogWriter $logWriter -Stdout $stdout
        return @{ ok = $false; reason = $failReason; process = $null; artifact = $artifactPath }
    }
    if (-not $running) {
        Stop-RunnerProcess -Process $proc -Stdin $stdin -LogWriter $logWriter -Stdout $stdout
        return @{ ok = $false; reason = 'runner ended before RUNNING'; process = $null; artifact = $artifactPath }
    }
    return @{ ok = $true; reason = ''; process = $proc; stdin = $stdin; artifact = $artifactPath; log = $logWriter; stdout = $stdout }
}

function Stop-RunnerProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [System.IO.StreamWriter]$Stdin,
        [System.IO.StreamWriter]$LogWriter = $null,
        [System.IO.StreamReader]$Stdout = $null
    )
    if ($null -eq $Process) {
        if ($LogWriter) { $LogWriter.Flush(); $LogWriter.Close() }
        return
    }
    try {
        if (-not $Process.HasExited -and $Stdin) {
            $Stdin.WriteLine('{"command":"stop"}')
            $Stdin.Flush()
            if (-not $Process.WaitForExit(15000)) {
                $Process.Kill()
                $Process.WaitForExit(5000)
            }
        }
    } catch {
        try { $Process.Kill() } catch { }
    }
    if ($Stdout -and $LogWriter) {
        while ($null -ne ($tail = $Stdout.ReadLine())) {
            $LogWriter.WriteLine($tail)
        }
        $LogWriter.Flush()
        $LogWriter.Close()
    } elseif ($LogWriter) {
        $LogWriter.Flush()
        $LogWriter.Close()
    }
}

function Copy-StreamEvidence {
    param([string]$ArtifactDir, [string]$DestDir)
    if (-not $ArtifactDir) { return }
    if (Test-Path -LiteralPath $ArtifactDir -PathType Leaf) { $ArtifactDir = Split-Path -Parent $ArtifactDir }
    # stream_runtime 寫 stream-evidence.json；rvc_runtime 寫 rvc-evidence.json；trace 開啟時另有 latency-trace.jsonl。
    foreach ($name in @('stream-evidence.json', 'rvc-evidence.json', 'latency-trace.jsonl')) {
        $src = Join-Path $ArtifactDir $name
        if (Test-Path -LiteralPath $src) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $DestDir $name) -Force
        }
    }
}

function Get-EngineList {
    param([string]$Choice)
    # 'none' 必須回傳空集合；舊版 switch 落空時會變成單一 $null，導致多出一列空白 through_engine。
    # 'all' 維持三個 stream_runtime 引擎；rvc 需登錄角色模型，請以 -Engine rvc 單獨指定。
    if ($Choice -eq 'all') { return [string[]]@('meanvc2', 'xvc', 'seed-vc') }
    if ($Choice -in @('meanvc2', 'xvc', 'seed-vc', 'rvc')) { return [string[]]@($Choice) }
    return [string[]]@()
}

function Resolve-ExactEndpointName {
    # runner_service／rvc_runtime 以「完整名稱 + host API」比對端點；profile 只存片段，於此換成唯一完整名稱。
    param([string]$Py, [string]$Fragment, [string]$HostApiName, [ValidateSet('input', 'output')][string]$Direction)
    if (-not $Py -or -not $Fragment) { return $Fragment }
    $code = @'
import sys, sounddevice as sd
frag, api, direction = sys.argv[1].lower(), sys.argv[2], sys.argv[3]
apis = sd.query_hostapis()
hits = [d["name"] for d in sd.query_devices()
        if apis[d["hostapi"]]["name"] == api and frag in d["name"].lower() and d[f"max_{direction}_channels"] > 0]
exact = [n for n in hits if n.lower() == frag]
hits = exact or hits
print(hits[0] if len(hits) == 1 else "")
'@
    try {
        $out = & $Py -c $code $Fragment $HostApiName $Direction 2>$null
        $name = [string]($out | Select-Object -Last 1)
        if ($LASTEXITCODE -eq 0 -and $name.Trim()) { return $name.Trim() }
    } catch { }
    return $Fragment
}

function Common-BenchArgs {
    param(
        [string]$Mode,
        [string]$RunDir,
        [string]$InputDev,
        [string]$OutputDev,
        [string]$BaselineReport
    )
    $args = @(
        '--mode', $Mode,
        '--out-dir', $RunDir,
        '--signal', $Signal,
        '--pulses', "$Pulses",
        '--interval-ms', "$IntervalMs",
        '--max-delay-ms', "$MaxDelayMs",
        '--host-api', $HostApi,
        '--input-device', $InputDev,
        '--output-device', $OutputDev
    )
    if ($BaselineReport) {
        $args += @('--baseline-report', $BaselineReport)
    }
    return $args
}

$repoRoot = Resolve-RepoRoot -Candidate $Root
$profileDefaults = Get-ProfileDefaults -Name $Profile
foreach ($key in @('Out', 'In', 'EngineIn', 'EngineOut', 'LineAOut', 'LineAIn', 'LineBOut', 'LineBIn', 'HostApi')) {
    if (-not $PSBoundParameters.ContainsKey($key)) {
        $dv = $profileDefaults[$key]
        if ($dv) { Set-Variable -Name $key -Value $dv }
    }
}
if (-not $Reference) {
    $Reference = Join-Path $repoRoot 'dataset\reference-voices\voice-female-f1.wav'
}
if ($Profile -eq 'pc2-virtual' -and -not $env:AETHERTUNE_WASAPI_AUTOCONVERT) {
    # PC2 的 Steam Streaming Microphone capture 為 44.1 kHz shared format；bench／runtime 固定 48 kHz，
    # 以 WASAPI auto_convert 由 Windows 轉換（只影響本程序及其子程序，不改系統設定）。
    $env:AETHERTUNE_WASAPI_AUTOCONVERT = '1'
}

$needAudioPython = (-not $SelfTest) -and (-not $RequestOnly)
$pyExe = if ($needAudioPython) {
    Resolve-PythonExe -RootPath $repoRoot -Explicit $Python
} else {
    Resolve-PythonExe -RootPath $repoRoot -Explicit $Python -AllowMissing
}
if (-not $pyExe -and ($SelfTest -or $RequestOnly)) {
    $pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pyExe) {
        Write-Error 'SelfTest／RequestOnly 仍需可執行的 python。'
        exit 2
    }
}

$bench = Join-Path $repoRoot 'tools\e2e-latency-bench.py'
$probeScript = Join-Path $repoRoot 'tools\virtual-line-probe.ps1'
$loopbackPy = Join-Path $repoRoot 'tools\virtual_cable_loopback.py'
if (-not (Test-Path -LiteralPath $bench)) {
    Write-Error "找不到 $bench"
    exit 2
}

if (-not $ResultsDir) {
    $ResultsDir = Join-Path $repoRoot 'artifacts\e2e-latency'
}
$ResultsDir = (New-Item -ItemType Directory -Force -Path $ResultsDir).FullName

$sessionStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$gitHead = Get-GitHead -RootPath $repoRoot
$rows = New-Object System.Collections.Generic.List[object]
$anyBlocked = $false
$baselineReportPath = $null
$globalBlockedReason = $null

if ($RequestOnly) {
    if ($Engine -eq 'none') {
        Write-Error 'RequestOnly 需要 -Engine（例如 meanvc2）。'
        exit 2
    }
    $engines = @(Get-EngineList -Choice $Engine)
    if ($engines.Count -ne 1) {
        Write-Error 'RequestOnly 一次僅支援單一 engine（勿用 all）。'
        exit 2
    }
    $engineId = $engines[0]
    $runDir = Join-Path $ResultsDir "$sessionStamp-requestonly-$engineId"
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
    $reqPath = Join-Path $runDir 'engine-request.json'
    if (-not (Test-Path -LiteralPath $Reference)) {
        Write-Host "BLOCKED: reference 不存在: $Reference"
        exit 1
    }
    $reqObj = New-AutoEngineRequest -RootPath $repoRoot -EngineId $engineId -EngineInName $EngineIn -EngineOutName $EngineOut -HostApiName $HostApi -ReferencePath $Reference
    ($reqObj | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $reqPath -Encoding UTF8
    Write-Host ($reqObj | ConvertTo-Json -Depth 10)
    Write-Host "Wrote $reqPath"
    exit 0
}

if ($SelfTest) {
    $runDir = Join-Path $ResultsDir "$sessionStamp-selftest"
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
    $code = Invoke-E2EBench -Py $pyExe -BenchScript $bench -ExtraArgs @(
        '--self-test', '--out-dir', $runDir, '--signal', $Signal, '--pulses', "$Pulses",
        '--interval-ms', "$IntervalMs", '--max-delay-ms', "$MaxDelayMs"
    )
    $report = Read-BenchReport -Path (Join-Path $runDir 'e2e-latency-report.json')
    if ($code -eq 3) { $anyBlocked = $true }
    $row = New-SummaryRow -EngineId 'selftest' -Mode 'synthetic' -RunDir $runDir -Report $report -ExitCode $code -Devices @{ input = 'synthetic'; output = 'synthetic' }
    [void]$rows.Add($row)
    if ($row.status -eq 'BLOCKED') { $anyBlocked = $true }
} else {
    $precheckDir = Join-Path $ResultsDir "$sessionStamp-precheck"
    if (-not $SkipPrecheck) {
        New-Item -ItemType Directory -Force -Path $precheckDir | Out-Null
        if (-not (Test-Path -LiteralPath $probeScript)) {
            $globalBlockedReason = '找不到 virtual-line-probe.ps1'
        } else {
            $pc = Invoke-RoutingPrecheck -ProbeScript $probeScript -PrecheckDir $precheckDir `
                -LineAOutFrag $LineAOut -LineAInFrag $LineAIn -LineBOutFrag $LineBOut -LineBInFrag $LineBIn `
                -Py $pyExe -LoopbackPy $loopbackPy
            if (-not $pc.ok) {
                $globalBlockedReason = 'routing precheck: ' + ($pc.reasons -join '; ')
            }
        }
    }

    function Invoke-DualBaseline {
        param([string]$ParentDir)
        $lineADir = Join-Path $ParentDir 'baseline-lineA'
        $lineBDir = Join-Path $ParentDir 'baseline-lineB'
        New-Item -ItemType Directory -Force -Path $lineADir | Out-Null
        New-Item -ItemType Directory -Force -Path $lineBDir | Out-Null
        $codeA = Invoke-E2EBench -Py $pyExe -BenchScript $bench -ExtraArgs (Common-BenchArgs -Mode 'loopback' -RunDir $lineADir -InputDev $LineAIn -OutputDev $LineAOut -BaselineReport '')
        $codeB = Invoke-E2EBench -Py $pyExe -BenchScript $bench -ExtraArgs (Common-BenchArgs -Mode 'loopback' -RunDir $lineBDir -InputDev $LineBIn -OutputDev $LineBOut -BaselineReport '')
        $reportA = Read-BenchReport -Path (Join-Path $lineADir 'e2e-latency-report.json')
        $reportB = Read-BenchReport -Path (Join-Path $lineBDir 'e2e-latency-report.json')
        $merged = Merge-BaselineSummaries -Parts @($reportA, $reportB)
        $combinedPath = Join-Path $ParentDir 'baseline-combined.json'
        Write-CombinedBaselineReport -Path $combinedPath -LineAReport $reportA -LineBReport $reportB -MergedSummary $merged -Meta @{
            profile = $Profile
            line_a  = @{ out = $LineAOut; in = $LineAIn }
            line_b  = @{ out = $LineBOut; in = $LineBIn }
        } | Out-Null
        $blocked = ($codeA -ne 0) -or ($codeB -ne 0) -or ($codeA -eq 3) -or ($codeB -eq 3)
        return @{
            combined_path = $combinedPath
            report_a      = $reportA
            report_b      = $reportB
            merged        = $merged
            exit_a        = $codeA
            exit_b        = $codeB
            blocked       = $blocked
            parent        = $ParentDir
        }
    }

    $runBaseline = ($Engine -eq 'none' -or $Engine -eq 'all')
    if ($runBaseline) {
        $baseDir = Join-Path $ResultsDir "$sessionStamp-baseline"
        New-Item -ItemType Directory -Force -Path $baseDir | Out-Null
        if ($globalBlockedReason) {
            $row = New-SummaryRow -EngineId 'baseline' -Mode 'loopback_baseline' -RunDir $baseDir -Report $null -ExitCode 3 -Devices @{
                blocked_reason = $globalBlockedReason
                profile        = $Profile
            }
            [void]$rows.Add($row)
            $anyBlocked = $true
        } else {
            $dual = Invoke-DualBaseline -ParentDir $baseDir
            if ($dual.blocked) { $anyBlocked = $true }
            $baselineReportPath = $dual.combined_path
            $fakeReport = @{ summary = $dual.merged; target_verdict = if ($dual.blocked) { 'BLOCKED' } else { 'WAITING' } }
            $row = New-SummaryRow -EngineId 'baseline' -Mode 'loopback_baseline' -RunDir $baseDir -Report $fakeReport -ExitCode $(if ($dual.blocked) { 3 } else { 0 }) -Devices @{
                host_api       = $HostApi
                profile        = $Profile
                baseline_line_a = @{ dir = (Join-Path $baseDir 'baseline-lineA'); out = $LineAOut; in = $LineAIn; summary = $dual.report_a.summary }
                baseline_line_b = @{ dir = (Join-Path $baseDir 'baseline-lineB'); out = $LineBOut; in = $LineBIn; summary = $dual.report_b.summary }
                baseline_sum    = $dual.merged
            }
            [void]$rows.Add($row)
            if ($row.status -eq 'BLOCKED') { $anyBlocked = $true }
        }
    }

    $engineInExact = Resolve-ExactEndpointName -Py $pyExe -Fragment $EngineIn -HostApiName $HostApi -Direction input
    $engineOutExact = Resolve-ExactEndpointName -Py $pyExe -Fragment $EngineOut -HostApiName $HostApi -Direction output
    foreach ($engineId in @(Get-EngineList -Choice $Engine)) {
        $runDir = Join-Path $ResultsDir "$sessionStamp-$engineId"
        New-Item -ItemType Directory -Force -Path $runDir | Out-Null
        $reqPath = Join-Path $runDir 'engine-request.json'
        if ($globalBlockedReason) {
            $blocked = New-SummaryRow -EngineId $engineId -Mode 'through_engine' -RunDir $runDir -Report $null -ExitCode 3 -Devices @{
                blocked_reason = $globalBlockedReason
                profile        = $Profile
            }
            [void]$rows.Add($blocked)
            $anyBlocked = $true
            continue
        }
        $requestPath = $Request
        if (-not $requestPath -or -not (Test-Path -LiteralPath $requestPath)) {
            if (-not (Test-Path -LiteralPath $Reference)) {
                $blocked = New-SummaryRow -EngineId $engineId -Mode 'through_engine' -RunDir $runDir -Report $null -ExitCode 3 -Devices @{
                    blocked_reason = "reference 不存在: $Reference（PC2 上 dataset/ 可能缺席）"
                    profile        = $Profile
                }
                [void]$rows.Add($blocked)
                $anyBlocked = $true
                continue
            }
            $reqObj = New-AutoEngineRequest -RootPath $repoRoot -EngineId $engineId -EngineInName $engineInExact -EngineOutName $engineOutExact -HostApiName $HostApi -ReferencePath $Reference
            ($reqObj | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $reqPath -Encoding UTF8
            $requestPath = $reqPath
        } else {
            Merge-EngineRequest -RootPath $repoRoot -RequestPath $requestPath -EngineInName $engineInExact -EngineOutName $engineOutExact -HostApiName $HostApi -DestPath $reqPath
            $requestPath = $reqPath
        }

        if (-not $baselineReportPath -and $Engine -ne 'none') {
            $engBaseDir = Join-Path $runDir 'baseline'
            $dual = Invoke-DualBaseline -ParentDir $engBaseDir
            if ($dual.blocked) {
                $blocked = New-SummaryRow -EngineId $engineId -Mode 'through_engine' -RunDir $runDir -Report $null -ExitCode 3 -Devices @{
                    blocked_reason = 'baseline loopback failed'
                    baseline_sum   = $dual.merged
                }
                [void]$rows.Add($blocked)
                $anyBlocked = $true
                continue
            }
            $baselineReportPath = $dual.combined_path
        }

        $stdoutLog = Join-Path $runDir 'engine-stdout.jsonl'
        $runner = Start-RunnerAndWaitRunning -Py $pyExe -RootPath $repoRoot -EngineId $engineId -RequestPath $requestPath -StdoutLog $stdoutLog -TimeoutSec $LoadTimeoutSec
        if (-not $runner.ok) {
            $blocked = New-SummaryRow -EngineId $engineId -Mode 'through_engine' -RunDir $runDir -Report $null -ExitCode 1 -Devices @{
                input = $In; output = $Out; engine_in = $EngineIn; engine_out = $EngineOut
                note = $runner.reason; profile = $Profile
            }
            [void]$rows.Add($blocked)
            $anyBlocked = $true
            continue
        }
        $code = Invoke-E2EBench -Py $pyExe -BenchScript $bench -ExtraArgs (Common-BenchArgs -Mode 'engine' -RunDir $runDir -InputDev $In -OutputDev $Out -BaselineReport $baselineReportPath)
        Stop-RunnerProcess -Process $runner.process -Stdin $runner.stdin -LogWriter $runner.log -Stdout $runner.stdout
        Copy-StreamEvidence -ArtifactDir $runner.artifact -DestDir $runDir
        $report = Read-BenchReport -Path (Join-Path $runDir 'e2e-latency-report.json')
        if ($code -eq 3) { $anyBlocked = $true }
        $row = New-SummaryRow -EngineId $engineId -Mode 'through_engine' -RunDir $runDir -Report $report -ExitCode $code -Devices @{
            input = $In; output = $Out; engine_in = $EngineIn; engine_out = $EngineOut; host_api = $HostApi; profile = $Profile
        }
        [void]$rows.Add($row)
        if ($row.status -eq 'BLOCKED') { $anyBlocked = $true }
    }
}

$meta = @{
    git_commit = $gitHead
    python     = $pyExe
    root       = $repoRoot
    self_test  = [bool]$SelfTest
    profile    = $Profile
}
Write-SummaryArtifacts -OutDir $ResultsDir -Stamp $sessionStamp -Rows $rows -Meta $meta | Out-Null
Write-ConsoleTable -Rows $rows

if ($anyBlocked) { exit 1 }
exit 0