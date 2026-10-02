# Desktop 資料效能基準

日期：2026-10-02（Asia/Taipei）。任務：BASE-01、PERF-02、MOD-02／F03、F07、F08、N02、N03。**本頁擁有合成資料的 SQLite、匯出及 Python service snapshot 基準、局部優化比較與投影模組驗證**；任務狀態在 [docs/status.md](../../status.md)，方法與完整驗收條件在[驗證計畫](../../specs/verification-plan.md#optimization-acceptance)，重跑入口在 [Agent 維護手冊](../../../.agent/reference/agent-maintenance-guide.md#storage-baseline)。

最新進展：已推送的[快照排序優化](#snapshot-order-comparison)後，接續[抽離快照投影模組](#snapshot-projection-module)。以下保留各輪基準及判定，不能將不同目錄／時間的量測直接當成 before／after。

## 判定與範圍

**PASS：10／100／1,000 筆各 3 個隔離案例，共 9 個案例。** 每個案例核對 request／Transcript／snapshot 筆數、SQLite integrity、DB 與 JSONL 的 request identity、文字內容、TXT 行數、關閉後 session 結束時間及最終匯出 hash。關閉後 fixture worker 全部退出。

本節是修改產品效能程式前的 baseline。BASE-01 整體仍 IN_PROGRESS：UI 更新／CPU／RSS／IPC transport、cold／warm／切換、模型與音訊品質尚未在同一固定矩陣量測。本次沒有操作桌面、錄音或播放；使用者正在使用電腦，Computer Use 暫緩。

## 固定條件與來源

| 項目 | 本次內容 |
|---|---|
| 程式 | `d478ee28c7a8b5e0db29792c792d6183ac7c586f` 加未提交的量測工具；production `service.py`／`storage.py` 未改 |
| runtime | repo `.venv` Python 3.10.11，Windows build 26200；單一 Python 程序循序執行，沒有宣稱宿主機負載受控 |
| 時間 | 2026-10-02 01:31:57～01:33:19（UTC+8）；report 另存 UTC 起迄 |
| 資料 | 固定文字「這是隔離的資料效能測試，沒有生成或播放語音。」；真實 voice catalogue 複製進每個 fixture，固定 `official-cosyvoice-sample` profile、合成 route；report 保存文字與 catalogue hash |
| 隔離 | 每案例全新 DB／session；只允許新建於 repo `artifacts/` 下，拒絕既有目錄；不讀寫使用者的 canonical DB |
| 模型／裝置 | 無；`NoGeneration` 禁止生成、`NullPlayback` 不開音訊。直接建立合成 terminal history，`completed` fixture 不代表真實發聲完成 |
| 取樣 | 每個資料量 3 案例；每案例 query／export／snapshot／JSON serialization 各 5 次。先取各案例 median，再列 3 個 median 的中位數與範圍，不將少量樣本換算 p95 |

執行命令（repo root）：`./.venv/Scripts/python.exe app/tests/baseline-storage.py --output artifacts/desktop/baseline-20261002/storage`，exit 0。原始 samples、每次新增資料的 commit＋export 耗時、最終檔案 bytes／hash、source fingerprints 都保留在 `artifacts/desktop/baseline-20261002/storage/report.json`；該 report SHA-256：`e4f6cad535d66eb15688e7014954ba076aab83a23566e9f07fb0d1981acd12c6`。

| 受測 source | SHA-256 |
|---|---|
| `app/tests/baseline-storage.py` | `5725a078d069cfa5dbb7591139ae5ead87715aca4fd978923a995194da2ef235` |
| `services/tts/service.py` | `424fec902adba96c5ed3fb208b537062f67de5549c88f6ea1e68aaf883672373` |
| `services/tts/storage.py` | `3ccb868196a0cc5a7b3d47356cdd851ebf84067d2555f8fc739c210effc13cd7` |

## 結果

耗時單位 ms。括號為 3 個案例 median 的最小～最大值；完整 raw samples 以 report 為準。

| 筆數 | snapshot | 完整 export | JSON serialization | snapshot UTF-8 bytes |
|---|---|---|---|---|
| 10 | 0.280（0.272～0.320） | 0.601（0.601～0.732） | 0.104（0.097～0.105） | 25,683 |
| 100 | 2.356（2.158～2.881） | 3.317（3.231～4.024） | 0.980（0.935～1.387） | 215,683 |
| 1,000 | 32.646（28.096～37.877） | 45.873（40.331～48.453） | 12.084（11.689～14.910） | 2,116,583 |

| 筆數 | request query | Transcript query |
|---|---|---|
| 10 | 0.066（0.061～0.085） | 0.055（0.055～0.055） |
| 100 | 0.628（0.567～0.816） | 0.482（0.471～0.627） |
| 1,000 | 13.223（10.866～14.544） | 7.244（6.567～7.791） |

snapshot timing 包含組裝完整 queue／Transcript 等資料，serialization 另外量；bytes 是 Python JSON 編碼結果，**不是已量測的 IPC 流量或 UI render 成本**。`record_completed_including_export_ms` 是資料從 1 筆增加至 N 筆時的序列，不是固定 N 筆的重複 latency，不能與上表混池比較。

## 量測工具修正與驗證

初輪 `artifacts/desktop/baseline-20261001/storage/report.json` 在 `service.close()` 前記錄匯出 hash；close 會補寫 `session.json` 的 `ended_at`，所以後續獨立檔案核對失敗。原始失敗證據保留，不將初輪的整體 PASS 當成最終資料驗證通過。工具改成先 close、驗 DB／匯出一致，再記錄最終 hash；本頁上表採用修正後完整重跑的 9 案例。

修正後另行讀回所有最終匯出檔案與 source fingerprints，bytes／hash 全部吻合。`py_compile`、非 artifacts 路徑拒絕、既有 evidence 目錄拒絕皆通過；後兩者預期 exit 2，沒有覆寫。`npm run test:contracts` 亦 PASS（6 manifests、Manual TTS 等契約及 negative fixtures），該檢核與合成量測資料的範圍分開。

初輪相同 production source 的耗時範圍與本輪不同，表示跨輪宿主條件的波動不可忽略；本次只改量測收尾，**不能將兩輪數字差異宣稱為產品加速**。日後須在同條件、交錯 before／after 並保留波動的前提下判定改善。

## 後續實作依據與限制

- 初始 source 的完整快照大小隨歷史筆數增加，`snapshot()` 以 list membership 排除已列入的 request，`record_completed()` 每筆重寫整個 session export。後續已處理 list membership，見下節；深拷貝及完整 export 仍需進一步評估。
- PERF-02 應先補事件／polling 次數、實際 transport／render／RSS；再決定有界快照、query／export 政策，保留完整 durable history、queue identity 與完成播放才寫 Transcript 的語意。
- 資料量測結果不等於模組化完成。MOD-01／02、DATA-01 的介面、單一 writer、migration／restore 條件仍按架構與任務列執行。
- 尚未量測長時間記憶體、cold cache、storage commit 的獨立成本、模型冷／暖啟動、GPU／音訊與 physical／LIVE；本報告不提升那些狀態。

<a id="snapshot-order-comparison"></a>
## PERF-02 子範圍：快照排序優化

基準 commit `27297026b9488c127d261e15a981214658dcd8e0`（已推送），after 為其上的工作樹修改。只改 `SpeechService.snapshot()` 的歷史 ID 篩選：先將 current／pending ID 建成 set，再依 `_requests` 的插入順序附加其他歷史。單次查找從掃描 list 改成 set membership，避免歷史部分的 O(n²) 比較。完整 queue／Transcript、profile／route、深拷貝、ACK、持久化與資料 writer 均維持原行為；沒有新增 cache、分頁或模組依賴。

這個子範圍已有 BASE-01 的資料基準，且不改 UI／IPC 或 DB schema，所以可在 UI-01 等待桌面操作時先做。跨 UI 訂閱、export 政策及整體模組拆分仍遵守任務列的其他依賴，PERF-02 不標 DONE。

### 定位與比較方法

先以 `cProfile` 在複製的 1,000 筆合成 fixture 執行 20 次舊 snapshot，保存 `artifacts/desktop/snapshot-profile-20261002/snapshot-before.prof` 與同目錄 `probe.py`。instrumented cumulative time 以 request 深拷貝占比最高，另有歷史 list membership 成本；profiler 有額外負擔，**不以其時間當 latency baseline，也沒有將排序稱為最大瓶頸**。

比較工具新增 `--compare-snapshot-ref`：從 repo 固定 commit 取出舊 snapshot 方法，使用目前相同 service／store／fixture 交錯執行 before／after。其他依賴固定目前程式；這只驗 snapshot 方法變更，不能用來比較任意兩個完整產品版本。先暖機，再於每案例各量 20 次，交替先後順序；10／100／1,000 筆各 3 案例，共 180 對完整 payload 等值檢查。p95 取每組 20 筆的 nearest-rank 第 19 筆，不混合案例。

實際命令：`./.venv/Scripts/python.exe app/tests/baseline-storage.py --compare-snapshot-ref 2729702 --output artifacts/desktop/snapshot-profile-20261002/comparison`，exit 0；執行時間 2026-10-02 01:44:02～01:45:27（UTC+8）。包含全部 before／after samples 的 `comparison/report.json` SHA-256：`60c5c460543ef235ea1fa46c47065c5ceb765bbe21919dca61277837d730e6dc`。

| 當輪 source | SHA-256 |
|---|---|
| `services/tts/service.py` | `5905a3d7108da39bc4d293edaa5e9406295e7c64b07c280a6c4f72a07588029b` |
| `app/tests/baseline-storage.py` | `7bba74be316dee37f364418cb3e220bcfa90e36244078b5e761383b5724ca60d` |

### 1,000 筆的成對結果

| 案例 | before median ms | after median ms | 降低 | before p95 ms | after p95 ms |
|---|---|---|---|---|---|
| 1 | 39.591 | 32.861 | 17.0% | 50.965 | 41.140 |
| 2 | 35.822 | 30.296 | 15.4% | 45.503 | 36.314 |
| 3 | 35.286 | 28.209 | 20.1% | 40.126 | 37.448 |

三輪的 median 差值至少 5.526 ms，大於 before 三輪 median 的範圍寬度 4.305 ms，且每輪改善超過 10%，符合本次資料子範圍的初始工程準則。10／100 筆的 median 降幅分別只有 1.6～5.1%／3.5～4.8%，未達 10% 準則；9 案例的 after median／p95 均未退步。這是本機固定 fixture 的結果，不保證真實長時間使用的同等比例。

所有成對 payload 完全相同，沒有藉由刪欄位或省略 terminal history 降低成本。此輪 fixture 目錄較長，`profile_path` 造成 bytes 與初始基準不同；同一成對比較的 before／after 路徑及 bytes 相同，不能跨兩輪目錄比較傳輸量。

### 相容性與剩餘工作

- `./.venv/Scripts/python.exe -m unittest services.tts.test_service -v`：38 tests PASS，13.706 秒，沒有 skip；log 在 `artifacts/desktop/snapshot-profile-20261002/service-tests.log`。新增 mixed current／reordered pending／completed／cancelled／failed history 順序及深層快照隔離回歸；既有 FIFO、取消、storage failure 與 Windows／WSL fixture 清理亦通過。
- 9 個資料案例的 DB／exports 一致，worker close 後回收；另行核對所有最終 export 與 source hash 通過。fake adapters／PortAudio 與短 WSL ownership fixture 不算真模型或實體音訊驗收。
- 未更動 UI、Rust、schema、資料儲存格式或模型程式，不需要 migration；回退此 snapshot 修改即可恢復舊算法。沒有重建或啟動 Desktop，也沒有進行 Computer Use。
- 深拷貝、全量 payload、重複訂閱／polling 與完整 export 尚未改；先補相應資源／IPC／UI 量測，再決定 MOD-01／02、DATA-01 與 PERF-02 的後續切分。

<a id="snapshot-projection-module"></a>
## MOD-02 子範圍：快照投影模組

基準是已推送的 `e7f5c34a46321149abe53efc0e256d99cc5a98ac`；本輪只將 queue 排序、request／profile 公開欄位與深拷貝搬至 `services/tts/snapshot.py`。`SpeechService` 仍在原鎖內取得 queue，仍擁有 DB、worker、adapter 與生命週期；新模組只有資料輸入／輸出，不反向 import service、storage 或 audio。未加入 cache、改欄位或調整持久化格式，既有 set membership 排序保持不變。

先前試驗曾略過不可變 scalar 的 `deepcopy`，三輪 median 降低只有 5.92%、3.88%、8.63%，未達 10% 準則，因此沒有採入產品。試驗 source 與 raw samples 保留在 `artifacts/desktop/snapshot-copy-20261002/explore.py`、`exploration.json`；目前投影仍逐公開欄位深拷貝，也維持跨欄位 alias 的隔離。

### 功能相容與量測邊界

- `./.venv/Scripts/python.exe -m unittest services.tts.test_service services.tts.test_snapshot -v`：41 tests PASS，55.203 秒，沒有 skip。log 為 `artifacts/desktop/snapshot-copy-20261002/service-tests.log`；新增純投影案例覆蓋 nested／跨欄位複製隔離、catalogue 隱藏 `profile_path` 而 request 保留路徑、空 queue 與 terminal history，原 service 的順序／取消／storage／cleanup 回歸一併通過。
- 新模組可單獨 import，沒有載入 service／storage／adapters／playback／numpy；`app/dev.ps1 -Test` 已納入純投影測試。沒有執行整套 Desktop UI／Rust 測試，這些檔案未受影響。
- module／direct script 的 service `--help` 均 exit 0，`app/dev.ps1` PowerShell parse 無錯。工具拒絕少於 20 樣本、未指定比較 ref 卻指定非預設樣本數、非 artifacts 或既有輸出目錄；合成已 import 投影的舊版本亦正確拒絕。檢核保存於同目錄 `tool-checks.json`，未建立使用者 DB 或啟動 service。
- 比較工具本輪改為凍結 Git 基準的 service class 與 private helpers，使用不執行 constructor 的比較物件共讀同一 fixture。先前只取 snapshot 方法的方式在 helper 搬移後不再適用；外部依賴仍是目前版本，不能作完整產品版本比較。若 Git 基準已 import 獨立 snapshot 模組，工具會拒絕，必須先補版本依賴隔離。
- 每輪仍是 10／100／1,000 筆各 3 個案例，全部 payload 逐對相等，並於 close 後驗 DB／exports 一致與 worker 回收。report 的 `status: PASS` 表示資料及相容性斷言通過，**不會自動判定效能門檻通過**。

### 效能複核

第一輪每案例各 20 次，在 TTS tests 同時執行時量測；9 個案例 median 變化在 -13.78%～+4.41% 之間，但 4 個案例 p95 增加超過 10%。原始 `artifacts/desktop/snapshot-copy-20261002/comparison/report.json` 保留，SHA-256 為 `0cd85989d8d754b92268adcda87857681dc9aa76717b86db91c1209bc0865d87`；不能因資料檢核 PASS 就忽略 latency 波動。

第二輪改為每案例各 100 次、nearest-rank p95 第 95 筆，量測期間不再同時執行其他測試；沒有宣稱使用者電腦的其他負載受控。命令為 `./.venv/Scripts/python.exe app/tests/baseline-storage.py --compare-snapshot-ref e7f5c34 --comparison-samples 100 --output artifacts/desktop/snapshot-copy-20261002/comparison-100`，exit 0；時間 2026-10-02 13:14:31～13:16:50（UTC+8）。900 對完整 payload 全部相同；report SHA-256 為 `0f099d2c906cb7eeb9342271e2b2857b31755c066a8e997611ee660eafd73235`。

| 筆數／案例 | before median ms | after median ms | before p95 ms | after p95 ms | p95 變化 |
|---|---|---|---|---|---|
| 10／1 | 0.372 | 0.384 | 0.537 | 0.691 | +28.68% |
| 10／2 | 0.256 | 0.258 | 0.312 | 0.340 | +9.11% |
| 10／3 | 0.258 | 0.257 | 0.287 | 0.286 | -0.45% |
| 100／1 | 3.790 | 3.717 | 4.722 | 4.850 | +2.70% |
| 100／2 | 3.969 | 3.924 | 6.192 | 6.097 | -1.53% |
| 100／3 | 4.687 | 4.922 | 9.796 | 11.146 | +13.78% |
| 1,000／1 | 40.828 | 40.934 | 73.139 | 65.260 | -10.77% |
| 1,000／2 | 43.181 | 44.045 | 61.734 | 62.783 | +1.70% |
| 1,000／3 | 45.451 | 44.826 | 69.593 | 69.385 | -0.30% |

**判定：功能相容 PASS；效能驗收 WAITING。** 第二輪所有 median 變化介於 -1.92%～+5.01%，1,000 筆的 median／p95 均未增加超過 10%；但 10／1、100／3 的 p95 仍超過門檻，不能宣稱整體無退步，也不能直接將差異歸因於主機。保留兩輪、不挑選有利樣本；待可控制負載時以同一基準、完整矩陣複核，必要時加入相同實作的 A/A 控制量測，區分工具／環境波動與抽離成本。沒有速度提升主張。

| 第二輪 source | SHA-256 |
|---|---|
| `services/tts/service.py` | `7f32a62c643258e459ca7aa38d7d8789a6617267c051395061381dc8c30b0d97` |
| `services/tts/snapshot.py` | `ff6fb0dcf051097038daaa895e68621cb984762bd84c3cee2303ce04c3a638c5` |
| `app/tests/baseline-storage.py` | `6f6c3c07775d7f91302e9549b30268fe33b794e8fe899e07bad2fcf7c26848ec` |

第二輪目前 source fingerprints、兩輪最終 export bytes／hash 及 median／p95 重算全部相符，獨立核對在 `artifacts/desktop/snapshot-copy-20261002/comparison-audit.json`。第一輪 source 指紋是增加樣本參數之前的版本，保留原值。

### 交接與回退

本輪不需 migration；回退 `service.py` 的投影呼叫並移除新增模組即可恢復基準實作，測試／量測入口需同步移除該模組引用，沒有使用者資料轉換。MOD-02 整體保持 IN_PROGRESS：本次拆分仍待效能驗收，validation、queue policy、執行協調與 evidence 亦未拆分；後續不可把純投影的功能測試當成全部完成。Computer Use／可視 UI／實體音訊／LIVE 都沒有執行，也不提升狀態。
