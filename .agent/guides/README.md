# guides（操作指南）

- 用途：特定工作的做法說明，按需讀取，不常駐 context。常見主題：`ui-verify.md`（前端操作驗證）、`api.md`、`db.md`（唯讀查詢與安全界線）、`deploy.md`、`explore.md`（專案探索路線）。
- 觸發條件：某類工作重複出現、且 rules 只需要一句「依 guides/xxx.md」即可指向時才建立；frontend capability 會帶入 `ui-verify.md`。
- 產生規範：一份指南一個主題；規則（必須／禁止）寫在 `rules/`，指南只寫步驟與判定；不寫帳密與正式環境連線資訊。
