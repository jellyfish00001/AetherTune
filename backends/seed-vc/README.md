# Seed-VC／Zero-Shot VC

Seed-VC 是不需先訓練角色模型的 voice conversion 路線：來源音檔提供內容與表現，參考音檔提供目標聲線。官方同時提供離線 VC 與即時 GUI；本專案已完成 `offline-v1` 男／女雙向與 60 秒長音檔推論，以及 `realtime-tiny` headless GPU streaming benchmark。實際麥克風／PortAudio 端到端仍需另外驗證。

## 輸入契約

- `source`：要保留內容的來源語音。
- `target`：1–30 秒、乾淨、單一說話者的參考語音。
- 建議先用 `dataset/reference-voices/` 的男聲與女聲各跑一次。
- 輸出必須記錄 source/target hash、checkpoint、設定、裝置與輸出 hash。

## 模型選擇

| profile | 官方模型 | 用途 | 大小／限制 |
|---|---|---|---|
| `realtime-tiny` | `Plachta/Seed-VC` 的 `DiT_uvit_tat_xlsr_ema.pth` | 即時 VC | 約 142 MB；官方 README 的 real-time 路線 |
| `offline-v1` | `seed-uvit-whisper-small-wavenet` | 離線 VC | 約 440 MB checkpoint；品質優先 |
| `v2` | `hubert-bsqvae-small` | accent／speaker disentanglement | 需同時下載 CFM/AR 資產，延後處理 |

## 使用

`tools/seed-vc-setup.ps1` 會建立獨立的 `tools/venvs/seed-vc`；`tools/seed-vc-run.ps1` 執行 `offline-v1` profile：檢查第三方 repo、checkpoint、輸入檔與輸出資料夾，再呼叫官方 `inference.py`。每次成功執行會寫出 `seed-vc-run.json`，記錄來源／目標／checkpoint／設定／Torch runtime／輸出 SHA-256 與 inference log。它不會自動覆蓋輸入，也不會把輸出誤登記成 ready model。`realtime-tiny` 要用官方 `real-time-gui.py`，不能把 tiny checkpoint 硬塞進 offline config。

```powershell
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-male-m1.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\male-to-female `
  -Fp16
```

### 測試 realtime-tiny 與 60 秒長音檔

`realtime-tiny` 測試會載入官方 real-time model，使用 3 個 0.3 秒 streaming block；它是 headless benchmark，不會開麥克風，也不會改動 Windows 音訊裝置：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-realtime-tiny-test.py `
  --source .\dataset\reference-voices\voice-male-m1.wav `
  --target .\dataset\reference-voices\voice-female-f1.wav `
  --blocks 3 --fp16 `
  --output-dir .\artifacts\seed-vc\realtime-tiny
```

長音檔可先產生 60 秒 source，再用一般 offline runner：

```powershell
$ff = 'C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe'
New-Item -ItemType Directory -Force .\artifacts\seed-vc\long | Out-Null
& $ff -hide_banner -loglevel error -y -stream_loop -1 `
  -i (Resolve-Path .\dataset\reference-voices\voice-male-m1.wav).Path `
  -t 60 -ar 48000 -ac 1 .\artifacts\seed-vc\long\source-60s.wav
& .\tools\seed-vc-run.ps1 `
  -Source .\artifacts\seed-vc\long\source-60s.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\long\male-to-female -Fp16
```

## 本機驗證結果

截至 2026-09-21，`offline-v1` 已在 RTX 5060 Ti 上以 Torch `2.7.1+cu128` 完成兩個方向與 60 秒長音檔的實際推論；`realtime-tiny` 完成 headless streaming benchmark：

- 男聲 → 女聲：RTF `0.3383`，結果與 manifest 位於 `artifacts/seed-vc/male-to-female/`。
- 女聲 → 男聲：RTF `0.3997`，結果與 manifest 位於 `artifacts/seed-vc/female-to-male/`。
- 60 秒男聲 → 女聲：RTF `0.3165`，結果與 manifest 位於 `artifacts/seed-vc/long/male-to-female/`。
- realtime-tiny：3 個 block 均產生 finite／non-zero output；warmup 後 p50 `190.6 ms`、steady-state RTF 約 `0.633`。

這代表「可以執行並產生 WAV」與「headless GPU streaming 可跑」已通過；聲音相似度、自然度、PortAudio 麥克風端到端、長時間 realtime 穩定性仍需人工聽測及獨立驗收。所有測試都留下上游 warning：`sampling_rate` 建議明確傳入，以及部分 estimator keys 因 shape mismatch 被略過；目前不影響產檔，但列為後續清理項目。完整紀錄見 [`docs/seed-vc-verification-latest.md`](../../docs/seed-vc-verification-latest.md)。

官方 repo：<https://github.com/Plachtaa/seed-vc>

模型與 license 以官方 Hugging Face model card 為準；Seed-VC code/model page 目前標示 GPL-3.0，使用前仍需核對上游條款與輸入聲音授權。
