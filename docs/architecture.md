# AetherTune 系統架構

更新日期：2026-09-22（Asia/Taipei）

## 定義

AetherTune 是本地 AI Voice Transformation Research Workbench，不是四個工具的安裝清單。研究問題是：在 RTX 5060 Ti 16GB、Windows、本地運算與完整音訊鏈路下，哪一種方法最自然、最接近目標音色、最能保留來源表演，並且端到端延遲不超過 5 秒。

優先序固定為：

1. 自然度。
2. 目標音色相似度。
3. 原始表演／情緒保留。
4. 延遲；但完整鏈路超過 5 秒就不能分類為 `LIVE`。

「免費」、「開源」、「open-weight」、「non-commercial」與「commercial-compatible」分開記錄；模型、reference voice 與輸出聲音的授權不是同一個問題。

## 分層架構

```text
┌──────────────────────────────────────────────────────────────┐
│ Capture / Preprocess                                         │
│ mic or fixed source → format/device/time marker             │
└──────────────────────────────┬───────────────────────────────┘
                               │ common input contract
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Backend Adapter                                               │
│ RVC baseline │ Seed-VC profiles │ MeanVC2 candidate           │
│ STT → CosyVoice2/3/Breeze reconstruction profiles             │
└──────────────────────────────┬───────────────────────────────┘
                               │ converted/reconstructed PCM
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Common Audio Rack                                             │
│ EQ → De-esser → Compressor → Saturation → optional Pitch     │
│ Correction → light Ambience → Limiter                        │
│ 每個 profile 都必須支援 bypass / full-chain                  │
└──────────────────────────────┬───────────────────────────────┘
                               │ processed PCM
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Virtual Audio Routing                                         │
│ VB-CABLE / Voicemeeter / other verified route                 │
└──────────────────────────────┬───────────────────────────────┘
                               │ loopback / terminal capture
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Benchmark Pipeline                                            │
│ LIVE technical │ acoustic objective │ human blind listening   │
└──────────────────────────────────────────────────────────────┘
```

`audio-rack/` 是 cross-cutting infrastructure，不是第五個 backend。既有 Light Host、Graillon、VB-CABLE、Voicemeeter 是 Windows 實作候選；它們不再被寫成 RVC 專屬架構，也不因安裝存在就視為已通過共用 rack。

## Backend 分組

| 分組 | Backend/profile | 研究責任 | 目前定位 |
|---|---|---|---|
| Streaming VC | RVC + FCPE/RMVPE | 角色模型、內容與部分 acoustic performance | `historical-baseline`；VCClient realtime evidence 仍 `BLOCKED/DEGRADED` |
| Streaming VC | Seed-VC upstream | zero-shot reference conversion | `established-baseline`；headless GPU evidence `PASS`，mic E2E `WAITING`；upstream archived |
| Streaming VC | Seed-VC realtime fork | worker/ring-buffer/device/VAD 路徑比較 | `candidate / PLANNED`，不與既有 venv 混用 |
| Streaming VC | MeanVC2 | 新的 low-latency zero-shot 候選 | `candidate / PLANNED`，未安裝、未驗證 |
| Research candidates | X-VC、RT-VC | 追蹤 codec／articulatory streaming 方向 | `research-candidate`，不進目前可執行矩陣 |
| Speech Reconstruction | CosyVoice2 | STT + reference TTS baseline | runtime evidence `PASS`；只作 offline baseline |
| Speech Reconstruction | Fun-CosyVoice3 | 與 CosyVoice2 A/B | `candidate / PLANNED`，未安裝／未驗證 |
| Speech Reconstruction | Breeze TTS 2 | voice design／reference clone | runtime evidence `PASS`；本機不能分類為 LIVE |

Streaming VC 與 Speech Reconstruction 分開報告。後者重新生成內容、韻律、呼吸與停頓，不宣稱完整保留原始聲學表演。

## 共用資料契約

每一個 backend adapter 都應接受或產生可追溯的 manifest：

1. `source_audio`：path、SHA-256、sample rate、channels、授權 provenance。
2. `reference_audio` 或 `voice_design_prompt`：path/hash 或 prompt、license/use scope。
3. `backend_id`、profile、upstream URL、revision、license classification、environment。
4. `transcript`：`exact`、`machine-generated`、`manual-verified` 或 `not_applicable`。
5. actual device/provider、chunk/block、buffer、sample rate 與模型設定。
6. output WAV／loopback path、SHA-256、signal validation。
7. timing：capture、backend、Post-FX、routing、first packet、p50/p95。
8. continuity：duration、dropouts、underruns。
9. human listening：自然度、相似度、表演保留、噪音與備註；未測就寫 `WAITING`。

## LIVE_GATE

完整 capture → backend → audio-rack → virtual routing 的 `e2e_first_packet_ms <= 5000` 才分類為 `LIVE`。只有 offline WAV、backend inference、RTF、model loading、UI HTTP 200 或 `available_providers` 不足以分類。

使用 [`docs/live-gate.md`](live-gate.md) 與 `tools/live-gate-validate.py`：

- `LIVE`：在 5 秒內且 evidence 欄位完整；仍需 stability 與人工聽測才能成為 live candidate。
- `OFFLINE`：可產生有效輸出，但超過 5 秒或沒有完整即時鏈路。
- `WAITING`：證據尚未補齊。
- `BLOCKED`：schema、artifact、輸出或 runtime 有明確錯誤。

目前 `LIVE` 只是延遲分類，不等同自然度、相似度或直播品質 PASS。正式長時間 gate 暫定至少 600 秒、零 dropout／underrun；這是研究驗收門檻，不是產品保證。

## Windows routing 語意

裝置名稱與方向必須用實際 inventory 驗證：

- 應用程式的 output 連到虛擬線路的 playback/input 端。
- 下一個處理程式的 input 選該虛擬線路的 recording/output 端。
- 最終通訊程式選處理完成的 output，不直接選實體麥克風。

目前已記錄的 Windows 候選路徑：

```text
physical microphone
  → backend capture / output
  → CABLE Input (VB-Audio Virtual Cable)
  → CABLE Output (VB-Audio Virtual Cable)
  → Light Host / common audio-rack
  → Voicemeeter Input (VB-Audio Voicemeeter VAIO)
  → Voicemeeter Standard B bus
  → Voicemeeter Out B1 (recording endpoint)
  → OBS / Discord / VTube Studio
```

Voicemeeter UI 上的 `B` 是 strip bus button；`Voicemeeter Out B1` 是 Windows recording endpoint，兩者不可混為同一語意。VB-CABLE／Voicemeeter loopback 必須同時保存 WAV、metrics JSON、route identity 與 SHA-256；全零訊號只能是 `WAITING`／`BLOCKED`，不能沿用舊 PASS。

## 驗收順序

1. source/reference provenance 與 hash。
2. backend isolated runtime／offline output validation。
3. fixed corpus 的 Streaming VC 或 Speech Reconstruction paired run。
4. audio-rack bypass 與 full-chain A/B，量實際 Δ latency。
5. mic／PortAudio → backend → rack → virtual route → loopback 的 LIVE_GATE。
6. acoustic objective comparison。
7. human blind listening。
8. 只有所有層級都有 evidence，才可更新主線或 default profile。

## 目前實作邊界

- 既有 RVC、Seed-VC、CosyVoice2、Breeze artifacts 與 verifier 保留；這次重構只改架構定位與共用契約，不刪除已存在的 runtime evidence。
- MeanVC2、Seed-VC realtime fork、CosyVoice3 目前只有 candidate intake 文件，沒有本機安裝或模型 PASS。
- audio-rack 已建立 profile、routing、preset 與 `rack-evidence-v1` schema；VB-CABLE／Voicemeeter synthetic route smoke `PASS`，但實體 VST chain、完整 mic E2E、blind listening 仍 `PLANNED/WAITING`。
- 任何與 RVC packaged VCClient、CUDA provider、模型 ready gate 有關的判定仍以各自最新 verifier 為準；不能被新的架構文件覆蓋。
