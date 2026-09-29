# AetherTune Desktop App — 產品需求與實作規格 v1

**文件邊界：**本頁是 Desktop 的**預期產品行為與里程碑**，不是已完成功能清單。實作分層看[app-architecture.md](app-architecture.md)，實際操作看[Desktop 手冊](../guides/desktop-user-guide.md)，哪些測試通過看[Desktop](../verification/desktop/app-verification-latest.md)與[Manual TTS](../verification/desktop/manual-tts-verification-latest.md)的分項驗證；不能把本頁的 M4～M8 計畫當成 runtime PASS。

日期：2026-09-27。依使用者提供的 v1 規格建立；首次交付 M0、M1、M2 skeleton。後續 Manual TTS 增量範圍以下節為準。

## 產品目的與使用流程

將既有 Research Workbench 編排成日常 Windows Desktop App。使用者不需理解 Python venv、backend script 或命令列參數。新 App 使用 Tauri 2 + React + TypeScript，沿用既有 backend，不重新實作任何模型或音訊算法。

主要場景：VTuber／OBS、Discord／遊戲、通話、變聲測試、STT → TTS 重建、文字發聲及對話逐字紀錄。

統一流程：**Mode → Engine → Voice / Model → Devices → Preset → Start → Overlay**。不得依 backend 建立五套獨立 UI；CosyVoice／Breeze 的重建與文字發聲共用 Engine UI。

| Mode | 音訊／控制流程 | Engines |
|---|---|---|
| Streaming VC | Mic → VC → Post FX → Virtual Output | Seed-VC、MeanVC2、X-VC、RVC + FCPE Legacy |
| Speech Reconstruction | Mic → VAD → STT → Text → TTS → Post FX → Virtual Output | CosyVoice2／3、Breeze TTS 2 |
| Text → Voice | Typed Text → TTS → Post FX → Virtual Output | 與重建共用 TTS Engine |

Engine 以 capabilities 宣告 `realtime_vc`、`speech_reconstruction`、`text_to_speech`；capability 是產品介面契約，不代表本輪 Adapter 已實作即時音訊。

## Desktop 與顯示狀態

Rust 負責 window／overlay／tray、程序、global hotkey、single instance、Windows 裝置發現、health 及 cleanup。React 負責操作畫面、manifest parameter forms、Voice／Preset、Transcript 與狀態。

| 顯示狀態 | 尺寸／內容 |
|---|---|
| Full Control Center | 約 900–1100 × 650–800；LIVE、VOICE、TRANSCRIPT、AUDIO、SETTINGS；進階參數與 Diagnostics |
| Compact Overlay | 寬 380–450；Mode、Engine／Voice、裝置、Start／Stop、Latency／GPU、Transcript |
| Mini Overlay | Running、Engine、Latency、Mic、Start／Stop、Expand |

上述 Full 分頁是完整產品目標。2026-09-30 的開發版只顯示 `WORKSPACE` 與 `SETTINGS`；原 `LIVE`／`VOICE`／`TRANSCRIPT` 三個同畫面分頁及尚未完成的 `AUDIO` 頁暫時收起，待各頁有獨立功能與驗證後再開放。`WORKSPACE` 的 TTS 播放裝置與 VC 麥克風／輸出使用 PortAudio 端點下拉選擇；這不代表 Mic STT 或即時音訊鏈已完成。

Overlay 必須支援 frameless、透明、Always on Top、drag、lock position、click-through、可調 opacity、模式切換、show／hide 與 Tray。預設 `Ctrl+Alt+A` 顯示／隱藏，`Ctrl+Alt+V` Start／Stop；快捷鍵可修改。Click-through 必須有快捷鍵／Tray 的解除入口。

關閉主視窗預設收至 Tray。完整產品 Tray：Open、Show Overlay、Start／Stop、Mute、Current Engine、Open Transcript、Exit。第一輪只有可以實際執行的 window／runner／Exit 項目，Mute／Transcript 不作假操作。

## Engine、參數、Preset、Voice

Manifest canonical location：`contracts/engines/*.json`。參數控制項包含 slider、select、toggle、number、file、text，分 basic／advanced／expert；advanced 預設折疊、expert 預設隱藏。UI 不硬寫成各 backend 專用畫面。

| Engine | 參數族群 |
|---|---|
| Seed | diffusion、CFG、chunk／block、crossfade、extra context、precision／device profile |
| MeanVC2 | 40ms／120ms 模型、reference、device |
| X-VC | current、chunk、future、smooth |
| RVC | model、index、F0、pitch、index rate、chunk、extra frame |
| CosyVoice | reference audio／text、speed、language、streaming、2／3 profile |
| Breeze | reference、voice design、instruction、CFG |

Manifest 只宣告現有 runner 真正接受的參數；Seed launcher 固定 realtime-tiny／FP32／CUDA 0，不將未支援 FP16／length adjust 誤呈為可修改。其他 upstream 選項需完成 runner support 才加入。

Preset 保存 Mode、Engine、參數、reference、model、Audio Rack、input／output 與 STT settings。範例：Gaming Fast、VTuber Natural、Female Soft、Seed Low Latency／Quality、MeanVC2 40ms、CosyVoice Natural。

VoiceProfile 獨立於模型：共用 reference audio／text，加 `engineOverrides` 的 Seed／Mean／Cosy 參數，或 RVC `.pth`／`.index`／pitch。選聲音取代每次找權重與 WAV。

Engine 切換採 Stop old → 釋放 GPU／audio → Load new → Ready → Start；第一版不做無縫 hot swap。**STT 不隨 Engine 停止。**

統一 lifecycle：`OFFLINE / VALIDATING / LOADING / READY / RUNNING / STOPPING / ERROR`。READY 必須有模型 readiness 證據；檔案存在／PID 成立只可視為預檢／載入中。Engineering classification 獨立使用 `LIVE / CANDIDATE / OFFLINE / WAITING / BLOCKED / LEGACY`，不是 Start 的唯一開關。

## 音訊與服務邊界

即時 PCM 只能走 Mic → Python Backend → Output；**禁止經 Tauri IPC／JS／WebView**。IPC 只傳 status、commands、parameters、metrics、transcript、error、log。

第一版控制協定是 JSON Lines over stdio，之後才評估 Named Pipe／Local Socket。已有 runner 不符合協定時由外層 Adapter 包裝；不修改 upstream 行為。開發期可標示 TEMPORARY 啟動 upstream GUI，最終日常產品必須是 headless runner。

AudioDeviceRegistry 的 canonical device：`id/name/direction/host_api/channels/sample_rate/is_default`。Adapter 映射成 PortAudio name／index 或 WASAPI endpoint；不能讓不同 backend 形成不同 UI 身分。

Audio Rack 跨 backend 共用：EQ、De-Esser、Compressor、Saturation、Pitch Correction、Ambience、Limiter。MVP 只接既有 Light Host／Graillon／VB-CABLE／Voicemeeter；無法程式控制的效果標示 **External / Manual**，提供 Open Rack。不得自行寫完整 VST3 host或假稱已套用。

## Transcript、Session 與儲存

常駐獨立 Transcription Service：physical Mic 同時供 VC 與 Self STT；Self STT 不讀變聲後輸出。Remote 使用選定 playback device 的 WASAPI loopback。MVP：Mic + 一個 Remote source，設備區分 ME／REMOTE，不要求辨識多人。

每個 source 保留 `source_id/source_type/device_id/display_name`，可改名如 Discord。`speaker_id` optional，Diarization 留 Phase 2。

Speech Reconstruction 的既有 STT 直接提供 `backend_stt` TranscriptProvider，禁止再跑第二次 self STT。其他 provider：`parallel_stt`、`manual_text`。

流程：Capture → VAD → Segment → TranscriptionEngine → utterance event。第一版 Faster-Whisper，抽象可換 Whisper.cpp／SenseVoice。Streaming VC 優先 GPU，STT 預設 CPU／small，GPU shared mode 另測。

SQLite 為 canonical storage；每個 utterance 立即 commit／flush，crash 不應遺失已完成 utterance。同步 session export：

```text
artifacts/sessions/<time-id>/
  session.json
  transcript.jsonl
  transcript.txt
  transcript.srt  # optional
```

Transcript event 必含 uuid、session、source、device、started／ended、language、text、confidence、provider，並保留 optional speaker。正式 JSON schema 在 `contracts/schemas/`。

Overlay：auto-scroll／pause、ME／REMOTE／Source filters、Copy、Clear View；Clear View 不刪 History。Full Viewer：Session history、搜尋、時間／source 篩選、TXT／JSONL／SRT export。Start 建立 Session，記錄 Engine、Model、Reference、Parameters、Audio Route、PostFX 與 Transcript。

## 狀態、錯誤與設定

Overlay 持續顯示 Engine／Status／Latency／Mic／Output／STT。Metrics：startup、first audio、rolling、p50／p95、dropout、underrun、GPU memory／utilization、CPU；無來源一律 N/A。

沿用專案 LIVE_GATE 首包 <= 5 秒及完整 mic、identity、600 秒、聽評要求。不能用程序成功、模型載入或 CUDA log 取代音訊證據。

錯誤至少分類 MODEL_NOT_FOUND、DEVICE_NOT_FOUND、DEVICE_BUSY、CUDA_OOM、BACKEND_CRASH、REFERENCE_INVALID、ROUTE_FAILED、STT_FAILED，顯示可理解的原因與重掃／Log 等修復入口。Full Diagnostics 提供 app／backend／STT log、程序、裝置、GPU、health；Compact 不塞工程 log。

Settings：General（Windows startup、start minimized、overlay、opacity、hotkeys）；Audio（default input／output、monitor、remote source）；Voice（Mode／Engine／Voice）；Transcript（enabled、provider、model、device、language、history folder、retention）；Advanced（backend／Python／WSL paths、CUDA、logging、developer mode）。未實作項目不得偽造設定生效。

## 里程碑、MVP 與驗收

| Milestone | 交付 |
|---|---|
| M0 | requirements／architecture；六個 Engine Manifest、state／transcript／session schema |
| M1 | Tauri desktop shell、三種顯示、Overlay／Tray／Hotkey；不碰 AI 算法 |
| M2 | Seed／Mean／X EngineManager、ProcessManager、validate／start／stop／status／log／crash；本輪 skeleton |
| M3 | manifest 動態參數與 Preset Save／Load |
| M4 | Mic + Remote、VAD、STT abstraction、SQLite／JSONL／TXT、history |
| M5 | Voice Library／VoiceProfile |
| M6 | CosyVoice2／3、Breeze 共用 Mode → Engine |
| M7 | existing Audio Rack adapter／routing |
| M8 | installer、auto update、startup、migration、OOM／recovery、packaging／portable |

日常 MVP = Overlay + Seed／Mean／X 即時統一控制 + Mic／Remote STT + history + Preset。可先發布 MVP 而不等 TTS、RVC、Diarization、VST automation；但本輪 skeleton **不是該 MVP**。

驗收須分開列：三種 UI、置頂、半透明、drag、click-through、Tray／遊戲滑鼠；三個 engine 的實際啟停、crash／AppExit cleanup；schema forms／presets；ME／REMOTE 即時轉文字、crash durability／exports；canonical device、PCM datapath；既有 verification 相容性。每個 milestone 要有可重跑檢核及 PASS／WAITING／BLOCKED 證據，UI 可開與音訊可用不能合併為整體 PASS。

第一輪原本不做模型／音訊算法重寫、Tk UI 刪除、TTS integration、Audio Rack rewrite、Diarization、Installer。其他 non-goals：cloud account／DB、手機／macOS／Linux UI、同時 preload 五個模型、合併 Python venv。2026-09-29 使用者決定移除舊 Tk 控制台，並以根目錄 `AetherTune.exe` 作為單一圖形入口；這項入口決定不代表 Desktop 的 VC params／devices／results 已達到舊控制台的功能完整度，缺口仍依 M3／後續驗收處理。

第一輪驗收報告見 [app-verification-latest.md](../verification/desktop/app-verification-latest.md)。

## Manual TTS 與 Agent Reply 增量

使用者增量規格要求 Speech Reconstruction 有 `microphone`、`manual_text`、`agent_reply` 三個 Input Mode。Manual Text 與麥克風狀態解耦；Microphone/STT runtime 尚未交付的部分保持 WAITING，Agent Reply 停用且 PLANNED。Microphone 選項下仍可使用文字 Composer，不能要求先關閉 Mic。Self STT 接入時只接受 physical microphone capture，不得讀取 mixed output／TTS loopback。

所有文字發聲共用 `SpeechRequest → SpeechQueue → TTSOrchestrator → Engine Adapter → Playback → 現有外部 Audio Rack／Output`。沿用 CosyVoice2、Breeze TTS 2 runner 與 reference；CosyVoice3 未安裝不得作為可選 runtime。沿用既有路由 profile 與外部 Post-FX，不新增 VST host。

- Speak 在 idle 立即開始；busy 時套用 Queue（預設）、Interrupt Current、Reject New Request。
- Add to Queue 永遠排入 FIFO；支援 Remove、Clear、Move Up／Down、Speak Now。
- Stop Speaking 僅取消 current generation／playback，pending queue 可繼續；Clear Queue 只取消 pending。兩者均不結束 App／STT。
- Request 保存 engine、voice、route 的提交時快照。切換 Voice 只影響下一次提交。
- Generation 與 Playback 分離，可取消；目前既有 adapter 產生完整 WAV，因此 `supports_streaming_tts=false`。保留 chunk 介面，不能宣告 streaming 首包成功。
- 記錄 created／generation started／first audio／playback started／completed，以及 TTFA、generation latency、total response latency。未完成欄位為 null，不能填假數值。
- 只有完成播放後寫入 ME Transcript：`source_type=self`、`provider=manual_text`、`transcript_provider=manual_text`、`speech_status=completed`。queued／cancelled／failed 保留 request history，不當成已說出的內容。
- Full Composer、Compact Quick Input、Mini `[T]` popup；Enter 送出、Shift+Enter 換行可在 Settings 修改，IME 選字不得誤送。
- Recent／Favorites 保存常用文字；Phrase Hotkeys、Agent API／Personality／Auto Reply 本輪 PLANNED。

共用 Session／SQLite／Transcript 不因 Input Mode、Voice、TTS Engine 切換而重建。既有 VC EngineManager 尚維持單一 active runner；VC 執行中應先 Stop runner 再啟動 TTS，不能同時爭用同一 GPU／Output。這項限制不代表要求 Mic STT 關閉。

驗收須分開記錄真實模型／VB-CABLE 音訊與注入 fixture 的 Queue 測試：Mic OFF、Mic ON 共存、三句 FIFO、取消、voice switch、engine error recovery、provider、20-request 程序穩定性。實體 Mic／外部 Rack／人工聽評未完成時保留 WAITING。增量結果見 [manual-tts-verification-latest.md](../verification/desktop/manual-tts-verification-latest.md)。
