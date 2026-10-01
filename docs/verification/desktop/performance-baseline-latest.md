# Desktop 資料效能基準

日期：2026-10-02（Asia/Taipei）。任務：BASE-01、PERF-02／F07、F08、N02。**本頁擁有合成資料的 SQLite、匯出及 Python service snapshot 基準／局部優化比較**；任務狀態在 [docs/status.md](../../status.md)，方法與完整驗收條件在[驗證計畫](../../specs/verification-plan.md#optimization-acceptance)，重跑入口在 [Agent 維護手冊](../../../.agent/reference/agent-maintenance-guide.md#storage-baseline)。

最新進展：[快照排序優化](#snapshot-order-comparison)已完成同 fixture 交錯比較；以下先保留 01:31 初始資料基準，不能將兩個不同目錄／時間的量測直接當成 before／after。

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
