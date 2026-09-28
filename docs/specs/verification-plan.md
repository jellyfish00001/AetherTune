# 驗證計畫與 Definition of Done

**文件邊界：**本頁只定義要收集的證據、執行順序與完成條件，**不記錄某輪是否通過**。`LIVE` 分類與門檻只由 [live-gate.md](live-gate.md) 定義；實際 PASS／WAITING、日期、命令、hash 和 artifact 依[文件權責地圖](../README.md)查對應驗證報告。不要把本頁的待測項目當成已完成狀態。

## 證據等級

| 等級 | 回答的問題 | 不能代替 |
|---|---|---|
| P0：來源 | revision、license、模型和音訊來源是否可追溯 | 安裝或執行 |
| P1：環境 | 依賴、模型 hash、裝置列舉及實際 provider 是否符合 | 有效輸出音訊 |
| P2：音訊 | 本輪 source／reference → backend 的 finite、非零 WAV、hash 與客觀檢查 | 實體麥克風或完整路由 |
| P3：線路 | physical mic → backend → Rack → virtual route → 終端 loopback 的同輪 artifact | 人工自然度與目標音色評分 |

每項測試都要記錄 run id、輸入與模型 hash、runtime、裝置／provider、命令、輸出 artifact、判定及未解事項。編譯、HTTP 200、UI 可開啟、provider 清單或合成 tone 只回答它們自己的檢查，不能提升其他層級。

## Phase 0：環境與來源

1. 固定上游 source／revision／license；登記模型、reference、依賴與本機位置。權威登錄在 [source-audit.md](../reference/source-audit.md)、`models/*register.csv` 和 `dataset/manifests/`。
2. 對每個隔離 runtime 檢查 Python／Torch／CUDA、FFmpeg／FFprobe、模型 hash 和裝置方向；`tools/voice-backend-check.ps1` 是唯讀盤點，實際音訊需另測。
3. 以 `tools/verify_wiring.ps1` 核對 VB-CABLE／Voicemeeter 端點；synthetic loopback 要保存 WAV、metrics 與 hash，且只歸為線路 smoke。

## Phase 1：Dataset 與角色資料

1. 原始資料須有明確使用權、單人乾聲、取樣率、聲道與來源；用 `tools/dataset_audit.py` 查空集合、疑似靜音、重複、來源與 hash。
2. 切片後抽查 5／10／15 秒邊界與子音；變調擴增只保留有理由的樣本，記錄參數、parent hash 和工具版本。
3. RVC 訓練後將 `.pth/.index` 配對、f0、訓練資料批次和 hash 寫入 model register，使用未參與訓練的保留語句做離線音訊測試。具體訓練操作由[訓練手冊](../guides/model-training-guide.md)擁有。

## Phase 2：Backend 輸出

1. 先以固定 source／reference 或人工核對文字，對每個 backend/profile 保存本輪 WAV／stream 與 runner manifest；先確認可解碼、finite、非零、hash 和實際 device/provider。
2. Streaming VC 的 Seed-VC、MeanVC2、X-VC、RVC 各自獨立報告；Speech Reconstruction 的 STT draft、reference transcript 與 TTS WAV 不與 VC 的表演保留結果混成單一品質分數。
3. 同一 corpus、sample rate／loudness policy 下比較內容正確性 proxy、RMS、peak、clipping、DC、silence 和速度；RTF／backend timing 不能作完整鏈路首包時間。

## Phase 3：VCClient 與 Windows 路由

VCClient packaged runtime 要獨立於專案 RVC `.venv` 驗證。角色 slot、model/index、f0、實際 GPU provider、有效 output、chunk 和 dropout 依[VCClient gate](vcclient-runtime-gate.md)執行；Web UI 回應不構成音訊通過。

每次只變動一個參數，使用同一角色模型與測試句；以下是**待測矩陣**，不是已採用預設值：

| 階段 | 固定條件 | 變動值 |
|---|---|---|
| baseline | pitch +9、chunkSec 0.50、extraFrameSec 0.08、index 0.50、RMVPE | 無 |
| chunk | 其他同 baseline | 0.25／0.50／0.75 s |
| extra | 其他同 baseline | 0.04／0.08／0.12 s |
| pitch | 其他同 baseline | +6／+9／+12 |
| index | 其他同 baseline | 0.00／0.50／0.70 |
| VST | 最佳 RVC 組合 | Graillon bypass／active |

各 case 保存 model/hash、測試句、持續時間、p50/p95、underrun、破音、WAV 和 log；矩陣證據支援後才調整預設值。Windows 操作順序只在[路由手冊](../guides/operation-guide.md)，線路的當次結果只在[線路驗證](../verification/audio/wiring-verification-latest.md)。

## Phase 4：Rack 與完整線路

1. 在同一 source、backend/model、hardware、route 下保存 `Post-FX bypass` 和 `Post-FX full-chain` 兩筆 WAV／metrics／hash，量實際 `delta_latency_ms`。Plugin、preset 和 paired evidence 欄位由 [`audio-rack/`](../../audio-rack/README.md) 擁有。
2. 先證明 backend → CABLE，再證明 Light Host／VST → Voicemeeter B1，最後在 Discord／OBS 等終端保存 loopback；每段的 input/output identity 必須能串回同一 run。
3. 以 physical mic 進入完整路徑，再按 [LIVE gate](live-gate.md) 執行首包、連續穩定、dropout／underrun 與 human listening；局部 CABLE capture 不代替完整鏈路。

## Phase 5：固定比較與候選 intake

固定 corpus 至少涵蓋對話、快語速、氣音、笑聲、驚叫、嘆氣、拉長音、音域變化、中日英混合、長句與長時間案例，且每筆有授權與 hash。[`benchmarks/`](../../benchmarks/README.md) 分別擁有 Live Technical、Acoustic Objective、Human Listening；人工自然度、相似度與表演評分不可由 Agent 代填。

新候選（例如 Seed-VC realtime fork、CosyVoice3）先做獨立 source／model／license／runtime intake，再進固定 corpus 與同一 Rack／LIVE gate。MeanVC2／X-VC 任何新 revision 或 profile 也重新走相應 gate；既有安裝結果只看[後端驗證](../verification/backends/backend-install-test-latest.md)。

## 完成定義

只有 P0–P3 都能由本輪可重跑證據串起、Rack bypass/full-chain 可成對比較、終端確實收到指定 backend 的聲音，並完成 [LIVE gate](live-gate.md) 所需長時間與人工驗收，才能宣稱完整即時鏈路完成。局部 PASS 保持局部分類；缺項清楚記為 `WAITING` 或 `BLOCKED`。
