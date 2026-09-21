[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("aethertune-wrapper-failure-" + [guid]::NewGuid().ToString('N'))
$runner = Join-Path $PSScriptRoot 'speech-reconstruction-run.ps1'
New-Item -ItemType Directory -Force -Path $root | Out-Null

try {
    $output = Join-Path $root 'missing-input.wav'
    $workflow = [System.IO.Path]::ChangeExtension($output, '.workflow.json')
    Set-Content -LiteralPath $workflow -Value '{"status":"PASS"}' -Encoding UTF8
    $failed = $false
    try {
        & $runner `
            -InputWav (Join-Path $root 'does-not-exist.wav') `
            -OutputDir $root `
            -Backend cosyvoice `
            -Output $output 2>&1 | Out-Null
    } catch {
        $failed = $true
    }
    if (-not $failed) { throw 'missing input unexpectedly accepted' }
    if (Test-Path -LiteralPath $workflow) { throw 'stale PASS workflow was not removed' }
    Write-Output 'PASS speech reconstruction stale workflow regression'
} finally {
    if (Test-Path -LiteralPath $root) {
        Remove-Item -LiteralPath $root -Recurse -Force
    }
}
