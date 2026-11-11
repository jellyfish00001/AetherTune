# Roles（角色目錄與節點契約）

本檔定義本專案的角色、節點契約與最低能力等級（`min_tier`）。誰來驅動各角色不寫在這裡：Orchestrator 派工的 planner／developer／reviewer 候選在 `.agent/workflow.yaml` 的 `profile`；其餘角色的現況填在下方「目前驅動者」表。

## 架構原則

1. **自動化是角色分配。** 只定義角色與節點契約（輸入、輸出、驗收、最低能力等級、權限、獨立性、失敗與升級），不綁定、也不為任何 Agent／Bot 客製化。Agent、Bot、腳本都只是可替換的「驅動者」；不同驅動者的差異（CLI 旗標、原生入口檔、額度、健康檢查）只放在設定與適配器，規則正文不寫「某 Agent 負責某事」。
2. **框架越完整，可接任的驅動者越多。** 某角色目前需要高階模型，是因為契約、驗證或復原還不完整；補齊後 `min_tier` 可逐步下修，讓更多驅動者接任。

## 名詞

- **角色（role）**：一個節點的責任與契約。
- **驅動者（driver）**：實際執行角色的 Agent／Bot／腳本＋模型，由設定選擇、可替換。
- **能力等級（tier）**：T0＝無 LLM 腳本；T1＝一般模型，照明確步驟執行；T2＝中高階模型，可在有界範圍內判斷；T3＝最高階模型，可做規劃、審查與跨檔推理。某驅動者屬於哪一級由設定與實測決定，不寫在規則裡。
- **獨立性（independence）**：審查者與實作者的分離程度，判定以 `.agent/workflow.yaml` 的 `profile.reviewer.independence` 為準。

## 契約欄位

每個角色寫齊：`id`、目的、輸入、輸出、驗收、`min_tier`、權限（ro 唯讀／rw 可寫 repo／system 系統級）、獨立性、失敗與升級。

## 角色目錄

`min_tier`：planner／developer（implementer）／reviewer（plan-／code-reviewer）的數值以 `.agent/workflow.yaml` 開頭的 Role contracts 註解為起點（init 時的框架預設快照，可依本專案調整；Engine 目前不依此篩選）。

| id | 目的 | 輸入 → 輸出 | 驗收 | min_tier | 權限 | 獨立性 | 失敗與升級 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `planner` | 把一個單位拆成可驗收的 Plan | 需求、相關檔 → `PLAN.md` | 範圍有界、每步可驗證 | 見 workflow.yaml 註解 | ro | — | 無法有界時退回需求方待決 |
| `plan-reviewer` | 核可或退回 Plan | `PLAN.md` → `VERDICT` | 對照需求與規則；`CHANGES_REQUESTED` 列具體理由 | 見 workflow.yaml 註解（reviewer） | ro | 依 `workflow.yaml` 的 `independenceBasis`：預設 `agent` 時與 `implementer` 不同 Agent；改成 `model` 則允許同一 Agent 換模型、另開 session | 不可用 → 該單位等待，不跳過 |
| `implementer` | 依已核可 Plan 實作並驗證 | `PLAN.md` → 候選 commit | 不超出 Plan；必要驗證通過 | 見 workflow.yaml 註解（developer） | rw（repo） | — | 同一錯誤 2 次換策略、3 次停下回報 |
| `code-reviewer` | 固定 SHA 對照 Plan 審查 | SHA、`PLAN.md` → `VERDICT` | 多做／漏做／偏離即 `CHANGES_REQUESTED` | 見 workflow.yaml 註解（reviewer） | ro | 同 `plan-reviewer` | 同 `plan-reviewer` |
| `verifier` | 機器驗證（型別、測試、Gate） | 工作樹 → 驗證結果 | 依 `project.md` 的驗證方式 | T0 | ro | — | 失敗回 `implementer` |
| `controller`（選用） | 對使用者的單一出入口：收需求、追蹤、整理待決事項 | 使用者訊息、事件 → 任務／決定 | 每個決定寫明怎麼了、影響、建議選項 | T3 | ro（repo） | — | 無法判斷時記錄待決並繼續不受影響的工作 |

## 本 repo 寫入授權（與 Orchestrator 候選分離）

- **本 repository 的唯一寫入者是 AetherTune Bot**（可替換驅動者，但同一時間只應有一個授權寫入者）。
- `.agent/workflow.yaml` 裡 `profile.planner`／`developer`／`reviewer` 所列的 claude／codex／cursor／agy **候選順序**只是 Orchestrator 在派工時的備援路由，**不是**多人可寫本 repo 的授權，也**不能**與日常互動式 Agent 的寫入權混為一談。
- **系統層級變更**（驅動、虛擬音效卡、PATH、全域 Python／CUDA 安裝與升級）由本機管家 **PC2-2060**／**PC1-5060Ti** 執行或核准；**不**寫進 `implementer` 契約的預設工作範圍。

## 目前驅動者與下修 min_tier 的缺口

| id | 目前驅動者（可替換的預設） | 下修 min_tier 前要補的缺口 |
| :--- | :--- | :--- |
| `controller` | **AetherTune Bot** | （由專案填寫） |
| `implementer` | **AetherTune Bot**（repo 寫入）；系統層不交給此角色 | （由專案填寫） |
| `planner`／`plan-reviewer`／`code-reviewer` | Orchestrator 依 `.agent/workflow.yaml` 候選派工（備援順序，非 repo 寫入授權） | （由專案填寫） |
| `verifier` | `repository.testCommands`（本專案為 `[]`；驗證依 `project.md` 與 verifier） | （由專案填寫） |
