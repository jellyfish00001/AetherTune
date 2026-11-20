#Requires -Version 5.1
<#
.SYNOPSIS
  E2E 延遲一行編排：loopback baseline、可選 streaming engine、彙總 artifacts。
#>
[CmdletBinding()]
param(
    [string]$Root = '',
    [string]$Python = '',
    [ValidateSet('none', 'meanvc2', 'xvc', 'seed-vc', 'all')]
    [string]$Engine = 'none',
    [string]$In = 'Voicemeeter Out B1',
    [string]$Out = 'CABLE Input',
    [string]$EngineIn = 'CABLE Output',
    [string]$EngineOut = 'Voicemeeter Input',
    [string]$BaselineIn = '',
    [string]$BaselineOut = '',
    [string]$HostApi = 'Windows WASAPI',
    [string]$Request = '',
    [ValidateSet('click', 'chirp')]
    [string]$Signal = 'chirp',
    [int]$Pulses = 8,
    [double]$IntervalMs = 1000,
    [double]$MaxDelayMs = 900,
    [int]$LoadTimeoutSec = 300,
    [string]$ResultsDir = '',
    [switch]$SelfTest
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
    param([string]$RootPath, [string]$Explicit)
    if ($Explicit) {
        if (-not (Test-Path -LiteralPath $Explicit)) {
            Write-Error "Python not found: $Explicit"
            exit 2
        }
        return (Resolve-Path -LiteralPath $Explicit).Path
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
    $src = Join-Path $ArtifactDir 'stream-evidence.json'
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $DestDir 'stream-evidence.json') -Force
    }
}

function Get-EngineList {
    param([string]$Choice)
    switch ($Choice) {
        'all' { return @('meanvc2', 'xvc', 'seed-vc') }
        { $_ -in @('meanvc2', 'xvc', 'seed-vc') } { return @($Choice) }
        default { return @() }
    }
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
$pyExe = Resolve-PythonExe -RootPath $repoRoot -Explicit $Python
$bench = Join-Path $repoRoot 'tools\e2e-latency-bench.py'
if (-not (Test-Path -LiteralPath $bench)) {
    Write-Error "找不到 $bench"
    exit 2
}

if (-not $ResultsDir) {
    $ResultsDir = Join-Path $repoRoot 'artifacts\e2e-latency'
}
$ResultsDir = (New-Item -ItemType Directory -Force -Path $ResultsDir).FullName

if (-not $BaselineIn) { $BaselineIn = $In }
if (-not $BaselineOut) { $BaselineOut = $Out }

$sessionStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$gitHead = Get-GitHead -RootPath $repoRoot
$rows = New-Object System.Collections.Generic.List[object]
$anyBlocked = $false
$baselineReportPath = $null

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
    if ($Engine -ne 'none' -and (-not $Request -or -not (Test-Path -LiteralPath $Request))) {
        Write-Error '非 -SelfTest 的 engine 量測需要 -Request 指向含 reference 的 JSON。'
        exit 2
    }

    if ($Engine -eq 'none' -or $Engine -eq 'all') {
        $runDir = Join-Path $ResultsDir "$sessionStamp-baseline"
        New-Item -ItemType Directory -Force -Path $runDir | Out-Null
        $code = Invoke-E2EBench -Py $pyExe -BenchScript $bench -ExtraArgs (Common-BenchArgs -Mode 'loopback' -RunDir $runDir -InputDev $BaselineIn -OutputDev $BaselineOut -BaselineReport '')
        $reportPath = Join-Path $runDir 'e2e-latency-report.json'
        $report = Read-BenchReport -Path $reportPath
        if ($code -eq 3) { $anyBlocked = $true }
        if (Test-Path -LiteralPath $reportPath) { $baselineReportPath = $reportPath }
        $row = New-SummaryRow -EngineId 'baseline' -Mode 'loopback_baseline' -RunDir $runDir -Report $report -ExitCode $code -Devices @{ input = $BaselineIn; output = $BaselineOut; host_api = $HostApi }
        [void]$rows.Add($row)
        if ($row.status -eq 'BLOCKED') { $anyBlocked = $true }
    }

    foreach ($engineId in (Get-EngineList -Choice $Engine)) {
        $runDir = Join-Path $ResultsDir "$sessionStamp-$engineId"
        New-Item -ItemType Directory -Force -Path $runDir | Out-Null
        $reqPath = Join-Path $runDir 'engine-request.json'
        Merge-EngineRequest -RootPath $repoRoot -RequestPath $Request -EngineInName $EngineIn -EngineOutName $EngineOut -HostApiName $HostApi -DestPath $reqPath
        $stdoutLog = Join-Path $runDir 'engine-stdout.jsonl'
        $runner = Start-RunnerAndWaitRunning -Py $pyExe -RootPath $repoRoot -EngineId $engineId -RequestPath $reqPath -StdoutLog $stdoutLog -TimeoutSec $LoadTimeoutSec
        if (-not $runner.ok) {
            $blocked = New-SummaryRow -EngineId $engineId -Mode 'through_engine' -RunDir $runDir -Report $null -ExitCode 1 -Devices @{ input = $In; output = $Out; engine_in = $EngineIn; engine_out = $EngineOut; note = $runner.reason }
            [void]$rows.Add($blocked)
            $anyBlocked = $true
            continue
        }
        $code = Invoke-E2EBench -Py $pyExe -BenchScript $bench -ExtraArgs (Common-BenchArgs -Mode 'engine' -RunDir $runDir -InputDev $In -OutputDev $Out -BaselineReport $baselineReportPath)
        Stop-RunnerProcess -Process $runner.process -Stdin $runner.stdin -LogWriter $runner.log -Stdout $runner.stdout
        Copy-StreamEvidence -ArtifactDir $runner.artifact -DestDir $runDir
        $report = Read-BenchReport -Path (Join-Path $runDir 'e2e-latency-report.json')
        if ($code -eq 3) { $anyBlocked = $true }
        $row = New-SummaryRow -EngineId $engineId -Mode 'through_engine' -RunDir $runDir -Report $report -ExitCode $code -Devices @{ input = $In; output = $Out; engine_in = $EngineIn; engine_out = $EngineOut; host_api = $HostApi }
        [void]$rows.Add($row)
        if ($row.status -eq 'BLOCKED') { $anyBlocked = $true }
    }
}

$meta = @{
    git_commit = $gitHead
    python     = $pyExe
    root       = $repoRoot
    self_test  = [bool]$SelfTest
}
Write-SummaryArtifacts -OutDir $ResultsDir -Stamp $sessionStamp -Rows $rows -Meta $meta | Out-Null
Write-ConsoleTable -Rows $rows

if ($anyBlocked) { exit 1 }
exit 0