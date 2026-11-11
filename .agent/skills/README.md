# skills（專案 Skill 來源說明）

- 用途：說明本專案使用哪些 Skill 與來源。通用 Skill（例如殼層、測試、瀏覽器工具）安裝在各 Agent 的使用者層級（全域）目錄，不複製進專案；專案層副本只放在原生目錄（`.agents/skills`、`.cursor/skills`、`.claude/skills`），由 Skills Installer 寫入時清單記在 `bootstrap.lock.json` 的 `skills`。
- 觸發條件：只有本專案自寫、別的專案用不到的 Skill 才放 `skills/<name>/SKILL.md`；Agent 不會掃描這裡，需要時把它複製到上述原生目錄並在本檔記錄。
- 產生規範：`SKILL.md` 需含 `name`、`description` frontmatter；不要手改帶 `.aw-skill.json` 的原生副本，否則安裝器會標為 CONFLICT。
- **本專案 Skill**：[`doc-routing/`](doc-routing/SKILL.md) — 文件定位與更新路由（見 [`.agent/README.md`](../README.md) 讀取順序）。
