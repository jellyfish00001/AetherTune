# AetherTune 人類操作手冊

這份文件回答兩件事：我該選哪一種方法，以及選好後要放什麼檔案、執行什麼命令。若只想快速開始，先讀根目錄 `README.md`；若要理解訓練與模型登錄，再讀 [`model-training-guide.md`](model-training-guide.md)。

## 1. 先選路線

### RVC + FCPE/RMVPE

選 RVC 的情況：

- 需要即時麥克風變聲。
- 要用於 Discord、遊戲或 OBS。
- 願意準備乾聲資料並訓練角色模型。
- 願意花時間測試 pitch、index、chunk 與音訊路由。

RVC 需要先有來源與授權完整的角色模型，並另外完成 VCClient／虛擬音訊／延遲驗收。目前 VCClient packaged role conversion 仍有 HTTP 500 與全零輸出阻塞；RVC 保留為 historical baseline，不能由離線 GPU 推論推論成即時 ready。若不打算訓練角色模型，Seed-VC 是目前較直接的 Streaming VC baseline。

### Seed-VC／Zero-Shot VC

選 Seed-VC 的情況：

- 不想先訓練角色模型。
- 想用授權 reference voice 做即時麥克風變聲或離線對照。
- 使用獨立 Python 3.10 環境，不與 RVC venv 混裝。

Seed-VC 會由 source 保留內容與表現，reference 提供目標聲線。它不是把 `.pth/.index` 放入 RVC，也不需要建立訓練資料集。

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

### 安裝與資產盤點

先閱讀 [`seed-vc-assets.md`](seed-vc-assets.md)。新 clone 不會包含 ignored third-party repo、模型權重或快取；setup 不會代為 clone、下載 checkpoint 或安裝到使用者的全域 Python。第一次執行先做唯讀 preflight：

```powershell
Set-Location D:\AetherTune
& .\tools\seed-vc-setup.ps1 -PreflightOnly
```

按輸出結果補齊 Python 3.10、固定 Seed-VC source、realtime-tiny checkpoint/config 和本機模型快取，再安裝獨立環境：

```powershell
& .\tools\seed-vc-setup.ps1
```

setup 會在任何 pip mutation 前印出資產狀態。缺 Python 3.10、upstream source 或 requirements 時以 `BLOCKED` 結束；缺 realtime model 時仍可建立 venv，但 GUI 會保持 `WAITING`。GUI launcher 預設離線，輔助模型快取缺失時會阻止 GUI 自行下載；主要 checkpoint 需由使用者先核對授權並手動放到清單指定位置。

### 選擇裝置與 reference，啟動官方 GUI

先唯讀列出 PortAudio 裝置，再依實際名稱啟動。輸入裝置和輸出裝置都必須在同一個 Host API 下唯一匹配；不使用 Windows 預設裝置作靜默 fallback：

```powershell
& .\tools\seed-vc-gui-run.ps1 -ListDevices
& .\tools\seed-vc-gui-run.ps1 `
  -HostApi 'Windows WASAPI' `
  -InputDevice '<PortAudio 顯示的實體麥克風名稱>' `
  -OutputDevice '<PortAudio 顯示的 CABLE Input 名稱>' `
  -Reference 'C:\Audio\authorized-reference.wav'
```

`-HostApi`、`-InputDevice`、`-OutputDevice` 和 `-Reference` 都可省略，但只有在 upstream GUI 的已保存設定能唯一核對且檔案仍存在時才沿用；第一次設定請明確傳入。reference path 必須是 GUI 可讀的音訊檔，並符合上游 GUI 的 ASCII 路徑限制。使用者也可以不傳 `-Reference`，在 GUI reference 欄位選取音檔。

啟動器會先檢查 CUDA device 0、checkpoint/config、XLS-R、CampPlus、HiFT、FunASR VAD 快取及裝置身份，並以 `--fp16 False --gpu 0` 啟動官方 GUI。一般 GUI 流程接收實體麥克風，不注入 WAV；它會保存裝置/reference 選擇到 ignored runtime config。未提供 `-AllowNetworkAssets` 時 Hugging Face／Transformers 設為 offline；該參數只允許缺少的輔助模型由 upstream loader 取得，主要 tiny checkpoint 仍不會自動下載。

### 路由、短測與 600 秒穩定性

- **先做 bypass**：Seed-VC GUI output 設為 `CABLE Input (VB-Audio Virtual Cable)`；`CABLE Output` 是給錄音程式讀取的另一端。
- **full-chain**：`CABLE Output` → Light Host Modern input → Graillon bypass 或 active → `Voicemeeter Input` → 開啟對應 strip 的 B bus → 下游使用 `Voicemeeter Out B1`。Discord/OBS 麥克風從該 app 設定選擇 B1。先用耳機，確認沒有 feedback。
- **正常停止／還原**：先按 Seed-VC GUI 的 Stop，再關閉 GUI；停止 Light Host；在 Discord/OBS 將麥克風改回使用前選項，並關閉 Voicemeeter 這條 route 的 B bus。整個流程不需改 Windows 預設音訊裝置。

GUI 啟動後，在實體 mic 前先短講測試句並確認端點 meter。準備擷取前可唯讀列出終端點，再做 30 秒短測：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-live-capture.py --list-devices
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-live-capture.py `
  --host-api 'Windows WASAPI' `
  --microphone '<實體麥克風錄音 endpoint 名稱>' `
  --backend-loopback '<CABLE Output endpoint 名稱>' `
  --terminal-loopback '<Voicemeeter Out B1 endpoint 名稱>' `
  --reference-audio 'C:\Audio\authorized-reference.wav' `
  --seconds 30
```

`--reference-audio` 必須指向該 GUI session 使用的非靜音 PCM WAV；runner 會保存 reference path／format／hash，不會複製音檔。開始 capture 後按 GUI Start 並持續對 mic 說話。runner 會保存原始 mic、backend loopback、B1 loopback WAV、SHA-256、PortAudio flags、callback frame/timestamp continuity 和首個非靜音 onset 時間。onset timing 是跨裝置 threshold estimate；先人工聽三份輸出、檢查 metrics，再做 `--seconds 600`。Rack bypass/full-chain A/B 要引用相同 capture source/reference WAV 與 hash；不同現場重講會產生不同 mic WAV，不能冒充為相同來源的 pair。必要時用固定、已授權 corpus source 做可重複的 rack A/B，再將實體 mic 的完整 route 單獨登記到 LIVE_GATE。600 秒 capture 也不會自動變成 LIVE：人工聽測、paired bypass/full-chain evidence 與 `tools/live-gate-validate.py` gate 仍須分開完成。

### 離線 WAV 對照

`source` 是要保留內容的語音；`target` 是建議 1–30 秒、乾淨、單一說話者的 reference。只使用本人或已取得授權的聲音：

### 男聲轉女聲

```powershell
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-male-m1.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\male-to-female
```

### 女聲轉男聲

```powershell
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-female-f1.wav `
  -Target .\dataset\reference-voices\voice-male-m1.wav `
  -OutputDir .\artifacts\seed-vc\female-to-male
```

成功後查看：

- `artifacts/seed-vc/<output-name>/<run-id>/vc_*.wav`：本次唯一 run 的音訊結果。
- `artifacts/seed-vc/<output-name>/<run-id>/seed-vc-run.json`：run id、輸入/reference/checkpoint hash、Torch runtime、每個新 WAV 的有限值/非靜音結果；失敗時保存 `FAIL` manifest。
- `backends/seed-vc/README.md` 與 `docs/agent-implementation-status-latest.md`：Seed-VC 輸入契約與目前實際驗證摘要。

目前已驗證 `offline-v1` 雙向 WAV、60 秒長音檔、`realtime-tiny` headless GPU block，以及 deterministic WAV 注入的官方 GUI callback user-flow；這些仍不能代替真人說話的實體 mic → backend → rack → B1 鏈路。

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

目前最新實測報告在 `artifacts/seed-vc/gui-userflow/phase-20260922-final/gui-userflow-report.json`；它使用 deterministic WAV 注入 callback，輸出只到 VB-CABLE，通過的是 GUI／CUDA／PortAudio callback 與訊號差異 gate，不是人工聽測或完整 `LIVE <= 5s` gate。

## 4. 使用 RVC

### RVC 的基本順序

```text
乾聲資料 → audit → 切片／保留測試集 → RVC 訓練
→ .pth + .index → model-register.csv → 離線聽測
→ VCClient → VST → VB-CABLE／Voicemeeter → Discord／OBS
```

先讀 [`model-training-guide.md`](model-training-guide.md) 準備資料與模型，再讀 [`operation-guide.md`](operation-guide.md) 接即時路由。

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
