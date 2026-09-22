# AetherTune

AetherTune 是一個本地即時 AI Voice Transformation Research Workbench。核心目標是在 RTX 5060 Ti 16GB 與 Windows 本地環境，以 `5 秒` 端到端延遲為硬上限，比較 Streaming Voice Conversion 與 Speech Reconstruction，並用共用的 Capture、Post-FX、Routing 與 Benchmark Pipeline 評估自然度、目標音色相似度、原始表演保留、穩定性與直播可用性。

`<= 5 秒` 才分類為 `LIVE`；`> 5 秒` 分類為 `OFFLINE`，不再和 Live 混合排名。完整分類與 evidence 契約見 [`docs/live-gate.md`](docs/live-gate.md)。

## 先看這張選擇表

| 研究路線／結果 | 使用方法 | 是否要訓練 | 輸入 | 目前狀態 |
|---|---|---:|---|---|
| 即時通話、遊戲、Discord、OBS | **Streaming VC**：Seed-VC realtime → MeanVC2 → 候選 | 通常不要 | mic/source + reference | Seed-VC headless GPU `PASS`；真實 mic E2E、共用 rack、virtual route 仍 `WAITING`；MeanVC2 `PLANNED / candidate` |
| 既有低延遲對照 | **RVC + FCPE/RMVPE** | 要 | 乾聲資料、角色 `.pth/.index` | `historical-baseline`；四組離線 GPU 證據 `PASS`，VCClient 即時鏈路 `BLOCKED/DEGRADED` |
| 改寫或重建內容，保留參考聲線 | **STT → TTS**：CosyVoice2／CosyVoice3／Breeze | 不要訓練角色 | source WAV → transcript + reference WAV | CosyVoice2／Breeze runtime 證據保留；CosyVoice3 `candidate`；目前不能列為 LIVE |

最簡單的判斷：

- 要「現在講、現在變」：先測 Seed-VC realtime；MeanVC2 intake 完成後再加入同一矩陣。RVC 只作 legacy baseline。
- 要「不用訓練，先快速試聲線」：選 Seed-VC offline／realtime profile。
- 要「先辨識文字，再重新說一遍」：選 STT → TTS。它重新生成聲學表演，不會完整保留原始笑聲、呼吸、停頓與語氣。
- 所有路線都要通過同一個 audio-rack 與 benchmark 契約；不要把 Post-FX 掛在 RVC 專屬流程中。

## 五分鐘開始

在 PowerShell 執行：

```powershell
Set-Location D:\AetherTune
& .\tools\voice-backend-check.ps1
```

### Seed-VC：目前最接近主線的 baseline

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

交換 `-Source` 和 `-Target` 就能測試女聲→男聲。結果 WAV 與 `seed-vc-run.json` 會留在 `artifacts/seed-vc/`。這只證明 offline/headless runtime，不是 mic → backend → audio-rack → virtual route 的 LIVE PASS。完整輸入契約與驗證結果見 [`backends/seed-vc/README.md`](backends/seed-vc/README.md) 及 [`docs/agent-implementation-status-latest.md`](docs/agent-implementation-status-latest.md)。Seed-VC upstream 已 archived；fork 候選見 [`backends/seed-vc-realtime/README.md`](backends/seed-vc-realtime/README.md)。

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

### Speech Reconstruction：CosyVoice2／CosyVoice3／Breeze

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

## 研究工作台資料流

```text
Capture / Preprocess
        │
        ▼
  Backend Adapter ──┬─ RVC / FCPE（legacy baseline）
                    ├─ Seed-VC realtime（established baseline）
                    ├─ MeanVC2（candidate）
                    └─ STT → CosyVoice2/3/Breeze（reconstruction）
        │
        ▼
  Common Audio Rack（bypass / full-chain）
        │
        ▼
  Virtual Audio Routing → OBS / Discord / VTube Studio
        │
        ▼
  Live Technical + Acoustic Objective + Human Listening Benchmarks
```

RVC／Seed-VC／MeanVC2 屬於 Streaming VC，目標是保留來源內容與表演；CosyVoice／Breeze 屬於 Speech Reconstruction，目標是以文字重新生成聲音。兩組必須分開報告，但都應共享 capture、audio-rack、routing、artifact 與 benchmark 契約。

## 文件地圖

給人使用時，建議只照這個順序：

1. [`README.md`](README.md)：選方法、快速命令、目前狀態。
2. [`docs/user-guide.md`](docs/user-guide.md)：完整人類操作手冊。
3. [`docs/model-training-guide.md`](docs/model-training-guide.md)：RVC 訓練與模型管理；Seed-VC、CosyVoice、Breeze 不需要一般角色訓練。
4. [`docs/operation-guide.md`](docs/operation-guide.md)：Windows 即時路由與驗收。
5. [`docs/live-gate.md`](docs/live-gate.md)：`LIVE`／`OFFLINE`／`WAITING`／`BLOCKED` 分類與 evidence 契約。
6. [`docs/voice-conversion-architecture.md`](docs/voice-conversion-architecture.md)：backend adapter、audio-rack 與 benchmark 架構。
7. 各後端 README：[`backends/rvc/README.md`](backends/rvc/README.md)、[`backends/seed-vc/README.md`](backends/seed-vc/README.md)、[`backends/seed-vc-realtime/README.md`](backends/seed-vc-realtime/README.md)、[`backends/meanvc2/README.md`](backends/meanvc2/README.md)、[`backends/speech-reconstruction/README.md`](backends/speech-reconstruction/README.md)。
8. `audio-rack/` 與 `benchmarks/`：共用後製、路由與三層 benchmark 契約。
9. `docs/*-verification-latest.md`：只看最新實際驗證，不把計畫當成通過。
10. [`docs/audio-quality-comparison-latest.md`](docs/audio-quality-comparison-latest.md)：目前 WAV 訊號層批次比較；它不是 MOS 或人工音質結論。
11. [`docs/agent-implementation-status-latest.md`](docs/agent-implementation-status-latest.md)：Agent 實作／測試總表與剩餘阻塞。

給 Agent 使用時，先讀根目錄 [`AGENTS.md`](AGENTS.md)，再依任務讀指定文件。根目錄 AGENTS 是專案規則與導航，不取代本 README。

## 目錄怎麼分

```text
dataset/                    # 原始乾聲、切片、reference voice 與 manifest
models/                     # RVC 模型登錄、多後端模型說明與本機權重
backends/                   # backend adapter 的入口、候選與限制
audio-rack/                 # 跨 backend 的 Post-FX、plugin 與 routing 契約
benchmarks/                 # Live、客觀訊號、人工盲測的固定 corpus 與規則
tools/                      # 可重跑的 setup、run、probe、verify 腳本
docs/                       # 人類操作手冊、訓練細節、架構與驗證證據
AGENTS.md                   # Agent 專用規則、導航、證據邊界
```

權重、音訊、第三方 repo、虛擬環境與 artifacts 預設不進 Git。所有聲音、角色模型與 reference voice 都必須先確認授權。

## 目前缺少什麼

- RVC 四組現有 `.pth/.index` 已各自通過 `FCPE + cuda:0` 離線推論並產生非零 WAV；模型 hash／配對 audit `PASS`，checkpoint 內嵌 sample rate／v2 version 已核對，但來源、授權、f0 演算法、revision、dataset metadata 與 ready gate 仍 `WAITING`。詳見 [`docs/rvc-model-audit-latest.md`](docs/rvc-model-audit-latest.md)。
- RVC 即時 latency、長時間穩定性、Light Host chain、Discord／OBS loopback 仍未驗收；VB-CABLE 與 Voicemeeter B1 synthetic loopback 已通過，現仍定位為 historical baseline。
- 共用 audio-rack 的 bypass/full-chain、plugin Δ latency 與 backend 實際 loopback 仍需建立；現有 Light Host + Graillon 記錄不再代表所有 backend 的架構。
- Seed-VC 已完成雙向離線、60 秒長音檔、realtime-tiny headless latency 與 synthetic virtual route；仍缺人工聽測、多說話者、PortAudio 實體麥克風 E2E、共用 rack 與 10 分鐘穩定性。
- Seed-VC realtime fork 與 MeanVC2 尚未安裝；CosyVoice3 尚未建立本機 candidate evidence。
- `LIVE_GATE` validator 已建立，但沒有真實 mic／virtual route evidence 就不能產生 LIVE PASS。
- CosyVoice2 已完成官方 zero-shot 與男女 reference clone；STT draft 已產生，但 exact transcript 人工聽核仍 `WAITING`。
- Breeze TTS 2 已完成 WSL2、CUDA、Voice Design 男女、reference clone 男女、`fast-all` CUDA graph 與 project-local SoX runner；flash-attn 仍 WAITING，system SoX 未安裝，人工音質評估仍待補。`fast-all` 本機 RTF 約 `11.4196`，不能套用 H100 benchmark。

狀態意義：`PASS` 是指定檢查或實際流程通過；`WAITING` 是有明確阻塞或尚未完成；`PLANNED` 是尚未開始或仍需選擇。檔案存在、模型下載、UI 可開啟都不等於端到端語音可用。

## 重要邊界

RVC、Seed-VC、CosyVoice、Breeze TTS 2、VB-CABLE、Voicemeeter、Graillon 的授權與用途不同；不要把「免費」寫成「全部開源」，也不要把公開 sample 的聲線當成使用者自有聲音。所有改動先保留現有 user worktree 內容，完成檢查後再由使用者決定是否 commit。
