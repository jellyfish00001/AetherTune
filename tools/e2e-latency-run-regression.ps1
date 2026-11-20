#Requires -Version 5.1
<#
.SYNOPSIS
  E2E latency 編排與 virtual-line-probe 離線 regression（不播放／不錄音，除 probe -List）。
#>
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$failures = New-Object System.Collections.Generic.List[string]

function Assert-True {
    param([bool]$Cond, [string]$Msg)
    if (-not $Cond) { $failures.Add($Msg) }
}

$ps1Files = @(
    (Join-Path $repoRoot 'tools\e2e-latency-run.ps1'),
    (Join-Path $repoRoot 'tools\virtual-line-probe.ps1')
)
foreach ($f in $ps1Files) {
    $tokens = $null
    $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tokens, [ref]$errors)
    Assert-True ($null -eq $errors -or $errors.Count -eq 0) "parse errors in $f"
}

$tempRoot = Join-Path $env:TEMP ("e2e-latency-regression-{0}" -f [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
try {
    $py = (Get-Command python -ErrorAction Stop).Source
    $refWav = Join-Path $tempRoot 'ref.wav'
    $wavCode = @'
import wave, struct, sys
path = sys.argv[1]
with wave.open(path, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(struct.pack('<h', 100) * 1600)
print(path)
'@
    & $py -c $wavCode $refWav | Out-Null
    Assert-True (Test-Path -LiteralPath $refWav) 'fake reference wav'

    $selfDir = Join-Path $tempRoot 'selftest'
    & pwsh -NoProfile -File (Join-Path $repoRoot 'tools\e2e-latency-run.ps1') -SelfTest -Root $repoRoot -Python $py -ResultsDir $selfDir
    Assert-True ($LASTEXITCODE -eq 0) "SelfTest exit $LASTEXITCODE"

    $reqDir = Join-Path $tempRoot 'requestonly'
    & pwsh -NoProfile -File (Join-Path $repoRoot 'tools\e2e-latency-run.ps1') `
        -RequestOnly -Engine meanvc2 -Root $repoRoot -Reference $refWav `
        -Profile pc2-virtual -ResultsDir $reqDir
    Assert-True ($LASTEXITCODE -eq 0) "RequestOnly exit $LASTEXITCODE"
    $reqJson = Get-ChildItem -LiteralPath $reqDir -Recurse -Filter 'engine-request.json' | Select-Object -First 1
    Assert-True ($null -ne $reqJson) 'engine-request.json missing'
    if ($reqJson) {
        $req = Get-Content -LiteralPath $reqJson.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        Assert-True ($req.input -match 'Steam') 'request input'
        Assert-True ($req.output -match 'Voice Changer') 'request output'
        Assert-True ([bool]($req.host_api -as [string]).Length) 'request host_api'
        Assert-True ([bool]($req.parameters.model -as [string]).Length) 'request parameters.model'
        Assert-True ($req.postfx.enabled -eq $false) 'postfx bypass'
        Assert-True ($req.monitor.enabled -eq $false) 'monitor disabled'
    }

    $listOut = & pwsh -NoProfile -File (Join-Path $repoRoot 'tools\virtual-line-probe.ps1') -List
    Assert-True ($LASTEXITCODE -eq 0) "virtual-line-probe -List exit $LASTEXITCODE"
    $listObj = $listOut | ConvertFrom-Json
    Assert-True ($listObj.devices.Count -gt 0) 'device list empty'
} finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

& $py (Join-Path $repoRoot 'tools\e2e-latency-analysis-regression.py')
Assert-True ($LASTEXITCODE -eq 0) "e2e-latency-analysis-regression exit $LASTEXITCODE"

Push-Location $repoRoot
try {
    & $py -m unittest services.engines.test_latency_trace -v 2>&1 | Out-Host
    Assert-True ($LASTEXITCODE -eq 0) "test_latency_trace exit $LASTEXITCODE"
} finally {
    Pop-Location
}

if ($failures.Count -gt 0) {
    Write-Host 'FAILURES:'
    $failures | ForEach-Object { Write-Host " - $_" }
    exit 1
}
Write-Host 'e2e-latency-run-regression PASS'
exit 0