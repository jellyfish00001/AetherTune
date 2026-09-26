# 日常 Seed GUI 不依賴 Codex 的 PATH；官方 portable PowerShell 不修改系統設定。
[CmdletBinding()]
param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$version = '7.6.6'
$sha256 = '02FE458BE20493FBDF43F61EA20610B811EE6C738AB1676C61B9CFCD1A33C860'
$runtimeRoot = Join-Path $root 'tools/external/powershell'
$exe = Join-Path $runtimeRoot 'pwsh.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    if ($VerifyOnly) { throw '本機 portable PowerShell 尚未安裝' }
    $cache = Join-Path $root 'tools/cache'
    $null = New-Item -ItemType Directory -Force -Path $cache
    $zip = Join-Path $cache "PowerShell-$version-win-x64.zip"
    if (-not (Test-Path -LiteralPath $zip)) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest "https://github.com/PowerShell/PowerShell/releases/download/v$version/PowerShell-$version-win-x64.zip" -OutFile $zip -UseBasicParsing
    }
    if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $sha256) { throw 'PowerShell 官方 ZIP SHA-256 不符，停止解壓' }
    if (Test-Path -LiteralPath $runtimeRoot) { throw "已有不完整 runtime，保留並停止：$runtimeRoot" }
    Expand-Archive -LiteralPath $zip -DestinationPath $runtimeRoot
}
$actual = & $exe -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
if ($LASTEXITCODE -ne 0 -or $actual.Trim() -ne $version) { throw 'portable PowerShell runtime 版本檢查失敗' }
Write-Output "PASS：PowerShell $actual；$exe；官方 ZIP SHA-256 $sha256"
