# GSV 含英文暖機驗證：bench（有/無英文暖機，各 3 次）＋虛擬麥端到端（有/無英文暖機）
$exp='D:\AetherTune-exp'; $h="$exp\wt-live-tts\tools\live-tts-bench"; $env:HF_HUB_OFFLINE='1'; $env:PYTHONIOENCODING='utf-8'
$L="$exp\logs\live-tts\enwarm"; mkdir $L -Force | Out-Null; $O="$exp\artifacts\live-tts-bench\gsv-mixed"; $VM="$exp\artifacts\live-tts-bench\vmic"
$ref="$exp\dataset\reference-voices\rvc-sage-zh.wav"; $py="$exp\tts-venvs\gsv-tts-lite\Scripts\python.exe"
function Disk { ((Get-Counter '\PhysicalDisk(_Total)\% Disk Time','\PhysicalDisk(_Total)\Disk Bytes/sec' -EA 0).CounterSamples | % { [math]::Round($_.CookedValue,1) }) -join '/' }
function Run($tag, [string[]]$argv, $timeoutSec) {
  $argv = $argv | % { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }  # Start-Process 會把含空白的參數拆開
  "=== $tag start $(Get-Date -Format HH:mm:ss) disk=$(Disk)"
  $p = Start-Process $py -ArgumentList $argv -RedirectStandardOutput "$L\$tag.out" -RedirectStandardError "$L\$tag.err" -NoNewWindow -PassThru
  if (-not $p.WaitForExit($timeoutSec * 1000)) { Stop-Process -Id $p.Id -Force; "TIMEOUT $tag" }
  Get-Content "$L\$tag.out" -Encoding utf8 | Select-String -Pattern '^(s4|m1|m2|RESULT|GSV_WARMUP)' | % Line
  "=== $tag end $(Get-Date -Format HH:mm:ss)"
}
nvidia-smi | Out-File "$L\nvsmi-start.txt" -Encoding utf8
$env:LIVE_TTS_SENTENCES="$h\mixed_zh_en_20261120.json"; $env:LIVE_TTS_RUNS='3'
$b=@('-u',"$h\bench_gsv_tts_lite.py",'--model-dir',"$exp\tts-models\gsv-tts-lite",'--ref-src',$ref,'--ref-set','rvc-sage','--out-dir',$O,'--zh-fix')
Run 'bench-enwarm' $b 240
Run 'bench-noenwarm' ($b + @('--no-en-warmup')) 240
Remove-Item Env:LIVE_TTS_SENTENCES, Env:LIVE_TTS_RUNS
$vargs=@('-u',"$h\live_tts_to_vmic.py",'--device','CABLE Input','--loopback','CABLE Output','--ref',$ref,'--text-file',"$exp\logs\live-tts\vmic-lines-mixed.txt")
Run 'vmic-enwarm' ($vargs + @('--log',"$VM\latency-log-mixed-enwarm.jsonl")) 180
Run 'vmic-noenwarm' ($vargs + @('--no-en-warmup','--log',"$VM\latency-log-mixed-noenwarm.jsonl")) 180
nvidia-smi | Out-File "$L\nvsmi-end.txt" -Encoding utf8
"=== END $(Get-Date -Format HH:mm:ss)"