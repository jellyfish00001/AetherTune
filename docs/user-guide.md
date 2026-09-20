# AetherTune 人類操作手冊

這份文件回答兩件事：我該選哪一種方法，以及選好後要放什麼檔案、執行什麼命令。若只想快速開始，先讀根目錄 `README.md`；若要理解訓練與模型登錄，再讀 [`model-training-guide.md`](model-training-guide.md)。

## 1. 先選路線

### RVC + FCPE/RMVPE

選 RVC 的情況：

- 需要即時麥克風變聲。
- 要用於 Discord、遊戲或 OBS。
- 願意準備乾聲資料並訓練角色模型。
- 願意花時間測試 pitch、index、chunk 與音訊路由。

RVC 會保留較多原始說話內容與聲學表演，但需要角色模型、VCClient、虛擬音訊與延遲驗收。這是最適合長時間即時使用的路線。

### Seed-VC／Zero-Shot VC

選 Seed-VC 的情況：

- 不想先訓練角色模型。
- 想用一段 source 聲音快速試男聲或女聲 reference。
- 可以接受先產生 WAV，而不是直接接入即時通話。

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

若尚未建立獨立環境，先執行一次：

```powershell
& .\tools\seed-vc-setup.ps1
```

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
- `docs/seed-vc-verification-latest.md`：目前實際驗證摘要。

目前已驗證 `offline-v1` 雙向 WAV、60 秒長音檔與 `realtime-tiny` headless GPU block；但官方 GUI、PortAudio 麥克風端到端、人工聽測與長時間 realtime 穩定性仍待補。

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
- sample rate、f0 method、RVC version、revision、dataset batch。
- 未參與訓練的測試句與人工聽測。
- VCClient 真實模型載入與延遲證據。

`sample_rate`、`f0`、`version`、`dataset_batch_id`、`rvc_revision` 目前以 `unknown` 明確標記，必須補齊後才能考慮 `ready`。

不要只因 VCClient Web UI 能開啟或模型檔存在，就跳過這些步驟。

### FCPE 與 RMVPE 怎麼用

- 專案 runtime 策略：FCPE 首選、RMVPE 備用。
- 若訓練用的上游 RVC WebUI 沒有 FCPE 選項，使用 RMVPE 完成該次訓練並在 register 記錄真實值。
- 執行 `tools/fcpe_probe.py` 時查看 artifact 的實際 device、provider、時間與輸出誤差。
- 不要把 `available_providers` 當成實際執行 provider。

## 5. 使用 STT → TTS

這條路線已可用 `tools/speech-reconstruction-run.ps1` 一鍵串接；若要可追溯與正式 clone，仍建議分階段核對：

1. 先對 source WAV 做 STT。
2. 人工核對 transcript，特別是 reference audio 的 prompt text。
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
