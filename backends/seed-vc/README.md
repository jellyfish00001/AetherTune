# Seed-VC／Zero-Shot VC

Seed-VC 是不需先訓練角色模型的 voice conversion 路線：來源音檔提供內容與表現，參考音檔提供目標聲線。原始 [Plachtaa/seed-vc](https://github.com/Plachtaa/seed-vc) 已於 2025-11-21 archived，因此本目錄現在定位為 `established-baseline`，不是「最新 SOTA」。官方離線 VC 與即時 GUI 的本機 evidence 保留；實際麥克風／PortAudio → audio-rack → virtual route 端到端仍需另外驗證。另有候選 fork 見 [`backends/seed-vc-realtime/README.md`](../seed-vc-realtime/README.md)。

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

`tools/seed-vc-setup.ps1` 會先完成唯讀 preflight，再建立獨立的 `tools/venvs/seed-vc`；目前 manifest gate 的支援範圍是 `realtime-tiny` GUI。缺少 realtime prerequisites 時會先列完整缺項，不會執行 pip；setup 不 clone source 或下載權重。Python 3.10 base interpreter 可由 `pyvenv.cfg`／本機安裝探索，也可只對 setup 明確傳 `-Python310 <base-python.exe>`。此 setup PASS 不表示 `offline-v1` checkpoint/config/Whisper/BigVGAN helper assets 齊全；offline helper completeness 維持 `WAITING / out-of-scope`，雖然本機保有先前離線推論 evidence。若另行執行 `tools/seed-vc-run.ps1`，它會檢查 offline route 的第三方 repo、checkpoint、輸入檔與輸出資料夾，再呼叫官方 `inference.py`。每次執行會先記錄現有 WAV 路徑/hash；只有本次新增 WAV 或內容 hash 變更的輸出，經 `audio_output_validation.py` 確認後才會記為 PASS，manifest 會記錄 run id、來源／目標／checkpoint／Torch runtime、輸出 SHA-256 與 inference log。單純觸碰舊 WAV 時間不會通過 stale-output gate。它不會自動覆蓋輸入，也不會把輸出誤登記成 ready model。`realtime-tiny` GUI 需搭配官方 XLS-R/Hifi-GAN preset，不能把 tiny checkpoint 硬塞進 offline config。

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

裝置和 reference 參數可省略；新 session 使用唯一的 Windows default endpoints，後續沿用 `artifacts/seed-vc/gui-session/configs/inuse/config.json`。名稱解析必須唯一且 input/output 共用 Host API；`-HostApi` 可消除同名歧義。launcher 依 `tools/seed-vc-assets.json` 驗證 `realtime-tiny` checkpoint、realtime GUI 所需 HF snapshots 與 ModelScope VAD 的 revision、exact size 及 SHA-256，並使用 realtime-tiny checkpoint、XLS-R/Hifi-GAN config、FP32、CUDA 0 與 HF offline cache。offline-v1 checkpoint/preset/Whisper/BigVGAN helper completeness 不在此 gate 範圍，維持 `WAITING / out-of-scope`；先前 offline 推論記錄不改變此限制。HF/VAD 的觀測值只是本機 bytes 證據；FSMN-VAD 上游完整 revision/license 仍 `UNKNOWN/WAITING`，不是 clean-machine bootstrap 證明。缺少 realtime GUI 必需 snapshot/model file 或 hash 不符時會停止，不隱性下載。

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

上述 `seed-vc-realtime-tiny-test.py` 與 `seed-vc-gui-userflow-test.py` 是 synthetic/headless 工具測試；任何 deterministic WAV callback、440 Hz synthetic route 或 GUI widget PASS 都不是使用者真實 mic E2E。GUI user-flow 目前四案均使用 callback 注入 WAV，請勿當成人聲經麥克風的證據。

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

## 本機驗證結果

截至 2026-09-21，`offline-v1` 已在 RTX 5060 Ti 上以 Torch `2.7.1+cu128` 完成兩個方向與 60 秒長音檔的實際推論；`realtime-tiny` 完成 headless streaming benchmark：

- 男聲 → 女聲：RTF `0.3383`，結果與 manifest 位於 `artifacts/seed-vc/male-to-female/`。
- 女聲 → 男聲：RTF `0.3997`，結果與 manifest 位於 `artifacts/seed-vc/female-to-male/`。
- 60 秒男聲 → 女聲：RTF `0.3165`，結果與 manifest 位於 `artifacts/seed-vc/long/male-to-female/`。
- realtime-tiny：3 個 block 均產生 finite／non-zero output；warmup 後 p50 `190.6 ms`、steady-state RTF 約 `0.633`。
- realtime-tiny 60 秒連續：200 個 block 均產生 finite／non-zero output；p50 `122.0 ms`、p95 `146.6 ms`、mean RTF `0.4312`。

這代表「可以執行並產生 WAV」與「60 秒 headless GPU streaming 可跑」已通過；聲音相似度、自然度、PortAudio 麥克風端到端、官方 GUI 與 10 分鐘以上穩定性仍需獨立驗收。所有測試都留下上游 warning：`sampling_rate` 建議明確傳入，以及部分 estimator keys 因 shape mismatch 被略過；目前不影響產檔，但列為後續清理項目。完整紀錄見 [`docs/agent-implementation-status-latest.md`](../../docs/agent-implementation-status-latest.md) 與既有 artifacts。

官方 upstream：<https://github.com/Plachtaa/seed-vc>（archived/read-only）

模型與 license 以官方 upstream／Hugging Face model card 為準；目前 upstream code page 標示 GPL-3.0，使用前仍需核對固定 revision、模型條款與輸入聲音授權。
