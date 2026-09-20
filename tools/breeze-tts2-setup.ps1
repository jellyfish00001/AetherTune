[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu',
    [switch]$DownloadModel
)

$ErrorActionPreference = 'Stop'
$wslRoot = '/mnt/d/AetherTune'
$wslPython = "$wslRoot/tools/venvs/breeze-tts-wsl/bin/python"

function Invoke-Wsl([string]$Command) {
    & wsl.exe -d $Distro -- bash -lc $Command
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed with exit=$LASTEXITCODE"
    }
}

Write-Output "Breeze TTS 2 WSL distro: $Distro"
Invoke-Wsl "set -e; test -d '$wslRoot'; cd '$wslRoot/tools/external'; if [ ! -d breeze-tts/.git ]; then git clone https://github.com/breezeblue-ai/breeze-tts.git breeze-tts; fi; test -f breeze-tts/infer.py"
Invoke-Wsl "set -e; uv python install 3.10; if [ ! -x '$wslPython' ]; then uv venv --python 3.10 '$wslRoot/tools/venvs/breeze-tts-wsl'; fi; cd '$wslRoot/tools/external/breeze-tts'; uv pip install --python '$wslPython' -r requirements.txt --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu128"

if ($DownloadModel) {
    Invoke-Wsl "set -e; mkdir -p '$wslRoot/models/speech-reconstruction/breeze-tts-2'; '$wslPython' -c `"from huggingface_hub import snapshot_download; snapshot_download(repo_id='BreezeBlue/Breeze-TTS-2', local_dir='$wslRoot/models/speech-reconstruction/breeze-tts-2')`""
}

Write-Output 'Breeze TTS 2 setup finished in the dedicated WSL venv.'
Write-Output 'Model license: BreezeBlue Research and Non-Commercial; see models/speech-reconstruction/breeze-tts-2/README.md.'
Write-Output 'Run tools/breeze-tts2-infer.py through the command documented in docs/breeze-tts2-verification-latest.md.'
