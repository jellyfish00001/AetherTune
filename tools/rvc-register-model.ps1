[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ModelId,
    [Parameter(Mandatory = $true)][string]$WeightsPath,
    [Parameter(Mandatory = $true)][string]$IndexPath,
    [Parameter(Mandatory = $true)][ValidateRange(8000, 192000)][int]$SampleRate,
    [Parameter(Mandatory = $true)][ValidateSet('fcpe', 'rmvpe')][string]$F0,
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$DatasetBatchId,
    [Parameter(Mandatory = $true)][string]$RvcRevision,
    [Parameter(Mandatory = $true)][string]$SourceUrl,
    [Parameter(Mandatory = $true)][string]$LicenseOrPermission,
    [Parameter(Mandatory = $true)][string]$TrainingEnvironment,
    [string]$TrainedAt = '',
    [ValidateSet('candidate', 'ready', 'retired')][string]$Status = 'candidate',
    [string]$VerificationArtifact = '',
    [string]$Notes = '',
    [string]$RegisterPath = 'models/model-register.csv',
    [switch]$UpdateExisting,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$registerFull = Join-Path $projectRoot $RegisterPath
$fields = @(
    'model_id', 'weights_relative_path', 'index_relative_path', 'weights_sha256', 'index_sha256',
    'sample_rate', 'f0', 'version', 'dataset_batch_id', 'rvc_revision', 'trained_at',
    'source_url', 'license_or_permission', 'training_environment', 'verification_artifact',
    'status', 'notes'
)

function Resolve-RepoFile([string]$InputPath, [string]$Extension) {
    $candidate = if ([System.IO.Path]::IsPathRooted($InputPath)) { $InputPath } else { Join-Path $projectRoot $InputPath }
    $resolved = (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
    $rootPrefix = $projectRoot.TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "檔案必須位於 repository root 內：$InputPath"
    }
    if ($Extension -and [System.IO.Path]::GetExtension($resolved).ToLowerInvariant() -ne $Extension) {
        throw "檔案副檔名必須是 $Extension：$resolved"
    }
    [pscustomobject]@{
        Full = $resolved
        Relative = $resolved.Substring($rootPrefix.Length).Replace('\', '/')
    }
}

function Assert-VerificationFile {
    param(
        [object]$Evidence,
        [string]$Label,
        [string]$ExpectedRelativePath = '',
        [string]$ExpectedSha256 = ''
    )

    if ($null -eq $Evidence) {
        throw "verification_artifact 缺少 $Label object"
    }
    $rawPath = ([string]$Evidence.path).Trim()
    $declaredHash = ([string]$Evidence.sha256).Trim().ToLowerInvariant()
    if (-not $rawPath) { throw "verification_artifact $Label 缺少 path" }
    if (-not ($declaredHash -match '^[0-9a-f]{64}$')) {
        throw "verification_artifact $Label sha256 不是合法 SHA-256"
    }
    $resolvedEvidence = Resolve-RepoFile $rawPath ''
    if ($ExpectedRelativePath -and $resolvedEvidence.Relative -ine $ExpectedRelativePath) {
        throw "verification_artifact $Label path 與本次 register 不一致：$($resolvedEvidence.Relative) != $ExpectedRelativePath"
    }
    $actualHash = (Get-FileHash -LiteralPath $resolvedEvidence.Full -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $declaredHash) {
        throw "verification_artifact $Label SHA-256 不一致：declared=$declaredHash actual=$actualHash"
    }
    if ($ExpectedSha256 -and $actualHash -ne $ExpectedSha256.ToLowerInvariant()) {
        throw "verification_artifact $Label SHA-256 與本次 register 不一致"
    }
}

function Assert-VerificationArtifact {
    param(
        [string]$ArtifactPath,
        [string]$ExpectedWeightsRelativePath,
        [string]$ExpectedWeightsSha256,
        [string]$ExpectedIndexRelativePath,
        [string]$ExpectedIndexSha256
    )

    $artifact = Resolve-RepoFile $ArtifactPath '.json'
    try {
        $payload = Get-Content -LiteralPath $artifact.Full -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        throw "verification_artifact 無法解析 JSON：$ArtifactPath；$($_.Exception.Message)"
    }
    if ($null -eq $payload -or $payload -is [array]) {
        throw 'verification_artifact JSON 根節點必須是 object'
    }
    if (([string]$payload.status).Trim().ToUpperInvariant() -ne 'PASS') {
        throw "verification_artifact status 必須是 PASS（目前 $([string]$payload.status)）"
    }
    Assert-VerificationFile $payload.model 'model' $ExpectedWeightsRelativePath $ExpectedWeightsSha256
    Assert-VerificationFile $payload.index 'index' $ExpectedIndexRelativePath $ExpectedIndexSha256
    Assert-VerificationFile $payload.input 'input'
    Assert-VerificationFile $payload.output 'output'
}

$weight = Resolve-RepoFile $WeightsPath '.pth'
$index = Resolve-RepoFile $IndexPath '.index'
$weightHash = (Get-FileHash -LiteralPath $weight.Full -Algorithm SHA256).Hash.ToLowerInvariant()
$indexHash = (Get-FileHash -LiteralPath $index.Full -Algorithm SHA256).Hash.ToLowerInvariant()

function Test-UnknownMetadata([string]$Value) {
    $normalized = if ($null -eq $Value) { '' } else { $Value.Trim().ToLowerInvariant() }
    return [string]::IsNullOrWhiteSpace($normalized) -or $normalized -match '^(unknown|pending|pending-manual|tbd|todo|n/?a|not[-_ ]?(provided|verified)|replace_with_sha256)([-_ ].*)?$'
}

if ($Status -eq 'ready') {
    # ready 是可追溯驗收狀態，即使 -DryRun 也不能用 placeholder 或自動產生訓練時間。
    $readyFields = [ordered]@{
        model_id = $ModelId
        sample_rate = [string]$SampleRate
        f0 = $F0
        version = $Version
        dataset_batch_id = $DatasetBatchId
        rvc_revision = $RvcRevision
        trained_at = $TrainedAt
        source_url = $SourceUrl
        license_or_permission = $LicenseOrPermission
        training_environment = $TrainingEnvironment
        verification_artifact = $VerificationArtifact
    }
    $invalidReadyFields = @($readyFields.GetEnumerator() | Where-Object { Test-UnknownMetadata ([string]$_.Value) } | ForEach-Object { $_.Key })
    if ($invalidReadyFields.Count -gt 0) {
        throw "ready 必須提供完整且可追溯欄位；空白或 unknown/pending placeholder：$($invalidReadyFields -join ', ')。未知值只能保留 candidate。"
    }

    Assert-VerificationArtifact $VerificationArtifact $weight.Relative $weightHash $index.Relative $indexHash
}

$existing = @()
if (Test-Path -LiteralPath $registerFull -PathType Leaf) { $existing = @(Import-Csv -LiteralPath $registerFull) }
$match = @($existing | Where-Object { ([string]$_.model_id).Trim() -eq $ModelId })
if ($match.Count -gt 0 -and -not $UpdateExisting) { throw "model_id 已存在；若要更新請明確加上 -UpdateExisting：$ModelId" }

$newRow = [ordered]@{
    model_id = $ModelId
    weights_relative_path = $weight.Relative
    index_relative_path = $index.Relative
    weights_sha256 = $weightHash
    index_sha256 = $indexHash
    sample_rate = $SampleRate
    f0 = $F0
    version = $Version
    dataset_batch_id = $DatasetBatchId
    rvc_revision = $RvcRevision
    trained_at = $TrainedAt
    source_url = $SourceUrl
    license_or_permission = $LicenseOrPermission
    training_environment = $TrainingEnvironment
    verification_artifact = $VerificationArtifact
    status = $Status
    notes = $Notes
}

if ($DryRun) {
    [pscustomobject]$newRow | ConvertTo-Json -Depth 3
    exit 0
}

$out = [System.Collections.Generic.List[object]]::new()
$replaced = $false
foreach ($row in $existing) {
    if (([string]$row.model_id).Trim() -eq $ModelId) {
        $out.Add([pscustomobject]$newRow)
        $replaced = $true
        continue
    }
    $normalized = [ordered]@{}
    foreach ($field in $fields) { $normalized[$field] = [string]$row.$field }
    $out.Add([pscustomobject]$normalized)
}
if (-not $replaced) { $out.Add([pscustomobject]$newRow) }

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $registerFull) | Out-Null
$out | Export-Csv -LiteralPath $registerFull -NoTypeInformation -Encoding UTF8
Write-Output "registered=$ModelId status=$Status weights_sha256=$weightHash index_sha256=$indexHash register=$registerFull"
