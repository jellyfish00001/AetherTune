# 只稽核本次 App 的程序樹；不終止既有、不屬於該樹的程序。
[CmdletBinding()]
param([Parameter(Mandatory=$true)][int]$AppProcessId)
$ErrorActionPreference='Stop'
$root=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$inventory=@(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CreationDate,ExecutablePath)
$owned=@($inventory | Where-Object ProcessId -eq $AppProcessId)
$entryExe=Join-Path $root 'AetherTune.exe'
$isRootEntry=$owned.Count -eq 1 -and $owned[0].ExecutablePath -ieq $entryExe
$isBuild=$owned.Count -eq 1 -and $owned[0].ExecutablePath -like "$root\app\src-tauri\target\*\aethertune-desktop.exe"
if (-not ($isRootEntry -or $isBuild)) {throw '不是本次 Desktop build 的 App PID'}
do {
    $ids=@($owned.ProcessId)
    $next=@($inventory | Where-Object {$_.ParentProcessId -in $ids -and $_.ProcessId -notin $ids})
    $owned+= $next
} while ($next.Count -gt 0)
Push-Location (Split-Path $PSScriptRoot -Parent)
try { & node tests/control.mjs exit; if ($LASTEXITCODE -ne 0) {throw 'App Exit command failed'} } finally {Pop-Location}
$deadline=[DateTime]::UtcNow.AddSeconds(10)
do {
    $fresh=@(Get-CimInstance Win32_Process | Select-Object ProcessId,CreationDate)
    $survivors=@($owned | Where-Object { $original=$_; @($fresh | Where-Object {$_.ProcessId -eq $original.ProcessId -and $_.CreationDate -eq $original.CreationDate}).Count -gt 0 })
    if($survivors.Count -gt 0){Start-Sleep -Milliseconds 200}
} while($survivors.Count -gt 0 -and [DateTime]::UtcNow -lt $deadline)
$report=@{status=if($survivors.Count){'BLOCKED'}else{'PASS'};scope='App Exit while runner alive';owned=$owned;survivors=$survivors;audio_status='WAITING'}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $root 'artifacts/desktop/integration/cleanup-report.json') -Encoding utf8
if($survivors.Count){throw 'App Exit 後仍有本次程序存活'}
Write-Output "PASS: App Exit cleared $($owned.Count) owned processes"
