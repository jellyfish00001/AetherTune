$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot 'seed-vc-run.ps1'
$runnerText = Get-Content -LiteralPath $runner -Raw -Encoding UTF8
if ($runnerText -notmatch '\$validatorPython\s*=\s*\$resolvedPython' -or $runnerText -match 'Join-Path\s+\$projectRoot\s+[''\"]\.venv') {
    throw 'Offline output validation must use the resolved Seed-VC Python, not the root RVC venv.'
}
$fixtureRoot = Join-Path $env:TEMP ("aethertune-seed-vc-run-preflight-regression-" + [Guid]::NewGuid().ToString('N'))
$repoPath = Join-Path $fixtureRoot 'repo'
$configPath = Join-Path $fixtureRoot 'config.yml'
$checkpointPath = Join-Path $fixtureRoot 'checkpoint.pth'
$pythonPath = Join-Path $fixtureRoot 'python.exe'
$sourcePath = Join-Path $fixtureRoot 'source.wav'
$targetPath = Join-Path $fixtureRoot 'target.wav'
$null = New-Item -ItemType Directory -Force -Path $repoPath
foreach ($path in @((Join-Path $repoPath 'inference.py'), $configPath, $checkpointPath, $pythonPath, $sourcePath, $targetPath)) {
    Set-Content -LiteralPath $path -Value 'fixture only; inference is never reached' -Encoding UTF8
}

$cases = @(
    @{ Name = 'missing source'; Source = (Join-Path $fixtureRoot 'missing-source.wav'); Target = $targetPath; Repo = $repoPath; Checkpoint = $checkpointPath; Config = $configPath; Python = $pythonPath },
    @{ Name = 'missing target'; Source = $sourcePath; Target = (Join-Path $fixtureRoot 'missing-target.wav'); Repo = $repoPath; Checkpoint = $checkpointPath; Config = $configPath; Python = $pythonPath },
    @{ Name = 'missing repo'; Source = $sourcePath; Target = $targetPath; Repo = (Join-Path $fixtureRoot 'missing-repo'); Checkpoint = $checkpointPath; Config = $configPath; Python = $pythonPath },
    @{ Name = 'missing checkpoint'; Source = $sourcePath; Target = $targetPath; Repo = $repoPath; Checkpoint = (Join-Path $fixtureRoot 'missing-checkpoint.pth'); Config = $configPath; Python = $pythonPath },
    @{ Name = 'missing config'; Source = $sourcePath; Target = $targetPath; Repo = $repoPath; Checkpoint = $checkpointPath; Config = (Join-Path $fixtureRoot 'missing-config.yml'); Python = $pythonPath },
    @{ Name = 'missing Python'; Source = $sourcePath; Target = $targetPath; Repo = $repoPath; Checkpoint = $checkpointPath; Config = $configPath; Python = (Join-Path $fixtureRoot 'missing-python.exe') }
)

foreach ($case in $cases) {
    $output = Join-Path $fixtureRoot ($case.Name -replace '[^a-zA-Z0-9-]', '-')
    $null = New-Item -ItemType Directory -Force -Path $output
    $manifestPath = Join-Path $output 'seed-vc-run.json'
    @{ status = 'PASS'; run_id = 'stale-pass-fixture' } | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    try {
        & $runner -Source $case.Source -Target $case.Target -OutputDir $output -Repo $case.Repo -Checkpoint $case.Checkpoint -Config $case.Config -Python $case.Python
    }
    catch {
        # Expected: each invalid precondition must persist this run's non-PASS manifest.
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.status -ne 'BLOCKED' -or $manifest.run_id -eq 'stale-pass-fixture' -or -not $manifest.failure) {
        throw "$($case.Name): expected a fresh BLOCKED manifest, got status=$($manifest.status) run_id=$($manifest.run_id)"
    }
}

Write-Output "PASS seed-vc runner preflight regression: all six missing-input/repo/checkpoint/config/Python cases replaced stale PASS with BLOCKED; fixture=$fixtureRoot"
