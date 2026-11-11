# scripts（Agent 輔助腳本）

- 用途：Agent 與人共用的掃描、驗證與輔助工具，例如產生 `manifests/` 索引、啟動本機服務並 health check、UI 驗證包裝指令。
- 觸發條件：同一段指令被 Agent 重複手打兩次以上、或 `workflow.yaml` 的 testCommands／uiVerification 需要包裝時才建立。
- 產生規範：腳本可重複執行、預設唯讀或只寫 runtime／暫存目錄；路徑從參數或環境變數推導，不寫死使用者名稱；不讀出或輸出秘密值。
