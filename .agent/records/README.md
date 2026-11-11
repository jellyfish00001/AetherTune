# records（長期紀錄）

- 用途：只保留兩類長期紀錄：`adr/` 的架構／政策決策（Decision Record），以及某個決策或檢查直接依賴的必要驗證證據。
- 觸發條件：做出需要日後追溯的決策，或有決策／測試直接引用的驗證結果時建立；單一 task 的交接由 Orchestrator 寫在 `handoffs/`，不放這裡。
- 不放：單次的執行、審查、測試報告。它們的歷史在 Git 與 Orchestrator 的 task／event／handoff artifact；可重用的修正結論更新到既有 guide 或 docs。
- 有效性：ADR 的 frontmatter `status: accepted` 才是有效決策；其餘內容預設是歷史，不是目前知識。
- 產生規範：ADR 放 `adr/NNNN-<topic>.md`，證據檔放 `<topic>/`；只寫結論與證據摘要（指令、結果、SHA），不放原始 CLI 輸出、截圖或秘密值。
