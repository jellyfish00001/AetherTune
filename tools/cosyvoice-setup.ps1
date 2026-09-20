[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu',
    [switch]$DownloadModel
)

$ErrorActionPreference = 'Stop'
$wslRoot = '/mnt/d/AetherTune'
$wslPython = "$wslRoot/tools/venvs/cosyvoice-wsl/bin/python"

function Invoke-Wsl([string]$Command) {
    & wsl.exe -d $Distro -- bash -lc $Command
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed with exit=${LASTEXITCODE}: $Command"
    }
}

Write-Output "CosyVoice WSL distro: $Distro"
Invoke-Wsl "set -e; test -d '$wslRoot'; cd '$wslRoot/tools/external'; if [ ! -d CosyVoice/.git ]; then git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git CosyVoice; else cd CosyVoice; git submodule update --init --recursive; fi"
Invoke-Wsl "set -e; uv python install 3.10; if [ ! -x '$wslPython' ]; then uv venv --python 3.10 '$wslRoot/tools/venvs/cosyvoice-wsl'; fi; uv pip install --python '$wslPython' 'setuptools<81' 'numpy==1.26.4' cython"
Invoke-Wsl "set -e; cd '$wslRoot/tools/external/CosyVoice'; uv pip install --no-build-isolation --index-strategy unsafe-best-match --python '$wslPython' -r requirements.txt -i https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu128; uv pip install --index-strategy unsafe-best-match --python '$wslPython' --index-url https://download.pytorch.org/whl/cu128 torch==2.7.1+cu128 torchaudio==2.7.1+cu128 torchvision==0.22.1+cu128"

if ($DownloadModel) {
    $downloadCommand = "set -e; '$wslPython' -c `"from huggingface_hub import snapshot_download; snapshot_download(repo_id='FunAudioLLM/CosyVoice2-0.5B', local_dir='$wslRoot/models/speech-reconstruction/cosyvoice')`""
    Invoke-Wsl $downloadCommand
}

Write-Output "CosyVoice environment/model setup finished. Run docs/cosyvoice-verification-latest.md checks before calling it usable."
