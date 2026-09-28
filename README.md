# AetherTune

AetherTune 是 Windows 本地的語音轉換與語音重建研究工作台。現有 Desktop 可輸入文字，透過 CosyVoice2／Breeze TTS 2 先產生完整 WAV，再播放到指定音訊裝置；這是**離線文字發聲**，不是已驗收的直播即時鏈路。Streaming VC、Audio Rack 與完整 LIVE 驗收是獨立工作。

## 從這裡開始

| 需求 | 唯一操作入口 |
|---|---|
| 第一次使用 Desktop 文字發聲 | [一頁式快速使用說明](docs/quick-start.md) |
| 建置 Desktop、操作 Queue／視窗、找結果與排錯 | [Desktop 詳細操作手冊](docs/desktop-user-guide.md) |
| 選擇 Seed-VC／RVC／STT → TTS 路線並執行 CLI | [後端使用手冊](docs/user-guide.md) |
| RVC 資料、訓練與模型交接 | [RVC 訓練手冊](docs/model-training-guide.md) |
| Windows 虛擬音訊、VST、VCClient 與下游接線 | [音訊路由操作手冊](docs/operation-guide.md) |
| 查一份文件應負責什麼、目前狀態看哪裡 | [文件權責地圖](docs/README.md) |
| Agent 尋找修改位置 | [AGENTS.md](AGENTS.md) → [Agent 快速地圖](docs/agent-quick-map.md) |

目前僅有開發版 Desktop 執行檔，沒有正式 installer／portable 發行包。模型、reference 音訊、第三方 source、Python 環境及執行證據不隨 Git 提供；新電腦須按[詳細操作手冊](docs/desktop-user-guide.md)與對應[backend 文件](backends/README.md)準備。`AetherTune.cmd` 是另一個既有 Tk 控制台，用於 Seed-VC GUI 與 MeanVC2／X-VC WAV 操作，**不包含**新的 Desktop 文字 Composer。

## 路線與目前邊界

- **Streaming VC**：使用來源聲音和 reference 改變聲線，目標是保留原始表演。Seed-VC 是 baseline；MeanVC2、X-VC 已有檔案驅動 CUDA WAV 證據；RVC 是需訓練模型的歷史對照。各 backend 的實際命令與限制由[後端使用手冊](docs/user-guide.md)及對應 `backends/<name>/README.md` 負責。
- **Speech Reconstruction**：從文字及 reference 重新生成語音，不保證保留原聲的呼吸、停頓與情緒。Desktop Manual TTS 操作由[快速說明](docs/quick-start.md)負責，離線 STT → TTS CLI 由[後端使用手冊](docs/user-guide.md)負責。
- `LIVE`、`OFFLINE`、`WAITING` 的判定只以 [LIVE gate](docs/live-gate.md) 及對應[驗證報告](docs/README.md)為準。程式可開啟、模型存在或產生 WAV 都不能單獨證明 physical mic → backend → rack → virtual route 完整通過。

新增、刪除或查找檔案時，先用[Agent 快速地圖](docs/agent-quick-map.md)找 owner，再按需查[逐檔用途索引](docs/project-file-map.md)。根目錄及保留資料夾各自應放什麼，也在該索引說明；本機 ignored 的模型、音訊及 artifacts 不因未進 Git 就能刪除。
