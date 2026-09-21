[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$registerScript = Join-Path $PSScriptRoot 'rvc-register-model.ps1'
$auditScript = Join-Path $PSScriptRoot 'rvc-model-audit.py'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$weights = Join-Path $projectRoot 'models\weights\Wukong_HeroicMale.pth'
$index = Join-Path $projectRoot 'models\indexes\Wukong_HeroicMale.index'
$repoTemp = Join-Path $PSScriptRoot ('.rvc-ready-gate-regression-' + [guid]::NewGuid().ToString())
$tempOutput = Join-Path ([IO.Path]::GetTempPath()) ('aethertune-ready-gate-' + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $repoTemp -Force | Out-Null
New-Item -ItemType Directory -Path $tempOutput -Force | Out-Null

function Assert-RegisterRejectsUnknown {
    $failed = $false
    try {
        $null = & $registerScript `
            -ModelId 'RegressionUnknown' `
            -WeightsPath $weights `
            -IndexPath $index `
            -SampleRate 40000 `
            -F0 fcpe `
            -Version v2 `
            -DatasetBatchId 'unknown-dataset' `
            -RvcRevision 'unknown-revision' `
            -SourceUrl 'unknown-source' `
            -LicenseOrPermission 'unknown-license' `
            -TrainingEnvironment 'unknown-environment' `
            -Status ready `
            -VerificationArtifact 'docs/vcclient-rvc-probe-latest.md' `
            -DryRun 2>&1
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    } catch {
        $failed = $true
    }
    if (-not $failed) { throw '回歸失敗：ready + unknown metadata unexpectedly succeeded' }
    Write-Output 'PASS register ready gate rejects unknown metadata'
}

function Assert-RegisterRejectsMissingArtifact {
    $failed = $false
    try {
        $null = & $registerScript `
            -ModelId 'RegressionMissingArtifact' `
            -WeightsPath $weights `
            -IndexPath $index `
            -SampleRate 40000 `
            -F0 fcpe `
            -Version v2 `
            -DatasetBatchId 'known-dataset' `
            -RvcRevision 'known-revision' `
            -TrainedAt '2026-09-20T00:00:00+08:00' `
            -SourceUrl 'https://example.invalid/source' `
            -LicenseOrPermission 'permission-record' `
            -TrainingEnvironment 'known-environment' `
            -Status ready `
            -VerificationArtifact 'docs/does-not-exist-ready-gate.json' `
            -DryRun 2>&1
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    } catch {
        $failed = $true
    }
    if (-not $failed) { throw '回歸失敗：ready + missing verification artifact unexpectedly succeeded' }
    Write-Output 'PASS register ready gate rejects missing verification artifact'
}

function New-ReadyRegister([string]$VerificationRelativePath) {
    $rows = @(Import-Csv (Join-Path $projectRoot 'models\model-register.csv'))
    $row = $rows | Where-Object { $_.model_id -eq 'Wukong_HeroicMale' }
    $row.f0 = 'fcpe'
    $row.dataset_batch_id = 'regression-dataset-batch'
    $row.rvc_revision = 'regression-rvc-revision'
    $row.trained_at = '2026-09-20T00:00:00+08:00'
    $row.source_url = 'https://example.invalid/regression-source'
    $row.license_or_permission = 'regression-permission-record'
    $row.training_environment = 'regression-environment'
    $row.verification_artifact = $VerificationRelativePath
    $row.status = 'ready'
    $registerPath = Join-Path $tempOutput 'ready-register.csv'
    $rows | Export-Csv -LiteralPath $registerPath -NoTypeInformation -Encoding UTF8
    return $registerPath
}

function Assert-AuditRejectsArtifact([string]$Label, [string]$Content, [string]$ExpectedIssue) {
    $artifactName = "$Label.json"
    $artifactPath = Join-Path $repoTemp $artifactName
    [IO.File]::WriteAllText($artifactPath, $Content, [Text.UTF8Encoding]::new($false))
    $relative = 'tools/' + (Split-Path -Leaf $repoTemp) + '/' + $artifactName
    $registerPath = New-ReadyRegister $relative
    $auditOutput = Join-Path $tempOutput "$Label-audit.json"
    $null = & $python $auditScript --register $registerPath --output $auditOutput 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) { throw "回歸失敗：audit unexpectedly accepted $Label verification artifact" }
    $report = Get-Content -LiteralPath $auditOutput -Raw -Encoding UTF8 | ConvertFrom-Json
    $auditRow = @($report.rows | Where-Object { $_.model_id -eq 'Wukong_HeroicMale' })[0]
    if ($auditRow.result -ne 'BLOCKED') { throw "回歸失敗：$Label row result=$($auditRow.result)" }
    if (-not (@($auditRow.issues) -match [regex]::Escape($ExpectedIssue))) {
        throw "回歸失敗：$Label issues 未包含 $ExpectedIssue"
    }
    Write-Output "PASS audit rejects $Label verification artifact"
}

try {
    Assert-RegisterRejectsUnknown
    Assert-RegisterRejectsMissingArtifact
    $known = Get-Content -LiteralPath (Join-Path $projectRoot 'artifacts\rvc-fcpe-gpu\Wukong_HeroicMale.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $known.status = 'FAIL'
    Assert-AuditRejectsArtifact 'fail-status' ($known | ConvertTo-Json -Depth 12) 'status 必須是 PASS'
    Assert-AuditRejectsArtifact 'malformed' '{' '無法解析 JSON'
    Write-Output 'PASS rvc ready gate regression'
    exit 0
} finally {
    Remove-Item -LiteralPath $repoTemp -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempOutput -Recurse -Force -ErrorAction SilentlyContinue
}
