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
    if ([System.IO.Path]::GetExtension($resolved).ToLowerInvariant() -ne $Extension) {
        throw "檔案副檔名必須是 $Extension：$resolved"
    }
    [pscustomobject]@{
        Full = $resolved
        Relative = $resolved.Substring($rootPrefix.Length).Replace('\', '/')
    }
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

    $verification = Resolve-RepoFile $VerificationArtifact ([System.IO.Path]::GetExtension($VerificationArtifact))
    if (-not $verification.Full -or -not (Test-Path -LiteralPath $verification.Full -PathType Leaf)) {
        throw "ready 必須提供 repository 內存在的 verification_artifact：$VerificationArtifact"
    }
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
