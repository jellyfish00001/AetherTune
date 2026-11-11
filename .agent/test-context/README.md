# test-context（測試情境知識）

- 用途：描述「怎麼測」的知識資產：Persona（角色、驗證方式、無法取得時的處置）、Fixture（測試資料的查找方式）、Scenario（步驟、斷言、證據節點）。不負責排程或迴圈。
- 觸發條件：前端 UI 驗證或需要重複回歸的流程才建立實際檔案；frontend capability 會帶入 `scenario.template.md`。
- 產生規範：ID 前綴 `TP-`（Persona）、`FIX-`（Fixture）、`SC-`（Scenario）；不寫帳密、連線字串或正式個資；找不到資料時結果為 `DATA_NOT_AVAILABLE`，不為測試寫入資料。
