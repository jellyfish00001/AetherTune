# RVC 的本機 Python 3.10/CUDA 12.8 安裝入口；模型與 upstream 不由此修改。
[CmdletBinding()]
param([string]$Python310, [switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$venv = Join-Path $root '.venv'
$runtime = Join-Path $venv 'Scripts/python.exe'
$repo = Join-Path $root 'tools/external/Retrieval-based-Voice-Conversion-WebUI'
$revision = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $revision -ne '81eed5e8f68b6bed1789f682fe78cdd324495afc') { throw 'RVC upstream revision 不符，保留 source 並停止' }
if ($VerifyOnly) {
    & $runtime -c 'import sys,torch; assert sys.version_info[:2]==(3,10); assert torch.cuda.is_available(); print(sys.version,torch.__version__,torch.cuda.get_device_name(0))'
    if ($LASTEXITCODE -ne 0) { throw 'RVC Python/CUDA runtime 不符' }
    & $runtime -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'RVC pip check 失敗' }
    return
}
if (-not $Python310) { $Python310 = (& py -3.10 -c 'import sys; print(sys.executable)').Trim() }
& $Python310 -c 'import sys,struct; assert sys.version_info[:2]==(3,10) and struct.calcsize("P")==8'
if ($LASTEXITCODE -ne 0) { throw '需要 Python 3.10 x64' }
if (Test-Path -LiteralPath $runtime) {
    & $runtime -c 'import sys; assert sys.version_info[:2]==(3,10)'
    if ($LASTEXITCODE -ne 0) { throw '既有 .venv 不是 3.10；請先保留備份，再重建。' }
} else {
    & $Python310 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'RVC venv 建立失敗' }
}
& $runtime -m pip install 'pip==26.2.1' 'setuptools==80.10.2' wheel
if ($LASTEXITCODE -ne 0) { throw 'packaging 安裝失敗' }
& $runtime -m pip install 'torch==2.7.1+cu128' 'torchaudio==2.7.1+cu128' --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'CUDA Torch 安裝失敗' }
# 沿用固定 upstream 的直接依賴；Python 3.10 resolver 選相容 wheels。
$requirements = Join-Path $root 'tools/external/Retrieval-based-Voice-Conversion-WebUI/requirments_cu128_py312.txt'
$packages = Get-Content -LiteralPath $requirements -Encoding UTF8 | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') -and -not $_.StartsWith('--') }
& $runtime -m pip install @packages
if ($LASTEXITCODE -ne 0) { throw 'RVC dependencies 安裝失敗' }
& $runtime -m pip check
if ($LASTEXITCODE -ne 0) { throw 'RVC pip check 失敗' }
Write-Output 'PASS：RVC Python 3.10 安裝與套件檢查；有效音訊需另跑 rvc-fcpe-gpu-infer.py。'
