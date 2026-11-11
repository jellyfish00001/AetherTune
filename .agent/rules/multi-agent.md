# Multi-Agent Rules（多 Agent 協作規則）

適用所有在本專案工作的 Agent（Codex、Cursor、Claude Code、Grok、Antigravity 等），不論是否由 Orchestrator 派發。專案本身的規則見同目錄的 `project.md`，開發與 Git 規則見 `development.md`、`git-policy.md`。

## Single Source（唯一來源）

- `.agent/` 是本專案 Agent 框架的唯一位置：
  - `rules/`：所有 Agent 規則；哪些規則常駐、哪些依路徑套用，登記在 `manifests/rules.yaml`。
  - `workflow.yaml`：角色、模型路由、審查政策、Git 政策、測試與 UI 驗證指令、`forbiddenPaths`（detached copy，直接在這裡修改）。
  - `bootstrap.lock.json`：導入來源、版本、技術棧與雜湊紀錄，不是執行時依賴。
  - `handoffs/<taskId>/`：Workflow task 的交接檔 PLAN／IMPL_NOTES／REVIEW／HANDOFF（由 Orchestrator 產生，位置以 `workflow.yaml` 的 `handoffDir` 為準）。新任務預設 `handoffStorage: archive`：這裡只是工作用副本，不 commit；固定 candidate 後 Orchestrator 另存不可變 artifact（Task ID、Base／Reviewed SHA、content hash）並備份。舊任務或 `handoffStorage: git` 才把這些檔案 commit 進分支。
  - `plans/`：專案規劃層（選用的 `VISION.md`／`ROADMAP.md`／`QUESTIONS.md`），跨 Workflow 的長期方向；不是任務狀態（Backlog 在 Orchestrator SQLite）也不是 task 計畫（在 handoff）。
  - `docs/`、`guides/`、`manifests/`、`skills/`、`test-context/`、`scripts/`、`records/`、`workflows/`：用途與觸發條件見各目錄 README。
- 各 Agent 的原生薄入口在根目錄 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 與 `.cursor/rules/`（及其他工具慣用之入口路徑，例如 `.claude/rules/`）：不寫、也不複製規則正文。**讀取順序與路由正本**是 `.agent/README.md`；**專案邊界正本**是 `.agent/rules/project.md`。其餘規則（`development.md`、`git-policy.md`、`roles.md` 等）與路徑專用規則依 `.agent/README.md` 與 `manifests/rules.yaml` 按需引用，勿要求 Agent 在開始任務前先讀完 `rules/` 目錄全部檔案。入口可由 `project:init` 依 manifest 產生或維護；新增規則寫進 `.agent/rules/` 並登記到 manifest 後，再重跑 `project:init`。
- 專案層 Skills 只從原生路徑探索（Codex、Grok、agy 用 `.agents/skills/`；Cursor 用 `.cursor/skills/`；Claude Code 用 `.claude/skills/`），由 Skills Installer 寫入受控副本；不要手改帶 `.aw-skill.json` 的目錄。

## Workflow Tasks（Workflow 任務）

- 每個 task 在自己的 Git worktree、分支 `aw/<taskId>` 上進行，只修改 task 允許的路徑。Agent 自己不 commit、merge、rebase 或 push；commit、push、PR 由 Orchestrator 依 `git-policy.md` 執行，merge 由人決定。
- Developer：完成實作，執行 `.agent/workflow.yaml` 的測試指令，在 `handoffs/<taskId>/IMPL_NOTES.md` 記錄改了什麼與如何驗證；該目錄只放 PLAN.md、IMPL_NOTES.md，不自行建立其他檔案，也不寫 REVIEW.md／HANDOFF.md。
- Reviewer：唯讀審查指定的 commit，blocker 附檔案與行號，並列出查核過的測試證據。審查綁定單一 SHA，之後任何變更都需要重新審查。archive 模式下 handoff 檔是該 SHA 的 checkpoint 唯讀還原，改動它或多放檔案都算污染 checkout。
- 沒有新的驗證輸出，不宣稱完成。
- 不提交本機 runtime 狀態、截圖或工具快取。金鑰／`.env`／Browser Profile／Session 等可否入 Git：若 `project.md` 有 Secrets／私有 repo 條則只認該條，否則一律不提交。
