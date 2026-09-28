# AetherTune Desktop App — 架構與開發入口

**文件邊界：**本頁只定義 Desktop React／Tauri／Python 的分層、程序生命週期與 IPC 設計。產品預期行為由 [app-requirements.md](app-requirements.md) 擁有；建置、測試與除錯命令由 [agent-maintenance-guide.md](agent-maintenance-guide.md) 擁有；真實結果見對應驗證報告。`backends/`、`tools/`、`models/`、`audio-rack/`、`benchmarks/` 與已驗證 runner 保持各自責任。

```mermaid
flowchart TB
  UI[React: Mode → Engine → Voice → Devices] -->|JSON commands / events| T[Tauri Rust]
  T --> W[Window / Tray / Hotkeys / Single instance]
  T --> EM[EngineManager: one active engine]
  EM --> PM[ProcessManager: Windows Job Object]
  PM --> B[services/engines/runner_service.py]
  B --> S[既有 Seed GUI launcher: TEMPORARY]
  B --> M[既有 MeanVC2 WAV runner]
  B --> X[既有 X-VC WAV runner]
  UI -. M4 .-> STT[獨立 Transcription Service]
  STT -.-> DB[SQLite + session exports]
  S -. 未驗證完整鏈路 .-> R[共用 Audio Rack → Virtual Output]
```

## 責任與依賴

| 位置 | 責任 |
|---|---|
| `app/src/main.tsx`／`services/desktop.ts` | 三種 layout、capability filtering、明確的 pending UX、Tauri IPC |
| `app/src-tauri/src/main.rs` | 原生視窗、Tray、快捷鍵、single instance、commands、Exit |
| `app/src-tauri/src/engine_manager/` | discover／validate／start／stop／status／logs，串行切換 |
| `app/src-tauri/src/process_manager/` | suspended spawn → assign Job → resume；stdout／stderr；crash／cleanup |
| `services/engines/runner_service.py` | JSONL bridge、參數／reference／端點預檢、受限制的 runner argv |
| `contracts/engines/` | 六個 manifest；只有 Seed／Mean／X 可啟動 |
| `contracts/schemas/` | manifest、state、Transcript、Session 的版本 1 契約 |

沒有把 React 塞到 `tools/`。本輪同一個 Python bridge 接三種 Adapter，避免尚無差異需求時建立三套 service；argv routing 清楚受 engine allowlist 限制，模型仍用各自 venv。之後 headless engine 可以取代對應的 TEMPORARY branch，而不重建 App。

## 程序與狀態語意

Rust 只啟動固定的 bridge 與既有 Python。前端不能指定 executable 或任意 shell command。bridge 的 request 寫入 ignored `artifacts/desktop/control/`；runner 結果進 `artifacts/desktop/runs/<uuid>/`。backend stdout／stderr 轉成 `log` events；每行立即 flush 到 `artifacts/desktop/logs/*.jsonl`，UI 僅保留最近 500 events。

Windows Job 開啟 `KILL_ON_JOB_CLOSE`；service 以 suspended 狀態建立，在 job 指派完成後 resume，衍生 PowerShell／venv launcher／Python 都繼承 job。Stop 先發 JSON command，最多等 3 秒，再 close Job、wait／join 所有 readers。service crash 自動 close Job；App Exit／硬結束由 Rust／OS close handle 清除子程序。只清理 App 自己擁有的 job，不依程序名稱掃殺既有 backend。

切換先 stop 舊 job，再啟動新 job，reader threads join 後才能復用 snapshot。UI 執行中鎖定 Engine 選擇；沒有無縫 hot swap。

`VALIDATING` = 資產、WAV、參數、Seed PortAudio 端點預檢。預檢 PASS 不是 READY；`LOADING` = runner 初始化。Mean 的既有 `Model load seconds:` 可推進 READY → RUNNING（僅 WAV operation）。Seed GUI 沒有模型 readiness ACK，X 沒有結構化 load ACK，保持 LOADING，不用 PID 假造 RUNNING。完成 file runner 後 OFFLINE，但 bridge 需 Stop 才釋放。`audio_verified` 本輪固定 false；不產生 LIVE 或音訊 PASS。

## 控制協定

App → bridge：

```jsonl
{"command":"start"}
{"command":"status"}
{"command":"set_parameter","name":"diffusion_steps","value":10}
{"command":"stop"}
```

非 runtime 可調參數回 `restart_required`，不假稱已套用。完整參數編輯／Presets 留 M3；目前使用 manifest defaults。

bridge → App：state（嚴格七狀態）、validation、artifact、process_started、process_exit、log、error、restart_required。process_started 是程序事件，不是新的 BackendState。非 JSON 行只能作 log。此通道不允許 PCM；STT／Metrics 日後也只傳 metadata。

## Overlay 與逃生入口

Full 1040 × 740、Compact 420 × 490、Mini 420 × 74，使用 logical pixel；Windows 125% DPI 的 physical size 相應放大。Compact／Mini 強制置頂；Full 可以自行選擇置頂。透明 WebView + Overlay CSS surface opacity 0.45–1；Full 維持不透明。標題以 pointer capture 取得 screen 座標差，再由 Rust `move_window` 套用 physical position；原生 drag region 在本機自動化測試未產生位移，因此使用此小型視窗控制替代。Lock Position 同時阻止前端 capture 與 Rust move／drag command；固定 frameless。

Click-through 只適用 Overlay；`Ctrl+Alt+A` 在 click-through 時解除並 show／focus，而非單純 hide。Tray 有 Disable click-through。重啟永遠清除 click-through，避免無法操控。快捷鍵修改先驗證、註冊失敗恢復舊值；外觀／hotkeys 保存 `artifacts/desktop/shell.json`。

瀏覽器預覽無原生能力，Start／Stop、Tray、native settings 按鈕明確停用。`npm run dev` 不是 Tauri 的音訊或程序驗收。

## 開發入口的設計界線

Windows WebView2、Rust MSVC／C++ Build Tools 與 Node/npm 是目前 Desktop build 的前置；模型／Python 仍按 backend 隔離。開發檔位於 `app/`，build/cache 與測試報告留在 ignored 目錄，不能由 exe 存在推論 portable installer 或音訊通過。具體建置、Browser／native 畫面測試與 cleanup 命令集中在[Agent 維護手冊](agent-maintenance-guide.md)；本機啟動結果以[Desktop 驗證](app-verification-latest.md)及[Manual TTS 驗證](manual-tts-verification-latest.md)為準。

## 後續架構邊界

M2 下一片完成 headless readiness／start／stop 與 canonical audio devices，再由 M3 產生分級動態控制項與 Preset。Seed GUI branch 明列 TEMPORARY，不宣稱日常 MVP。

M4 的常駐 STT 不掛在 EngineManager job 下；Mic self 與 Remote loopback 分 source。重建使用 backend_stt provider 避免雙重辨識。SQLite transaction 在 completed utterance 後立即 commit，export 可由 canonical DB 重建；Clear View 不刪 DB。GPU 預設保留 VC，STT CPU。

M5 VoiceProfile 與 M6 TTS 共用 Mode → Engine；M7 只接既有 Audio Rack。M8 才處理 bundle resources、backend detection、installer／portable／auto update／startup／settings migration。任何超出此分層的改動先說明，不自行形成平行架構。

## Manual TTS 增量架構

以下只保留設計層的關係；修改步驟、probe 命令和錯誤分流集中在[Agent 維護手冊](agent-maintenance-guide.md)。實測以[Manual TTS 驗證](manual-tts-verification-latest.md)為準。

新增服務留在 `services/tts/`，原生 bridge 留在 `app/src-tauri/src/speech_manager/`。`speech_status` 懶啟動受 Windows Job 管理的 Python JSONL service；`speech_action` 傳入 allowlist 動作，每次 command_id 都要收到 accepted／error ACK，拒絕新 request 不能被 UI 當成送出成功。IPC／WebView 仍不傳 PCM。

`SpeechRequest → SpeechQueue → TTSOrchestrator` 負責串行生命週期；Generation Adapter 沿用 CosyVoice2 WSL Python 與 Breeze wrapper，Playback 在 Windows 對指定 PortAudio output／host API 開啟音訊。現有 `seed-vc-virtual-route` 與 `seed-vc-neutral` 是跨 backend 共用外部 rack／route，Post-FX 仍為 External / Manual，不能將 playback completion 等同完整 rack／LIVE PASS。

SpeechManager 與 VC EngineManager 分開持有程序，Audio control mutex 防止兩邊同時提交佔用 Output 的啟動動作。Stop Speaking 送 TTS command，不關閉 TTS service；App Exit 才送 shutdown 並釋放 Job。WSL generation 的取消另外要清除自己建立的 Linux process group；Windows Job 不能當成 Linux 子程序已消失的證據。

Session、request history、成功 Transcript 與 phrase settings 由 SQLite 保存；每個成功播放事件立即 commit，session exports 由 canonical records 寫出。Voice profiles 將已使用的 reference 音訊／文字包成 catalogue，保留 draft／授權限制，不冒充已有人類採納的 Voice Library。

現有 adapter 的輸出是完整 WAV，`supports_streaming_tts=false`；Generation 與 Playback 保留分層及 chunk extension。AgentReplyProvider／AgentReply 僅契約，agent_reply input 與 agent source 提交均停用。

無視窗正式 manager probe 與實際 CABLE 擷取的命令、輸入和限制由[Agent 維護手冊](agent-maintenance-guide.md)與[Manual TTS 驗證](manual-tts-verification-latest.md)擁有，不在架構文件複製。
