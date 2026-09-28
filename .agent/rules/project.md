# AetherTune 專案規則

## 邊界

- AetherTune 分為 Streaming VC（由 source 保留表演並轉換聲線）和 Speech Reconstruction（由文字重新生成表演）。RVC 使用訓練角色模型；Seed-VC、MeanVC2、X-VC 是不同 zero-shot VC 路線；CosyVoice2／Breeze TTS 2 屬語音重建。`audio-rack/`、`benchmarks/` 是跨 backend 共用設施。
- Seed-VC、MeanVC2、X-VC 與 TTS checkpoint 不走 RVC `.pth/.index` 流程；STT → TTS 不等於保留來源聲學表演。
- Desktop Manual TTS 先生成完整 WAV 再播放；Mic OFF 不阻止 manual，僅 completed playback 寫入 `manual_text` Transcript。Agent Reply、physical Mic／Rack／LIVE 分別驗收。
- profile 的 installed／candidate／PASS／WAITING 以 register 和分項驗證為準。下載、import、HTTP 200、CUDA/provider 清單、模型檔或 GUI 存在都不是音訊 E2E。

## 查找與修改

- 按 [文件入口](../../docs/README.md)找任務；程式 owner 先看[快速地圖](../reference/agent-quick-map.md)。研究設計見[架構](../../docs/specs/architecture.md)，Desktop 預期行為見[需求](../../docs/specs/app-requirements.md)，LIVE 分類見[gate](../../docs/specs/live-gate.md)；具體欄位以 `contracts/` 為準。
- 新增 backend/profile 前，查[多後端契約](../../docs/specs/voice-conversion-architecture.md)與對應 `backends/<name>/README.md`；實作後同步需求、架構、register、來源審核與驗證入口。候選 intake 不得冒充已安裝 backend。
- 修改前讀 `git status --short --untracked-files=all`，保留既有變更，只改任務範圍。新增 orchestration 只在 `app/`、`contracts/`、`services/`；不以 ignored upstream、venv、模型、音訊或 artifacts 冒充 source 修改。
- 文件用繁體中文；官方名稱、命令、revision、license 保留原文。本機文件編輯用 `apply_patch`。依[文件權責](../../docs/README.md)更新 owner 文件；其他位置只保留短摘要和連結。新增、刪除、更名 Git 管理檔案時同步[逐檔索引](../reference/project-file-map.md)。
- 測試報告記錄命令、輸入／模型 hash、device/provider、輸出 artifact、判定與未解事項。文件與當輪結果衝突時，以可重跑 artifact、verifier 和真實命令輸出為準，再修正文檔；歷史報告不得覆蓋新證據。
- 不提交權重、音訊、第三方 repo、`.venv`、WSL env、artifacts 或 secrets；不記錄 API key、密碼、cookie、token、私人聲音授權資料。
- 長期整合分支只保留 `main`。並行隔離或明確 review 才建立 `codex/<area>-<problem>`；確認整合 commit 可由 `origin/main` 到達後才刪除，不丟棄未整合內容。

完成時回報改動檔案、實際驗證、仍為 `WAITING`／`PLANNED` 的項目，以及下一步應讀的文件或命令。
