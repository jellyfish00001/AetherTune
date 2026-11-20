# PC1：依序跑 GSV-TTS-Lite → Qwen3-TTS → VoxCPM2，每個後端先用 Qwen 官方中文示範音，再用 JVNV f1。
param([string[]]$Backends = @('gsv', 'qwen3', 'voxcpm2'), [string[]]$RefSets = @('qwen-zh', 'f1'))
$ErrorActionPreference = 'Continue'
$exp = 'D:\AetherTune-exp'
$here = $PSScriptRoot
$env:HF_HUB_OFFLINE = '1'
$env:PYTHONIOENCODING = 'utf-8'
$src = @{ 'f1' = 'D:\AetherTune\dataset\reference-voices\voice-female-f1.wav'; 'qwen-zh' = "$exp\dataset\reference-voices\qwen3-tts-clone_1.wav" }
$cfg = @{
  'gsv'     = @{ py = "$exp\tts-venvs\gsv-tts-lite\Scripts\python.exe"; script = 'bench_gsv_tts_lite.py'; model = "$exp\tts-models\gsv-tts-lite"; out = 'gsv-tts-lite'; extra = @() }
  'qwen3'   = @{ py = "$exp\tts-venvs\qwen3-tts\Scripts\python.exe"; script = 'bench_qwen3_tts.py'; model = "$exp\tts-models\qwen3-tts-0.6b-base"; out = 'qwen3-tts'; extra = @() }
  'qwen3-1.7b' = @{ py = "$exp\tts-venvs\qwen3-tts\Scripts\python.exe"; script = 'bench_qwen3_tts.py'; model = "$exp\tts-models\qwen3-tts-1.7b-base"; out = 'qwen3-tts'; extra = @() }
  'voxcpm2' = @{ py = "$exp\tts-venvs\voxcpm2\Scripts\python.exe"; script = 'bench_voxcpm2.py'; model = "$exp\tts-models\voxcpm2"; out = 'voxcpm2'; extra = @() }
}
foreach ($b in $Backends) {
  foreach ($r in $RefSets) {
    $c = $cfg[$b]
    Write-Output "=== $b @ $r $(Get-Date -Format HH:mm:ss)"
    & $c.py -u (Join-Path $here $c.script) --model-dir $c.model --ref-src $src[$r] --ref-set $r --out-dir "$exp\artifacts\live-tts-bench\$($c.out)" @($c.extra) 2>&1 | ForEach-Object { "$_" }
    Write-Output "=== exit $LASTEXITCODE $(Get-Date -Format HH:mm:ss)"
  }
}
Write-Output 'ALLDONE'