[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:18000',
    [Parameter(Mandatory = $true)][string]$ModelPath,
    [string]$IndexPath = '',
    [Parameter(Mandatory = $true)][int]$SlotIndex,
    [Parameter(Mandatory = $true)][string]$Name,
    [ValidateSet('hubert_base_l9fp', 'hubert_base_l12', 'contentvec', 'hubert_base_japanese_l9fp', 'hubert_base_japanese_l12', 'whisper', 'applio_japanese_hubert_base_l12', 'applio_chinese_hubert_base_l12', 'applio_korean_hubert_base_l12')]
    [string]$Embedder = 'hubert_base_l12',
    [string]$TermsOfUseUrl = '',
    [int]$ChunkMiB = 16,
    [string]$ReportRoot = '.\artifacts\vcclient-rvc-register'
)

$ErrorActionPreference = 'Stop'
$runId = [guid]::NewGuid().ToString()
$runDir = Join-Path (Resolve-Path (New-Item -ItemType Directory -Path $ReportRoot -Force)).Path $runId
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
$reportPath = Join-Path $runDir 'vcclient-rvc-register.json'
$client = [System.Net.Http.HttpClient]::new()

function Send-MultipartChunk {
    param([string]$Path, [string]$Filename, [int]$Index)
    $stream = [IO.File]::OpenRead($Path)
    try {
        $buffer = [byte[]]::new([Math]::Min($ChunkMiB * 1MB, [int]$stream.Length))
        $read = $stream.Read($buffer, 0, $buffer.Length)
        if ($read -ne $buffer.Length) { throw "讀取 chunk 長度不符：$Filename/$Index" }
        $content = [Net.Http.ByteArrayContent]::new($buffer)
        $content.Headers.ContentType = [Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/octet-stream')
        $form = [Net.Http.MultipartFormDataContent]::new()
        $form.Add($content, 'file', $Filename)
        $form.Add([Net.Http.StringContent]::new($Filename), 'filename')
        $form.Add([Net.Http.StringContent]::new($Index.ToString()), 'index')
        try {
            $response = $client.PostAsync("$BaseUrl/api/uploader/upload_file_chunk", $form).GetAwaiter().GetResult()
            $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            if (-not $response.IsSuccessStatusCode) { throw "upload HTTP $([int]$response.StatusCode): $body" }
            return $body | ConvertFrom-Json
        } finally {
            $form.Dispose(); $content.Dispose()
        }
    } finally { $stream.Dispose() }
}

function Upload-File {
    param([string]$Path)
    $filename = [IO.Path]::GetFileName($Path)
    $length = (Get-Item -LiteralPath $Path).Length
    $chunkBytes = [int64]$ChunkMiB * 1MB
    $chunkCount = [int][Math]::Ceiling($length / [double]$chunkBytes)
    for ($index = 0; $index -lt $chunkCount; $index++) {
        $offset = [int64]$index * $chunkBytes
        $remaining = $length - $offset
        $currentLength = [int][Math]::Min($chunkBytes, $remaining)
        $stream = [IO.File]::OpenRead($Path)
        try {
            [void]$stream.Seek($offset, [IO.SeekOrigin]::Begin)
            $buffer = [byte[]]::new($currentLength)
            $read = $stream.Read($buffer, 0, $currentLength)
            if ($read -ne $currentLength) { throw "讀取 chunk 長度不符：$filename/$index" }
            $content = [Net.Http.ByteArrayContent]::new($buffer)
            $content.Headers.ContentType = [Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/octet-stream')
            $form = [Net.Http.MultipartFormDataContent]::new()
            $form.Add($content, 'file', $filename)
            $form.Add([Net.Http.StringContent]::new($filename), 'filename')
            $form.Add([Net.Http.StringContent]::new($index.ToString()), 'index')
            try {
                $response = $client.PostAsync("$BaseUrl/api/uploader/upload_file_chunk", $form).GetAwaiter().GetResult()
                $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                if (-not $response.IsSuccessStatusCode) { throw "upload HTTP $([int]$response.StatusCode): $body" }
            } finally { $form.Dispose(); $content.Dispose() }
        } finally { $stream.Dispose() }
    }
    $concatFields = [System.Collections.Generic.List[System.Collections.Generic.KeyValuePair[string, string]]]::new()
    [void]$concatFields.Add([System.Collections.Generic.KeyValuePair[string, string]]::new('filename', $filename))
    [void]$concatFields.Add([System.Collections.Generic.KeyValuePair[string, string]]::new('filename_chunk_num', $chunkCount.ToString()))
    $concat = [Net.Http.FormUrlEncodedContent]::new($concatFields)
    try {
        $response = $client.PostAsync("$BaseUrl/api/uploader/concat_uploaded_file_chunk", $concat).GetAwaiter().GetResult()
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) { throw "concat HTTP $([int]$response.StatusCode): $body" }
        return $body | ConvertFrom-Json
    } finally { $concat.Dispose() }
}

$status = 'BLOCKED'
$errorMessage = $null
$slot = $null
try {
    $model = (Resolve-Path -LiteralPath $ModelPath).Path
    if (-not (Test-Path -LiteralPath $model -PathType Leaf)) { throw "找不到 model：$ModelPath" }
    $index = $null
    if (-not [string]::IsNullOrWhiteSpace($IndexPath)) {
        $index = (Resolve-Path -LiteralPath $IndexPath).Path
        if (-not (Test-Path -LiteralPath $index -PathType Leaf)) { throw "找不到 index：$IndexPath" }
    }
    [void](Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing -TimeoutSec 15)
    $existing = Invoke-RestMethod "$BaseUrl/api/slot-manager/slots/${SlotIndex}?reload=true"
    if ($existing.voice_changer_type) { throw "slot_index=$SlotIndex 已存在；本工具不覆寫既有 slot" }
    $modelUpload = Upload-File -Path $model
    $indexUpload = if ($index) { Upload-File -Path $index } else { $null }
    $body = [ordered]@{
        voice_changer_type = 'RVC'
        name = $Name
        terms_of_use_url = $TermsOfUseUrl
        slot_index = $SlotIndex
        icon_file = $null
        model_file = [IO.Path]::GetFileName($model)
        index_file = if ($index) { [IO.Path]::GetFileName($index) } else { $null }
        embedder = $Embedder
    } | ConvertTo-Json -Depth 12
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/slot-manager/slots" -Method Post -ContentType 'application/json' -Body $body -UseBasicParsing
    $slot = Invoke-RestMethod "$BaseUrl/api/slot-manager/slots/${SlotIndex}?reload=true"
    if (-not $slot.voice_changer_type -or -not $slot.chunk_sec) { throw 'slot 建立後缺少 voice_changer_type/chunk_sec' }
    $status = 'PASS'
} catch { $errorMessage = $_.Exception.Message }
finally { $client.Dispose() }

$report = [ordered]@{
    run_id = $runId; status = $status; base_url = $BaseUrl; slot_index = $SlotIndex; name = $Name
    model_path = $ModelPath; model_sha256 = if (Test-Path -LiteralPath $ModelPath) { (Get-FileHash -LiteralPath $ModelPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    index_path = $IndexPath; index_sha256 = if ($IndexPath -and (Test-Path -LiteralPath $IndexPath)) { (Get-FileHash -LiteralPath $IndexPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    slot = $slot; error = $errorMessage; note = '不呼叫 /api/operation/initialize；VCClient 2.1.4-alpha 可能因該 lifecycle 清空 model_dir。'
}
$report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Output "status=$status"
Write-Output "report=$reportPath"
if ($errorMessage) { Write-Output "error=$errorMessage"; exit 2 }
