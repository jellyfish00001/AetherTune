# AetherTune 文件入口

本頁讓人與 Agent 共用相同規格與進度，再依任務找到唯一 owner。Agent 規則與 Skill 在 [`.agent/`](../.agent/README.md)；本頁不複製功能表、待辦、操作步驟或實測數字。

## 先了解產品與目標進度

| 想了解什麼 | 唯一完整內容 |
|---|---|
| 想先看「文字轉語音、變聲、語音重建、混音……」條列需求 | [應用功能需求單](specs/application-feature-checklist.md)：依操作目的排列的大功能與小功能摘要 |
| 有哪些大功能？每個小功能做什麼？ | [產品規格 F01～F10／品質要求 N01～N04](specs/app-requirements.md) |
| 現在做到哪裡？下一批優先做什麼？ | [目標與任務進度](status.md)：交付程度、證據、任務 ID、依賴、完成條件及人工條件 |
| UI、效能、程式／資料架構如何改善？ | [App 架構](specs/app-architecture.md#modular-boundaries)：現況、依賴邊界、資料 writer／migration；執行順序只看進度頁 |
| 怎樣才算完成，而不是只有畫面或程式？ | [驗證計畫](specs/verification-plan.md#optimization-acceptance)：UI、baseline／after、行為相容、資料復原與各證據層 |
| 下一位 Agent 如何接手？ | [快速地圖](../.agent/reference/agent-quick-map.md)找 owner → [維護手冊交接流程](../.agent/reference/agent-maintenance-guide.md#task-handoff) |

## Agent：先找 owner

| 任務 | 先讀 | 必要時再讀 |
|---|---|---|
| 判斷專案邊界與修改規則 | [專案規則](../.agent/rules/project.md) | [系統架構](specs/architecture.md)、[多後端契約](specs/voice-conversion-architecture.md) |
| 找程式修改位置 | [Agent 快速地圖](../.agent/reference/agent-quick-map.md) | [逐檔索引](../.agent/reference/project-file-map.md)、[維護手冊](../.agent/reference/agent-maintenance-guide.md) |
| 改 Desktop 預期行為或 IPC | [產品需求](specs/app-requirements.md)、[App 架構](specs/app-architecture.md) | `contracts/`、[Manual TTS 驗證](verification/desktop/manual-tts-verification-latest.md) |
| 加 backend、模型或來源 | [多後端契約](specs/voice-conversion-architecture.md)、[backend README](../backends/README.md) | [來源審核](reference/source-audit.md)、[Seed 資產](reference/seed-vc-assets.md)、[模型盤點](reference/current-rvc-model-inventory.md) |
| 判定 LIVE／音訊證據 | [LIVE gate](specs/live-gate.md)、[驗證計畫](specs/verification-plan.md) | 對應分項驗證與當輪 artifact |
| 查 VCClient 相容性 | [runtime gate](specs/vcclient-runtime-gate.md) | [packaged 實測](verification/backends/vcclient-packaged-repair-latest.md)、[RVC probe](verification/backends/vcclient-rvc-probe-latest.md) |

**權威順序：**`contracts/` schema／manifest 和實際程式定資料契約；需求與架構定預期；本輪可重跑 artifact、verifier、命令輸出定實測結果。衝突時標出缺口並修正文檔，不以摘要覆蓋證據。同一資訊只在一份 owner 文件完整記錄，其他位置只放限定摘要與連結。

## 開發者：狀態、規劃與追溯

| 要查什麼 | 文件 |
|---|---|
| 功能進度、工作順序與未解項 | [目標與任務進度](status.md)；驗證結果以分項報告的日期與 artifact 為準 |
| 待驗收條件 | [驗證計畫](specs/verification-plan.md)、[LIVE gate](specs/live-gate.md) |
| 已採納與未定案選擇 | [決策紀錄](reference/decision-log.md)、[未決問題](reference/open-questions.md) |
| 來源、資產、模型 | [來源審核](reference/source-audit.md)、[Seed 資產](reference/seed-vc-assets.md)、[RVC 模型盤點](reference/current-rvc-model-inventory.md)、[參數模板](reference/parameter-matrix-template.csv) |

### 分項驗證：只對報告日期與測試範圍有效

| 範圍 | 報告 |
|---|---|
| Desktop 與本機入口 | [介面語言](verification/desktop/ui-language-verification-latest.md)、[六引擎音效設定](verification/desktop/audio-effects-verification-latest.md)、[操作畫面審查](verification/desktop/usability-audit-latest.md)、[四 VC 串流／音效修復](verification/desktop/realtime-vc-verification-latest.md)、[Manual TTS](verification/desktop/manual-tts-verification-latest.md)、[App 首輪](verification/desktop/app-verification-latest.md) |
| Desktop 資料效能 | [隔離 DB／export／snapshot 基準](verification/desktop/performance-baseline-latest.md)：實測範圍、raw artifact、來源 hash 與尚未量測的層級 |
| Desktop 載入與調音 | [載入提示、引擎參數、輸入降噪及提示介面](verification/desktop/audio-tuning-verification-latest.md)：本輪模型／DSP／Browser／原生 WebView2 證據與人耳驗收邊界 |
| Streaming VC／模型 | [Backend 安裝與基本音訊](verification/backends/backend-install-test-latest.md)、[Seed readiness](verification/backends/seed-vc-readiness-latest.md)、[Seed GUI 音訊](verification/backends/seed-vc-verification-latest.md)、[RVC 模型 audit](verification/backends/rvc-model-audit-latest.md) |
| Speech Reconstruction | [CosyVoice](verification/backends/cosyvoice-verification-latest.md)、[Breeze TTS 2](verification/backends/breeze-tts2-verification-latest.md) |
| VCClient／音訊線路 | [packaged repair](verification/backends/vcclient-packaged-repair-latest.md)、[RVC probe](verification/backends/vcclient-rvc-probe-latest.md)、[latency matrix](verification/backends/vcclient-rvc-latency-matrix-latest.md)、[wiring](verification/audio/wiring-verification-latest.md)、[客觀 WAV 比較](verification/audio/audio-quality-comparison-latest.md) |

歷史快照：[本機環境](archive/local-environment.md)、[初次線路部署](archive/wiring-deployment-report.md)、[Seed 2026-09-26](archive/seed-vc-readiness-2026-09-26.md)、[候選 intake 2026-09-26](archive/streaming-vc-candidate-intake-2026-09-26.md)、[架構審查 2026-09-27](archive/project-architecture-review-report-2026-09-27.md)、[已移除的 Python／Tk 控制台驗證](verification/desktop/python-ui-verification-latest.md)。檔名含 `latest` 也要看內文日期，不能推論今天重新驗證。

## 一般使用者：從操作開始

| 需求 | 唯一操作文件 |
|---|---|
| 第一次 Desktop 文字發聲 | [快速使用](guides/quick-start.md) |
| Desktop 建置、Queue、輸出與排錯 | [Desktop 手冊](guides/desktop-user-guide.md) |
| 選擇 Seed-VC／RVC／STT → TTS 路線 | [後端使用手冊](guides/user-guide.md)，特有命令在[各 backend README](../backends/README.md) |
| Windows 虛擬音訊、VST 與終端接線 | [音訊路由手冊](guides/operation-guide.md) |
| RVC 資料、訓練與模型登錄 | [模型訓練手冊](guides/model-training-guide.md) |
