# PC1 Windows 原生跑 CosyVoice2（實驗 venv D:\AetherTune-exp\tts-venvs\cosyvoice2-win；原始碼唯讀引用 D:\AetherTune\tools\external\CosyVoice；
# 權重用 D:\AetherTune-exp\tts-models\cosyvoice2 的本機複本，JIT/TRT 產物只寫在複本）。
# 用法：pwsh -File run_cosyvoice2_win.ps1 [-Combos qwen-zh:spk] [-Extra "--fp16 --trt"]
param([string]$Combos = "qwen-zh:spk", [string]$Extra = "")
$src = 'D:\AetherTune\tools\external\CosyVoice'
$env:PYTHONPATH = "$src;$src\third_party\Matcha-TTS"
$env:HF_HUB_OFFLINE = '1'; $env:PYTHONIOENCODING = 'utf-8'
$py = 'D:\AetherTune-exp\tts-venvs\cosyvoice2-win\Scripts\python.exe'
$argv = @("-u", "$PSScriptRoot\bench_cosyvoice2.py", "--model-dir", "D:\AetherTune-exp\tts-models\cosyvoice2",
  "--ref-src", "qwen-zh=D:\AetherTune-exp\dataset\reference-voices\qwen3-tts-clone_1.wav",
  "--ref-src", "rvc-sage=D:\AetherTune-exp\dataset\reference-voices\rvc-sage-zh.wav",
  "--out-dir", "D:\AetherTune-exp\artifacts\live-tts-bench\cosyvoice2", "--combos", $Combos, "--tag", "win")
if ($Extra) { $argv += $Extra.Split(' ') }
& $py @argv
