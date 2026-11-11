# Development Rules（開發規則）

適用所有 Agent 的通用開發流程。

**專案邊界、分支慣例、不提交清單、測試報告與證據標準**以 [project.md](project.md) 為唯一正本；本檔不重述。

## Tools（工具選擇）

- **按任務適配選工具**，不把「原生 → CLI → Skill → MCP」當跨領域硬階梯；共用 CLI 名稱跨 Agent 一致。
- 需要專門方法／工作流再載入 Skill；MCP／應用原生 API 在它們就是正確介面時直接用。同一用途不要雙裝。
- 一般開發任務不要掃描、重裝或驗證整套 CLI；缺少工具時回報並指向既有安裝／Bootstrap 流程。

## Explore（探索）

- 先依 [`.agent/README.md`](../README.md) 與 [docs/README.md](../../docs/README.md) 選最小資料集，再用符號搜尋定位；大型檔案只讀相關段落。
- 找到真值來源與連動檔案後再修改；保留無關變更，不整檔重寫。

## Change and Verify（修改與驗證）

- 只改 task 或使用者核准的範圍；`workflow.yaml` 的 `forbiddenPaths` 一律不碰。
- 完成後依 `project.md` 的驗證方式與當輪 artifact 回報；`repository.testCommands` 本專案為 `[]`，不編造通過指令。
- 沒有可重跑的實際輸出不宣稱已測試或通過；工具不可用時說明並列人工步驟。
- 失敗時在核准範圍內修正並重測；同一操作連續失敗兩次停下來回報證據。

## Safety（安全）

- 秘密值與可提交例外以 [project.md](project.md) 為準。
- Browser 與測試只連本機或已授權環境；正式系統、真實帳號、金流與刪除資料需明確授權。

## Rule Sources（規則來源與優先序）

- Upstream／Framework／Project Local／Generated 的修改位置與優先序：Project Local 覆寫僅限 `project.md` 等明確宣告範圍，不整體覆蓋 Framework 通用規則。

## Records（紀錄）

- `.agent/records/` 長期保留 ADR 與決策直接依賴的必要驗證證據；單次執行報告見 Git 與 Orchestrator artifact。task 交接由 Orchestrator 寫 `handoffs/`，與 `records/` 不互寫。

## Memory（專案記憶）

- 只記有證據、可重用、未重複的決策；accepted ADR 與標記為 active 的知識才作為目前依據。`.agent/MEMORY.md` 按需建立。
