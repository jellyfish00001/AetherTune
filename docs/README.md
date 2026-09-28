# AetherTune 文件權責地圖

這份文件只回答「**某項資訊該寫在哪裡、衝突時信哪一份**」。不複製操作步驟、參數表或測試數字。讀者先從根目錄 [README.md](../README.md) 選任務；Agent 先遵守 [AGENTS.md](../AGENTS.md)。以下每個 Markdown 檔只擁有表中指明的範圍，其餘只能用一句背景和連結導向權威來源。

## 衝突與更新規則

1. **可執行契約**：`contracts/` 的 schema／manifest 與實際程式決定目前可接受的資料；[產品需求](app-requirements.md)記錄預期行為，[架構](architecture.md)記錄設計意圖。實作和需求不一致時不要悄悄改需求，應標出缺口。
2. **測試事實**：本輪可重跑 artifact／verifier 優先於報告文字；報告必須限定日期、backend、profile、裝置和證據範圍。不同測試報告不能互相覆蓋，較舊的報告保留歷史身分。
3. **使用方式**：對外文字發聲由 [quick-start.md](quick-start.md) 擁有；Desktop 詳細操作由 [desktop-user-guide.md](desktop-user-guide.md) 擁有；CLI 後端使用由 [user-guide.md](user-guide.md) 擁有；Windows 線路由 [operation-guide.md](operation-guide.md) 擁有。入口頁只連結，不重抄步驟。
4. **開發定位**：[agent-quick-map.md](agent-quick-map.md) 只指 owner；[agent-maintenance-guide.md](agent-maintenance-guide.md) 擁有跨層改動／除錯；[project-file-map.md](project-file-map.md) 擁有逐檔及保留資料夾用途。新增／刪除／更名檔案時同步後者。
5. 同一事實若需要出現在其他文件，只寫**一句限定範圍的摘要與連結**；不要複製命令、數值或 PASS 表。歷史文件不可被當成目前可用性宣告。

## 入口、操作、設計與開發

| 文件 | 唯一負責的內容；不負責的內容 |
|---|---|
| [本文件](README.md) | 所有說明文件的內容權責、衝突優先序與更新方式；不保存各文件正文。 |
| [根 README](../README.md) | 對外專案定位、路線選擇與文件入口；不放完整命令、當次測試矩陣。 |
| [AGENTS.md](../AGENTS.md) | Agent 邊界、漸進讀取與修改規則；不放逐檔清單、操作手冊或快照狀態。 |
| [quick-start.md](quick-start.md) | 對外 Desktop 文字發聲最短流程與目前限制；不放建置、內部協定或全部 Queue 細節。 |
| [desktop-user-guide.md](desktop-user-guide.md) | Desktop 建置、UI／Queue／視窗、輸出路由、檔案位置和故障排除；不定義產品需求或宣告完整 LIVE。 |
| [user-guide.md](user-guide.md) | Seed-VC、RVC、STT → TTS 的路線選擇與共同 preflight；單一 backend CLI 命令只在各 backend README。 |
| [operation-guide.md](operation-guide.md) | Windows 虛擬音訊、VCClient、VST／Rack 與終端收音的接線順序；不擁有 backend 安裝、訓練或最新測試狀態。 |
| [model-training-guide.md](model-training-guide.md) | RVC 原始資料、切片、訓練、模型提取與 register 流程；不擁有日常路由或其他 TTS 訓練。 |
| [agent-quick-map.md](agent-quick-map.md) | 任務 → 模組 owner → 最小檢核入口；不複製長篇改動流程或逐檔索引。 |
| [agent-maintenance-guide.md](agent-maintenance-guide.md) | Desktop／Manual TTS 跨 UI、Rust、Python、WSL、播放、儲存的協定、修改與除錯；不取代對外操作。 |
| [project-file-map.md](project-file-map.md) | Git 管理檔案的單一逐檔用途索引，以及保留／ignored 資料夾應放的內容；不判定 runtime readiness。 |
| [architecture.md](architecture.md) | 整體研究需求、系統分層和跨路線不變條件；不放 backend 細節、實作命令或即時狀態。 |
| [voice-conversion-architecture.md](voice-conversion-architecture.md) | Streaming VC／Speech Reconstruction 的 backend adapter、共用 Rack 與比較介面；不重述整體需求或產品 UI。 |
| [app-requirements.md](app-requirements.md) | Desktop 預期使用流程、功能與里程碑；PLANNED 不等於已實作。 |
| [app-architecture.md](app-architecture.md) | Desktop React／Tauri／service 分層、程序與 IPC 設計；實際改動步驟到維護手冊。 |
| [live-gate.md](live-gate.md) | `LIVE`／`OFFLINE`／`WAITING`／`BLOCKED` 的正式分類與必要證據；其他文件只能引用。 |
| [verification-plan.md](verification-plan.md) | 尚未執行或跨路線的驗證計畫與 Definition of Done；不宣告測試 PASS。 |
| [decision-log.md](decision-log.md) | 已採納的選型決策、日期及原因；不代替現行需求、code 或測試結果。 |
| [open-questions.md](open-questions.md) | 尚未定案的問題及處理方向；不能改寫成已採納設計。 |
| [source-audit.md](source-audit.md) | 上游來源、revision、license 與採納／隔離決定；不宣告模型品質或商品授權完成。 |
| [seed-vc-assets.md](seed-vc-assets.md) | Seed-VC asset manifest、來源、hash 與新環境準備；不宣告 GUI 音訊已通過。 |
| [vcclient-runtime-gate.md](vcclient-runtime-gate.md) | VCClient packaged 相容性前置 gate；不擁有角色音質或完整 LIVE 結論。 |
| [current-rvc-model-inventory.md](current-rvc-model-inventory.md) | `models/model-register.csv` 的人類可讀快照；CSV 是欄位權威，本頁不自行升格模型。 |
| [local-environment.md](local-environment.md) | 建立當時的本機環境快照；不作今日安裝／runtime readiness 權威。 |

## 各資料夾的 README 權責

| 文件 | 唯一負責的內容 |
|---|---|
| [backends/README.md](../backends/README.md) | backend 清單、路線入口與各 backend 文件連結；不保存完整安裝命令。 |
| [backends/rvc/README.md](../backends/rvc/README.md) | RVC adapter 的輸入、模型格式與 legacy 邊界。 |
| [backends/seed-vc/README.md](../backends/seed-vc/README.md) | Seed-VC upstream profile、輸入與 runner 特有命令。 |
| [backends/seed-vc-realtime/README.md](../backends/seed-vc-realtime/README.md) | 獨立 realtime fork 候選的 intake 邊界。 |
| [backends/meanvc2/README.md](../backends/meanvc2/README.md) | MeanVC2 的版本、資產、CLI 參數與輸出契約。 |
| [backends/xvc/README.md](../backends/xvc/README.md) | X-VC 的版本、資產、CLI 參數與輸出契約。 |
| [backends/speech-reconstruction/README.md](../backends/speech-reconstruction/README.md) | STT → TTS runner 輸入、reference 文字核對與 backend 限制。 |
| [audio-rack/README.md](../audio-rack/README.md) | 共用後製鏈的總入口與 bypass/full-chain 原則。 |
| [audio-rack/benchmarks/README.md](../audio-rack/benchmarks/README.md) | paired Rack evidence 欄位與配對規則。 |
| [audio-rack/plugin-profiles/README.md](../audio-rack/plugin-profiles/README.md) | VST plugin 身分、版本、授權與延遲欄位。 |
| [audio-rack/presets/README.md](../audio-rack/presets/README.md) | Post-FX preset 格式與參數保存。 |
| [audio-rack/routing/README.md](../audio-rack/routing/README.md) | Rack 輸入／輸出及虛擬裝置方向契約。 |
| [benchmarks/README.md](../benchmarks/README.md) | 三層 benchmark 的共同入口及不可互代原則。 |
| [benchmarks/corpus/README.md](../benchmarks/corpus/README.md) | 固定比較語料與來源欄位。 |
| [benchmarks/live/README.md](../benchmarks/live/README.md) | 實體音訊全鏈路的 live evidence 形狀。 |
| [benchmarks/quality/README.md](../benchmarks/quality/README.md) | 客觀 WAV／訊號品質檢查。 |
| [benchmarks/subjective/README.md](../benchmarks/subjective/README.md) | 人工匿名盲聽與評分流程。 |
| [dataset/raw/README.md](../dataset/raw/README.md) | 原始授權乾聲應放內容。 |
| [dataset/sliced/README.md](../dataset/sliced/README.md) | 可追溯切片應放內容。 |
| [dataset/augmented/README.md](../dataset/augmented/README.md) | 衍生／變調音訊應放內容。 |
| [dataset/reference-voices/README.md](../dataset/reference-voices/README.md) | reference voice 來源、用途與個資界線。 |
| [dataset/manifests/README.md](../dataset/manifests/README.md) | 來源、審核、hash 與 audit CSV 欄位。 |
| [models/README.md](../models/README.md) | 模型目錄與 register 總入口；權重本身不進 Git。 |
| [models/weights/README.md](../models/weights/README.md) | RVC `.pth` 應放內容。 |
| [models/indexes/README.md](../models/indexes/README.md) | 配對 RVC `.index` 應放內容。 |
| [models/seed-vc/README.md](../models/seed-vc/README.md) | Seed-VC checkpoint 路徑責任。 |
| [models/shared/README.md](../models/shared/README.md) | 已決定共用模型資產的放置與來源責任。 |
| [models/speech-reconstruction/README.md](../models/speech-reconstruction/README.md) | TTS 模型分類與共同資產邊界。 |
| [models/speech-reconstruction/breeze-tts-2/README.md](../models/speech-reconstruction/breeze-tts-2/README.md) | Breeze 特有模型內容與限制。 |
| [tools/README.md](../tools/README.md) | 可重跑腳本的入口、參數目的與副作用；不替各驗證報告判 PASS。 |

## 驗證與歷史紀錄

每份下列報告只對**自己的標題、日期及測試範圍**有證據權威。即使檔名帶 `latest`，也要看內文日期與 artifact，不能由檔名推論仍是今天的狀態。

| 文件 | 唯一擁有的證據範圍 |
|---|---|
| [agent-implementation-status-latest.md](agent-implementation-status-latest.md) | 分項報告的集中導航與未解事項；不是獨立測試結果。 |
| [manual-tts-verification-latest.md](manual-tts-verification-latest.md) | Desktop Manual TTS 的 service／Queue／生成／播放／Transcript 該輪 evidence。 |
| [app-verification-latest.md](app-verification-latest.md) | Desktop M0/M1/M2 首輪 shell、VC adapter 與 lifecycle evidence；Manual TTS 另見專報。 |
| [python-ui-verification-latest.md](python-ui-verification-latest.md) | Python 3.10 runtime 與 `AetherTune.cmd` Tk 控制台 evidence。 |
| [backend-install-test-latest.md](backend-install-test-latest.md) | Seed／MeanVC2／X-VC 安裝、基本 CUDA WAV 與 backend intake 當次 evidence。 |
| [seed-vc-readiness-latest.md](seed-vc-readiness-latest.md) | Seed-VC setup、資產、launcher、環境與使用者交接 readiness；GUI 有效聲音證據看下一份。 |
| [seed-vc-verification-latest.md](seed-vc-verification-latest.md) | Seed-VC GUI settings、callback、CABLE capture 與 realtime-tiny 音訊缺口。 |
| [cosyvoice-verification-latest.md](cosyvoice-verification-latest.md) | CosyVoice runtime、clone、UI 與 frontend CUDA probe。 |
| [breeze-tts2-verification-latest.md](breeze-tts2-verification-latest.md) | Breeze TTS 2 安裝、CUDA 音訊、UI 與 RTF。 |
| [rvc-model-audit-latest.md](rvc-model-audit-latest.md) | RVC 權重／index hash、register 欄位與 dataset audit gate。 |
| [vcclient-packaged-repair-latest.md](vcclient-packaged-repair-latest.md) | VCClient packaged 修復與 role conversion 阻塞。 |
| [vcclient-rvc-probe-latest.md](vcclient-rvc-probe-latest.md) | 專案 RVC FCPE + GPU 離線角色輸出，與 packaged client 分開。 |
| [vcclient-rvc-latency-matrix-latest.md](vcclient-rvc-latency-matrix-latest.md) | VCClient chunk／dropout／buffer 的 bounded matrix。 |
| [wiring-verification-latest.md](wiring-verification-latest.md) | Windows 線路、元件與 probe 的最新分層檢查。 |
| [audio-quality-comparison-latest.md](audio-quality-comparison-latest.md) | 固定 WAV 集合的客觀訊號比較；不是人工音質結果。 |
| [seed-vc-readiness-2026-09-26.md](seed-vc-readiness-2026-09-26.md) | 2026-09-26 當日封存的 Seed readiness，不更新成最新結論。 |
| [streaming-vc-candidate-intake-2026-09-26.md](streaming-vc-candidate-intake-2026-09-26.md) | 2026-09-26 MeanVC2／X-VC 候選研究決策快照；安裝後狀態看 backend 專報。 |
| [wiring-deployment-report.md](wiring-deployment-report.md) | 初次部署與新人接線的歷史紀錄；現行步驟看 operation-guide。 |
| [project-architecture-review-report-2026-09-27.md](project-architecture-review-report-2026-09-27.md) | 2026-09-27 架構審查當次 findings；現行架構看 architecture／app-architecture。 |

維護文件時先在本表找到 owner，再改那一份及直接相依的契約／測試；其他文件只更新入口連結或失效的限定摘要。[逐檔用途索引](project-file-map.md)處理檔案與資料夾，不複製本表的內容所有權規則。
