# Seed-VC／Zero-Shot VC

**文件邊界：**本頁負責 Seed-VC upstream profile、資產要求、離線與官方 GUI 的啟動命令；本機音訊結果由[Seed 驗證](../../docs/seed-vc-verification-latest.md)和[後端安裝測試](../../docs/backend-install-test-latest.md)負責。Seed-VC 是不需先訓練角色模型的 voice conversion 路線：來源音檔提供內容與表現，參考音檔提供目標聲線。原始 [Plachtaa/seed-vc](https://github.com/Plachtaa/seed-vc) 已於 2025-11-21 archived；另有[獨立 realtime fork 候選](../seed-vc-realtime/README.md)。

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

## 即時 GUI

Windows realtime-tiny 走官方 `real-time-gui.py`，不使用 offline inference config。先讀 [`docs/seed-vc-assets.md`](../../docs/seed-vc-assets.md)，檢查 source／checkpoint／config／encoder／vocoder／VAD cache，再用本文件下方的 GUI `-PreflightOnly` 列舉裝置並以 `tools/seed-vc-gui-run.ps1` 啟動。Launcher 使用 FP32／CUDA device 0，預設 offline mode 並要求唯一裝置名稱，不改 Windows 預設 audio endpoints，也不注入 WAV。`tools/seed-vc-live-capture.py` 可另行錄製 mic、CABLE Output 與 Voicemeeter B1 的實際 PCM／callback evidence；onset estimate 不能代替完整 LIVE_GATE。

## 離線使用

`tools/seed-vc-setup.ps1` 先做唯讀 preflight，再建立獨立的 `tools/venvs/seed-vc`；manifest gate 的支援範圍是 `realtime-tiny` GUI，不能推論 `offline-v1` 所需 config／Whisper／BigVGAN 資產也齊全。缺少 realtime 前置時會先列缺項，不執行 pip；setup 不 clone source 或下載權重。Python 3.10 base interpreter 可由 `pyvenv.cfg`／本機安裝探索，也可只對 setup 傳 `-Python310 <base-python.exe>`。`tools/seed-vc-run.ps1` 另檢查 offline route 的 repo、checkpoint、輸入與輸出，再呼叫官方 `inference.py`；它以新 WAV 或新 hash 通過 stale-output gate，經 `audio_output_validation.py` 驗證後才寫本輪 manifest。`realtime-tiny` GUI 需搭配官方 XLS-R/Hifi-GAN preset，不能把 tiny checkpoint 塞進 offline config。當次 setup／asset completeness 看[Seed readiness](../../docs/seed-vc-readiness-latest.md)。

```powershell
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-male-m1.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\male-to-female `
  -Fp16
```

### 一般使用者手動即時 GUI

先檢查，再啟動官方 GUI（不是 callback 測試 harness）：

```powershell
pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly
pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 `
  -InputDeviceName 'PortAudio 顯示的完整 input 名稱' `
  -OutputDeviceName 'PortAudio 顯示的完整 output 名稱' `
  -ReferenceWav .\dataset\reference-voices\voice-female-f1.wav
```

GUI launcher 要求 PowerShell 7.2 以上（`pwsh`，提供 .NET 6 junction resolution API），預設使用 setup 建立的 `tools\venvs\seed-vc\Scripts\python.exe`。若改用自訂 GUI venv，傳 `-Python <venv\Scripts\python.exe>`；不要把 setup 的 `-Python310` base interpreter 當作 GUI venv。

裝置和 reference 參數可省略；新 session 使用唯一的 Windows default endpoints，後續沿用 `artifacts/seed-vc/gui-session/configs/inuse/config.json`。名稱解析必須唯一且 input/output 共用 Host API；`-HostApi` 可消除同名歧義。launcher 依 `tools/seed-vc-assets.json` 驗證 `realtime-tiny` checkpoint、realtime GUI 所需 HF snapshots 與 ModelScope VAD 的 revision、exact size 及 SHA-256，並使用 realtime-tiny checkpoint、XLS-R/Hifi-GAN config、FP32、CUDA 0 與 HF offline cache。缺少必需 snapshot/model file 或 hash 不符時會停止，不隱性下載。此 gate 不涵蓋 offline-v1 helper completeness，也不是 clean-machine bootstrap 證明；資產來源與待查 license 看[Seed assets](../../docs/seed-vc-assets.md)及[來源審核](../../docs/source-audit.md)。

官方 GUI 會把日常裝置和 reference 設定存到 ignored 的 `artifacts/seed-vc/gui-session/` overlay；上游 repo、user profile、Windows default audio devices 和原始 cache 不會被 launcher 改寫。GUI 啟動時不開 stream；先檢查畫面上的 source/reference、input/output endpoint，再由使用者按 `Start VC`。停止時按 `Stop VC`，再關閉 GUI。輸出選 CABLE Input 後，完整 route 還要另做真實 mic／audio-rack／B1 驗收。

### 測試 realtime-tiny 與 60 秒長音檔

`realtime-tiny` 測試會載入官方 real-time model，使用 3 個 0.3 秒 streaming block；它是 headless benchmark，不會開麥克風，也不會改動 Windows 音訊裝置：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-realtime-tiny-test.py `
  --source .\dataset\reference-voices\voice-male-m1.wav `
  --target .\dataset\reference-voices\voice-female-f1.wav `
  --blocks 3 --fp16 `
  --output-dir .\artifacts\seed-vc\realtime-tiny
```

使用本機 cache 做 60 秒連續 headless streaming：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-realtime-tiny-test.py `
  --source .\artifacts\seed-vc\long\source-60s.wav `
  --target .\dataset\reference-voices\voice-female-f1.wav `
  --blocks 200 --block-time 0.30 --diffusion-steps 10 --fp16 `
  --output-dir .\artifacts\seed-vc\realtime-long-60s
```

上述 `seed-vc-realtime-tiny-test.py` 與 `seed-vc-gui-userflow-test.py` 是 synthetic/headless 工具測試；deterministic WAV callback、440 Hz synthetic route 或 GUI widget PASS 都不是使用者真實 mic E2E。當次 GUI case 的輸入與結果看[Seed 驗證](../../docs/seed-vc-verification-latest.md)。

測試預設 `local-first` 且設定 Hugging Face offline mode；若本機 cache 不完整，才明確加上 `--allow-network-assets`。

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

## 本機結果要讀哪裡

離線 WAV／file-driven streaming 的本機證據看[後端安裝測試](../../docs/backend-install-test-latest.md)；GUI callback、CABLE loopback、實體麥克風與未解缺口看[Seed 驗證](../../docs/seed-vc-verification-latest.md)。當次 artifact 和 verifier 優先於摘要；不要由 profile 名稱、模型檔或 GUI 啟動推論 `LIVE`。

官方 upstream：<https://github.com/Plachtaa/seed-vc>（archived/read-only）

模型與 license 以官方 upstream／Hugging Face model card 為準；目前 upstream code page 標示 GPL-3.0，使用前仍需核對固定 revision、模型條款與輸入聲音授權。
