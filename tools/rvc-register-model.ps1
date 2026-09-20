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

if ([string]::IsNullOrWhiteSpace($TrainedAt)) { $TrainedAt = (Get-Date).ToString('o') }
$weight = Resolve-RepoFile $WeightsPath '.pth'
$index = Resolve-RepoFile $IndexPath '.index'
$weightHash = (Get-FileHash -LiteralPath $weight.Full -Algorithm SHA256).Hash.ToLowerInvariant()
$indexHash = (Get-FileHash -LiteralPath $index.Full -Algorithm SHA256).Hash.ToLowerInvariant()

if ($Status -eq 'ready' -and ([string]::IsNullOrWhiteSpace($VerificationArtifact) -or @($SourceUrl, $LicenseOrPermission, $TrainingEnvironment) | Where-Object { $_ -match '^(?i)(unknown|pending|pending-manual)$' })) {
    throw 'ready 必須同時提供來源、授權、訓練環境與 verification_artifact；未知值只能保留 candidate。'
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
