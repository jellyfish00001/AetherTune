# AetherTune

Windows 語音變聲與語音重建實驗專案。這個專案同時保留三種不同路線，請先依「要不要即時、要不要訓練、要不要保留原始表演」選擇方法，不要把三種模型混在同一個 RVC 流程裡。

## 先看這張選擇表

| 你想要的結果 | 使用方法 | 是否要訓練 | 輸入 | 目前狀態 |
|---|---|---:|---|---|
| 即時通話、遊戲、Discord、OBS | **RVC + FCPE/RMVPE** | 要 | 乾聲資料、角色 `.pth/.index` | 官方 sample 離線轉換 `PASS`；四組自有角色與即時音訊鏈路仍 `WAITING` |
| 快速把一段聲音換成男聲／女聲 | **Seed-VC / Zero-Shot VC** | 不要 | source WAV + 1–30 秒 reference WAV | `offline-v1` 雙向離線產檔 `PASS`；人工聽測與即時性仍待補 |
| 改寫或重建內容，保留參考聲線 | **STT → TTS**：CosyVoice／Breeze TTS 2 | 不要訓練角色 | source WAV → transcript + reference WAV | CosyVoice zero-shot TTS `PASS`；完整 STT 與 Breeze `WAITING/PLANNED` |

最簡單的判斷：

- 要「現在講、現在變」：選 RVC。
- 要「不用訓練，先快速試聲線」：選 Seed-VC。
- 要「先辨識文字，再重新說一遍」：選 STT → TTS。它不會完整保留原始笑聲、呼吸、停頓與語氣。

## 五分鐘開始

在 PowerShell 執行：

```powershell
Set-Location D:\AetherTune
& .\tools\voice-backend-check.ps1
```

### Seed-VC：現在可直接產生男／女聲 WAV

如果 `tools/venvs/seed-vc/` 尚未存在，先執行一次：

```powershell
& .\tools\seed-vc-setup.ps1
```

然後執行：

```powershell
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-male-m1.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\male-to-female `
  -Fp16
```

交換 `-Source` 和 `-Target` 就能測試女聲→男聲。結果 WAV 與 `seed-vc-run.json` 會留在 `artifacts/seed-vc/`。完整輸入契約、警告與驗證結果見 [`docs/seed-vc-verification-latest.md`](docs/seed-vc-verification-latest.md) 及 [`backends/seed-vc/README.md`](backends/seed-vc/README.md)。

### RVC：先用官方 sample 驗證離線轉換

VCClient 官方 sample slot 0 已完成短音檔轉換驗證。先啟動 VCClient，再執行：

```powershell
& .\tools\vcclient-rvc-probe.ps1 `
  -SlotIndex 0 `
  -ChunkSec 0.5 `
  -FfmpegPath 'C:\Users\User\AppData\Local\CapCut\Apps\8.5.0.3590\ffmpeg.exe'
```

這是「官方 sample + packaged VCClient」的離線 PASS，不代表目前四組自有 `.pth/.index` 已可用，也不代表 Discord／OBS 即時 loopback 已通過。角色模型仍須依 [`docs/current-rvc-model-inventory.md`](docs/current-rvc-model-inventory.md) 補 metadata、註冊 slot 並重新驗收。

### RVC：先準備資料與註冊模型

RVC 目前不是「放入 `.pth` 就能宣稱完成」。請依序閱讀：

1. [`docs/user-guide.md`](docs/user-guide.md)：依目的選路線與日常使用順序。
2. [`docs/model-training-guide.md`](docs/model-training-guide.md)：乾聲資料、切片、訓練、模型登錄與驗收。
3. [`docs/operation-guide.md`](docs/operation-guide.md)：VCClient、VST、VB-CABLE、Voicemeeter、Discord／OBS 的完整操作。
4. [`docs/current-rvc-model-inventory.md`](docs/current-rvc-model-inventory.md)：目前四組本機模型與 hash；已登錄為 `candidate`，但 metadata 與實際驗收仍是 `WAITING`。

RVC 的音高策略是 **FCPE 首選、RMVPE 備用**。FCPE 的實際 provider 與延遲以 `tools/fcpe_probe.py` 的 artifact 為準；不要只因套件存在就宣稱 FCPE runtime 已通過。

### CosyVoice 2：可直接做 zero-shot TTS；STT 仍需另外接上

CosyVoice 2 已在 WSL2 GPU 產生官方 zero-shot WAV。執行方式、reference transcript 契約與完整證據見 [`docs/cosyvoice-verification-latest.md`](docs/cosyvoice-verification-latest.md)。目前仍需先以 STT 取得並人工核對 source／reference transcript；Breeze TTS 2 尚未安裝。

## 三種方法的資料流

```text
RVC：       麥克風／source WAV → RVC + FCPE/RMVPE → VCClient → 虛擬音訊 → Discord／OBS
Seed-VC：   source WAV + reference WAV → Seed-VC Zero-Shot VC → output WAV
STT → TTS： source WAV → STT transcript → CosyVoice／Breeze + reference → output WAV
```

RVC 是「角色模型推論」；Seed-VC 是「參考聲音條件式轉換」；STT → TTS 是「文字內容重建」。三者輸出不可用同一套品質標準比較。

## 文件地圖

給人使用時，建議只照這個順序：

1. [`README.md`](README.md)：選方法、快速命令、目前狀態。
2. [`docs/user-guide.md`](docs/user-guide.md)：完整人類操作手冊。
3. [`docs/model-training-guide.md`](docs/model-training-guide.md)：RVC 訓練與模型管理；Seed-VC、CosyVoice、Breeze 不需要一般角色訓練。
4. [`docs/operation-guide.md`](docs/operation-guide.md)：Windows 即時路由與驗收。
5. [`docs/voice-conversion-architecture.md`](docs/voice-conversion-architecture.md)：架構、資料契約與比較方式。
6. 各後端 README：[`backends/rvc/README.md`](backends/rvc/README.md)、[`backends/seed-vc/README.md`](backends/seed-vc/README.md)、[`backends/speech-reconstruction/README.md`](backends/speech-reconstruction/README.md)。
7. `docs/*-verification-latest.md`：只看最新實際驗證，不把計畫當成通過。

給 Agent 使用時，先讀根目錄 [`AGENTS.md`](AGENTS.md)，再依任務讀指定文件。根目錄 AGENTS 是專案規則與導航，不取代本 README。

## 目錄怎麼分

```text
dataset/                    # 原始乾聲、切片、reference voice 與 manifest
models/                     # RVC 模型登錄、多後端模型說明與本機權重
backends/                   # 每條方法的入口與限制
tools/                      # 可重跑的 setup、run、probe、verify 腳本
docs/                       # 人類操作手冊、訓練細節、架構與驗證證據
AGENTS.md                   # Agent 專用規則、導航、證據邊界
```

權重、音訊、第三方 repo、虛擬環境與 artifacts 預設不進 Git。所有聲音、角色模型與 reference voice 都必須先確認授權。

## 目前缺少什麼

- RVC 四組現有 `.pth/.index` 已完成檔案與 hash 的 candidate 登錄，但來源、授權、f0、取樣率、revision 與 dataset metadata 尚未補齊；目前 PASS 是官方 sample slot，不是這四組自有角色。
- RVC 官方 sample 短音檔 conversion 已取得非零輸出 WAV；GPU provider、四組自有角色、即時 latency、長時間穩定性與 Light Host loopback 仍未驗收。
- Light Host + Graillon 的實際 chain 與 loopback 仍需人工完成。
- Seed-VC 已能產檔，但仍缺人工聽測、長音檔、多說話者與 realtime tiny latency matrix。
- CosyVoice2 官方 zero-shot TTS 已 PASS；完整 STT→TTS、個人 reference 的 exact transcript 與人工聽測仍 `WAITING`。
- Breeze TTS 2 與 STT pipeline 尚未建立，維持 `PLANNED`／`WAITING`。

狀態意義：`PASS` 是指定檢查或實際流程通過；`WAITING` 是有明確阻塞或尚未完成；`PLANNED` 是尚未開始或仍需選擇。檔案存在、模型下載、UI 可開啟都不等於端到端語音可用。

## 重要邊界

RVC、Seed-VC、CosyVoice、Breeze TTS 2、VB-CABLE、Voicemeeter、Graillon 的授權與用途不同；不要把「免費」寫成「全部開源」，也不要把公開 sample 的聲線當成使用者自有聲音。所有改動先保留現有 user worktree 內容，完成檢查後再由使用者決定是否 commit。
