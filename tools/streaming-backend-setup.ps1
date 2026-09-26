# 單人維護用 setup：兩個 upstream、兩個 venv；不新增服務或更動其他 backend。
param(
    [Parameter(Mandatory)][ValidateSet('meanvc2','xvc')][string]$Backend,
    [string]$Python,
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$repoName = if ($Backend -eq 'meanvc2') { 'MeanVC2' } else { 'X-VC' }
$repoUrl = if ($Backend -eq 'meanvc2') { 'https://github.com/ASLP-lab/MeanVC2.git' } else { 'https://github.com/Jerrister/X-VC.git' }
$revision = if ($Backend -eq 'meanvc2') { '13acf84c1bf135ea5edad9c245b345289b06b33e' } else { '49df8c591eafc48b096e466d96f9839f9c0dd739' }
$expectedVersion = '3.10'
$repo = Join-Path $root "tools/external/$repoName"
$venv = Join-Path $root "tools/venvs/$Backend"

function Test-PythonVersion {
    param([string]$Executable, [string]$Version)
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
    $detected = & $Executable -c 'import sys; print("%s.%s" % sys.version_info[:2])' 2>$null
    return ($LASTEXITCODE -eq 0 -and $detected -and $detected.Trim() -eq $Version)
}

function Assert-BackendRuntime {
    param([string]$Executable, [string]$Context)
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "找不到 $Backend $Context Python：$Executable"
    }
    $runtimeInfo = & $Executable -c 'import struct,sys; print("%s.%s|%s" % (sys.version_info[0], sys.version_info[1], struct.calcsize("P") * 8))' 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $runtimeInfo) { throw "無法啟動 $Backend $Context Python：$Executable" }
    $expectedRuntime = "$expectedVersion|64"
    if ($runtimeInfo.Trim() -ne $expectedRuntime) {
        throw "$Backend $Context 需要 Python $expectedVersion 64-bit，收到 $($runtimeInfo.Trim())"
    }
}

function Find-VenvBasePython {
    param([string]$VenvPath, [string]$Version)
    $cfgPath = Join-Path $VenvPath 'pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $cfgPath -PathType Leaf)) { return $null }

    $venvFullPath = [System.IO.Path]::GetFullPath($VenvPath).TrimEnd('\') + '\'
    $cfg = Get-Content -LiteralPath $cfgPath -Encoding UTF8
    $candidatePaths = @()
    foreach ($line in $cfg) {
        if ($line -match '^\s*home\s*=\s*(.+?)\s*$') {
            $baseHomePath = $Matches[1].Trim('"')
            if (Test-Path -LiteralPath $baseHomePath -PathType Container) {
                $candidatePaths += Join-Path $baseHomePath 'python.exe'
            }
        } elseif ($line -match '^\s*executable\s*=\s*(.+?)\s*$') {
            $candidatePaths += $Matches[1].Trim('"')
        }
    }

    foreach ($candidate in ($candidatePaths | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $candidateFullPath = [System.IO.Path]::GetFullPath($candidate)
        if ($candidateFullPath.StartsWith($venvFullPath, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
        if (Test-PythonVersion -Executable $candidateFullPath -Version $Version) { return $candidateFullPath }
    }
    return $null
}

$runtime = Join-Path $venv 'Scripts/python.exe'
$downloadScript = Join-Path $PSScriptRoot 'streaming-backend-download.py'

if ($VerifyOnly) {
    Assert-BackendRuntime -Executable $runtime -Context '既有 venv'
    if (-not (Test-Path -LiteralPath $repo -PathType Container)) { throw "找不到既有 upstream checkout：$repo" }
    $remote = & git -C $repo remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $remote.Trim() -ne $repoUrl) { throw "upstream origin 不符：$($remote.Trim())" }
    if (& git -C $repo status --porcelain --untracked-files=no) { throw "upstream tracked source 有本機變更，保留並停止：$repo" }
    $head = & git -C $repo rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $head.Trim() -ne $revision) {
        throw "$Backend upstream revision 不符；預期 $revision，實際 $($head.Trim())。VerifyOnly 不會 checkout。"
    }
    & $runtime -m pip check
    if ($LASTEXITCODE -ne 0) { throw '既有環境 dependencies 檢查失敗' }
    & $runtime $downloadScript --backend $Backend --verify-only
    if ($LASTEXITCODE -ne 0) { throw '既有資產 hash 檢查失敗' }
    Write-Output "PASS：$Backend VerifyOnly（Python $expectedVersion 64-bit、固定 revision、pip check、資產 hash）。未執行 checkout、pip install 或下載。"
    return
}

if (Test-Path -LiteralPath $runtime -PathType Leaf) {
    Assert-BackendRuntime -Executable $runtime -Context '既有 venv'
}

if (-not $Python) {
    $Python = Find-VenvBasePython -VenvPath $venv -Version $expectedVersion
    if (-not $Python) {
        $launcherVersion = "-$expectedVersion"
        $detectedPython = & py $launcherVersion -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $detectedPython) { $Python = $detectedPython.Trim() }
    }
    if (-not $Python) {
        throw "找不到可用的 Python $expectedVersion；既有 pyvenv.cfg 沒有有效 base Python，且 py $launcherVersion 無法解析。請提供 -Python 完整路徑；不會自動下載 Python。"
    }
}
if (-not (Test-PythonVersion -Executable $Python -Version $expectedVersion)) {
    $actualVersion = & $Python -c 'import sys; print("%s.%s" % sys.version_info[:2])' 2>$null
    if ($LASTEXITCODE -ne 0) { throw "無法啟動指定的 Python：$Python" }
    throw "$Backend 需要 Python $expectedVersion，收到 $($actualVersion.Trim())"
}

if (-not (Test-Path -LiteralPath $repo)) {
    & git clone $repoUrl $repo
    if ($LASTEXITCODE -ne 0) { throw 'upstream clone 失敗' }
}
$remote = & git -C $repo remote get-url origin
if ($remote -ne $repoUrl) { throw "upstream origin 不符：$remote" }
if (& git -C $repo status --porcelain --untracked-files=no) { throw "upstream tracked source 有本機變更，保留並停止：$repo" }
& git -C $repo checkout --detach $revision
if ($LASTEXITCODE -ne 0) { throw '固定 revision checkout 失敗' }
$head = & git -C $repo rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $head.Trim() -ne $revision) { throw "upstream revision 驗證失敗：預期 $revision，實際 $($head.Trim())" }
if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) {
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'venv 建立失敗' }
    Assert-BackendRuntime -Executable $runtime -Context '新建 venv'
}
& $runtime -m pip install 'pip==26.2.1'
if ($LASTEXITCODE -ne 0) { throw 'pip 安裝失敗' }
$torchPackages = @('torch==2.7.1','torchaudio==2.7.1')
if ($Backend -eq 'xvc') { $torchPackages += 'torchvision==0.22.1' }
& $runtime -m pip install @torchPackages --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'CUDA Torch 安裝失敗' }
if ($Backend -eq 'meanvc2') {
    # Python 3.10 使用相容的 SciPy/Matplotlib；不變更模型或官方推論程式。
    $packages = @('numpy==1.26.4','einops==0.8.0','x-transformers==2.2.11','s3prl==0.4.18','soundfile==0.14.0','librosa==0.11.0','soxr==1.1.0','scipy==1.12.0','matplotlib==3.7.5','huggingface-hub==1.33.0','omegaconf==2.3.1','safetensors==0.8.0','gdown==6.4.0','sounddevice==0.5.6')
} else {
    # 只裝已驗證的 inference dependencies；不需 DeepSpeed、PESQ 或訓練環境。
    $packages = @('numpy==1.26.4','einops==0.8.0','x-transformers==1.40.2','hydra-core==1.3.2','julius==0.2.7','librosa==0.10.2','matplotlib==3.7.5','omegaconf==2.3.0','scipy==1.12.0','soundfile==0.12.1','soxr==0.3.7','tqdm==4.66.5','wandb==0.18.5','einx==0.3.0','transformers==4.44.1','torchmetrics==1.8.0','ema-pytorch==0.7.7','packaging==24.2','lightning==2.2.4','gdown==5.1.0','tensorboard==2.20.0','descript_audiotools==0.7.2','modelscope==1.40.1','huggingface-hub==0.36.2','hf-xet==1.6.0')
}
& $runtime -m pip install @packages
if ($LASTEXITCODE -ne 0) { throw '推論 dependencies 安裝失敗' }
& $runtime -m pip check
if ($LASTEXITCODE -ne 0) { throw 'dependencies 檢查失敗' }
& $runtime $downloadScript --backend $Backend
if ($LASTEXITCODE -ne 0) { throw '資產下載／完整性檢查失敗' }
Write-Output "PASS：$Backend 安裝／資產檢查。請依 docs/backend-install-test-latest.md 執行實際音訊推論。"
