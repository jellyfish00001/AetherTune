[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu',
    [string]$Output = '.\artifacts\cosyvoice-frontend\cudnn8-gpu.json',
    [string]$ProbeRoot = '/mnt/d/AetherTune/artifacts/cosyvoice-frontend/cudnn8-probe'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

function Convert-ToWslPath([string]$Path) {
    $resolved = if (Test-Path -LiteralPath $Path) {
        (Resolve-Path -LiteralPath $Path).Path
    } else {
        $parent = Split-Path -Parent $Path
        if (-not $parent) { $parent = '.' }
        Join-Path (Resolve-Path -LiteralPath $parent).Path (Split-Path -Leaf $Path)
    }
    return '/mnt/' + $resolved.Substring(0, 1).ToLowerInvariant() + ($resolved.Substring(2) -replace '\\', '/')
}

$outputPath = Convert-ToWslPath $Output
$modelPath = '/mnt/d/AetherTune/models/speech-reconstruction/cosyvoice/speech_tokenizer_v2.onnx'
$projectCudaRoot = '/mnt/d/AetherTune/tools/venvs/cosyvoice-wsl/lib/python3.10/site-packages/nvidia'
$probeCudaRoot = "$ProbeRoot/lib/python3.10/site-packages/nvidia"
$cudnnPath = "$ProbeRoot/lib/python3.10/site-packages/nvidia/cudnn/lib"
$cudaLibs = @(
    # cuDNN 8 probe venv also contains the matching cuBLAS/cuBLASLt pair;
    # keeping it first avoids mixing an incompatible project CUDA wheel.
    "$probeCudaRoot/cublas/lib",
    "$probeCudaRoot/cuda_nvrtc/lib",
    "$projectCudaRoot/cuda_runtime/lib",
    "$projectCudaRoot/cufft/lib",
    "$projectCudaRoot/curand/lib",
    "$projectCudaRoot/cusolver/lib",
    "$projectCudaRoot/cusparse/lib",
    "$projectCudaRoot/nvjitlink/lib"
)
# Wrap the first scalar as an array; scalar + array in PowerShell otherwise
# concatenates the first item without a separator and emits the rest as spaces.
$libraryPath = (@($cudnnPath) + $cudaLibs) -join ':'
$bash = @'
set -e
if [ ! -f '__CUDNN_PATH__/libcudnn.so.8' ]; then
  echo "缺少隔離 cuDNN8：__CUDNN_PATH__/libcudnn.so.8；請先建立 __PROBE_ROOT__" >&2
  exit 2
fi
export LD_LIBRARY_PATH='__LIBRARY_PATH__'
export PYTHONPATH='/mnt/d/AetherTune/tools/external/CosyVoice:/mnt/d/AetherTune/tools/external/CosyVoice/third_party/Matcha-TTS'
'/mnt/d/AetherTune/tools/venvs/cosyvoice-wsl/bin/python' '/mnt/d/AetherTune/tools/cosyvoice-frontend-probe.py' \
  --model '__MODEL_PATH__' \
  --output '__OUTPUT_PATH__'
'@
$bash = $bash.Replace('__PROBE_ROOT__', $ProbeRoot).Replace('__CUDNN_PATH__', $cudnnPath).Replace('__LIBRARY_PATH__', $libraryPath).Replace('__MODEL_PATH__', $modelPath).Replace('__OUTPUT_PATH__', $outputPath)

& wsl.exe -d $Distro -- bash -lc $bash
if ($LASTEXITCODE -ne 0) {
    throw "CosyVoice cuDNN8 frontend probe failed with exit=$LASTEXITCODE"
}
