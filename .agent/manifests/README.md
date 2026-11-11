# manifests（機器可讀索引）

- 用途：`rules.yaml` 是規則套用範圍的唯一來源（`scope: always` 或 `glob`），`project:init` 依它產生 `AGENTS.md`、`GEMINI.md`、`.cursor/rules/*.mdc`、`.claude/rules/*.md`。其他 JSON 索引（頁面、路由、大型檔清單）由專案掃描腳本產生。
- 觸發條件：`rules.yaml` 一律存在；掃描索引在專案大到需要「先查索引再搜尋」時才建立，腳本放 `scripts/`。
- 產生規範：索引一律由腳本重產並含 `generatedAt`，不手寫；大型產物（數百 KB）不進 Git。改 `rules.yaml` 後重跑 `project:init` 更新原生入口。
