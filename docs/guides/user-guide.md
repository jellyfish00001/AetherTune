# AetherTune 後端使用手冊

**文件邊界：**本頁幫使用者選研究路線、準備輸入，並找到各 backend 的實際 CLI 入口。backend 特有參數與完整命令只由對應 `backends/<name>/README.md` 擁有；Desktop 按鈕操作看[快速說明](quick-start.md)和[Desktop 手冊](desktop-user-guide.md)；Windows 虛擬線路看[路由手冊](operation-guide.md)。本頁不維護第二份安裝／測試狀態表；各輪結果按[文件地圖](../README.md)找對應驗證。

## 1. 選擇路線

| 目標 | 路線與輸入 | 先讀 |
|---|---|---|
| 保留來源說話內容與表演，不想訓練角色模型 | Seed-VC baseline：source／實體麥克風與 reference voice | [Seed-VC backend](../../backends/seed-vc/README.md)；資產準備見[seed-vc-assets.md](../reference/seed-vc-assets.md) |
| 比較其他 zero-shot Streaming VC | MeanVC2 或 X-VC：source WAV＋reference WAV；目前重點是 file-driven output | [MeanVC2](../../backends/meanvc2/README.md)、[X-VC](../../backends/xvc/README.md) |
| 使用既有訓練角色模型作歷史對照 | RVC：訓練後的 `.pth/.index` 配對與 source | [RVC backend](../../backends/rvc/README.md)、[訓練手冊](model-training-guide.md) |
| 先辨識文字，再重新說一遍 | STT → TTS：source WAV、目標文字／reference 與人工核對 transcript | [Speech Reconstruction backend](../../backends/speech-reconstruction/README.md) |
| 直接打字發聲、不使用 STT | Desktop Manual TTS | [快速說明](quick-start.md)；不使用本頁的 CLI 流程 |

Seed-VC、MeanVC2、X-VC 的 reference/checkpoint 不放入 RVC `.pth/.index` 路徑。STT → TTS 重新生成聲音，不等於保留來源的呼吸、停頓與情緒。對應 backend 的模型及來源登錄放在 `models/` 與 `dataset/manifests/`；檔案應放哪裡看[逐檔／資料夾索引](../../.agent/reference/project-file-map.md)。

## 2. 執行前的共同檢查

1. 先確認輸入聲音與 reference 可合法使用，並核對 `dataset/manifests/`、模型 register 的來源、授權、路徑和 hash。參考聲線的來源／用途不能由檔名猜測。
2. 選定**一個** backend/profile，按它的 README 準備隔離環境、固定 revision 與本機資產。各 backend 的 Windows／WSL Python 不共用；Git clone 不包含模型、venv 或輸出。
3. 用 backend 文件列出的 preflight 或唯讀盤點先查缺項，再按該 README 執行。`tools/voice-backend-check.ps1` 只能證明環境／檔案盤點，不能證明實際音訊。
4. 為每次執行使用新的 output 位置，保存 source／reference／model hash、參數、device/provider、WAV 和 runner manifest。先核對 finite、非零音訊，再依[路由手冊](operation-guide.md)接 CABLE／Rack／終端。

## 3. 分路線的驗收重點

| 路線 | 先驗什麼 | 不能據此宣稱 |
|---|---|---|
| Seed-VC offline | source/reference、固定 checkpoint、非零 WAV 與本輪 manifest | 官方 GUI 麥克風與完整 LIVE 已通過 |
| Seed-VC GUI | 真實 input/output、Host API、reference、callback 與同期 CABLE capture | 只有 GUI 可開或 synthetic tone 就算 physical mic E2E |
| MeanVC2／X-VC | 雙向 source/reference、CUDA provider、輸出 WAV／hash | file-driven streaming 就等於實體 mic 直播鏈路 |
| RVC | 模型/index 配對、f0、離線音訊；VCClient slot 另驗 | `.pth` 存在或服務 HTTP 200 就算角色即時變聲 |
| STT → TTS | STT draft、人工核對的 reference transcript、TTS WAV 與 workflow manifest | 重建輸出等同原始表演或 reference 已經人類批准 |

RVC 資料與訓練只按[訓練手冊](model-training-guide.md)進行；`FCPE`／`RMVPE`、模型 register 和 VCClient 都是分開的驗收層。STT → TTS 的 `TextFile` 是要說的目標內容，`ReferenceTextFile` 是 reference audio 的逐字文字；只有逐字核對後才使用 `-ReferenceTextVerified`。具體 wrapper 參數及 Voice Design／clone 分流在[Speech Reconstruction backend](../../backends/speech-reconstruction/README.md)。

## 4. 結果該看哪裡

backend 自己的 README 擁有命令與輸出檔名；[逐檔索引](../../.agent/reference/project-file-map.md)說明保留資料夾應放什麼；[文件權責地圖](../README.md)將每輪驗證導向對應報告。音訊檔、模型、venv、第三方 source 和 artifacts 預設不進 Git，也不能因某資料夾沒有 tracked 檔案就當成可刪除。

`LIVE`／`OFFLINE`／`WAITING` 的完整定義只在 [live-gate.md](../specs/live-gate.md)。任何路線都要以相同 run identity 驗證 source／mic → backend → Rack bypass/full-chain → virtual route → loopback；再做長時間穩定與人工聽測。離線 WAV、RTF、preflight 或局部 CABLE capture 只回答自己的測試問題。
