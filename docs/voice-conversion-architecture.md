# AetherTune 多後端語音架構與比較契約

更新日期：2026-09-26（Asia/Taipei）

## 研究分組

```text
                         AetherTune
                             │
              ┌──────────────┴──────────────┐
              │                             │
       Streaming VC                   Speech Reconstruction
       保留來源表演                    重新生成聲學表演
              │                             │
   RVC / Seed-VC / MeanVC2 / X-VC       CosyVoice2 / CosyVoice3 / Breeze
              │                             │
              └──────────────┬──────────────┘
                             ▼
                  Common Audio Rack
                             │
                    Virtual Routing
                             │
                       Benchmarks
```

Streaming VC 優先比較內容、韻律、情緒、呼吸、笑聲與目標音色保留；Speech Reconstruction 優先比較內容一致性、聲線、自然度與可控制性。不能把兩組用同一個「效果分數」混成單一排名。

## Backend adapter 契約

每個 adapter 都要有：

- `backend_id` 與 profile 名稱。
- source／reference audio path、SHA-256、sample rate、channels、provenance。
- upstream URL、固定 revision、license classification、runtime environment。
- input mode：`microphone`、`source_wav`、`stt_text` 或 `voice_design`。
- output WAV／stream、output hash、finite／non-zero／clipping 驗證。
- device/provider、chunk／block、buffer、RTF 與完整鏈路 timing。
- `PASS`、`WAITING`、`PLANNED`、`BLOCKED` 或更精確的 `candidate`／`historical-baseline`。

### 路線責任

| 路線 | 來源輸入 | 目標條件 | 能保留什麼 | 不能宣稱什麼 |
|---|---|---|---|---|
| RVC | mic/source + trained role model | `.pth/.index` + f0 | 內容與部分 acoustic performance | 訓練／離線輸出不等於 VCClient realtime |
| Seed-VC | source + 1–30 秒 reference | zero-shot reference | 來源內容與較多原始表演線索 | upstream benchmark 不等於本機 LIVE |
| MeanVC2 | streaming source + reference | 下一順位 zero-shot streaming candidate | 研究目標是低延遲與表演保留 | 上游 [40 ms chunk／110 ms 宣稱](https://github.com/ASLP-lab/MeanVC2) 不等於 RTX 5060 Ti E2E |
| X-VC | streaming source + reference | codec-space zero-shot streaming research candidate | 由同一 source/reference 契約比較內容與聲線轉換 | [官方程式碼](https://github.com/Jerrister/X-VC) 尚未在本機完成來源、weights、license 或 runtime intake |
| CosyVoice2/3 | text + prompt/reference | TTS／clone | 文字內容與重建聲線 | 不保證原始笑聲、呼吸、停頓與情緒 |
| Breeze TTS 2 | text + reference 或 instruction | clone／voice design | 文字內容與重建聲線 | 本機 runtime／RTF 不等於 LIVE |

## Common Audio Rack

所有需要輸出至直播／通話端點的 backend 都接到 `audio-rack/`：

```text
backend output
  → corrective EQ
  → de-esser
  → compressor
  → saturation
  → optional pitch correction
  → light ambience
  → limiter
  → virtual route
```

每個 backend 至少跑 `Post-FX bypass` 與 `Post-FX full-chain`。報告需量實際 `delta_latency_ms`；不能用 VST 數量推估延遲。Pitch correction 預設 optional，避免把模型自身韻律全部修平。

## 三層 benchmark

### 1. Live Technical

完整鏈路：

```text
capture input
  → backend
  → audio-rack
  → virtual routing
  → loopback／terminal capture
```

`e2e_first_packet_ms <= 5000` 是進入 `LIVE_CANDIDATE` 的延遲硬門檻。`LIVE` 還需要本次 physical-mic input/final-output artifact、hash/identity、至少 600 秒連續 evidence、zero dropout／underrun 與人工聽測。schema 與分類見 [`docs/live-gate.md`](live-gate.md)。

### 2. Acoustic Objective

固定 corpus、固定 reference、固定 sample rate／loudness policy，記錄 decode、finite、non-zero、RMS、peak、silence、DC、clipping、hash、內容正確性 proxy。這一層不能導出 MOS、自然度或聲線相似度。

### 3. Human Listening

建議盲測維度：自然度、目標音色相似度、原始表演／情緒保留、內容正確性、噪音／破音、可接受度與偏好。每筆評分要能回指 source、reference、backend profile、rack profile 與 output hash。

## Windows 路由邊界

目前候選路徑是：

```text
physical microphone
  → backend
  → CABLE Input (VB-Audio Virtual Cable)
  → CABLE Output (VB-Audio Virtual Cable)
  → Light Host / audio-rack
  → Voicemeeter Input (VB-Audio Voicemeeter VAIO)
  → Voicemeeter B bus
  → Voicemeeter Out B1
  → OBS / Discord / VTube Studio
```

正式驗證要記錄裝置名稱、input/output direction、sample rate、channel、buffer、WAV、metrics JSON 與 hash。`Voicemeeter Out B1` 是 Windows endpoint，不是 UI 上的 `B` 按鈕；不能混寫。

## 目前 scope

- RVC 既有 verifier、模型 audit 與 VCClient failure evidence 保留，重新定位為 baseline。
- Seed-VC upstream 的本機 headless evidence 保留；2026-09-26 官方 Python 3.10.11 Tcl/Tk Support 修復後，Seed-VC venv preflight 與四個 GUI 設定／backend／VB-CABLE loopback case 均 `PASS`；實體麥克風、Light Host full-chain 與 600 秒穩定性仍待驗收。
- Streaming VC 順序為 Seed-VC established baseline → MeanVC2 priority candidate → X-VC／新 streaming zero-shot candidate intake；Seed-VC realtime fork 另作執行路徑比較。
- MeanVC2、X-VC、Seed-VC realtime fork、CosyVoice3 只建立候選位置與驗收契約，不在本輪下載模型或宣稱 runtime PASS。
- Audio Rack、固定 corpus、LIVE_GATE validator 與三層 benchmark 文件先落地；實際 mic E2E、VST chain、blind listening 是後續工作。
