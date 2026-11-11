# Git Policy（Git 政策）

本專案的 Git 政策是 **`reviewed`**（`.agent/workflow.yaml` 的 `git.policy`）。

**日常分支慣例、長期整合分支與不提交清單**以 [project.md](project.md) 為唯一正本（長期分支僅 `main`；並行隔離用 `codex/<area>-<problem>`）。下方 `aw/<taskId>` 僅描述 **Orchestrator Workflow task** 的執行分支，不取代 `project.md` 的分支慣例。

## Orchestrator 動作（reviewed）

| 動作 | 本專案（reviewed，預設） |
| --- | --- |
| Candidate commit（Orchestrator 在 `aw/<taskId>` 分支） | 允許 |
| Handoff commit | 允許 |
| Push | 需任務授權 |
| 開 PR | 需任務授權，且 `gh` 已驗證可用 |

## Commit 訊息與自動 Push

- Commit 訊息：語言 **繁體中文**，長度 **簡短（一行摘要）**（`workflow.yaml` 的 `git.commitMessage`）。`AW-*` trailer 由程式讀取，維持原樣。
- 自動 Push：**否**（`git.autoPush`）。開啟時每個 ACCEPTED 的 `aw/<taskId>` 分支會 push 到 `origin`；仍不 merge。

## Always（所有政策共通）

- Agent 不 merge 主分支、不 rebase、不 force push；ACCEPTED 不等於已 push 或已 merge。
- Orchestrator 在 candidate commit、handoff commit、push、PR 前檢查 task 授權快照、分支（Workflow 用 `aw/<taskId>`）、remote 與 `forbiddenPaths`。未授權或失敗時依 Orchestrator 狀態機處理；PR 需 push 與 PR 兩項授權。
- 在 Orchestrator 外直接使用 git／gh 不受程式檢查；互動式 Agent 仍須遵守 [project.md](project.md) 與使用者指示。
- 高風險操作（secrets、正式 DB、正式部署）需人明確核准。
