# AetherTune 系統架構

更新日期：2026-09-26（Asia/Taipei）

## 定義

AetherTune 是本地 AI Voice Transformation Research Workbench，不是四個工具的安裝清單。研究問題是：在 RTX 5060 Ti 16GB、Windows、本地運算與完整音訊鏈路下，哪一種方法最自然、最接近目標音色、最能保留來源表演，並且端到端延遲不超過 5 秒。

優先序固定為：

1. 自然度。
2. 目標音色相似度。
3. 原始表演／情緒保留。
4. 延遲；但完整鏈路超過 5 秒就不能分類為 `LIVE`。

「免費」、「開源」、「open-weight」、「non-commercial」與「commercial-compatible」分開記錄；模型、reference voice 與輸出聲音的授權不是同一個問題。

## 研究需求與驗收條件

| 需求 | 驗收條件 | 證據狀態 |
|---|---|---|
| 使用目標 | Windows、本地運算、RTX 5060 Ti 16GB；以 VTuber、OBS、Discord 等互動場景為目標 | 研究目標，不代表所有 backend 已支援 |
| 品質排序 | 先比較自然度，再比較目標音色相似度與原始表演／情緒保留 | 需用固定 corpus 的盲測結果，不由模型規格推定 |
| Live 硬門檻 | 實際 capture → backend → audio-rack → virtual route → loopback 的首個有效封包 `<= 5000 ms`；超過即歸 `OFFLINE` | 現有完整 mic E2E 仍 `WAITING` |
| 後製公平性 | 同一 source/reference 分別跑 `Post-FX bypass` 與 `full-chain`，記錄實測 `delta_latency_ms`；Pitch Correction 為 optional | audio-rack 契約已建立，實體 plugin chain 仍 `WAITING` |
| 穩定性 | live candidate 至少連續 600 秒，零 dropout／underrun，並保留人工聽測 | 尚無完整 PASS |
| 比較可重現 | 每次保留 source/reference hash、模型與 upstream revision、license、device/provider、設定、輸出 hash、timing 與 benchmark 結果 | 各 backend 依共用 manifest 契約提交 |

Live 延遲是分類門檻；只有通過門檻的 profile 才能按自然度、音色相似與表演保留比較。離線 WAV、RTF、GUI 開啟成功或 synthetic routing 不可代替這項驗收。

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
│ Streaming VC: RVC / Seed-VC / MeanVC2 / X-VC                  │
│ Speech reconstruction: STT → CosyVoice2/3 / Breeze            │
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
| Streaming VC | MeanVC2 | 下一個優先驗收的 low-latency zero-shot streaming 候選 | `priority candidate / PLANNED`，未安裝、未驗證；[上游宣稱 40 ms chunk 與 110 ms first-packet](https://github.com/ASLP-lab/MeanVC2)，不代表本機結果 |
| Streaming VC | X-VC | 下一階段 codec-space zero-shot streaming 候選 | `research-candidate`；[官方程式碼](https://github.com/Jerrister/X-VC) 已發布，本機來源、權重、license 與 runtime 尚未 intake |
| Streaming VC | Seed-VC realtime fork | worker/ring-buffer/device/VAD 路徑比較 | `candidate / PLANNED`，先做獨立 source/revision/runtime intake，不與既有 venv 混用 |
| Research candidates | RT-VC 與後續新方法 | 追蹤 articulatory／streaming VC 方向 | `research-candidate`，沒有固定 revision/runtime 證據前不進可執行矩陣 |
| Speech Reconstruction | CosyVoice2 | STT + reference TTS baseline | runtime evidence `PASS`；只作 offline baseline |
| Speech Reconstruction | Fun-CosyVoice3 | 與 CosyVoice2 A/B | `candidate / PLANNED`，未安裝／未驗證 |
| Speech Reconstruction | Breeze TTS 2 | voice design／reference clone | runtime evidence `PASS`；本機不能分類為 LIVE |

Streaming VC 與 Speech Reconstruction 分開報告。後者重新生成內容、韻律、呼吸與停頓，不宣稱完整保留原始聲學表演。

### Streaming VC 研究順序

Seed-VC upstream 保留為已建立的本機 baseline；下一順位是完成 MeanVC2 的來源、權重／授權、相依性與隔離環境 intake，再以同一 corpus、audio-rack 和 LIVE_GATE 比較。MeanVC2 完成同一組驗收後，再把 X-VC 作為已發布 streaming zero-shot code 的下一候選；後續新方法沿用相同 intake，不因論文或上游 latency 宣稱直接升級主線。Seed-VC realtime fork 是獨立的執行路徑比較，不能替代 model-to-model evidence。

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

完整 capture → backend → audio-rack → virtual routing 的 `e2e_first_packet_ms <= 5000` 是即時候選硬門檻。`LIVE` 還要求本次 physical mic input/final output artifacts 與 hash/identity、至少 600 秒連續零 dropout/underrun，以及人工聽評；未達這些條件時分類 `LIVE_CANDIDATE` 或 `WAITING`。只有 offline WAV、backend inference、RTF、model loading、UI HTTP 200 或 `available_providers` 不足以分類。

使用 [`docs/live-gate.md`](live-gate.md) 與 `tools/live-gate-validate.py`：

- `LIVE`：真實麥克風完整鏈路在 5 秒內，並具備 artifacts/identity、600 秒穩定性及人工聽評。
- `LIVE_CANDIDATE`：完整 artifacts/identity 與首包延遲符合門檻，但仍缺長時穩定性或人工聽評。
- `OFFLINE`：可產生有效輸出，但超過 5 秒或沒有完整即時鏈路。
- `WAITING`：證據尚未補齊。
- `BLOCKED`：schema、artifact、輸出或 runtime 有明確錯誤。

即使完整 `LIVE` PASS，也不等同自然度、相似度或其他硬體／聲線的品質 PASS。600 秒、零 dropout／underrun 是目前研究驗收門檻，不是產品保證。

## UI 設定流程驗收

Seed-VC 官方 GUI 的設定操作只有在以下條件全數通過時，才可標成可直接使用：

1. `--preflight` 確認 source、checkpoint、reference、GUI dependency 與輸入／輸出裝置方向。
2. user-flow 將 reference、host API、裝置及即時參數送入官方 `start_vc` event；所有 widget 更新都成功，測試不得吞掉設定錯誤。
3. PortAudio duplex stream 可啟停；四組 reference 的 callback 輸出均為 finite、non-zero，且與注入 source 不相同。
4. 啟用 loopback 時，VB-CABLE recording endpoint 收到 finite、non-zero 的同案輸出。

這個 GUI user-flow 只驗證設定、backend 與 VB-CABLE 的部分路徑，不等同實體麥克風、full-chain audio-rack、600 秒穩定性或 LIVE PASS。2026-09-26 官方修復 Python 3.10.11 Tcl/Tk Support 元件後，Seed-VC venv preflight 與四個 GUI settings／backend／loopback case 已 PASS；完整範圍與限制見 [`seed-vc-verification-latest.md`](seed-vc-verification-latest.md)。

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
- MeanVC2、X-VC、Seed-VC realtime fork、CosyVoice3 目前只有 candidate intake 文件，沒有本機安裝或模型 PASS。
- audio-rack 已建立 profile、routing、preset 與 `rack-evidence-v1` schema；VB-CABLE／Voicemeeter synthetic route smoke `PASS`，但實體 VST chain、完整 mic E2E、blind listening 仍 `PLANNED/WAITING`。
- 任何與 RVC packaged VCClient、CUDA provider、模型 ready gate 有關的判定仍以各自最新 verifier 為準；不能被新的架構文件覆蓋。
