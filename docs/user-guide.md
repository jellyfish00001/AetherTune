# AetherTune 人類操作手冊

這份文件回答兩件事：我該選哪一種方法，以及選好後要放什麼檔案、執行什麼命令。若只想快速開始，先讀根目錄 `README.md`；若要理解訓練與模型登錄，再讀 [`model-training-guide.md`](model-training-guide.md)。

## 1. 先選路線

### Seed-VC／Zero-Shot VC

選 Seed-VC 的情況：

- 不想先訓練角色模型。
- 想用一段 source 聲音快速試男聲或女聲 reference。
- 可以接受先產生 WAV，而不是直接接入即時通話。

Seed-VC 會由 source 保留內容與表現，reference 提供目標聲線。它不是把 `.pth/.index` 放入 RVC，也不需要建立訓練資料集。

目前 Streaming VC 的日常手動比較基線是 Seed-VC；一般 GUI 啟動、真實 mic 到最終 route 的完整驗收仍有 `WAITING` gate。MeanVC2 是下一個 priority candidate，尚未安裝或在本機驗證。

### RVC + FCPE/RMVPE（historical/degraded）

只有在需要保留既有訓練角色模型、做離線對照或維護舊 VCClient 路徑時才選 RVC。它需要乾聲資料與角色訓練；目前 VCClient 即時鏈路被標為 `historical-baseline / degraded`，不得當成已驗收或推薦的日常 LIVE 路線。新即時比較先以 Seed-VC baseline 建立基準，再按計畫 intake MeanVC2。

### STT → TTS

選 STT → TTS 的情況：

- 想先把聲音辨識成文字，再用另一個聲線重新說出來。
- 想改寫文字、跨語言、控制情緒、速度或語氣。
- 可以接受原始笑聲、呼吸、停頓與節奏被重新生成。

CosyVoice 與 Breeze TTS 2 是這條路線的不同 TTS backend，不是 RVC 模型。voice clone 需要 reference audio 與正確的 reference transcript。

## 2. 第一次檢查

```powershell
Set-Location D:\AetherTune
& .\tools\voice-backend-check.ps1
```

這個命令只檢查檔案與環境存在。它不代表：模型品質通過、聲音相似度通過、即時鏈路通過或 Discord/OBS 已成功收音。

## 3. 使用 Seed-VC

若尚未建立獨立環境，先執行一次：

```powershell
& .\tools\seed-vc-setup.ps1 -PreflightOnly
& .\tools\seed-vc-setup.ps1
```

Preflight 會一次列出 Python 3.10、固定 upstream revision、Tcl/Tk、checkpoint、HF snapshot 檔案與 ModelScope VAD 的缺項，通過前不會執行 pip。此流程不會 clone repo 或下載權重；找不到 Python 時以 `-Python310 <python.exe>` 明確指定。模型資產需先按專案 source/license 流程取得。

### 輸入規則

- `-Source`：保留內容的來源 WAV。
- `-Target`：目標聲線 reference，建議 1–30 秒、乾淨、單一說話者。
- reference voice 目前放在 `dataset/reference-voices/`。
- 輸出與輸入不會互相覆蓋。

### 男聲轉女聲

```powershell
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-male-m1.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\male-to-female `
  -Fp16
```

### 女聲轉男聲

```powershell
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-female-f1.wav `
  -Target .\dataset\reference-voices\voice-male-m1.wav `
  -OutputDir .\artifacts\seed-vc\female-to-male `
  -Fp16
```

成功後查看：

- `artifacts/seed-vc/<run>/vc_*.wav`：音訊結果。
- `artifacts/seed-vc/<run>/seed-vc-run.json`：輸入、checkpoint、Torch runtime、輸出 hash 與 warning。
- `backends/seed-vc/README.md` 與 `docs/agent-implementation-status-latest.md`：Seed-VC 輸入契約與目前實際驗證摘要。

目前已驗證 `offline-v1` 雙向 WAV、60 秒長音檔、`realtime-tiny` headless GPU block，以及官方 GUI callback user-flow 的四組 reference 輸出；但實體 mic E2E、audio-rack paired bypass/full-chain、人工聽測與 600 秒 realtime 穩定性仍待補。

### 一般使用者：手動即時 GUI

`tools/seed-vc-gui-run.ps1` 啟動官方 realtime-tiny GUI，使用本機 Hifi-GAN profile、FP32 與 CUDA device 0。先唯讀檢查，再啟動：

```powershell
pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly
pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 `
  -InputDeviceName '麥克風 (HyperX QuadCast S)' `
  -OutputDeviceName 'CABLE Input (VB-Audio Virtual Cable)' `
  -HostApi 'Windows DirectSound' `
  -ReferenceWav .\dataset\reference-voices\voice-female-f1.wav
```

上述裝置名稱是目前這台主機 PortAudio inventory 的完整字串；在其他電腦請替換成 launcher preflight 顯示的完整名稱與對應 Host API。此 Host API 下該 CABLE output 唯一匹配 1 個 endpoint；launcher 會在啟動前重新驗證。

GUI launcher 要由 PowerShell 7.0 以上（`pwsh`）執行。預設會使用 setup 建立且含 Seed-VC GUI dependencies 的 `tools\venvs\seed-vc\Scripts\python.exe`；若改用自訂 venv，傳入 `-Python <venv\Scripts\python.exe>`。`-Python310 <base python.exe>` 僅供 `seed-vc-setup.ps1` 建立 venv 時選 Python 3.10，不能傳給 GUI launcher，也不能拿未安裝 Seed-VC dependencies 的 base Python 取代 venv。

`-InputDeviceName`、`-OutputDeviceName`、`-HostApi` 與 `-ReferenceWav` 都可省略；省略時沿用 launcher 的 isolated session 設定或唯一的 Windows default endpoint。名稱以 preflight 列出的 PortAudio 裝置為準，必須能唯一解析；裝置缺失、重名、方向不符或 input/output Host API 不一致時會停止。Launcher 不更改 Windows default endpoint、不注入測試 WAV、不開啟 stream，也不下載模型。

設定副本、隔離的 HF cache lock 和 ModelScope cache root 位於 ignored `artifacts/seed-vc/gui-session/`；HF 模型目錄只連結到已驗證的本機 snapshot，VAD 以程序內 local-path mapping 讀取已驗證的本機 snapshot。官方 GUI 儲存的裝置／reference 偏好因此落在隔離資料夾，不寫入 third-party repo、使用者 profile 或原 cache。啟動後再次核對畫面上的 reference、input、output、Host API 和 CUDA device 0，再按 `Start VC`；通話結束按 `Stop VC`，關閉視窗。若輸出到 `CABLE Input`，仍要另驗證 `CABLE Output → audio-rack → Voicemeeter B1 → Discord/OBS`。

### 工具測試：deterministic callback harness

正式啟動 GUI user-flow 前，先做不改裝置、不開 stream 的唯讀 preflight：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-gui-userflow-test.py --preflight
```

回傳 `0/PASS` 才表示檔案、預期 MME 裝置與 `FreeSimpleGUI` import 都通過；回傳 `3/WAITING` 表示環境仍被 GUI 依賴阻塞，回傳 `2/BLOCKED` 表示必要資源或裝置缺失。這項檢查不會建立音訊 artifact，也不等於完整 mic → Seed-VC → virtual route 的 LIVE evidence。

preflight 通過後執行官方 GUI callback user-flow：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-gui-userflow-test.py `
  --output .\artifacts\seed-vc\gui-userflow\<run-id>
```

Harness 以 deterministic WAV 注入 callback，輸出可同步錄到 VB-CABLE；輸入不是實體麥克風內容。既有 2026-09-26 report `artifacts/seed-vc/gui-userflow/20260926-after-tcl-repair/gui-userflow-report.json` 的 synthetic route/settings PASS 不能證明實體 mic、full-chain 或 `LIVE <= 5s`。每次 harness 測試要使用新的 `<run-id>` 目錄，避免 artifact 混淆。

## 4. 使用 RVC

### RVC 的基本順序

```text
乾聲資料 → audit → 切片／保留測試集 → RVC 訓練
→ .pth + .index → model-register.csv → 離線聽測
```

先讀 [`model-training-guide.md`](model-training-guide.md) 準備資料與模型。舊 VCClient → VST → virtual route 僅供 historical/degraded 對照，REST probe 與 GPU 推論仍未驗收；日常 Streaming VC 路線以 Seed-VC baseline 為先，MeanVC2 保持 `PLANNED`。

### 目前模型為什麼不能直接視為 ready

目前 `models/weights/` 與 `models/indexes/` 有四組配對，已先以已驗證檔案與 hash 登錄為 `candidate`。因此還缺：

- 模型來源與授權。
- `.pth`／`.index` 各自 SHA-256。
- f0 method、revision、dataset batch；四個 checkpoint 的 sample rate 與 v2 version 已從內嵌欄位核對，但仍需補 provenance。
- 未參與訓練的測試句與人工聽測。
- VCClient 真實模型載入與延遲證據。

`f0`、`dataset_batch_id`、`rvc_revision`、來源、授權與 verification artifact 仍以 `unknown` 明確標記，必須補齊後才能考慮 `ready`；checkpoint 內嵌的 `sample_rate` 與 `version=v2` 已核對並登記。

不要只因 VCClient Web UI 能開啟或模型檔存在，就跳過這些步驟。

### FCPE 與 RMVPE 怎麼用

- 專案 runtime 策略：FCPE 首選、RMVPE 備用。
- 若訓練用的上游 RVC WebUI 沒有 FCPE 選項，使用 RMVPE 完成該次訓練並在 register 記錄真實值。
- 執行 `tools/fcpe_probe.py` 時查看 artifact 的實際 device、provider、時間與輸出誤差。
- 不要把 `available_providers` 當成實際執行 provider。

## 5. 使用 STT → TTS

這條路線已可用 `tools/speech-reconstruction-run.ps1` 一鍵串接；若要可追溯與正式 clone，仍建議分階段核對：

1. 先對 source WAV 做 STT。
2. 人工核對 transcript，特別是 reference audio 的 prompt text；確認後以 `-ReferenceTextFile` 搭配 `-ReferenceTextVerified` 執行 wrapper。
3. 將文字與 reference audio 送入 CosyVoice 或 Breeze。
4. 保存 STT model/revision、transcript、reference hash、TTS model、輸出 hash 與 RTF。

Faster-Whisper STT、CosyVoice2 與 Breeze TTS 2 都已在獨立 WSL2 環境完成安裝與實際 WAV 測試。快速使用 `tools/speech-reconstruction-run.ps1`；單獨驗證則使用 [`cosyvoice-verification-latest.md`](cosyvoice-verification-latest.md)、[`breeze-tts2-verification-latest.md`](breeze-tts2-verification-latest.md) 與 `tools/breeze-tts2-run.ps1`。

詳細狀態：[`backends/speech-reconstruction/README.md`](../backends/speech-reconstruction/README.md)、[`docs/cosyvoice-verification-latest.md`](cosyvoice-verification-latest.md)、[`docs/breeze-tts2-verification-latest.md`](breeze-tts2-verification-latest.md)。

## 6. 常用檔案位置

| 內容 | 位置 |
|---|---|
| RVC 乾聲 | `dataset/raw/` |
| RVC 切片 | `dataset/sliced/` |
| 男／女 reference | `dataset/reference-voices/` |
| RVC weights | `models/weights/` |
| RVC indexes | `models/indexes/` |
| RVC register | `models/model-register.csv` |
| 多後端 register | `models/backend-register.csv` |
| Seed-VC checkpoint | `models/seed-vc/checkpoints/` |
| CosyVoice/Breeze 模型 | `models/speech-reconstruction/` |
| 可重跑腳本 | `tools/` |
| 最新驗證 | `docs/*verification-latest.md` |

## 7. 狀態判讀

- `PASS`：指定檢查或實際流程已通過。
- `WAITING`：有明確缺口、阻塞或尚未完成驗收。
- `PLANNED`：尚未開始或仍需選擇方案。
- `candidate`：可拿來測試，但尚未完成品質、授權或穩定性驗收。
- `ready`：只有在 register、runtime、輸出與人工驗收都完成後才能使用。
