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

<a id="optimization-acceptance"></a>
## UI、效能與模組化的驗收

本節定義[任務進度](../status.md)中 BASE／UI／MOD／DATA／PERF 的共同完成條件；這些是接下來的檢核規格，不是已量測成果。各任務可只執行受影響的測試，不要求每次文件修改重跑模型。

### UI 與操作流程

| 情境 | 驗收重點 |
|---|---|
| Full／Compact／Mini | 基準 logical viewport 1040×740、420×490、420×74，TTS Quick Input 420×260；另核對 Windows 125% DPI。主操作可達，長裝置名稱與英文不遮擋控制，沒有水平溢出 |
| 輸入與切換 | 鍵盤／IME 不誤送，草稿、已接受 Queue、route／FX 快照不因語言／layout／頁面切換而改變；繁中／英文標籤與可及性名稱一致 |
| 空白／載入／忙碌／錯誤 | 說明目前輸入與去向；真實狀態呈現排隊／載入／生成／播放／停止。不可用按鈕有原因；失敗提供可執行下一步，不靜默成功或盲目重送 |
| 原生系統操作 | fresh App PID 驗證 drag／lock、click-through 解除、Tray、hotkey、Exit／重啟；失敗需分辨產品缺陷與測試定位問題，不能只移除斷言 |
| 實際發聲 | preview／mock 只驗畫面及 payload；新增或改音訊流程需另用 native request、生成 WAV、output／capture、Transcript 及 cleanup 串起證據 |

先用內建 Browser／一般 Browser 重現可見狀態，再用 Playwright／CDP 做可重跑斷言，修改後兩者複核。每份報告記工具、URL／route、viewport／DPI、actions、assertions、console／network、screenshots／trace、native 或 mock 邊界。某層不可用明列 WAITING；沒有操作的系統匣不能由物件文字讀回推定實體點擊通過。

### 效能 baseline 與改善判定

| 範圍 | 固定案例／資料 | 必須量的指標 |
|---|---|---|
| VC 載入／處理 | 相同 commit、engine、模型／reference hash、precision、block／lookahead、端點與 FX；cold 與 RUNNING 後分報 | load／warmup、首個非零輸出、model p50／p95、RTF、backlog／drops、underrun／overrun、CPU／GPU memory；端到端另量 |
| TTS cold／warm／切換 | 固定文字、voice／reference、seed、引擎參數、route／FX；cold、同 worker warm、切 engine、取消後重載各獨立案例 | queue wait、model load、generation、完整 WAV 可用、postfx、first playback callback、完成播放、Stop 清理時間與 worker identity |
| UI 更新 | Full／Compact／Mini、idle／active／hidden，各記錄 60 秒；包含事件湧入與漏事件恢復 | IPC 次數／bytes、in-flight 數、update／render 時間、CPU／RSS；訂閱卸載與終態到達，不因停 poll 失去更新 |
| DB／長 Session | 隔離測試 DB 的 10／100／1000 筆 request／Transcript，固定文字長度；同一程式與磁碟 | snapshot bytes／耗時、query／commit／export latency、檔案 bytes、UI render／RSS；1000 筆是合成儲存測試，不跑 1000 次模型或冒充音訊穩定 |

初始量測方法：每個受影響配置至少 3 次 cold 記 median／range，warm 至少 20 次記 median／p95 與樣本數；不足就明列樣本限制，不混池推算 p95。UI／storage 案例重跑 3 次。原始 samples、失敗輪次、測量工具與起迄事件都需保留；不同引擎、硬體、DPI、路由不能直接平均。昂貴案例只跑本次受影響配置，已通過且未變動者不反覆重跑。

效能任務開始時由 BASE-01 鎖定目標指標與容許波動，再做修改。初始工程評估準則是：目標 latency 或工作量降低至少 10%，且大於 baseline 的重跑波動；其他關鍵 latency 不惡化超過 10%，無新增音訊失敗／drops／程序殘留。這是待 baseline 校準的內部準則，**不是使用者已承諾接受的等待時間，也不修改 LIVE gate**；若量測波動大於差異，結論只能是無法證明改善。單純拆檔以行為不變及無可辨識效能退步驗收，不強求速度提升。

品質與資源 gate 同時適用：輸出 finite／nonzero、sample rate／frame／hash evidence 完整，保留取消／錯誤 recovery；涉及音色／index／precision／buffer 的改善要成對聽評。Stop／Exit 後 audit 本輪 Windows／WSL ownership；長時間記憶體與音訊穩定按該任務時長與 [LIVE gate](live-gate.md) 分別報告。單次 VRAM 截圖或 60 秒 UI idle 不證明沒有 memory leak 或 600 秒 LIVE。

### 程式與資料模組化

- **依賴與介面：**按[架構](app-architecture.md#modular-boundaries)核對 import／call graph；共用模組不反向依賴 UI／orchestrator。原公開入口、ACK／error、request snapshot 與 schema 相容；變更前後相同 contract fixtures。
- **故障隔離：**用注入 adapter／playback／storage 驗 FIFO、取消、普通失敗後下一句、cleanup failure 阻擋、完成播放後 storage failure 不重播；共用 Post-FX 比較 bypass／wet／聲道／frames，不能只測模組可 import。
- **資料 migration：**舊 schema／設定 fixtures → 備份 → 升級 → 重開 → 重跑 migration，驗 row／identity、unique request transcript、favorites／settings；注入中斷驗 rollback／restore。未知版本明確拒絕，不靜默清空。
- **匯出與效能：**DB commit 成功後 export failure 仍可重建且不重播；改增量／分頁時覆蓋中斷、重試、不重複、不漏資料；先記錄 10／100／1000 baseline 再比較。
- **交付範圍：**報告給出改動模組、依賴前後、相容／migration 與 rollback；UI／native／音訊是否需補驗按實際影響判斷。實際命令集中於[Agent 維護手冊](../../.agent/reference/agent-maintenance-guide.md)，結果回寫 owner report，再更新任務列。

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
