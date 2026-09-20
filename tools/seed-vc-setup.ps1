[CmdletBinding()]
param(
    [string]$Python310 = 'C:\Users\User\AppData\Local\Programs\Python\Python310\python.exe',
    [string]$Environment = '.\tools\venvs\seed-vc'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path -LiteralPath $Python310 -PathType Leaf)) {
    throw "找不到 Python 3.10：$Python310"
}

$envRoot = [IO.Path]::GetFullPath($Environment)
$envPython = Join-Path $envRoot 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $envPython -PathType Leaf)) {
    Write-Output "建立 Seed-VC Python environment：$envRoot"
    & $Python310 -m venv $envRoot
    if ($LASTEXITCODE -ne 0) { throw "建立 venv 失敗，exit=$LASTEXITCODE" }
}

Write-Output '更新 pip/setuptools/wheel'
& $envPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "更新 packaging tools 失敗，exit=$LASTEXITCODE" }

Write-Output '安裝與現有 RTX 5060 Ti runtime 對齊的 Torch CUDA 12.8'
& $envPython -m pip install --index-url 'https://download.pytorch.org/whl/cu128' `
    'torch==2.7.1+cu128' 'torchaudio==2.7.1+cu128' 'torchvision==0.22.1+cu128'
if ($LASTEXITCODE -ne 0) { throw "安裝 Torch CUDA runtime 失敗，exit=$LASTEXITCODE" }

$requirementsPath = Join-Path $projectRoot 'tools\external\seed-vc\requirements.txt'
$packages = Get-Content -LiteralPath $requirementsPath -Encoding UTF8 |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith('#') -and $_ -notmatch '^--' -and $_ -notmatch '^(torch|torchvision|torchaudio)(\s|=|$)' }

Write-Output '安裝 Seed-VC 其他官方依賴（略過 requirements.txt 內舊 Torch pin）'
& $envPython -m pip install @packages
if ($LASTEXITCODE -ne 0) { throw "安裝 Seed-VC 依賴失敗，exit=$LASTEXITCODE" }

& $envPython -c "import torch, torchaudio, torchvision, munch, dac, funasr; print('Seed-VC imports PASS'); print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw "Seed-VC import smoke test 失敗，exit=$LASTEXITCODE" }

Write-Output "Seed-VC environment ready: $envPython"
