# plans（專案規劃層）

- 用途：跨多個 Workflow 的長期規劃，供人與 Agent 接續工作。選用檔案（依專案需要建立，Framework 只提供本檔）：
  - `VISION.md`：定位、目標、成功條件、原則與非目標。
  - `CAPABILITY_MAP.md`（選用）：理想能力分類樹（穩定能力 ID、最大深度 L1～L5）；不是現況盤點，不保存實作進度。需要時手寫；**不**由 `project:init` 自動生成完整地圖。
  - `ROADMAP.md`：里程碑、工作包、驗收條件，以及有證據支撐的目前狀態。
  - `QUESTIONS.md`：待決問題、選項、依賴與在決定前可安全採用的暫行做法。
- 觸發條件：專案有跨多個 task 的方向、里程碑或待決問題時建立對應檔案；需要能力分類樹時再加 `CAPABILITY_MAP.md`。小型專案可以都不建；`project:init` 不會建立空的 VISION／ROADMAP／QUESTIONS，也不自動生成能力地圖正文。
- 與其他計畫分開：專案規劃放這裡；任務執行狀態（Backlog）在 Orchestrator SQLite；單一 task 的計畫在 handoff／artifact，完成後即為歷史。本目錄不是第二套任務狀態機，也不手抄 task 進度。
- 產生規範：手寫、短而準；frontmatter 標 `status: active` 並加 `verified_at` 或 `evidence`，才會被知識索引視為目前知識（見 `rules/development.md` 的 Memory）。只在規劃／重新規劃流程並經使用者授權時更新；一般 Memory 流程不寫入本目錄。
