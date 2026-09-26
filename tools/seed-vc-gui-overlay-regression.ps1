#Requires -Version 7.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'seed-vc-gui-overlay.ps1')

# Keep the isolated fixture for inspection; this regression never removes files or links.
$fixtureRoot = Join-Path $env:TEMP ("aethertune-seed-vc-overlay-regression-" + [Guid]::NewGuid().ToString('N'))
$targetRoot = Join-Path $fixtureRoot 'verified-cache'
$wrongTargetRoot = Join-Path $fixtureRoot 'other-cache'
$linkRoot = Join-Path $fixtureRoot 'session-checkpoints'
$linkPath = Join-Path $linkRoot 'models--fixture--model'
$null = New-Item -ItemType Directory -Force -Path $targetRoot, $wrongTargetRoot, $linkRoot
Set-Content -LiteralPath (Join-Path $targetRoot 'sentinel.txt') -Value 'fixture-owned cache marker' -Encoding UTF8

$first = Ensure-SeedVcCacheJunction -LinkPath $linkPath -TargetPath $targetRoot
$second = Ensure-SeedVcCacheJunction -LinkPath $linkPath -TargetPath $targetRoot
if ($first -ne 'CREATED_AND_VERIFIED' -or $second -ne 'EXISTING_AND_VERIFIED') {
    throw "Two-pass overlay regression returned unexpected states: first=$first second=$second"
}

$wrongTargetRejected = $false
try {
    $null = Ensure-SeedVcCacheJunction -LinkPath $linkPath -TargetPath $wrongTargetRoot
}
catch {
    $wrongTargetRejected = $true
}
if (-not $wrongTargetRejected) { throw 'Existing junction to a different target was not rejected.' }

$resolved = [System.IO.DirectoryInfo]::new($linkPath).ResolveLinkTarget($true)
$expected = Get-SeedVcCanonicalDirectoryPath -Path $targetRoot
$actual = Get-SeedVcCanonicalDirectoryPath -Path $resolved.FullName
if ($actual -ine $expected -or -not (Test-Path -LiteralPath (Join-Path $linkPath 'sentinel.txt') -PathType Leaf)) {
    throw 'Wrong-target preflight changed or detached the original fixture junction.'
}

Write-Output "PASS seed-vc GUI overlay regression: first=$first; second=$second; wrong target rejected without deleting fixture data; fixture=$fixtureRoot"
