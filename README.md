# AetherTune

Windows 語音變聲與語音重建實驗專案。這個專案同時保留四個可比較的後端：RVC、Seed-VC、CosyVoice2、Breeze TTS 2。請先依「要不要即時、要不要訓練、要不要保留原始表演」選擇方法，不要把不同模型混在同一個 RVC 流程裡。

## 先看這張選擇表

| 你想要的結果 | 使用方法 | 是否要訓練 | 輸入 | 目前狀態 |
|---|---|---:|---|---|
| 即時通話、遊戲、Discord、OBS | **RVC + FCPE/RMVPE** | 要 | 乾聲資料、角色 `.pth/.index` | 四組本機 candidate 角色模型 `FCPE + cuda:0` 離線推論 `PASS`；即時音訊鏈路仍 `WAITING` |
| 快速把一段聲音換成男聲／女聲 | **Seed-VC / Zero-Shot VC** | 不要 | source WAV + 1–30 秒 reference WAV | `offline-v1` 雙向／60 秒長檔與 `realtime-tiny` 60 秒 headless GPU `PASS`；麥克風端到端仍 `WAITING` |
| 改寫或重建內容，保留參考聲線 | **STT → TTS**：CosyVoice2／Breeze TTS 2 | 不要訓練角色 | source WAV → transcript + reference WAV | STT、CosyVoice2、Breeze TTS 2 輸出 `PASS`；CosyVoice speech tokenizer partial CUDA、transcript／人工聽核仍待補 |

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

### RVC：先用專案 FCPE + GPU，VCClient packaged 另行驗收

四組本機 candidate 角色模型已由專案 RVC pipeline 完成 `FCPE + cuda:0` 離線推論；先用這條路線開始測試。VCClient packaged runtime 的官方 modules 已修復，但真實 role conversion 仍被 `SlotInfo.chunk_sec` HTTP 500 或短的全零 chunk 阻塞，不能把任何短全零 response 當成成功。註冊與最新證據見 [`docs/vcclient-packaged-repair-latest.md`](docs/vcclient-packaged-repair-latest.md)。

先啟動 VCClient，再以安全註冊器建立新 slot：

```powershell
& .\tools\vcclient-rvc-register.ps1 `
  -ModelPath .\models\weights\Wukong_HeroicMale.pth `
  -IndexPath .\models\indexes\Wukong_HeroicMale.index `
  -SlotIndex 9 `
  -Name 'AetherTune Wukong Heroic Male'
```

直接使用 `tools/vcclient-rvc-probe.ps1` 時，`-ConfigureSlot` 是 probe 的 switch，會明確切換並核對 requested／active slot；若出現 packaged API error，請看 report，不要把服務 HTTP 200 視為可用。矩陣會自行把 `-ConfigureSlot` 傳給 probe，使用者不要把它當成矩陣參數。矩陣預設測試專案目前 active slot `7`。

要測 RVC realtime chunk／dropout／10 分鐘 gate，使用 [`tools/vcclient-rvc-latency-matrix.ps1`](tools/vcclient-rvc-latency-matrix.ps1)；最新證據與判定規則見 [`docs/vcclient-rvc-latency-matrix-latest.md`](docs/vcclient-rvc-latency-matrix-latest.md)。

### RVC：先準備資料與註冊模型

RVC 目前不是「放入 `.pth` 就能宣稱完成」。請依序閱讀：

1. [`docs/user-guide.md`](docs/user-guide.md)：依目的選路線與日常使用順序。
2. [`docs/model-training-guide.md`](docs/model-training-guide.md)：乾聲資料、切片、訓練、模型登錄與驗收。
3. [`docs/operation-guide.md`](docs/operation-guide.md)：VCClient、VST、VB-CABLE、Voicemeeter、Discord／OBS 的完整操作。
4. [`docs/current-rvc-model-inventory.md`](docs/current-rvc-model-inventory.md)：目前四組本機模型與 hash；已登錄為 `candidate`，但 metadata 與實際驗收仍是 `WAITING`。

RVC 的音高策略是 **FCPE 首選、RMVPE 備用**。FCPE 的實際 provider 與延遲以 `tools/fcpe_probe.py` 的 artifact 為準；不要只因套件存在就宣稱 FCPE runtime 已通過。

### CosyVoice2 與 Breeze TTS 2：可直接做 STT → TTS

Faster-Whisper、CosyVoice2 與 Breeze TTS 2 都已建立獨立環境並完成實際 WAV 輸出。要一鍵跑完整流程，可使用 `tools/speech-reconstruction-run.ps1`；單獨測試則看 [`docs/cosyvoice-verification-latest.md`](docs/cosyvoice-verification-latest.md) 與 [`docs/breeze-tts2-verification-latest.md`](docs/breeze-tts2-verification-latest.md)。reference transcript 目前是 STT draft，正式 voice clone 前仍應人工逐字確認。

一鍵 STT → CosyVoice2（未提供 `-TextFile` 時會自動先跑 Faster-Whisper）：

```powershell
& .\tools\speech-reconstruction-run.ps1 `
  -InputWav .\dataset\reference-voices\voice-male-m1.wav `
  -Backend cosyvoice `
  -Output cosyvoice-from-stt.wav
```

把 `-Backend cosyvoice` 換成 `-Backend breeze-tts-2` 即可使用 Breeze。 `-TextFile` 是要合成的目標文字，`-ReferenceTextFile` 是 reference audio 的 prompt transcript；未提供人工核對文字時，workflow 會標記 `caller_provided_unverified` 或 STT draft 與 `manual_review_required=true`。若沒有 `-TextFile`，目標內容仍是 source STT draft，即使 reference transcript 已 verified，`manual_review_required` 也維持 `true`；只有 caller 提供 `TextFile` 且 reference verified 時才會是 `false`。只有使用者已逐字核對 reference transcript 時，才加上 `-ReferenceTextVerified`；沒有 `-ReferenceTextFile` 時使用這個 switch 會被拒絕。

Breeze 若要使用 Voice Design 而不取 reference voice，請在同一個 wrapper 加上 `-VoiceDesign -Instruction '...'`；這個模式不可同時指定 `-ReferenceAudio` 或 `-ReferenceTextFile`。若未加 `-VoiceDesign`，wrapper 維持以輸入音檔作為快速 clone smoke test 的相容行為。

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
8. [`docs/audio-quality-comparison-latest.md`](docs/audio-quality-comparison-latest.md)：四種後端的 WAV 訊號層批次比較；它不是 MOS 或人工音質結論。
9. [`docs/agent-implementation-status-latest.md`](docs/agent-implementation-status-latest.md)：本輪八項 Agent 實作／測試的總表與剩餘阻塞。

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

- RVC 四組現有 `.pth/.index` 已各自通過 `FCPE + cuda:0` 離線推論並產生非零 WAV；模型 hash／配對 audit `PASS`，checkpoint 內嵌 sample rate／v2 version 已核對，但來源、授權、f0 演算法、revision、dataset metadata 與 ready gate 仍 `WAITING`。詳見 [`docs/rvc-model-audit-latest.md`](docs/rvc-model-audit-latest.md)。
- RVC 即時 latency、長時間穩定性、Light Host chain、VB-CABLE／Voicemeeter／Discord／OBS loopback 仍未驗收。
- Light Host + Graillon 的實際 chain 與 loopback 仍需人工完成。
- Seed-VC 已完成雙向離線、60 秒長音檔與 realtime-tiny headless latency；仍缺人工聽測、多說話者、PortAudio 麥克風端到端與長時間 realtime 穩定性。
- CosyVoice2 已完成官方 zero-shot 與男女 reference clone；STT draft 已產生，但 exact transcript 人工聽核仍 `WAITING`。
- Breeze TTS 2 已完成 WSL2、CUDA、Voice Design 男女、reference clone 男女、`fast-all` CUDA graph 與 project-local SoX runner；flash-attn 仍 WAITING，system SoX 未安裝，人工音質評估仍待補。`fast-all` 本機 RTF 約 `11.4196`，不能套用 H100 benchmark。

狀態意義：`PASS` 是指定檢查或實際流程通過；`WAITING` 是有明確阻塞或尚未完成；`PLANNED` 是尚未開始或仍需選擇。檔案存在、模型下載、UI 可開啟都不等於端到端語音可用。

## 重要邊界

RVC、Seed-VC、CosyVoice、Breeze TTS 2、VB-CABLE、Voicemeeter、Graillon 的授權與用途不同；不要把「免費」寫成「全部開源」，也不要把公開 sample 的聲線當成使用者自有聲音。所有改動先保留現有 user worktree 內容，完成檢查後再由使用者決定是否 commit。
