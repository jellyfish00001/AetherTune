[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:18000',
    [int]$SlotIndex = 7,
    [string]$InputWav = '.\tools\external\VCClient\2.1.4-alpha\dist\main\web_front\assets\voices\JVNV\partial\M1_happy_regular_26.wav',
    [Parameter(Mandatory = $true)][string]$FfmpegPath,
    [double[]]$ChunkSeconds = @(0.25, 0.5, 0.75, 1.0),
    [int]$StabilitySeconds = 600,
    [string]$OutputRoot = '.\artifacts\vcclient-rvc-latency-matrix'
)

$ErrorActionPreference = 'Stop'
$runId = [guid]::NewGuid().ToString()
$root = Join-Path (Resolve-Path (New-Item -ItemType Directory -Path $OutputRoot -Force)).Path $runId
New-Item -ItemType Directory -Path $root -Force | Out-Null
$probe = Join-Path $PSScriptRoot 'vcclient-rvc-probe.ps1'
$rows = [System.Collections.Generic.List[object]]::new()

function Get-ProbeReport {
    param([double]$ChunkSec, [string]$Label, [string]$ProbeInputWav = $InputWav)
    $probeRoot = Join-Path $root $Label
    New-Item -ItemType Directory -Path $probeRoot -Force | Out-Null
    $text = (& $probe -BaseUrl $BaseUrl -SlotIndex $SlotIndex -InputWav $ProbeInputWav -FfmpegPath $FfmpegPath -OutputRoot $probeRoot -ChunkSec $ChunkSec -ConfigureSlot -OverrideSlotChunkSec 2>&1 | Out-String)
    $match = [regex]::Match($text, 'report=(?<path>[^\r\n]+)')
    $report = $null
    if ($match.Success -and (Test-Path -LiteralPath $match.Groups['path'].Value.Trim())) {
        $report = Get-Content -LiteralPath $match.Groups['path'].Value.Trim() -Raw | ConvertFrom-Json
    }
    return [pscustomobject]@{ command_output = $text.Trim(); report = $report }
}

foreach ($chunkSec in $ChunkSeconds) {
    $result = Get-ProbeReport -ChunkSec $chunkSec -Label ("chunk-{0}s" -f ($chunkSec.ToString('0.00').Replace('.', '_')))
    $report = $result.report
    $dropouts = if ($report) { @($report.chunk_metrics | Where-Object { $_.valid_chunk -ne $true -or $_.output_bytes -lt 4 -or $_.output_all_zero }).Count } else { $null }
    $rowStatus = if (-not $report) { 'BLOCKED' } elseif ($report.status -ne 'PASS') { $report.status } elseif ($dropouts -gt 0) { 'DEGRADED' } else { 'PASS' }
    $rows.Add([ordered]@{
            test_type = 'short'
            chunk_sec = $chunkSec
            status = $rowStatus
            total_chunks = if ($report) { $report.total_chunks } else { $null }
            successful_chunks = if ($report) { $report.successful_chunks } else { $null }
            p50_latency_ms = if ($report) { $report.latency_p50_ms } else { $null }
            p95_latency_ms = if ($report) { $report.latency_p95_ms } else { $null }
            dropout_count = $dropouts
            invalid_chunk_count = if ($report) { $report.invalid_chunk_count } else { $null }
            empty_chunk_count = if ($report) { $report.empty_chunk_count } else { $null }
            short_chunk_count = if ($report) { $report.short_chunk_count } else { $null }
            unaligned_chunk_count = if ($report) { $report.unaligned_chunk_count } else { $null }
            nonfinite_chunk_count = if ($report) { $report.nonfinite_chunk_count } else { $null }
            requested_slot_index = if ($report) { $report.requested_slot_index } else { $SlotIndex }
            active_slot_index = if ($report) { $report.active_slot_index } else { $null }
            slot_model_evidence = if ($report) { $report.slot_model_evidence } else { $null }
            output_rms = if ($report) { $report.output_rms } else { $null }
            artifact_dir = if ($report) { $report.artifact_dir } else { $null }
            error = if ($report) { $report.error } else { $result.command_output }
        })
}

$shortPass = @($rows | Where-Object { $_.test_type -eq 'short' -and $_.status -eq 'PASS' }).Count -eq $ChunkSeconds.Count
if ($shortPass -and $StabilitySeconds -gt 0) {
    $longInput = Join-Path $root 'stability-input.wav'
    & $FfmpegPath -hide_banner -loglevel error -y -stream_loop -1 -i (Resolve-Path $InputWav).Path -t $StabilitySeconds -ar 48000 -ac 1 $longInput
    if ($LASTEXITCODE -ne 0) { throw "建立 stability input 失敗，exit=$LASTEXITCODE" }
    $result = Get-ProbeReport -ChunkSec 0.5 -Label 'stability-600s' -ProbeInputWav $longInput
    $report = $result.report
    $dropouts = if ($report) { @($report.chunk_metrics | Where-Object { $_.valid_chunk -ne $true -or $_.output_bytes -lt 4 -or $_.output_all_zero }).Count } else { $null }
    $rowStatus = if (-not $report) { 'BLOCKED' } elseif ($report.status -ne 'PASS') { $report.status } elseif ($dropouts -gt 0) { 'DEGRADED' } else { 'PASS' }
    $rows.Add([ordered]@{
            test_type = 'stability'
            duration_sec = $StabilitySeconds
            chunk_sec = 0.5
            status = $rowStatus
            total_chunks = if ($report) { $report.total_chunks } else { $null }
            successful_chunks = if ($report) { $report.successful_chunks } else { $null }
            p50_latency_ms = if ($report) { $report.latency_p50_ms } else { $null }
            p95_latency_ms = if ($report) { $report.latency_p95_ms } else { $null }
            dropout_count = $dropouts
            invalid_chunk_count = if ($report) { $report.invalid_chunk_count } else { $null }
            empty_chunk_count = if ($report) { $report.empty_chunk_count } else { $null }
            short_chunk_count = if ($report) { $report.short_chunk_count } else { $null }
            unaligned_chunk_count = if ($report) { $report.unaligned_chunk_count } else { $null }
            nonfinite_chunk_count = if ($report) { $report.nonfinite_chunk_count } else { $null }
            requested_slot_index = if ($report) { $report.requested_slot_index } else { $SlotIndex }
            active_slot_index = if ($report) { $report.active_slot_index } else { $null }
            slot_model_evidence = if ($report) { $report.slot_model_evidence } else { $null }
            output_rms = if ($report) { $report.output_rms } else { $null }
            artifact_dir = if ($report) { $report.artifact_dir } else { $null }
            error = if ($report) { $report.error } else { $result.command_output }
        })
} else {
    $rows.Add([ordered]@{
            test_type = 'stability'
            duration_sec = $StabilitySeconds
            chunk_sec = 0.5
            status = 'BLOCKED'
            total_chunks = $null
            successful_chunks = $null
            p50_latency_ms = $null
            p95_latency_ms = $null
            dropout_count = $null
            invalid_chunk_count = $null
            empty_chunk_count = $null
            short_chunk_count = $null
            unaligned_chunk_count = $null
            nonfinite_chunk_count = $null
            requested_slot_index = $SlotIndex
            active_slot_index = $null
            slot_model_evidence = $null
            output_rms = $null
            artifact_dir = $null
            error = '短測未全部 PASS，依 gate 不執行 10 分鐘長測'
        })
}

$reportPath = Join-Path $root 'vcclient-rvc-latency-matrix.json'
[ordered]@{
    run_id = $runId
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    base_url = $BaseUrl
    slot_index = $SlotIndex
    requested_slot_index = $SlotIndex
    input_wav = $InputWav
    chunk_seconds = $ChunkSeconds
    stability_seconds = $StabilitySeconds
    gate = '短測所有 chunk PASS 後才執行 stability'
    rows = @($rows)
} | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Output "report=$reportPath"
if (@($rows | Where-Object { $_.status -ne 'PASS' }).Count -gt 0) { exit 2 }
