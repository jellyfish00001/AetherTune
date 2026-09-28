# AetherTune Agent Reference

本檔只規定**專案邊界、讀取順序與修改規則**，不保存操作命令、逐檔清單或當次測試結果。人類入口是 [README.md](README.md)；Agent 先讀本檔，再用[快速地圖](docs/agent-quick-map.md)定位 owner，按需讀對應 source、契約與驗證。各文件的唯一權責由[文件地圖](docs/README.md)指定。

## 研究與實作邊界

AetherTune 有 **Streaming VC**（由 source 保留表演並轉換聲線）與 **Speech Reconstruction**（從文字重新生成表演）兩組。RVC 需要訓練角色模型；Seed-VC、MeanVC2、X-VC 是不同的 zero-shot VC 路線；CosyVoice2／Breeze TTS 2 服務於語音重建。各 profile 的 installed／candidate／PASS／WAITING 以其 register 和分項驗證為準。`audio-rack/` 與 `benchmarks/` 是跨 backend 的共用設施，不是另一個模型 backend。

不要把 Seed-VC、MeanVC2、X-VC 或 TTS checkpoint 放進 RVC `.pth/.index` 流程，也不要把 STT → TTS 描述成保留原始聲學表演。Desktop Manual TTS 目前先生成完整 WAV 再播放；Mic OFF 不得阻止 manual，completed playback 才寫入 `manual_text` Transcript。Agent Reply 與完整 physical Mic／Rack／LIVE 證據各自獨立，不因 UI、模型檔或合成 WAV 存在而升格。

研究需求由 [architecture.md](docs/architecture.md) 負責；Desktop 預期行為由 [app-requirements.md](docs/app-requirements.md) 負責；`LIVE`／`OFFLINE` 分類由 [live-gate.md](docs/live-gate.md) 負責。具體契約以 `contracts/` schema／manifest 為準。**當文件敘述與實際結果衝突，以本輪可重跑 artifact、verifier 與真實命令輸出為準，然後修正文檔。** 最新狀態請開對應 verification；[集中狀態表](docs/agent-implementation-status-latest.md)只作導航。

## 漸進式讀取

1. 先以[Agent 快速地圖](docs/agent-quick-map.md)選 owner，不載入整庫或整份逐檔索引。
2. 操作問題讀[一頁式說明](docs/quick-start.md)或對應[詳細手冊](docs/desktop-user-guide.md)；跨層實作與排錯才讀[維護手冊](docs/agent-maintenance-guide.md)。
3. 單一檔案職責在[逐檔索引](docs/project-file-map.md)用 `rg -n '<路徑或名稱>'` 查；目錄放置內容也在該索引。新增、刪除或更名 Git 管理檔案時同步索引。
4. 新增 backend/profile 先查[多後端契約](docs/voice-conversion-architecture.md)與對應 `backends/<name>/README.md`，再更新需求、架構、register、source audit、驗證入口；候選 intake 不得冒充已安裝 backend。

## 修改與證據規則

- 先讀 `git status --short --untracked-files=all`，保留使用者既有變更；只改任務範圍。新增 orchestration 只在 `app/`、`contracts/`、`services/`，不改 ignored upstream、venv、模型、音訊或 artifacts 來冒充 source 變更。
- 文件用繁體中文；官方名稱、命令、revision、license 保留原文。本機文件編輯使用 `apply_patch`，不要用 shell redirect 覆寫。
- 依[文件地圖](docs/README.md)只更新擁有該資訊的文件。導覽頁只能給短摘要與連結；歷史報告不可覆蓋最新 evidence。避免把同一操作流程、參數預設或狀態表複製到多份文件。
- 下載、import、HTTP 200、CUDA/provider 清單、模型檔存在及 GUI 開啟都不是音訊 E2E。報告實測時記錄命令、輸入／模型 hash、device/provider、輸出 artifact、`PASS`／`WAITING`／`BLOCKED` 與未解事項。
- 不提交權重、音訊、第三方 repo、`.venv`、WSL env、artifacts 或 secrets；不記錄 API key、密碼、cookie、token 或私人聲音授權資料。
- 長期整合分支只保留 `main`。只有並行隔離或明確 review 才建立 `codex/<area>-<problem>`；整合並確認 commit 可由 `origin/main` 到達後才刪除，不丟棄未整合內容。

完成時至少回報改動檔案、實際驗證與結果、仍為 `WAITING`／`PLANNED` 的項目，以及使用者下一步應讀的文件或命令。
