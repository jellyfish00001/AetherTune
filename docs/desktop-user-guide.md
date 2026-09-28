# Desktop／Manual TTS 操作手冊

適用版本：2026-09-28 的 Desktop 與 Manual TTS 實作。第一次使用先讀[一頁式快速使用說明](quick-start.md)；本文再回答「開哪個程式、按什麼、結果放哪裡、出錯先看什麼」。程式用途先看[Agent 快速地圖](agent-quick-map.md)，必要時查[逐檔索引](project-file-map.md)；修改／除錯查[維護手冊](agent-maintenance-guide.md)，實測 hash 與 PASS 範圍查 [manual-tts-verification-latest.md](manual-tts-verification-latest.md)。

## 1. 先選正確入口

| 入口 | 用途 | 本機啟動方式 |
|---|---|---|
| 舊 Tk 控制台 | Seed 官方 GUI、MeanVC2／X-VC WAV 轉換、參數及日誌 | 根目錄 `AetherTune.cmd` |
| Tauri Desktop | Full／Compact／Mini 視窗、受管制 VC runner、Manual TTS／Queue／Transcript | `app/src-tauri/target/debug/aethertune-desktop.exe` |
| 瀏覽器預覽 | 檢查版面、輸入與 UI；沒有真實 backend／視窗控制 | `app/` 下 `npm run dev`，開 `http://127.0.0.1:1420/` |
| 離線腳本 | 直接執行單一 backend 或 STT → TTS WAV 流程 | [user-guide.md](user-guide.md)、[tools/README.md](../tools/README.md) |

要使用文字發聲，請開 **Tauri Desktop**。`AetherTune.cmd` 尚未整合新的 Manual Composer；瀏覽器的 Speak／Queue 停用是預期行為。

目前 CosyVoice2／Breeze 的 Manual TTS 是 **offline**：先生成完整 WAV，再播放。CosyVoice2 的 20 次批次實測約 30 分鐘，單句 generation 約 61～134 秒；排隊還會增加等待。不要因為數秒沒有聲音而重複提交。這不是已驗收的直播即時系統。

## 2. 啟動前與第一次建置

在這台已準備的 PC，先開 PowerShell：

```powershell
Set-Location D:\AetherTune
Test-Path .\app\src-tauri\target\debug\aethertune-desktop.exe
& .\app\src-tauri\target\debug\aethertune-desktop.exe
```

若回傳 `False`，需要建置 Desktop。這是開發版 exe，尚無 installer／完整 portable 包：

```powershell
Set-Location D:\AetherTune\app
# 首次取得專案或 package-lock.json 更新後，安裝 lockfile 所列 UI 依賴。
npm ci
.\dev.ps1 -Build
# build 成功後再啟動。
.\src-tauri\target\debug\aethertune-desktop.exe
```

建置需要 Node/npm、Rust MSVC、Visual Studio C++ Build Tools 與 WebView2。`dev.ps1` 優先使用本機 `artifacts/desktop-toolchain/` 的 Rust，只設定當次 process 環境；準備方式見 [app-architecture.md](app-architecture.md)。不要同時開著 exe 又覆蓋它，以免 Windows file lock 讓 build 失敗。

Git 只包含程式／契約／文件，不包含模型、reference WAV、venv、第三方 source 或 build。新機還要按 [local-environment.md](local-environment.md)、[backends/speech-reconstruction/README.md](../backends/speech-reconstruction/README.md) 準備 Windows Seed Python、WSL `Ubuntu`、CosyVoice／Breeze 環境與資產。只 clone repository 不等於可以發聲。Desktop 預設 root 是建置時的 checkout；移動位置需重新建置，或在啟動前明確設定 `AETHERTUNE_ROOT` 指向完整專案。

已有環境的唯讀盤點：

```powershell
Set-Location D:\AetherTune
& .\tools\voice-backend-check.ps1
& .\tools\python-runtime-check.ps1
wsl.exe --list --quiet
```

這些檢查不取代音訊 E2E。Manual service 的 Windows interpreter 是 `tools/venvs/seed-vc/Scripts/python.exe`；生成用 `tools/venvs/cosyvoice-wsl/bin/python` 或 `tools/venvs/breeze-tts-wsl/bin/python`，不能任意換成系統 Python 或 RVC venv。

## 3. 第一次讓文字發聲

1. 開啟 Desktop，選 **Full** 與 **LIVE** 頁。在 `Mode` 選 `Text → Voice` 或 `Speech Reconstruction`。這兩種模式目前共用 Manual TTS workspace。
2. 如果已有 VC runner，先在 Streaming VC 模式按 `STOP`。VC 與 TTS 不可同時爭用 Output／GPU；Mic STT 的未來共存是另一件事。
3. `Engine` 選 **CosyVoice**（目前實際使用 CosyVoice2）或 **Breeze TTS 2**。CosyVoice3 尚未接入。
4. `Input` 選 **manual_text**。`microphone` 尚未有常駐實體 Mic/STT；選它仍能打字，但不會開始收音。`agent_reply` 停用。
5. 明確選 `Voice profile`，核對畫面顯示的 reference WAV／文字路徑。
6. 設定 `Host API` 與 `Output`。本機已驗證組合如下，字串需完整一致：

   | 欄位 | 值 |
   |---|---|
   | Host API | `Windows DirectSound` |
   | Output | `CABLE Input (VB-Audio Virtual Cable)` |

7. Composer 輸入 `今天先測試文字模式。`，按 **Speak** 一次。接受後 Composer 會清空；不是音訊已播完。
8. 在 Speech Queue 看 `CURRENT` 與狀態：`GENERATING → BUFFERING → PLAYING`。完成後移入 `history`，Transcript 出現 `ME · manual_text` 和原文。
9. 如果 Output 是 CABLE，需在接收程式選 **CABLE Output** 才會收得到。電腦喇叭沒有直接出聲不代表生成失敗，先看第 5 節路由。

| Voice profile | 可用 Engine | 用途／限制 |
|---|---|---|
| Official CosyVoice Sample | CosyVoice | 上游測試 reference；可作第一次 pipeline 檢核，實際顯示名稱以 profile 為準 |
| Reference Female | CosyVoice、Breeze | 使用 `dataset/reference-voices/voice-female-f1.wav`；prompt transcript 仍需人工核對 |
| Reference Male | CosyVoice、Breeze | 使用 `dataset/reference-voices/voice-male-m1.wav`；prompt transcript 仍需人工核對 |

`WAITING`／`DRAFT` 表示 reference metadata、人工審核或完整 route 的狀態，不等於這次生成已失敗。可以跑已準備的測試 profile，但不能將它當成正式批准或聲線品質通過。自訂聲線由 Agent 修改 `contracts/voices/`，目前沒有 UI 的新增 Voice Library 功能。

目前 TTS UI 可改文字、Engine、Voice、Input、Output／Host API、interrupt policy 與 Enter 行為；manifest 的進階參數不等於畫面已有可用控制項。Breeze `cfg_scale`／seed／fast-all 等進階需求使用既有 CLI，或按維護手冊補完整 UI→request→adapter 傳遞。

## 4. Speak、Queue 與取消

| 操作 | 實際作用 |
|---|---|
| Speak | Idle 開始；忙碌時依 interrupt policy 處理 |
| Add to Queue | 永遠加入 pending 的 FIFO 尾端 |
| Clear（Composer） | 只清除尚未送出的文字 |
| Stop Speaking | 取消 current 的生成或播放；不清 pending、不退出 App |
| Clear Queue | 取消 pending；current 繼續，App 保持執行 |
| Remove | 取消指定 pending 項目；current 不提供此操作 |
| Move Up／Move Down | 調整 pending 次序 |
| Speak Now（pending） | 將原 request 移到下一個；是否打斷 current 依該 request 保存的 policy |

在 `Speech settings` 或 Full 的 `SETTINGS` 頁設定：

| Interrupt policy | 正在生成／播放時按 Speak |
|---|---|
| `queue`（預設） | 加入 FIFO，不中斷 current |
| `interrupt_current` | 取消 current，最新 request 接著執行 |
| `reject_new` | 拒絕提交；Composer 草稿保留 |

pending 的 `Speak Now` 在 `queue` policy 下是排到下一個，不會打斷；`reject_new` 且有 current 時會拒絕。修改 Settings 不會回頭改已接受 request 的 policy／Voice／route。

三句練習：依次輸入「等一下，我先看一下。」「這個問題有點複雜。」「我等等再回答你。」並各按 Add to Queue。`active` 數包含 current＋pending；`history` 另計。先前生成可能已開始，因此不必期待三句永遠同時顯示 pending。

`Enter to send` 預設勾選：Enter 按 Speak 的 policy 送出，Shift+Enter 換行，中文 IME 選字的 Enter 不應送出。取消勾選後，Enter 換行，使用按鈕送出。

Recent 只收錄已完成播放的文字；點選文字回填 Composer，仍需按 Speak／Queue。點 `☆` pin 成 `★`，再點取消；Favorites／Recent 保存在 SQLite，跨 session 保留。取消或 failed request 不應產生已說出的 Transcript。

## 5. Output、監聽與外部 Audio Rack

```text
Manual Text → CosyVoice2／Breeze → Windows playback
  → CABLE Input（播放端）→ CABLE Output（錄音端）
  → 由使用者設定的接收程式／外部 Rack／Discord／OBS
```

**CABLE Input 是 App 寫入的播放端；CABLE Output 是下游讀取的錄音端。** 不要反過來填。Desktop 不會替使用者更改 Windows 預設裝置，也不會自動插入 VST。

Output 與 Host API 必須是 PortAudio 列舉的精確配對，且至少支援 2 output channels；adapter 播放為 48 kHz stereo。列出本機可選播放端點：

```powershell
Set-Location D:\AetherTune
& .\tools\venvs\seed-vc\Scripts\python.exe -c "import json,sounddevice as sd; tts_apis=sd.query_hostapis(); print(json.dumps([{'name':d['name'],'host_api':tts_apis[d['hostapi']]['name'],'output_channels':d['max_output_channels']} for d in sd.query_devices() if d['max_output_channels']>=2],ensure_ascii=False,indent=2))"
```

不同 Host API 可能有同名裝置；不能只看 Windows 顯示名稱。若想直接聽喇叭，需填該實體播放端點與正確 Host API，並另做實測；本輪 PASS 是明確的 CABLE／DirectSound 配對，不能推廣成所有裝置都通過。

接 Discord／OBS 或 VST 的步驟見 [operation-guide.md](operation-guide.md) 與 [audio-rack/README.md](../audio-rack/README.md)。`seed-vc-neutral`／`seed-vc-virtual-route` 是共用外部設定身分，不是已在 App 內執行 Post-FX 的證據。未來 Self STT 必須讀實體 Mic，不能讀 CABLE Output 或最後混音，避免 TTS→STT→TTS 迴圈。

## 6. Full、Compact、Mini 與退出

| 視窗／頁面 | 怎麼用 |
|---|---|
| Full（1040×740 logical px） | 設定 Mode／Engine／Voice／Output、完整 Composer、Queue、Recent／Favorites、Transcript |
| Compact（420×490） | 快速打字與 Queue；內容可捲動，下方 history／設定可能需要捲動 |
| Mini（420×74） | 簡略狀態與 `[T]`；先在 Full／Compact 選 TTS Mode |
| Mini `[T]`（展開至 420×260） | Quick Input → Speak；ACK accepted 後自動收起，失敗保留草稿。Popup 的 × 只收 popup |
| `LIVE`／`VOICE`／`TRANSCRIPT` | TTS Mode 下目前顯示同一個 workspace；不是獨立的歷史 session browser／正式 Voice Library |
| `AUDIO` | canonical 裝置 registry 仍為 placeholder；TTS 的 Output／Host API 在 workspace 填 |
| `SETTINGS` | Speech settings（TTS Mode）與 Overlay／快捷鍵／Exit |

Mini 的 `[T]` 停用時，按 `↗` 回 Compact，先將 Mode 改為 Text → Voice。Mini 不能做完整 Queue 管理；停止 current 請回 Compact／Full 用 Stop Speaking。`N/A ms` 不是實測延遲，完整 metrics 在 request exports。

視窗 ×、`─` 或原生 Close 會**隱藏至 Tray**；生成／Queue 可以繼續。結束時使用 SETTINGS 的 **Exit AetherTune** 或 Tray 的 **Exit**，才會取消 current／pending、保存 session end 並回收所屬程序。Stop Speaking、VC STOP、隱藏視窗、Exit 是四種不同操作。

預設 `Ctrl+Alt+A` 顯示／隱藏；Click-through 時會解除穿透並顯示。Tray 也可選 Disable click-through。預設 `Ctrl+Alt+V` 是 VC runner 的 Start／Stop，不是 TTS phrase／Stop Speaking 快捷鍵。快捷鍵可在 SETTINGS 改，請以保存值為準。Compact／Mini 強制置頂；Full 可勾 Always on Top。Opacity 對 Overlay 生效，Full 保持不透明。Lock Position 禁止拖移，不禁止打字。

## 7. Session、Transcript 與檔案在哪裡

| 路徑 | 內容／何時查看 |
|---|---|
| `artifacts/tts/tts.sqlite3` | canonical sessions、requests、transcripts、settings、recent、favorites |
| `artifacts/sessions/<session-id>/session.json` | 本次 service session metadata，Exit 後有 ended_at |
| 同目錄 `requests.jsonl` | queued／completed／cancelled／failed、profile／route snapshot 與 metrics |
| 同目錄 `transcript.jsonl`／`transcript.txt` | 已完成播放的內容；前者可供 Agent 做結構化檢核 |
| 同目錄 `<request-id>.evidence.json` | runner、model fingerprint、output hash、PID audit、route、Transcript evidence |
| 同目錄 `jobs/<request-id>/` | 生成 WAV／runner JSON／tts-text.txt／WSL launch、cancel、stdout／stderr |
| `artifacts/desktop/shell.json` | Overlay mode／opacity／位置鎖定／快捷鍵；不保存所有 TTS 選擇 |
| `artifacts/desktop/logs/` | VC runner logs；TTS 的模型錯誤主要讀 session job logs |

service 首次進入 TTS 懶啟動，一次 App 執行可共用同一 TTS session。改 Engine／Voice／Input 或切頁不會重建服務；Exit 後再開是新 session，不自動續播舊 pending。GUI Transcript 顯示目前 session，尚無選舊 session 的操作；過去記錄仍在 SQLite／exports。

Composer／Input／profile 的 UI 暫存使用 WebView sessionStorage，切 layout 可保留，但不能當作退出後的可靠備份。Mode／Engine／Output 不保證重啟恢復，重開時重新核對。要備份歷史與常用語，先正常 Exit，再備份 `artifacts/tts/` 與需要的 `artifacts/sessions/`；不要只複製執行中的 SQLite 主檔而漏掉 WAL／SHM。這些資料可能含個人文字／聲音，不提交 Git。

## 8. 常見現象與下一步

| 現象 | 先做什麼 |
|---|---|
| Browser 的 Speak 灰色 | 改開 Desktop exe；不是 backend 故障 |
| TTS 的 START 灰色 | 使用 Speak／Add to Queue |
| GENERATING 很久 | 看 current 與 job stdout／stderr；已有實測一至數分鐘，不重複提交 |
| completed，但本機沒聽見 | 核對 Output，若用 CABLE 檢查下游是否讀 CABLE Output／監聽；不要把 completed 當 Discord／rack 驗收 |
| rejected／QUEUE_BUSY | 查看 policy；草稿還在，等 current 完成或改新 request 的 policy |
| DEVICE_NOT_FOUND | 列舉端點，核對 exact name＋Host API＋output channels |
| MODEL_NOT_FOUND／ENV_PROBE_TIMEOUT | 查看 engine requiredPaths、WSL Ubuntu 與既有 venv；依 backend 文件補環境，勿在 UI 盲目重送 |
| REFERENCE_INVALID | 查看 Voice 支援 Engine、WAV／prompt text 是否存在；profile 不相容不靠改顯示名稱解決 |
| ERROR／AUDIO_BLOCKED／PLAYBACK_OPEN_TIMEOUT | 保存 request／job evidence，Clear pending 後正常 Exit 再重開；driver 阻塞不靠反覆 Speak 解決 |
| CANCEL_CLEANUP_FAILED | 不再啟另一個 TTS／VC runner；正常 Exit，按維護手冊稽核本次 PID／group |
| 成功播放卻沒 Transcript | 看 history 的 TRANSCRIPT_STORAGE_FAILED、session export_error.json 與 SQLite；勿直接重播來補 DB |
| 收進 Tray 後找不到 | 用 Tray Open／Show Overlay 或已設定的顯示快捷鍵 |

若需要交給 Agent，提供 Engine／Voice、Host API／Output、文字、操作次序、session／request ID、畫面 error、jobs stdout／stderr 與 evidence 的路徑。不要只說「沒有聲音」，也不要把私人音訊或 credentials 貼進版本庫。

## 9. 自己確認結果的最短清單

成功應同時看到：request history 為 completed、原文的 ME／manual_text、該 request 的非零 WAV、正確 profile／route evidence；如果要確認 CABLE 確實收到，再用維護手冊的獨立擷取。取消項目留 history、不進已發聲 Transcript。完整 Mic／rack／600 秒／聽評則按 [live-gate.md](live-gate.md) 另驗。

本手冊補充現有操作，不新增 runtime 或功能。原生 GUI 完整互動、physical Mic 共存、外部 Post-FX 與 LIVE 仍 WAITING；Agent Reply／Auto Reply／Phrase Hotkeys 仍 PLANNED。
