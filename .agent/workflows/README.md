# workflows（可選工作流說明）

- 用途：`workflow.yaml` 之外的可選工作流與驗證流程說明，例如發布前檢查清單、資料修正流程、跨 repo 協作步驟。
- 觸發條件：預設不需要；只有出現 `workflow.yaml` 的 planner → developer → reviewer 流程涵蓋不了、又會重複執行的流程時才建立。
- 產生規範：一個流程一個檔案，寫明觸發條件、步驟、Gate 與證據；不得另建任務狀態機，執行仍交給 Orchestrator Workflow 或人。
