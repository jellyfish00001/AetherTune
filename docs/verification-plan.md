# 驗證計畫與 Definition of Done

## 證據等級

- `P0`：來源/授權/版本文件證據。
- `P1`：本機命令、模型載入、檔案 hash 或裝置列舉證據。
- `P2`：離線音訊輸入輸出結果與人工聽測。
- `P3`：真實即時路由、loopback、延遲與終端應用收音證據。

編譯成功、頁面能開啟或單一 mock 不得單獨宣稱整條管線完成。

## Phase 0：環境與來源

- [x] 建立 `dataset/`、`models/`、`tools/` 骨架。
- [x] 登記上游來源、目前授權與未決版本。
- [x] 記錄本機 GPU、Python、FFmpeg 與已知阻塞。
- [x] 建立 Python 3.12 x64 隔離環境（`.venv`）。
- [x] 確認 FFmpeg/FFprobe 9.0.1 可執行與來源；目前以固定絕對路徑驗證。
- [ ] 在新 PowerShell 確認 `ffmpeg -version` 與 `ffprobe -version` 不需絕對路徑。
- [x] 確認 VB-CABLE、Voicemeeter 與實體麥克風可被 Windows；FFmpeg/PortAudio 列舉路徑已分開保留。
- [x] 建立 `tools/verify_wiring.ps1` 與最新 P1 報告；BLOCKED 會以非零 exit code 結束。
- [x] 合成 loopback 產生 WAV、metrics JSON 與 WAV SHA-256；只存在 WAV 不算 PASS。
- [x] 加入 sample RVC ONNX synthetic inference probe，記錄實際 executed provider；provider 清單不再單獨算推論成功。

## Phase 1：Dataset

- [x] 建立只讀 metadata audit 與 provenance manifest 工具。
- [x] 加入來源／授權／批次 register、空資料集 gate、疑似靜音 gate，以及重跑時保留人工 notes。
- [ ] 將具授權的原始音檔放入 `dataset/raw/`，再執行 `dataset_audit.py`。
- [ ] 來源具備明確使用權與 provenance。
- [ ] 原始資料為乾聲、單人、低底噪，並記錄取樣率/聲道。
- [ ] 完成切片；抽查 5、10、15 秒邊界與切點是否截斷子音。
- [ ] 變調擴增僅保留有理由的樣本，記錄 `+3/+5/-3/-5` 與工具版本。
- [ ] 以 manifest 記錄每個檔案的來源、處理鏈與 hash。

## Phase 2：RVC

- [x] RVC WebUI clone 到 `tools/external/` 並固定 revision。
- [x] RVC WebUI 依賴在獨立 `.venv` 完成安裝，`pip check` 通過。
- [x] Torch CUDA smoke test 成功識別 RTX 5060 Ti；不等同於模型推論已驗證。
- [x] HuBERT 與 RMVPE runtime 資產下載、hash 與 CUDA smoke test 完成。
- [x] RVC `pretrained/`、`pretrained_v2/` 與 `logs/mute/` 訓練資產完成下載。
- [ ] 使用具授權的真實乾聲完成離線 f0/推論檢核。
- [ ] 產出 `.pth` 與 `.index`，並依 `models/model-register.csv` 記錄訓練設定、資料批次與檔案 hash。
- [ ] 以未參與訓練的保留語句做離線驗證。

## Phase 3：即時 VCClient

- [x] VCClient `2.1.4-alpha cuda` 官方整合包已部署。
- [x] VCClient 本機 Web UI 回應 `HTTP 200`，內建示例頁可操作。
- [ ] 角色 `.pth/.index` 載入與 GPU 推論；目前整合包啟動時有 RTX 5060 Ti `sm_120` 相容性警告，必須用實際角色模型確認。

使用同一個角色模型與同一段固定測試語句，一次只改一個參數；`chunkSec`、`extraFrameSec` 單位都是秒：

| 階段 | 固定值 | 唯一變動值 |
|---|---|---|
| baseline | pitch +9、chunkSec 0.50、extraFrameSec 0.08、index 0.50、RMVPE | 無 |
| chunk | 其他同 baseline | 0.25 / 0.50 / 0.75 s |
| extra | 其他同 baseline | 0.04 / 0.08 / 0.12 s |
| pitch | 其他同 baseline | +6 / +9 / +12 |
| index | 其他同 baseline | 0.00 / 0.50 / 0.70 |
| VST | 最佳 RVC 組合 | Graillon bypass / active |

- [ ] 每 case 記錄模型載入、CPU/GPU、破音、斷音與端到端延遲。
- [ ] 每 case 記錄 model/hash、測試句、持續時間、p50/p95 延遲、underrun、斷音與 artifact；暫定日常 gate 是 10 分鐘零斷音／零 underrun、p95 ≤ 250 ms。
- [ ] 以固定錄音與人工聽測比較自然度、咬字、音高穩定度。
- [ ] 只有在矩陣證據支持時，才把某一組設定提升為預設值。

## Phase 4：VST 與路由

- [x] Light Host Modern `v1.3.1` portable 已部署並可啟動。
- [x] Graillon Free `3.2` VST3/VST2 已安裝。
- [ ] 由 Light Host 掃描 Graillon、設定 input/output、完成離線/loopback 音訊通過。
- [ ] 以 Chromatic、慢速、低深度的修音候選做 A/B；不得只記參數、不記聲音結果。
- [x] 實際列舉 VB-CABLE/Voicemeeter 裝置名稱，記錄播放端與錄音端方向。
- [x] 以合成音完成 VB-CABLE 與 `Voicemeeter Input → B1 → Voicemeeter Out B1` virtual route smoke；保存 WAV、JSON、SHA-256 與 Remote API level evidence。
- [ ] 完成「麥克風 → VCClient → VST → 虛擬輸出 → loopback 錄音」P3 證據。
- [ ] 最後才以 Discord/OBS 測試收音；確認對方端或錄影檔聽到的是後製訊號。

## 完成定義

只有當 Phase 1–4 各自有可追溯證據，且實體 P3 loopback/終端測試成功，才能標示「系統完成」。目前狀態為 `wiring deployed; synthetic virtual route smoke PASS; role dataset/model, audio-rack full-chain and physical P2/P3 evidence pending`。最新唯讀結果見 `docs/wiring-verification-latest.md`。

## 新架構追加的研究 Gate

既有 Phase 1–4 保留作 RVC／Windows wiring 歷史基線；新的跨 backend 研究必須另外通過以下分層，不能用既有 RVC 的成功或失敗代替：

### Phase 5：Common Audio Rack

- [ ] 在 `audio-rack/` 登記 plugin／host／route profile、版本、license classification 與來源。
- [x] 建立 VB-CABLE／Voicemeeter virtual route smoke evidence；這不等同 audio-rack plugin full-chain。
- [ ] 以同一 backend、同一 source、同一 output route 完成 `Post-FX bypass`。
- [ ] 以同一組輸入完成 `Post-FX full-chain`。
- [ ] 保存 bypass latency、full-chain latency、`delta_latency_ms`、WAV、metrics JSON 與 hash。
- [ ] Pitch correction 保持 `optional`；未經人工聽測不得變成所有 backend 的預設。

### Phase 6：LIVE_GATE

- [x] 建立 `docs/live-gate.md` 的 `aethertune-live-gate/v1` evidence 契約。
- [x] 建立 `tools/live-gate-validate.py`，分類 `LIVE`／`OFFLINE`／`WAITING`／`BLOCKED`。
- [ ] Seed-VC 完成 mic／PortAudio → backend → audio-rack → virtual route → loopback 的 60 秒 screening。
- [ ] 通過至少 600 秒 stability、zero dropout／underrun，才可稱為 `live_candidate`。
- [ ] 所有 first-packet timing 必須是完整鏈路，不可只填 inference 或 RTF。

### Phase 7：三層比較

- [ ] `benchmarks/corpus/` 建立有授權且固定 hash 的測試語料：對話、快語速、氣音、大笑、驚叫、嘆氣、拉長音、音域變化、中日英混合、60 秒與 10 分鐘。
- [ ] `benchmarks/live/` 完成 Live Technical paired run。
- [ ] `benchmarks/quality/` 完成同 sample rate／loudness policy 的 Acoustic Objective paired run。
- [ ] `benchmarks/subjective/` 由人類完成 blind listening；Agent 不代填自然度、相似度或情緒保留分數。

### Phase 8：候選 intake

- [ ] Seed-VC realtime fork：固定 revision、來源、license、獨立 environment 與實測 gate。
- [ ] MeanVC2：確認上游 code／checkpoint／依賴／license、RTX 5060 Ti 相容性，再進固定 corpus。
- [ ] Fun-CosyVoice3：與 CosyVoice2 做 isolated A/B；先確認 model snapshot、license、RTF／TTFA 與人工聽測。

在 Phase 5–8 尚未完成前，README 的新架構只是正確的研究方向與證據邊界，不代表新 backend 或共用 audio-rack 已可直接使用。
