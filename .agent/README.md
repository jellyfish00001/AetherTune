# AetherTune Agent 控制中心

本目錄是跨 Agent 的單一控制來源。各 Agent 的原生入口只連到這裡，不複製規則或 Skill 正文。Codex 使用根目錄 [`AGENTS.md`](../AGENTS.md)；其他 Agent 加入時，依該工具的實際載入機制建立薄入口。

## 讀取順序

1. 修改前讀 [專案規則](rules/project.md)，確認 owner、資料與證據邊界。
2. 用 [文件入口](../docs/README.md)依任務選最小資料集；規格用 F01～F10、工作用[任務進度](../docs/status.md)的 ID 對齊。程式 owner 用 [快速地圖](reference/agent-quick-map.md)，逐檔用途才查 [檔案索引](reference/project-file-map.md)。
3. 可重複的文件定位與更新工作使用 [文件路由 Skill](skills/doc-routing/SKILL.md)；其他 Skill 只有在任務符合其 `description` 時才讀取。
4. 實作與報告依 `contracts/`、source、verifier 和當輪 artifact 核對；依[交接流程](reference/agent-maintenance-guide.md#task-handoff)回寫 owner report 與任務列。`docs/` 保存操作、設計與證據，不能替代可執行契約。

## 放置邊界

| 位置 | 內容 |
|---|---|
| `rules/` | 所有任務都適用的專案邊界與修改規則；不放當輪 PASS 表。 |
| `skills/<name>/SKILL.md` | 有明確觸發條件、可重複的工作流程；引用權威文件與腳本，不複製內容。 |
| `docs/` | Agent 優先的查找入口，其次是開發狀態與規劃，最後是一般使用者手冊。 |
| `contracts/`、`tools/`、`backends/` | 資料契約、可重跑檢核與各 backend 的實際介面。 |

`rules/` 是專案工作規範，`skills/` 是按任務使用的流程；正文只留在 `.agent/`。Codex 會自動讀取根目錄 `AGENTS.md`，再依其指示讀取這裡；`.agent/skills/` 不會自動出現在 Codex 的原生 Skill 清單。加入其他 Agent 時，需建立並驗證該工具的薄入口。
