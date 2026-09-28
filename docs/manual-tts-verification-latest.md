# Manual TTS 增量實作與驗證

**文件邊界：**本報告只保存 2026-09-27～28 Desktop Manual TTS 的 service／Queue／生成／播放／Transcript 驗收命令與 evidence，不作完整操作手冊、產品需求或 LIVE 結論。第一次使用讀[快速說明](quick-start.md)，建置與排錯讀[Desktop 手冊](desktop-user-guide.md)，跨層維護讀[Agent 維護手冊](agent-maintenance-guide.md)。

日期：2026-09-27～28（Asia/Taipei）。範圍依使用者「Manual TTS 與 Agent Reply Extension」規格：實作 Manual Text、統一 Request／Queue／Orchestrator、完成播放後的 Transcript，以及 Full／Compact／Mini 快速輸入。Agent API、Personality、Auto Reply、Phrase Hotkeys 停用且 PLANNED。

本輪沿用已安裝的 CosyVoice2／Breeze WSL runtime、Seed Windows Python 的 sounddevice／soundfile 與既有 reference／VB-CABLE，不新增模型下載、套件安裝或改變 Windows 預設音訊裝置。各種 PASS 僅代表本表明列的範圍；完整 physical Mic／Post-FX／LIVE 驗收仍獨立。

## 修改位置與資料流

| 位置 | 用途 |
|---|---|
| `app/src/components/SpeechWorkspace.tsx`、`app/src/services/speech.ts`、`main.tsx`、`style.css` | Composer、Queue、Input Mode、Recent／Favorites、Settings、成功 Transcript、Mini popup |
| `app/src-tauri/src/speech_manager/`、`main.rs`、`lib.rs`、`process_manager/mod.rs` | 獨立 JSONL TTS control、ACK、Windows Job、Mini 展開尺寸與有界 Exit cleanup |
| `services/tts/` | Request queue、生成／播放分層、取消與 WSL ownership、SQLite／session exports |
| `contracts/voices/`、`contracts/schemas/`、TTS engine manifests | 沿用 reference profiles、SpeechRequest、TTS state、Agent Reply／Transcript 擴充 |
| `contracts/agent_reply.py` | 停用的 AgentReplyProvider／AgentReply／latency budget 契約 |
| `app/tests/`、`speech-probe.rs`、`app/dev.ps1` | UI／音訊／正式 Rust manager probe／artifact 檢核入口 |
| `README.md`、`AGENTS.md`、Desktop requirements／architecture／verification 與集中狀態文件 | 更新操作入口、共用 TTS 邊界及實測狀態；保留原有驗證歷史 |

```text
Manual Composer（不呼叫 STT）
  → SpeechRequest（engine／voice／route 提交時快照）
  → FIFO SpeechQueue → TTSOrchestrator
  → CosyVoice2／Breeze generation → WAV buffer
  → Windows playback → 指定 Output → 既有外部 Audio Rack／virtual route
  → 完成播放 → SQLite commit → ME Transcript／JSONL／TXT
```

生成狀態與播放狀態分開；TTS state 使用 `IDLE / QUEUED / GENERATING / BUFFERING / PLAYING / STOPPING / ERROR`。Request 使用 `queued / generating / ready / playing / completed / cancelled / failed`。當前 runner 為完整 WAV，`supports_streaming_tts=false`，TTFA 為本 adapter 首個可用 buffer 的時間；真正 chunk streaming 與 warm model residency 尚未交付。

Speak 遵守 interrupt policy，Add to Queue 永遠 FIFO。Stop Speaking 取消 current，Clear Queue 取消 pending，均不關閉 App 或服務。Mic OFF／Input Mode 不作為 manual 的 gate。未來 STT 提交入口只接受 physical microphone source；本輪尚未實作真實常駐 mic capture，因此 Mic ON 的完整共存驗收保持 WAITING。

## 驗證狀態

本輪自動驗證已完成；下列狀態按實際命令與 artifact 分類，不以程式存在作為 PASS。

| 驗收 | 結果 | 範圍／證據 |
|---|---|---|
| Rust command ACK／Windows cleanup | PASS | `cargo test --lib`：4 tests；TTS bridge fixture 及原有 stop／crash／孫程序 cleanup |
| Queue 三句 FIFO／CRUD／interrupt／error recovery | PASS（fixture／真實 FIFO） | 23 項 core tests 涵蓋 CRUD、policy、backend error recovery、startup／open-timeout／cancel-during-open；20 次真實模型生成／播放另驗證三句循環 FIFO。CRUD／error injection 不冒充原生 GUI E2E |
| Mic OFF／Mic ON 共存 | PASS（Mic OFF 真實 Manual／UI 模式切換）／WAITING（實體 Mic ON） | 真實 probe 的 mic_enabled=false，不呼叫 STT；Microphone mode 下 composer 仍可用；常駐 physical mic capture 尚未實作，不能宣稱 Mic ON E2E |
| Transcript provider | PASS（兩引擎與 20-request 真實完成播放） | ME／manual_text；只記錄 completed，session export 與 canonical DB 一致 |
| Cancel | PASS（fixture／真實生成及播放取消） | 23 tests；兩輪各 1 cancelled＋1 completed，取消後同服務恢復生成與播放；播放取消前有非零 capture 時窗 |
| 20-request stability（CosyVoice2） | PASS（真實模型／播放／擷取） | 同一 service：20 completed／20 非零播放時窗／20 Transcript，female／male 各 10 次，FIFO／schema／hash PASS；退出後 21 個 Windows PID、20 個 WSL group 均無存活 |
| CosyVoice2 → CABLE | PASS（本機 offline Manual 鏈路） | `cosyvoice-r5/`：新生成／完成播放／非零擷取／provider／hash／owned process audit 全通過 |
| Breeze → CABLE | PASS（本機 offline Manual 鏈路） | `breeze-final/`：新生成／完成播放／非零擷取／provider／hash／owned process audit 全通過 |
| Full／Compact／Mini／Settings UI | PASS（Browser／mock） | Playwright + 內建 Browser 交叉複核；原生 WebView 互動仍 WAITING |
| Recent／Favorites | PASS（UI mock／SQLite fixture） | 點擊回填 Composer、pin／unpin 與儲存；原生 UI 操作仍 WAITING |
| External Post-FX、physical Mic、600 秒與聽評 | WAITING | 未以此次 Manual TTS 完成共用 rack／LIVE 驗收 |
| Agent API／Personality／Auto Reply／Phrase Hotkeys | PLANNED | 契約停用，無網路 Agent 實作 |

UI 使用 `http://127.0.0.1:1420/`，Full 1040×740、Compact 420×490、Mini popup 420×260。Browser 複核保留草稿、Microphone mode 下仍可編輯、Compact 首屏 composer、Mini 的 Close／輸入／Speak；預覽 send 保持 disabled。Playwright explicit mock 驗證 Enter／Shift+Enter／IME、拒絕保留文字、Queue actions、Mini accepted 後收起及 object error 不造成白屏。console／network errors 為空；證據位於 `artifacts/desktop/ui/manual-tts-report.json` 與 `artifacts/desktop/manual-tts-browser/report.json`，截圖為 `full.png`、`compact.png`、`mini-popup.png`。

初次真實測試發現 WSL `setsid` 提早回傳，以及跨 Windows／WSL shell quoting 讓 PID 提早展開；新啟動器改為 job-local `launch.sh`／`cancel.sh` 與 `--exec setsid --wait`，不以全域程序名稱清理。另一次原始 24 kHz／mono blocking playback 卡在 PLAYING，已停止該 owned probe；Windows Job 內程序及真實 Linux child 均已退出。`cosyvoice-r3/audio-report.json` 保留 BLOCKED，不能當作完整播放 PASS。

修正後既有真實 WAV replay 已完成：24 kHz mono → 48 kHz stereo，109440 frames／2.28 秒，underrun 0。這只驗證 playback adapter。若 WSL cancellation 無法驗證 group 回收，服務固定 ERROR、拒絕新 submit 並暫停 pending；Clear Queue 與 Exit 保持可用，VC runner 也不會在該狀態啟動。Stop／worker／shutdown 重複取消會沿用已驗證結果。

`cosyvoice-final` 仍曾卡在 PLAYING，已停止持有的 probe，process audit PASS。未取得當時 native stack，阻塞根因尚未確認。後續改為主執行緒先 `prepare()`、bounded OutputStream open；open-timeout 固定服務 ERROR／AUDIO_BLOCKED、暫停 pending，直到 Exit。`worker-capture-r2/report.json` 的獨立 child 主執行緒 prepare／worker replay／另一程序 CABLE capture PASS：191040 capture frames、peak `0.369812`、RMS `0.037396`、finite、capture errors 空，child exit 0；這是既有真實 WAV 的回放，不是新模型生成。診斷腳本首次失敗為 test bootstrap 將 venv typing backport 提前於標準函式庫；修正後通過，未變更 venv。

Queue 的 current 依 `current_request_id` 判定，包含 BUFFERING／ready；完成或取消項目移入 history，pending 可 Remove／Move Up／Move Down／Speak Now。Engine／Voice／reference／route 在 submit 時保存快照，後續修改選擇只影響新 request。普通 engine error 留下 failed evidence 後可處理下一句；ownership cleanup 未驗證或 native audio open 被阻塞時，固定 ERROR 並阻止後續執行，直到 Exit。

既有 `tools/virtual_cable_loopback.py` 的 WASAPI 48 kHz／stereo synthetic route preflight PASS（RMS `0.082622`、peak `0.160000`）；同樣 callback 流程改用 DirectSound 48 kHz／stereo 亦 PASS（RMS `0.082187`、peak `0.160004`）。兩輪只證明端點路由，未取代真實 TTS 驗收。報告位於 `artifacts/desktop/manual-tts-audio/route-preflight/`。

## 真實 Manual 音訊 evidence

CosyVoice2 `cosyvoice-r5` session：`3a0f1666-eb6a-4468-bf76-ce197b38a8ac`，request：`8c7a9fa1-51d8-475e-b64a-51e91c2cba56`。輸入「今天先測試文字模式。」檔案 SHA-256 `c611970242c30c77af8e5960dbab08853c83c521edeb9e8d31d1e8f6e0a62e18`；official prompt audio SHA-256 `c7b31d6dbe7cc6a716dded00550db5b50940bf209e424e4ad207b12e657c8ff6`。

| evidence | 實測 |
|---|---|
| 模型 fingerprint | 19 個 model files 全內容 SHA-256；aggregate `204861ce8b518b73fd5c36e4dab0641cfa326ae7ef8d554810d853a3c0f08d60`，逐檔資料在 request evidence |
| Runner runtime | PyTorch `2.7.1+cu128`，manifest 回報 CUDA available、RTX 5060 Ti；此欄不是所有 frontend tensors 都在 GPU 的證明 |
| 生成 WAV | 24 kHz mono、54720 frames／2.28 秒、peak `0.369629`、RMS `0.049396`；SHA-256 `bf1257521f81cfa426f1349814040d6dbe511e48de8e22681e4006c8c0fe1bdc` |
| Windows playback | CABLE Input／Windows DirectSound，48 kHz stereo、109440 frames、underrun 0 |
| 對應播放時窗擷取 | 非零、finite、capture errors 空；peak `0.369781`、RMS `0.043961` |
| Capture artifact | `artifacts/desktop/manual-tts-audio/cosyvoice-r5/cable-loopback.wav`；SHA-256 `8019f161f4cd2586f30fd0767909660eb3d84da06c4a6d01e1357a99f2ed276d` |
| Generation／TTFA／total | `141944.168 / 156299 / 159834` ms；包含完整 WAV buffer／首次 model hash／等待，首包不符合 5 秒 LIVE 門檻 |
| Transcript／退出 | 1 completed → 1 ME／manual_text；requests／session／transcript schema PASS、session ended_at 已寫入；Windows owned PIDs／WSL group audit 無存活 |

Playback adapter 的 `route_status=WAITING`、`playback_verified=false` 保留完整 rack／外部路由驗收邊界；此次外部 verifier 只將指定 CABLE 擷取鏈路判為 PASS，不改寫其他 profiles 的 readiness。

Breeze `breeze-final` session：`f9fdf062-97ba-4495-82ce-b47b41622a03`，request：`62fd5b6d-4c1c-41d5-a87d-f761b24ccff7`。同一文字輸入，female reference SHA-256 `37976f69f73fb13d6fefaf80268794d545d6e19be5059437db067455a795f406`；reference transcript 保持 DRAFT。17 個 model files 全內容 SHA-256，aggregate `b998a8b18f7d874b8a7c4f5cd61c8ee9da5ce08230e7fb3f5ffcc706ac6d6d61`。

Runner 為 PyTorch `2.9.1+cu128`、CUDA `12.8`、RTX 5060 Ti，`ref_clone_tata / cfg_scale=1 / seed=42 / eager / fast_all=false`。生成 WAV：24 kHz mono、57600 frames／2.4 秒、peak `0.155029`、RMS `0.031124`、SHA-256 `9c5da2ebde079f9791f2ad79586e53ad1c4b9da64ec2c6724525172dcbfdaa58`。同一 CABLE／DirectSound 48 kHz stereo playback 完成，underrun 0；對應擷取時窗 peak `0.155090`、RMS `0.027821`、finite、capture errors 空；capture SHA-256 `dd51b33180e5d3cd9e4fda4446abd8cfe02024b0a47cadab422c978da456dbf1`。Generation／TTFA／total：`212883.507 / 235282 / 240545` ms，屬 offline。Transcript／schemas／session end 與 owned process audit 全 PASS。

生成取消：`cancel-generation-final` session `56e540e7-f802-493d-823d-ff64f2e32930`，連續提交兩句，5 秒後 Stop Speaking。第一句 cancelled、owned Linux group 654 token 驗證後回收；第二句仍完成生成／播放，對應擷取 peak `0.369812`、RMS `0.044115`。只產生第二句的 1 個 ME／manual_text Transcript，兩個 request／session exports schema PASS；退出後 Windows PIDs 與兩個 WSL groups 均無存活。取消沒有關閉服務或清掉 pending。

第一輪 `cancel-playback-final` 的 probe 未同步到新版取消時間記錄，因此缺少取消前非零擷取的對應時窗，audio verifier 正確回報 BLOCKED，即使 probe exit 0 也不採納為播放取消 PASS；process audit PASS。重跑使用「PLAYING 持續 1 秒＋probe_cancel 時間＋獨立 capture 非零時窗」驗收。

播放取消重跑 `cancel-playback-r2` session `959d4ff3-2aa8-44c6-bd0a-e4182c1bbbea` 全 PASS。第一句 `d3665b30-3b00-45dc-82d1-76a06e368d4b` 的取消前時窗擷取 66240 frames、peak `0.233612`，實際停止播放後為 cancelled、無 Transcript；第二句 `18bc76aa-81e5-40d4-9c35-52f2cac65f2f` completed、擷取 RMS `0.044115`，只有該句的 ME／manual_text。兩個 request／session exports schema 與 owned process audit PASS，WSL groups 632／860、Windows recorded PIDs 均無存活。capture SHA-256 `ab00c47f4324be1148425905c7f121bed1eaf1a2b5ab7d66a4a75e3e40c9f993`。

20-request 真實批次 `queue-20-final` session `3b504f49-a879-41ed-a0d9-46c93d8bdb3c` 全 PASS。20 個 request 由正式 Rust manager 提交到同一 Python service，逐次啟動既有 CosyVoice2 runner，新生成／播放後才提交 Transcript；不是 fixture 或既有 WAV replay。三句文字依序循環，次數為 7／7／6，female／male profile 各 10 次交替；所有 runner reference hash、實際 output WAV hash、五個時間點、FIFO、session exports 與 canonical Transcript schema 均通過。

| 20-request evidence | 實測 |
|---|---|
| 文字檔 | `app/tests/fixtures/manual-queue.txt`；SHA-256 `1d95d8e4161d483b542b7effd87a28f068e41f515188b861f4712893c9b6c613` |
| Reference audio | female `37976f69f73fb13d6fefaf80268794d545d6e19be5059437db067455a795f406`；male `3a4a5a048154cff60d717fc1fce929ebebc887f7c9222c56222dad48adb60662`；reference transcript 審核仍 WAITING，未宣稱人工音色相似度通過 |
| 模型／runtime | 同上 CosyVoice2 19 個 full-hash files、aggregate `204861ce8b518b73fd5c36e4dab0641cfa326ae7ef8d554810d853a3c0f08d60`；runner 回報 PyTorch `2.7.1+cu128`、CUDA available、RTX 5060 Ti |
| 代表輸出 WAV | 首句 female SHA-256 `2474e19b12afdec8a6a7e36dd2bc918eed6a9d968d06ba2a654160365f384690`；末句 male `807486f2022736901cf658294b400dc98140a438771d5dd0a6325a5d22401a3c`；逐句輸出及 runner evidence 在 session jobs，檢核全數非零 |
| 播放／擷取 | CABLE Input → CABLE Output、Windows DirectSound、48 kHz stereo；20 個 completed 時窗均非零，RMS 約 `0.008590～0.056884`、peak 約 `0.074890～0.337128`；finite、capture errors 空、output underrun 合計 0 |
| 整批 Capture | 87154560 frames；SHA-256 `3cf0deec85fbfe65ea210fd9ee213d5056eff893ad6d4c3a186eb315e6f39c4c`；`artifacts/desktop/manual-tts-audio/queue-20-final/cable-loopback.wav` |
| 時間／延遲 | request 起點 `2026-09-27T19:07:04.002Z`，最後完成 `19:37:17.594Z`，約 30 分 14 秒；generation `60964.575～133689.401` ms、中位 `67334.856` ms；TTFA `139175～1810424` ms、total `142053～1813534` ms，後兩者包含 queue 等待 |
| Transcript／退出 | 20 completed → 20 ME／manual_text，cancelled／failed 均 0；session ended_at 已保存、service_alive=false；21 個記錄的 Windows PIDs 與 20 個 WSL groups 無存活 |
| 驗證報告 | `queue-20-final/audio-report.json`、`artifact-verification.json`、`process-audit.json` 均 PASS；完整 request／timestamps／hash 在 `artifacts/sessions/3b504f49-a879-41ed-a0d9-46c93d8bdb3c/` |

這輪證明 offline Manual TTS 的 20-request 穩定性與 profile/reference 切換；Breeze 仍是前述單次真實鏈路驗證。每句重載模型，沒有 warm residency 或真正 chunk streaming，不能將約 30 分鐘批次執行當作連續 600 秒 realtime／LIVE PASS。

## 操作與重跑

```powershell
Set-Location D:\AetherTune\app
.\dev.ps1 -Build
.\dev.ps1 -Test
# 背景啟動 Vite 後：
npm run test:ui
npm run test:manual-tts-ui
# 啟動 Desktop；根目錄 AetherTune.cmd 仍是既有 Tk 控制台。
.\src-tauri\target\debug\aethertune-desktop.exe
```

App 選擇 Speech Reconstruction 或 Text → Voice，選 Input／TTS Engine／Voice Profile 與 Output，再輸入文字使用 Speak 或 Add to Queue。Microphone/STT 未完成的控制項維持 WAITING；Manual Text 不需要先開麥克風。若 VC runner 尚在執行，先 Stop runner 釋放 GPU／Output。

無視窗真實音訊測試：先用專案 Cargo 環境 build `speech-probe`，再由既有 Windows Python 執行 `app/tests/manual-audio-smoke.py`。測試讀取 CABLE Output，不讀 physical mic 或 final mixed output；每輪留下 `probe.jsonl`、`audio-report.json`、`cable-loopback.wav`，session request／transcript／model evidence 留在 ignored `artifacts/sessions/<session-id>/`。不要將權重、聲音或測試 artifacts 加入 Git。

```powershell
Set-Location D:\AetherTune
$ttsPython = '.\tools\venvs\seed-vc\Scripts\python.exe'
# 每輪完成並稽核後才啟動下一輪，避免同時使用 GPU／CABLE。
& $ttsPython app\tests\manual-audio-smoke.py --engine cosyvoice --voice official-cosyvoice-sample --output artifacts\desktop\manual-tts-audio\cosyvoice-r5
& $ttsPython app\tests\manual-audio-smoke.py --engine breeze --voice reference-female --output artifacts\desktop\manual-tts-audio\breeze-final
& $ttsPython app\tests\manual-audio-smoke.py --engine cosyvoice --voice official-cosyvoice-sample --count 2 --cancel-after 5 --output artifacts\desktop\manual-tts-audio\cancel-generation-final
& $ttsPython app\tests\manual-audio-smoke.py --engine cosyvoice --voice official-cosyvoice-sample --count 2 --cancel-on-playing --output artifacts\desktop\manual-tts-audio\cancel-playback-r2
& $ttsPython app\tests\manual-audio-smoke.py --engine cosyvoice --voice reference-female,reference-male --count 20 --text-file app\tests\fixtures\manual-queue.txt --output artifacts\desktop\manual-tts-audio\queue-20-final
# 以下以 cosyvoice-r5 為例；其餘輪替換同一 probe.jsonl 路徑。
Push-Location app
node tests\verify-speech-artifacts.mjs ..\artifacts\desktop\manual-tts-audio\cosyvoice-r5\probe.jsonl
Pop-Location
& $ttsPython app\tests\audit-speech-processes.py artifacts\desktop\manual-tts-audio\cosyvoice-r5\probe.jsonl
```

上述為本輪執行命令；重跑請另選空的 Output 資料夾，以保留本文既有 evidence。服務測試 `python -m unittest services.tts.test_service -v` 共 23 項 PASS；取消訊息改為簡短中文後，相關 5 項另行重跑 PASS，完整 PID audit 留在 evidence。原有 runner／cache tests 6＋6、Rust lifecycle 4 項與 Desktop build 均 PASS。

2026-09-28 發布前另行重跑 `app/dev.ps1 -Test`：contracts、原有 runner／cache 6＋6、TTS 23 項及 Rust lifecycle 4 項全 PASS；五輪真實音訊案例的 audio／artifact／process 共 15 份報告仍為 PASS。45 個本輪 source／contract／test／文件的 credential-pattern scan 無命中。此發布範圍不包含 ignored 音訊、模型、runtime 或測試 artifacts，Mic／原生 GUI／Post-FX／LIVE 的 WAITING 不因推送改成 PASS。

不修改 upstream、模型／venv、舊 Tk 控制台或系統預設路由。
