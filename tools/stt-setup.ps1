[CmdletBinding()]
param([string]$Distro = 'Ubuntu')

$ErrorActionPreference = 'Stop'
$wslRoot = '/mnt/d/AetherTune'
$wslPython = "$wslRoot/tools/venvs/stt-wsl/bin/python"
& wsl.exe -d $Distro -- bash -lc "set -e; uv python install 3.10; if [ ! -x '$wslPython' ]; then uv venv --python 3.10 '$wslRoot/tools/venvs/stt-wsl'; fi; uv pip install --python '$wslPython' faster-whisper --index-url https://pypi.org/simple"
if ($LASTEXITCODE -ne 0) { throw "STT setup failed with exit=$LASTEXITCODE" }
Write-Output 'Faster-Whisper STT setup finished in tools/venvs/stt-wsl.'
