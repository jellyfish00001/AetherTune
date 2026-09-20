[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:18000',
    [string]$InputWav = '.\tools\external\VCClient\2.1.4-alpha\dist\main\web_front\assets\voices\JVNV\partial\M1_happy_regular_26.wav',
    [string]$FfmpegPath = 'ffmpeg',
    [int]$SlotIndex = 7,
    [string]$OutputRoot = '.\artifacts\vcclient-rvc-test',
    [switch]$ConfigureSlot,
    [double]$ChunkSec = 0.5
)

$ErrorActionPreference = 'Stop'
$runId = [guid]::NewGuid().ToString()
$status = 'BLOCKED'
$errorMessage = $null
$restoreError = $null
$convertedBytes = 0
$successfulChunks = 0
$totalChunks = 0
$slot = $null
$initialConfiguration = $null
$client = $null

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$runDir = Join-Path (Resolve-Path $OutputRoot).Path $runId
$reportPath = Join-Path $runDir 'vcclient-rvc-probe.json'
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

function Invoke-JsonRequest {
    param(
        [ValidateSet('Get', 'Post', 'Put')]
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null
    )

    $params = @{
        Uri = $Uri
        Method = $Method
        TimeoutSec = 60
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $params.Body = $Body | ConvertTo-Json -Depth 12
        $params.ContentType = 'application/json'
    }
    return Invoke-RestMethod @params
}

try {
    if (-not (Test-Path -LiteralPath $InputWav -PathType Leaf)) {
        throw "找不到輸入 WAV：$InputWav"
    }

    $ffmpegCommand = Get-Command $FfmpegPath -ErrorAction SilentlyContinue
    if ($null -eq $ffmpegCommand -and -not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
        throw "找不到 FFmpeg：$FfmpegPath；請以 -FfmpegPath 傳入絕對路徑"
    }
    $ffmpegExe = if ($ffmpegCommand) { $ffmpegCommand.Source } else { (Resolve-Path $FfmpegPath).Path }

    $health = Invoke-WebRequest -Uri "$BaseUrl/" -Method Get -TimeoutSec 15 -UseBasicParsing
    if ($health.StatusCode -ne 200) {
        throw "VCClient Web UI HTTP $($health.StatusCode)"
    }

    $slots = Invoke-JsonRequest -Method Get -Uri "$BaseUrl/api/slot-manager/slots"
    $slot = @($slots) | Where-Object { $_.slot_index -eq $SlotIndex } | Select-Object -First 1
    if ($null -eq $slot -or $slot.voice_changer_type -ne 'RVC') {
        throw "找不到 RVC slot_index=$SlotIndex"
    }

    if ($ConfigureSlot) {
        # VCClient 2.1.4-alpha 的 configuration PUT 在部分 packaged 狀態會清空 slot；
        # 只有明確指定 -ConfigureSlot 才修改服務狀態，預設直接測試目前已選 slot。
        $initialConfiguration = Invoke-JsonRequest -Method Get -Uri "$BaseUrl/api/configuration-manager/configuration"
        $probeConfiguration = $initialConfiguration | Select-Object *
        $probeConfiguration.current_slot_index = $SlotIndex
        $probeConfiguration.input_sample_rate = 48000
        $probeConfiguration.output_sample_rate = 48000
        [void](Invoke-JsonRequest -Method Put -Uri "$BaseUrl/api/configuration-manager/configuration" -Body $probeConfiguration)
        [void](Invoke-JsonRequest -Method Post -Uri "$BaseUrl/api/operation/initialize")
    }

    $inputRaw = Join-Path $runDir 'input-48k-mono-f32le.raw'
    $outputRaw = Join-Path $runDir 'output-f32le.raw'
    $outputWav = Join-Path $runDir 'output.wav'
    & $ffmpegExe -hide_banner -loglevel error -y -i (Resolve-Path $InputWav).Path -ar 48000 -ac 1 -f f32le $inputRaw
    if ($LASTEXITCODE -ne 0) {
        throw "FFmpeg 輸入轉換失敗，exit=$LASTEXITCODE"
    }

    $inputBytes = [IO.File]::ReadAllBytes((Resolve-Path $inputRaw).Path)
    $chunkSec = if ($slot.PSObject.Properties.Name -contains 'chunk_sec' -and $slot.chunk_sec) { [double]$slot.chunk_sec } else { $ChunkSec }
    $chunkBytes = [Math]::Max(4, [int]([Math]::Round(48000 * $chunkSec)) * 4)
    $totalChunks = [int][Math]::Ceiling($inputBytes.Length / $chunkBytes)
    $converted = [System.Collections.Generic.List[byte]]::new()
    $client = [System.Net.Http.HttpClient]::new()

    for ($offset = 0; $offset -lt $inputBytes.Length; $offset += $chunkBytes) {
        $length = [Math]::Min($chunkBytes, $inputBytes.Length - $offset)
        $part = [byte[]]::new($length)
        [Array]::Copy($inputBytes, $offset, $part, 0, $length)
        $form = [System.Net.Http.MultipartFormDataContent]::new()
        $content = [System.Net.Http.ByteArrayContent]::new($part)
        $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/octet-stream')
        $form.Add($content, 'waveform', 'waveform.bin')
        $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Post, "$BaseUrl/api/voice-changer/convert_chunk_bulk")
        $request.Headers.Add('x-timestamp', [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds().ToString())
        $request.Content = $form
        try {
            $response = $client.SendAsync($request).GetAwaiter().GetResult()
            $responseBytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
            if (-not $response.IsSuccessStatusCode) {
                $detail = [Text.Encoding]::UTF8.GetString($responseBytes)
                throw "convert_chunk_bulk HTTP $([int]$response.StatusCode): $detail"
            }
            if ($responseBytes.Length -gt 0) {
                $converted.AddRange($responseBytes)
                $successfulChunks++
            }
        } finally {
            $request.Dispose()
            $form.Dispose()
        }
    }

    [IO.File]::WriteAllBytes($outputRaw, $converted.ToArray())
    $convertedBytes = $converted.Count
    & $ffmpegExe -hide_banner -loglevel error -y -f f32le -ar 48000 -ac 1 -i $outputRaw $outputWav
    if ($LASTEXITCODE -ne 0) {
        throw "FFmpeg 輸出 WAV 轉換失敗，exit=$LASTEXITCODE"
    }
    if ($convertedBytes -lt 4096) {
        throw "轉換端點只回傳 $convertedBytes bytes，未形成可驗收的語音輸出"
    }
    $status = 'PASS'
} catch {
    $errorMessage = $_.Exception.Message
} finally {
    if ($null -ne $client) {
        $client.Dispose()
    }
    if ($null -ne $initialConfiguration) {
        try {
            [void](Invoke-JsonRequest -Method Put -Uri "$BaseUrl/api/configuration-manager/configuration" -Body $initialConfiguration)
        } catch {
            $restoreError = $_.Exception.Message
        }
    }
}

$report = [ordered]@{
    run_id = $runId
    status = $status
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    base_url = $BaseUrl
    input_wav = $InputWav
    slot_index = $SlotIndex
    slot_name = if ($slot) { $slot.name } else { $null }
    slot_sample_rate = if ($slot) { $slot.sample_rate } else { $null }
    slot_pitch_estimator = if ($slot) { $slot.pitch_estimator } else { $null }
    slot_inferencer_type = if ($slot) { $slot.inferencer_type } else { $null }
    total_chunks = $totalChunks
    successful_chunks = $successfulChunks
    converted_bytes = $convertedBytes
    error = $errorMessage
    restore_error = $restoreError
    artifact_dir = $runDir
}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Output "status=$status"
Write-Output "report=$reportPath"
if ($errorMessage) {
    Write-Output "error=$errorMessage"
}
if ($status -ne 'PASS') {
    exit 2
}
