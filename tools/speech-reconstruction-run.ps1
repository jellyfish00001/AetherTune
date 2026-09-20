[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$InputWav,
    [ValidateSet('cosyvoice', 'breeze-tts-2')] [string]$Backend = 'cosyvoice',
    [string]$OutputDir = '.\artifacts\speech-reconstruction'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path -LiteralPath $InputWav -PathType Leaf)) {
    throw "找不到輸入音檔：$InputWav"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$inputHash = (Get-FileHash -LiteralPath $InputWav -Algorithm SHA256).Hash
Write-Output "Input SHA256: $inputHash"
Write-Output "Backend: $Backend"
Write-Output "目前只建立安全的流程入口；STT/TTS 需使用 backends/speech-reconstruction/README.md 指定的獨立環境與官方命令。"
Write-Output "下一步：先產生 exact transcript，再把 reference audio、transcript、model revision 與輸出 hash 寫入 artifact。"
