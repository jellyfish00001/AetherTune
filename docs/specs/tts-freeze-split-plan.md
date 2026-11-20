# 純配音（Manual TTS／語音重建）凍結與 VSF 移交計畫

**文件擁有者：**本頁為凍結期間與拆分順序的唯一完整說明。決策原文見 [決策紀錄](../reference/decision-log.md#2026-11-20-aethertune-即時變聲邊界與純配音凍結)；進度摘要見 [目標與任務進度](../status.md)。

**基線 commit：**`origin/main` @ `05b1ec4`（本 worktree 分支 `exp/tts-freeze-plan`）。

**產品邊界（已採納）：**AetherTune 只負責即時變聲與混音。內容配音（TTS、角色聲線、語音克隆、離線／品質取向的語音重建）移交 創作工坊 Bot 的 VisualSoundForge（VSF）；重疊能力以 VSF 為準。本輪僅凍結標記與計畫，不刪除程式、不移除 UI、不改變行為。

---

## 1. 純配音功能盤點（凍結後移交 VSF）

下列項目皆為「以 CosyVoice2／Breeze TTS 2 產生完整 WAV、或 STT→TTS 重建」能力；與即時 VC 共用之 playback／裝置列舉見 §2。

### 1.1 產品功能（需求 ID）

| 項目 | 說明 | 主要依據 |
|---|---|---|
| F03 Manual TTS | 手動文字、Queue、Transcript、雙 TTS 引擎 | `docs/specs/app-requirements.md` §F03（約 L31–36） |
| F04.3 重建（STT→TTS） | 共用文字發聲佇列、backend_stt 提供者 | 同上 §F04.3（約 L43） |
| M6 TTS 里程碑 | CosyVoice2／Breeze Manual 已接通 | `docs/status.md` M6 列（約 L115） |

**不重複凍結為「純配音」者（留在 AetherTune 或另案）：**F02 四 VC、`services/engines/*` streaming／RVC；F10 Agent Reply 目前為 `PLANNED` 契約（`contracts/agent_reply.py`、`services/tts/service.py` 拒絕 agent source）；即時串流 TTS 邊界見 §3。

### 1.2 Desktop／Rust orchestration

| 路徑 | 角色 |
|---|---|
| `app/src/components/SpeechWorkspace.tsx` | Manual TTS UI（`inputSource: 'manual_text'`，約 L177） |
| `app/src/services/speech.ts` | `speech_status`／`speech_action`、`audio_devices`（約 L408–410） |
| `app/src/services/desktop.ts` | 匯入 `cosyvoice.json`／`breeze.json` manifest（約 L7–8） |
| `app/src-tauri/src/speech_manager/mod.rs` | 以 `seed-vc` venv 啟動 `services.tts.service`（L33–36、L140） |
| `app/src-tauri/src/bin/speech-probe.rs` | CosyVoice／Breeze 探針 CLI（約 L8） |
| `app/src-tauri/src/main.rs` | `speech_blocks_vc` 與 VC `start` 互鎖（L96–97、L102–106、L117） |
| `app/src/main.tsx` | 掛載 `SpeechWorkspace`（約 L444–446） |

### 1.3 `services/tts/`（生成與 Manual 專用邏輯）

| 路徑 | 角色 |
|---|---|
| `services/tts/adapters.py` | CosyVoice2／Breeze `ResidentGenerationAdapter`、WSL runner（L1–5、L392–408、L545–558） |
| `services/tts/wsl_job.py` | WSL 子行程 mailbox（adapter 依賴） |
| `services/tts/validation.py` | `ALLOWED_ENGINES = {"cosyvoice", "breeze"}`（L9、L47） |
| `services/tts/service.py` | Queue／generation／playback 編排；**整檔**在拆分前視為凍結區，但其中 `playback`／`list_audio_devices` 為 VC 共用（§2） |
| `services/tts/postfx.py` | TTS 請求後製 FX |
| `services/tts/snapshot.py`、`storage.py` | Manual TTS session／SQLite／Transcript |

**VC 亦會 import 的模組（先抽出再移交）：**`services/tts/playback.py`（§2）。

### 1.4 契約與 catalogue

| 路徑 | 角色 |
|---|---|
| `contracts/engines/cosyvoice.json` | CosyVoice TTS manifest；`supports_streaming_tts: false`（L11–12、L29–30） |
| `contracts/engines/breeze.json` | Breeze TTS 2 manifest（L11–12、L28–29） |
| `contracts/voices/*.json` | TTS reference voice profiles（4 檔） |
| `contracts/schemas/speech-request.schema.json` | Manual TTS request 形狀 |
| `contracts/schemas/voice-profile.schema.json` | Voice profile 形狀 |
| `contracts/schemas/tts-state.schema.json` | TTS snapshot／capabilities（含 `agent_reply: PLANNED`） |
| `contracts/model-load-estimates.json` | `cosyvoice`／`breeze` 載入估計（約 L112、L125） |
| `contracts/schemas/engine-manifest.schema.json` | **無** lifecycle 欄位；`additionalProperties: false`（L5–6）—凍結標記改以文件為準 |

### 1.5 工具與離線管線

| 路徑 | 角色 |
|---|---|
| `tools/cosyvoice-infer.py`、`tools/cosyvoice-setup.ps1` | CosyVoice runner／setup |
| `tools/cosyvoice-frontend-cudnn8-probe.ps1`、`tools/cosyvoice-frontend-probe.py` | CosyVoice 環境探測 |
| `tools/breeze-tts2-infer.py`、`tools/breeze-tts2-run.ps1`、`tools/breeze-tts2-setup.ps1`、`tools/breeze-tts2-webui.py` | Breeze runner／setup／WebUI |
| `tools/speech-reconstruction-run.ps1` | STT→TTS 一鍵 wrapper |
| `tools/speech-reconstruction-failure-regression.ps1` | 重建失敗 regression |
| `tools/tts-resident-worker.py` | WSL resident Manual TTS worker（L1–5） |
| `tools/voice-backend-check.ps1` | CosyVoice／Breeze 模型目錄就緒檢查（約 L33–42） |
| `tools/fixtures/cosyvoice/*`、`tools/fixtures/breeze-*` | Reference／target 文字 fixture |

### 1.6 模型登錄與文件

| 路徑 | 角色 |
|---|---|
| `models/backend-register.csv` | `cosyvoice2-0.5b`、`breeze-tts-2` 列 |
| `models/speech-reconstruction/**` | CosyVoice／Breeze／STT 權重目錄契約 |
| `backends/speech-reconstruction/README.md` | STT→TTS 操作契約 |
| `docs/verification/backends/cosyvoice-verification-latest.md` | CosyVoice 分項驗證 |
| `docs/verification/backends/breeze-tts2-verification-latest.md` | Breeze 分項驗證 |
| `docs/verification/desktop/manual-tts-verification-latest.md` | Desktop Manual TTS 驗證 |

### 1.7 測試與 regression

| 路徑 | 角色 |
|---|---|
| `services/tts/test_service.py`、`test_validation.py`、`test_snapshot.py`、`test_postfx.py` | TTS service 契約測試 |
| `app/tests/manual-tts.mjs`、`manual-tts-native-smoke.mjs` | Manual TTS UI／IPC |
| `app/tests/manual-contracts.mjs` | TTS state schema |
| `app/tests/resident-tts-smoke.py`、`manual-audio-smoke.py` | Resident worker／音訊 smoke |
| `app/tests/audio-effects.mjs`、`audio-tuning.mjs` | 含 TTS 引擎 manifest 的音效／調音測試 |

### 1.8 本機／ignored 路徑（不移交 Git，但 VSF 需對照）

由 manifest `requiredPaths` 與 adapter 硬編路徑指向：`tools/venvs/cosyvoice-wsl`、`tools/venvs/breeze-tts-wsl`、`tools/venvs/stt-wsl`、`tools/external/CosyVoice`、`tools/external/breeze-tts`、`models/speech-reconstruction/cosyvoice`、`models/speech-reconstruction/breeze-tts-2`（見 `contracts/engines/cosyvoice.json` L12–20、`adapters.py` L392–408）。

---

## 2. 須先抽出的共用基礎設施（拆分前）

以下為已核對的事實與建議落點（**提案**，本輪不實作）。

| 關切 | 現況（檔案:行） | 建議目標家 |
|---|---|---|
| 播放與監聽 route | VC `runner_service` 呼叫 `services.tts.playback.resolve_route`（`services/engines/runner_service.py` L71） | `services/audio/playback.py`（或 `services/audio/routing.py`） |
| RVC file 模式播放 | `rvc_runtime` 使用 `MonitoredPlayback`、`PlaybackCancelled`（`services/engines/rvc_runtime.py` L279–283） | 同上 |
| 裝置列舉 | UI `getAudioDevices` → action `audio_devices`（`app/src/services/speech.ts` L408–410）→ `list_audio_devices()`（`services/tts/service.py` L338–339；實作 `services/tts/playback.py` L89） | `services/audio/devices.py` |
| Speech service runtime venv | TTS service 固定 `tools/venvs/seed-vc/Scripts/python.exe`（`speech_manager/mod.rs` L33、L140） | 中立 `tools/venvs/audio-service/`（或拆成 VC venv + 輕量 audio helper） |
| Seed-VC 與 CosyVoice 資產重疊 | Seed-VC 需要 HiFT `hift.pt` from `FunAudioLLM/CosyVoice-300M`（`docs/reference/seed-vc-assets.md` L28） | **留在 AetherTune**；TTS checkpoint 移交 VSF 時不得誤刪 Seed-VC vocoder 依賴 |
| TTS／VC 互鎖 | `speech_blocks_vc`（`main.rs` L102–106）；`start` 前檢查（L117） | 中立「音訊／GPU runner 鎖」模組（Rust + 可選 Python），釋放後才啟動 VC |

**風險：**若在 S4 之前未抽出 playback／devices，VC validate／RVC file 播放會隨 TTS service 搬家而中斷。

---

## 3. 留在 AetherTune 與邊界／未決項

### 3.1 即時串流 TTS（直播／Agent Reply 類）

- 現行 adapter **只產完整 WAV**，`supports_streaming_tts: false`（`adapters.py` L3–4、`contracts/engines/cosyvoice.json` L11、`breeze.json` L11）。
- 產品架構保留 Generation／Playback 分層與 chunk 擴充（`docs/specs/app-requirements.md` 約 L244）。
- **品質／角色 TTS 模型**應由 VSF 擁有；AetherTune 未來若實作即時語音，應透過 **介面／契約** 引用 VSF，不複製 checkpoint。

### 3.2 待 Johnny 確認（open questions）

1. **F10 Agent Reply：**是否仍由 AetherTune 負責「即時觸發 + 播放編排」，僅將**生成**委派 VSF？或 F10 整體改在 VSF 交付？
2. **F04 常駐 STT：**Self STT 與 STT→TTS 重建中，哪些層留在 AetherTune（即時 capture）vs VSF（重建與克隆）？
3. **Desktop SpeechWorkspace：**凍結期是否維持現有 UI 作為過渡，還是僅 hidden／委派至 VSF？（本輪決策：不移除 UI。）

記錄管道： [未決問題](../reference/open-questions.md)（若需正式登記可另開條目）。

---

## 4. 分階段步驟（S0→S5）

| 階段 | 目標 | 主要觸及檔案 | 風險 | 驗證 | 回滾 | 工時 |
|---|---|---|---|---|---|---|
| **S0 凍結標記（今日）** | 文件與狀態標記；manifest 不違 schema | 本計畫、`status.md`、`decision-log.md`、`backends/speech-reconstruction/README.md` | 無 runtime 變更 | `python -c` 載入 `contracts/**/*.json`；`app/tests/contracts.mjs`（若有 Node） | 還原文件 commit | **S（2–4h）** |
| **S1 抽出 playback／devices** | VC 不再依賴 `services.tts.playback` 路徑語意 | 新增 `services/audio/*`；改 `runner_service.py` L71、`rvc_runtime.py` L279、`service.py` import | 循環 import、sounddevice 行為差異 | `services/engines/test_runner_service.py`；`app/tests/vc-native.mjs`；RVC validate 路徑 | 保留舊 re-export shim | **M（8–16h）** |
| **S2 脫鉤 TTS venv 與互鎖** | Speech service 不用 Seed-VC venv；互鎖改中立鎖 | `speech_manager/mod.rs` L33–36；`main.rs` L102–117 | 雙 service 搶 GPU／裝置 | `app/tests/manual-tts-native-smoke.mjs` + VC start 互斥手動案例 | 還原 venv 路徑與舊互鎖 | **L（16–32h）** |
| **S3 VSF 呼叫契約** | 定義 cross-repo API（HTTP／IPC／檔案 mailbox） | 新 `contracts/vsf-*` 或文件；`adapters.py` 邊界 | 授權、延遲、取消語意不一致 | 契約測試 + 假 VSF stub | 保留本機 adapter | **M（8–16h）** |
| **S4 移交／封存純配音程式** | 將 §1 清單移至 VSF repo 或 archive 分支 | §1 大量路徑 | 破壞 VC 尚未抽離的依賴 | `manual-tts*.mjs`、`resident-tts-smoke.py`、`speech-reconstruction-*` | VSF 未就緒則不做 S4 | **L（24–80h）** |
| **S5 清理（可選）** | 移除重複 catalogue、更新 discover | `desktop.ts`、`engine_manager` discover 列表 | 誤刪 VC manifest | 全契約 regression | 僅在 VSF 已承接後 | **M（8–16h）** |

---

## 5. 凍結期間規則

1. **§1 盤點路徑：**不得新增功能；僅允許修復阻擋 VC 或系統無法啟動的缺陷。
2. **§2 共用基礎設施：**允許重構與抽出，但需保持 VC 與既有測試行為不變（或先在計畫中增列驗證）。
3. **契約：**不得為凍結而修改 `engine-manifest.schema.json` 破壞驗證；引擎凍結說明以本頁與 `backends/speech-reconstruction/README.md` 為準。
4. **文檔：**新決策寫入 `decision-log.md`；進度摘要只改 `status.md`，細節留在本頁。
5. **禁止：**刪除程式、移除 UI、改變使用者可見行為（除非明確解阻 VC 的 bugfix）。

---

## 6. 相關連結（單行摘要）

| 文件 | 摘要 |
|---|---|
| [目標與任務進度](../status.md) | F03／M6 凍結狀態一行 |
| [產品需求 F03](app-requirements.md#f03) | Manual TTS 行為定義 |
| [語音重建 backend README](../../backends/speech-reconstruction/README.md) | STT→TTS 凍結註記 |
| [Seed 資產](../reference/seed-vc-assets.md) | Seed-VC 與 CosyVoice-300M 共用資產 |