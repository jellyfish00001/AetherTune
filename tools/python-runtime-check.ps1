[CmdletBinding()]
param([string]$Distro = 'Ubuntu', [string]$OutFile)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$probe = Join-Path $PSScriptRoot 'python-runtime-probe.py'
$results = @()
foreach ($backend in @('rvc','seed-vc','meanvc2','xvc')) {
    $relative = if ($backend -eq 'rvc') { '.venv/Scripts/python.exe' } else { "tools/venvs/$backend/Scripts/python.exe" }
    $python = Join-Path $root $relative
    $raw = & $python $probe --backend $backend
    if (-not $raw) { throw "無法檢查 $backend" }
    $results += $raw | ConvertFrom-Json
}
# WSL 保留 Linux venv；與 Windows 共用 Python minor version，不混用 binaries。
$wslPathOutput = & wsl.exe -d $Distro -- wslpath -a ($root -replace '\\','/')
if ($LASTEXITCODE -ne 0 -or -not $wslPathOutput) { throw "WSL 無法解析專案路徑：$root" }
$wslRoot = $wslPathOutput.Trim()
foreach ($entry in @(@('cosyvoice','cosyvoice-wsl'), @('breeze','breeze-tts-wsl'), @('stt','stt-wsl'))) {
    $raw = & wsl.exe -d $Distro -- "$wslRoot/tools/venvs/$($entry[1])/bin/python" "$wslRoot/tools/python-runtime-probe.py" --backend $entry[0]
    if (-not $raw) { throw "無法檢查 $($entry[0])" }
    $results += $raw | ConvertFrom-Json
}
$report = [ordered]@{ generated_at = (Get-Date).ToString('o'); python_minor = '3.10'; scope = 'project-managed runtimes; excludes VCClient embedded runtime and system Python'; status = if (@($results | Where-Object status -ne 'PASS').Count) { 'BLOCKED' } else { 'PASS' }; runtimes = $results }
$json = $report | ConvertTo-Json -Depth 8
if ($OutFile) {
    $path = [IO.Path]::GetFullPath($OutFile)
    $null = New-Item -ItemType Directory -Force -Path (Split-Path $path -Parent)
    Set-Content -LiteralPath $path -Value $json -Encoding UTF8
}
Write-Output $json
if ($report.status -ne 'PASS') { exit 2 }
