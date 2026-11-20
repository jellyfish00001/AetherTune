# 聽感對照：三個引擎各把 listening_zh_20261120.json 六句生成一次（開頭暖機一句不存）。
$exp='D:\AetherTune-exp'; $h="$exp\wt-live-tts\tools\live-tts-bench"; $env:HF_HUB_OFFLINE='1'; $env:PYTHONIOENCODING='utf-8'
$env:LIVE_TTS_SENTENCES="$h\listening_zh_20261120.json"
$R="$exp\artifacts\listening\live-tts-zh-20261120\raw"; $L="$exp\logs\live-tts\listening"; mkdir $L -Force | Out-Null
$ref="$exp\dataset\reference-voices\rvc-sage-zh.wav"
function Disk { ((Get-Counter '\PhysicalDisk(_Total)\% Disk Time','\PhysicalDisk(_Total)\Disk Bytes/sec' -EA 0).CounterSamples | % { [math]::Round($_.CookedValue,1) }) -join '/' }
function Run($tag, $py, [string[]]$argv, $timeoutSec) {
  "=== $tag start $(Get-Date -Format HH:mm:ss) disk=$(Disk)"
  $p = Start-Process $py -ArgumentList $argv -RedirectStandardOutput "$L\$tag.out" -RedirectStandardError "$L\$tag.err" -NoNewWindow -PassThru
  if (-not $p.WaitForExit($timeoutSec * 1000)) { Stop-Process -Id $p.Id -Force; "TIMEOUT $tag" }
  Get-Content "$L\$tag.out" -Encoding utf8 | Select-String -Pattern '^(s\d|RESULT)' | % Line
  Get-Content "$L\$tag.err" | Select-String -Pattern 'Error' | Select-Object -Last 2 | % Line
  "=== $tag end $(Get-Date -Format HH:mm:ss)"
}
nvidia-smi | Out-File "$L\nvsmi-start.txt" -Encoding utf8
Run 'gsv' "$exp\tts-venvs\gsv-tts-lite\Scripts\python.exe" @('-u',"$h\bench_gsv_tts_lite.py",'--model-dir',"$exp\tts-models\gsv-tts-lite",'--ref-src',$ref,'--ref-set','rvc-sage','--out-dir',"$R\gsv-tts-lite",'--zh-fix') 300
Run 'voxcpm2' "$exp\tts-venvs\voxcpm2\Scripts\python.exe" @('-u',"$h\bench_voxcpm2.py",'--model-dir',"$exp\tts-models\voxcpm2",'--ref-src',$ref,'--ref-set','rvc-sage','--out-dir',"$R\voxcpm2",'--timesteps','6') 420
$src='D:\AetherTune\tools\external\CosyVoice'; $env:PYTHONPATH="$src;$src\third_party\Matcha-TTS"
Run 'cosyvoice2' "$exp\tts-venvs\cosyvoice2-win\Scripts\python.exe" @('-u',"$h\bench_cosyvoice2.py",'--model-dir',"$exp\tts-models\cosyvoice2",'--ref-src',"rvc-sage=$ref",'--out-dir',"$R\cosyvoice2",'--combos','rvc-sage:spk','--tag','win','--hop-fix','--jit','--trt','--fp16','--zhs') 420
Remove-Item Env:PYTHONPATH
nvidia-smi | Out-File "$L\nvsmi-end.txt" -Encoding utf8
"=== END $(Get-Date -Format HH:mm:ss)"