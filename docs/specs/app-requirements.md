# AetherTune 產品規格：大功能、小功能與驗收範圍

**文件邊界：**本頁是功能範圍與預期行為的唯一權威；功能 ID 用於追蹤，不代表已完成。實作／驗收進度與工作順序只記在[目標與任務進度](../status.md)；程式、資料與效能設計看[App 架構](app-architecture.md)，測試條件看[驗證計畫](verification-plan.md)，操作看[Desktop 手冊](../guides/desktop-user-guide.md)。

規格整理日期：2026-10-01（Asia/Taipei）。保留 2026-09-27 v1 與後續增量要求，補上可供人與 Agent 共用的功能目錄。這次整理不代表新增音訊、UI 或效能實作。

## 功能目錄：先了解能做什麼

以下小功能是使用目的摘要；精確流程、限制與欄位由後半部行為規格及 `contracts/` 定義。依 F01～F10 到[進度表](../status.md)查看實作程度、證據與未完成項。

<a id="f01"></a>
### F01 統一工作區與桌面操作

- **F01.1 模式切換：**區分即時變聲、語音重建、文字發聲；畫面明確告知輸入來源與下一步操作。
- **F01.2 三種視窗：**Full 做完整設定，Compact 用於日常控制，Mini 保留狀態、停止與展開；主操作在各自視窗內可達。
- **F01.3 系統整合：**置頂、透明度、拖曳、鎖定、穿透、Tray、快捷鍵與完整退出；穿透必須有恢復操作入口。
- **F01.4 雙語與可及性：**繁中／英文即時切換、鍵盤操作、可讀標籤，切換不遺失草稿或重送工作。

<a id="f02"></a>
### F02 即時變聲與引擎控制

- **F02.1 四引擎：**Seed-VC／MeanVC2／X-VC 以 reference 轉換聲線；RVC 使用登錄角色模型與 index，不能混用素材流程。
- **F02.2 明確來源：**Mic 用於說話，RVC File 用於指定 WAV；不能把檔案播放誤標為麥克風即時變聲。
- **F02.3 生命週期：**預檢、載入、預熱、執行、停止、失敗與程序回收各有明確狀態；切引擎先釋放舊資源。
- **F02.4 參數控制：**依 manifest 呈現實際支援的參數，執行中不可改的項目鎖定並提示下次啟動套用。

<a id="f03"></a>
### F03 文字發聲與語音佇列

- **F03.1 手動文字：**CosyVoice2／Breeze TTS 2 使用所選聲音生成 WAV，再送指定播放端；不依賴 Mic 開啟。
- **F03.2 排程與取消：**Speak、FIFO、立即插播、拒絕新請求、排序、移除、停止目前工作與清除等待工作各自有明確語意。
- **F03.3 快速輸入：**完整 Composer、Compact 輸入、Mini popup、Recent／Favorites 與 IME 防誤送。
- **F03.4 結果追蹤：**顯示生成／播放／錯誤；只把完成播放的內容寫成已發聲 Transcript，保留每次送出的聲音、路由與音效快照。

<a id="f04"></a>
### F04 麥克風／遠端轉文字與語音重建

- **F04.1 Self STT：**physical Mic → VAD → STT，不擷取變聲後輸出或 TTS 回授。
- **F04.2 Remote STT：**擷取一個指定 playback source 的 WASAPI loopback，以 ME／REMOTE 區分來源；多人分離另期處理。
- **F04.3 重建：**STT → Text → TTS 共用文字發聲佇列，以 backend_stt 提供逐字稿，避免同一句跑兩次辨識。
- **F04.4 獨立服務：**切換或停止 VC 不停止 STT；GPU 資源優先給 VC，STT 預設 CPU。常駐 Desktop 與既有離線 CLI 分開驗收。

<a id="f05"></a>
### F05 聲音、模型與情境預設

- **F05.1 聲音目錄：**用 VoiceProfile 選 reference／逐字內容或 RVC 角色，保留來源、hash、語言及使用限制。
- **F05.2 Voice Library：**提供匯入、檢查與管理，讓使用者不必每次手填路徑；已附 catalogue 不等於完整管理功能。
- **F05.3 Preset：**保存、載入及辨識失效的 Mode／Engine／參數／聲音／裝置／音效／STT 組合；不能只保存名稱。
- **F05.4 模型準備：**沿用現有 RVC 資料 audit、訓練及 register 工具；Desktop 管理不自行重寫訓練算法。

<a id="f06"></a>
### F06 裝置、自己監聽、音效與輸出路由

- **F06.1 裝置選擇：**區分輸入、主輸出、監聽；精簡重複顯示但保留 exact name／Host API 與進階清單。
- **F06.2 自己監聽：**獨立開關與實體耳機／喇叭，不將虛擬輸出再回送造成迴授；停播同步回收。
- **F06.3 六引擎音效：**各自保存 EQ、壓縮、殘響、乾濕與增益；只重設選定引擎，已排隊工作不跟隨後續修改。
- **F06.4 外部 Rack／接收端：**沿用 Light Host／VST／VB-CABLE／Voicemeeter；不能自動控制的項目標為人工操作，Discord／OBS 等需逐段驗證。

<a id="f07"></a>
### F07 Session、逐字稿與歷史資料

- **F07.1 即時逐字稿：**保留來源、時間、provider 與已發聲狀態，支援捲動、暫停、篩選、複製與清畫面。
- **F07.2 歷史查詢：**跨 Session 搜尋、時間／來源篩選及分頁；清畫面不刪資料。
- **F07.3 持久化與匯出：**SQLite 保存 canonical records；JSONL／TXT 為可重建輸出，SRT 為選配；crash 不遺失已提交紀錄。
- **F07.4 資料生命週期：**資料版本、升級、備份還原、保留期限與使用者確認的清理；不能因 artifacts 被 ignored 就刪除。

<a id="f08"></a>
### F08 執行狀態、診斷與效能

- **F08.1 等待回饋：**分開排隊、冷載入、預熱、生成、播放與停止；顯示已等待時間，沒有可靠量測就不提供假 ETA。
- **F08.2 效能觀測：**區分載入時間、首音、模型 p50／p95、RTF、端到端延遲、drops、CPU／GPU／記憶體；缺值顯示 N/A。
- **F08.3 錯誤復原：**可理解的原因、下一步操作與詳細 log；提交逾時先確認是否已接受，避免重複發聲。
- **F08.4 同條件改善：**分開 cold／warm、不同引擎／模型／路由，比較改善前後；速度不得以音質、來源證據或取消清理退步換取。

<a id="f09"></a>
### F09 設定、安裝與更新

- **F09.1 偏好保存：**視窗、語言、音訊、Voice、Transcript 與進階設定各有清楚 owner；草稿不冒充可靠持久化。
- **F09.2 安裝交付：**開發版 exe、完整 installer、portable package 分別驗證；新機需檢查 runtime／模型與裝置條件。
- **F09.3 更新復原：**版本相容性、設定／資料 migration、失敗回復、OOM／crash recovery 與開機啟動；未實作選項不能假裝已生效。

<a id="f10"></a>
### F10 Agent Reply 與自動回覆擴充

- **F10.1 回覆來源：**AgentReplyProvider 產生可追溯文字，再交由既有 SpeechRequest／Queue／TTS 流程發聲。
- **F10.2 控制與權限：**Agent API、Personality、Auto Reply 與 Phrase Hotkeys 分項開發；未完成授權、取消及防回授前不得啟用自動發聲。

## 跨功能品質要求

- **N01 UI 可用性：**主流程能辨認來源、目的地及下一步；空白、載入、忙碌、錯誤都有可操作回饋。每次 UI 改善需自動化與實際畫面交叉驗證。
- **N02 執行效率：**先建立固定案例與 baseline，再優化冷啟動、warm 重用、UI 更新、資料匯出與記憶體；量測及判定規則由[驗證計畫](verification-plan.md#optimization-acceptance)擁有。
- **N03 程式／資料模組化：**沿用 React → Rust → service → adapter／audio／storage 分層；單向依賴、資料唯一 writer、版本與遷移按[架構邊界](app-architecture.md#modular-boundaries)執行，不能只靠拆檔宣稱完成解耦。
- **N04 人與 Agent 共用進度：**每個工作有功能 ID、責任模組、依賴、完成條件與證據；只在[進度頁](../status.md)維護工作狀態。Agent 交接流程在[維護手冊](../../.agent/reference/agent-maintenance-guide.md#task-handoff)。

## 詳細行為規格

## 產品目的與使用流程

將既有 Research Workbench 編排成日常 Windows Desktop App。使用者不需理解 Python venv、backend script 或命令列參數。新 App 使用 Tauri 2 + React + TypeScript，沿用既有 backend，不重新實作任何模型或音訊算法。

主要場景：VTuber／OBS、Discord／遊戲、通話、變聲測試、STT → TTS 重建、文字發聲及對話逐字紀錄。

統一流程：**Mode → Engine → Voice / Model → Devices → Preset → Start → Overlay**。不得依 backend 建立五套獨立 UI；CosyVoice／Breeze 的重建與文字發聲共用 Engine UI。

| Mode | 音訊／控制流程 | Engines |
|---|---|---|
| Streaming VC | Mic → VC → Post FX → Virtual Output | Seed-VC、MeanVC2、X-VC、RVC + FCPE／RMVPE |
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

介面語言在設定中切換繁體中文／英文，預設繁中；操作、提示、狀態、可及性名稱與系統匣依同一偏好立即更新，完整重開仍保留。切換不清空草稿、不修改路由／音效或重新送出佇列；機器 ID、裝置名稱、使用者內容與原始診斷資料保留原文。保存／系統匣失敗明確提示，無效儲存值回到繁中。

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

RVC 已提供四個登錄角色的 `model_id`、Mic／來源 WAV、FCPE／RMVPE、pitch、index rate、chunk、crossfade 與 extra context 控制。`.pth/.index` 由 register 配對及驗 hash，不使用 zero-shot reference WAV。自己監聽預設關閉，可另選實體播放端；參數／監聽在執行時鎖定，Stop 後再啟動套用。實作存在與 callback 驗證不改變 CANDIDATE／LIVE 分類。

Preset 保存 Mode、Engine、參數、reference、model、Audio Rack、input／output 與 STT settings。範例：Gaming Fast、VTuber Natural、Female Soft、Seed Low Latency／Quality、MeanVC2 40ms、CosyVoice Natural。

VoiceProfile 獨立於模型：共用 reference audio／text，加 `engineOverrides` 的 Seed／Mean／Cosy 參數，或 RVC `.pth`／`.index`／pitch。選聲音取代每次找權重與 WAV。

Engine 切換採 Stop old → 釋放 GPU／audio → Load new → Ready → Start；第一版不做無縫 hot swap。**STT 不隨 Engine 停止。**

統一 lifecycle：`OFFLINE / VALIDATING / LOADING / READY / RUNNING / STOPPING / ERROR`。READY 必須有模型 readiness 證據；檔案存在／PID 成立只可視為預檢／載入中。Engineering classification 獨立使用 `LIVE / CANDIDATE / OFFLINE / WAITING / BLOCKED / LEGACY`，不是 Start 的唯一開關。

## 音訊與服務邊界

即時 PCM 只能走 Mic → Python Backend → Output；**禁止經 Tauri IPC／JS／WebView**。IPC 只傳 status、commands、parameters、metrics、transcript、error、log。

第一版控制協定是 JSON Lines over stdio，之後才評估 Named Pipe／Local Socket。已有 runner 不符合協定時由外層 Adapter 包裝；不修改 upstream 行為。開發期可標示 TEMPORARY 啟動 upstream GUI，最終日常產品必須是 headless runner。

AudioDeviceRegistry 的 canonical device：`id/name/direction/host_api/channels/sample_rate/is_default`。Adapter 映射成 PortAudio name／index 或 WASAPI endpoint；不能讓不同 backend 形成不同 UI 身分。

Manual TTS 的輸出選單預設每個裝置只顯示一項，收起重複 Host API、系統音效對應表、WDM-KS 與額外虛擬通道；進階選項保留完整 PortAudio 清單。MME 截短名稱只能在唯一符合完整名稱時合併；目前選中的 exact name／Host API 必須保留，切換顯示模式不得改變播放路由。這是顯示層篩選，不卸載系統裝置。

Manual TTS 提供預設關閉的「自己監聽」與獨立耳機／喇叭選擇。提交時在 `metadata.route.monitor` 保存 `enabled`、精確 `output`／`host_api`，已接受的 queue request 保留快照，切 layout 不重設、完整重啟關閉。停播同時停止主輸出與監聽；監聽失敗只記錄獨立警告，不重播、改送或取消已完成主輸出。同名實體主輸出只開一條 stream，禁止將已知 CABLE／Voicemeeter 虛擬線路當監聽回送。主輸出為實體裝置時不受額外監聽開關影響。音訊仍在 Python playback 處理，不經 WebView／IPC 傳 PCM；本機 callback 不升格 Discord、聽評或 LIVE。

內建音效在 SETTINGS 調整：RVC／MeanVC2／X-VC／Seed-VC／CosyVoice／Breeze 各有獨立、可持久保存的紀錄，包含啟用、三頻 EQ、壓縮閾值／比例、殘響、乾濕及增益。切換項目還原各自設定，重設只影響選定引擎；保存失敗明確提示。VC 於下一次 START 套用；TTS 於送出時保存快照，生成後於播放前處理，原始生成 WAV 保留。內建音效不等於外部 VST 或 LIVE 驗收。

Audio Rack 跨 backend 共用：EQ、De-Esser、Compressor、Saturation、Pitch Correction、Ambience、Limiter。外部 Rack 沿用既有 Light Host／Graillon／VB-CABLE／Voicemeeter；無法程式控制的效果標示 **External / Manual**，提供 Open Rack。不得自行寫完整 VST3 host或假稱已套用。

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
| M2 | VC EngineManager、ProcessManager、validate／start／stop／status／log／crash；早期由 Seed／Mean／X skeleton 起步，後續接入 RVC |
| M3 | manifest 動態參數與 Preset Save／Load |
| M4 | Mic + Remote、VAD、STT abstraction、SQLite／JSONL／TXT、history |
| M5 | Voice Library／VoiceProfile |
| M6 | CosyVoice2／3、Breeze 共用 Mode → Engine |
| M7 | existing Audio Rack adapter／routing |
| M8 | installer、auto update、startup、migration、OOM／recovery、packaging／portable |

原始日常 MVP = Overlay + Seed／Mean／X 即時統一控制 + Mic／Remote STT + history + Preset。M0～M8 保留需求分組用途；後續 TTS／RVC 提早接入不代表 STT／history／Preset 已完成。目前交付程度與優先順序以[任務進度](../status.md)為準，不以最高 M 編號推定 MVP 完成。

驗收須分開列：三種 UI、置頂、半透明、drag、click-through、Tray／遊戲滑鼠；三個 engine 的實際啟停、crash／AppExit cleanup；schema forms／presets；ME／REMOTE 即時轉文字、crash durability／exports；canonical device、PCM datapath；既有 verification 相容性。每個 milestone 要有可重跑檢核及 PASS／WAITING／BLOCKED 證據，UI 可開與音訊可用不能合併為整體 PASS。

第一輪原本不做模型／音訊算法重寫、Tk UI 刪除、TTS integration、Audio Rack rewrite、Diarization、Installer。其他 non-goals：cloud account／DB、手機／macOS／Linux UI、同時 preload 五個模型、合併 Python venv。2026-09-29 使用者決定移除舊 Tk 控制台，並以根目錄 `AetherTune.exe` 作為單一圖形入口；這項入口決定不代表 Desktop 的 VC params／devices／results 已達到舊控制台的功能完整度，缺口仍依 M3／後續驗收處理。

第一輪驗收報告見 [app-verification-latest.md](../verification/desktop/app-verification-latest.md)。

## Manual TTS 與 Agent Reply 增量

使用者增量規格要求 Speech Reconstruction 有 `microphone`、`manual_text`、`agent_reply` 三個 Input Mode。Manual Text 與麥克風狀態解耦；Microphone/STT runtime 尚未交付的部分保持 WAITING，Agent Reply 停用且 PLANNED。Microphone 選項下仍可使用文字 Composer，不能要求先關閉 Mic。Self STT 接入時只接受 physical microphone capture，不得讀取 mixed output／TTS loopback。

所有文字發聲共用 `SpeechRequest → SpeechQueue → TTSOrchestrator → Engine Adapter → 內建 Post-FX → Playback → 現有外部 Audio Rack／Output`。沿用 CosyVoice2、Breeze TTS 2 runner 與 reference；CosyVoice3 未安裝不得作為可選 runtime。沿用既有路由 profile 與外部 Rack，不新增 VST host。

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
