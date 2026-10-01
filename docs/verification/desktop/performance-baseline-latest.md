# Desktop 資料效能基準

日期：2026-10-02（Asia/Taipei）。任務：BASE-01／F07、F08、N02。**本頁只擁有本次合成資料的 SQLite、匯出及 Python service snapshot 量測**；任務狀態在 [docs/status.md](../../status.md)，方法與完整驗收條件在[驗證計畫](../../specs/verification-plan.md#optimization-acceptance)，重跑入口在 [Agent 維護手冊](../../../.agent/reference/agent-maintenance-guide.md#storage-baseline)。

## 判定與範圍

**PASS：10／100／1,000 筆各 3 個隔離案例，共 9 個案例。** 每個案例核對 request／Transcript／snapshot 筆數、SQLite integrity、DB 與 JSONL 的 request identity、文字內容、TXT 行數、關閉後 session 結束時間及最終匯出 hash。關閉後 fixture worker 全部退出。

這是 baseline，沒有修改產品效能程式。BASE-01 整體仍 IN_PROGRESS：UI 更新／CPU／RSS／IPC transport、cold／warm／切換、模型與音訊品質尚未在同一固定矩陣量測。本次沒有操作桌面、錄音或播放；使用者正在使用電腦，Computer Use 暫緩。

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

- 完整快照大小隨歷史筆數增加；`snapshot()` 目前以 list membership 排除已列入的 request，`record_completed()` 每筆重寫整個 session export。這些 source 路徑值得進一步拆分 profiling；本輪尚未證明其中任一項單獨占據主要成本。
- PERF-02 應先補事件／polling 次數、實際 transport／render／RSS；再決定有界快照、query／export 政策，保留完整 durable history、queue identity 與完成播放才寫 Transcript 的語意。
- 資料量測結果不等於模組化完成。MOD-01／02、DATA-01 的介面、單一 writer、migration／restore 條件仍按架構與任務列執行。
- 尚未量測長時間記憶體、cold cache、storage commit 的獨立成本、模型冷／暖啟動、GPU／音訊與 physical／LIVE；本報告不提升那些狀態。
