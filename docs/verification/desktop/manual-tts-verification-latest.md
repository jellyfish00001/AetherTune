# Manual TTS 增量實作與驗證

<a id="native-quick-input-20261003"></a>
## 2026-10-03：原生 Quick Input 新生成與播放生命週期

基準 `5484500`，Computer Use 實際從 Mini 開啟 Quick Input，輸入「原生介面驗收：草稿保持。」、Shift+Enter、關閉／重開確認草稿，再按 Speak。不是 mock 或舊 WAV replay；完成後 Queue 同一 request 為 completed，唯一對應 Transcript 為 `manual_text`／completed。視窗操作、exe 身分、測試修正與退出稽核由 [UI-01 報告](usability-audit-latest.md#computer-use-20261003)擁有。

| 項目 | 本輪證據 |
|---|---|
| Session／request | `890ce2f6-df88-465e-bc09-46ea612b6817`／`d7ddf9d6-27f6-4511-a170-d3dbdb09fe41` |
| 引擎／profile | CosyVoice2 resident WSL worker、`official-cosyvoice-sample`；model aggregate SHA-256 `204861ce8b518b73fd5c36e4dab0641cfa326ae7ef8d554810d853a3c0f08d60`，各檔 hash 見 session 下 request evidence |
| 輸出 WAV | session 的 `jobs/<request-id>/<request-id>.wav`；147,918 bytes、24 kHz mono PCM16、73,920 frames／3.08 秒；finite／nonzero、RMS 0.062309、peak 0.516541；SHA-256 `f90089a656b398881c890a6f9d88325d5cbb84ba6168d9dc94b7eff482e35913` |
| 等待時間 | generation_latency_ms=194008.058；完整 WAV 可用的 ttfa_ms=200982，total_response_ms=204875。這是本輪冷載入單次結果，無 before／after 比較，不是 streaming 首包或效能達標 |
| 播放與路由 | `喇叭 (HyperX QuadCast S)`／MME、rendered 48 kHz stereo、monitor off、FX bypass；playback 3.08 秒、underrun_count=0；`playback_verified=false`、`route_status=WAITING` |
| 完成時間 | 2026-10-03 00:19:32.738（Asia/Taipei；UTC 2026-10-02 16:19:32.738） |
| 程序回收 | Settings Exit 後本輪 App／service／host Windows 程序與 worker Linux group 已消失；詳見 UI 報告的 cleanup artifact |

原始 evidence 在 `artifacts/sessions/890ce2f6-df88-465e-bc09-46ea612b6817/`：request evidence、jobs WAV／runner JSON、Transcript exports，以及 `workers/cosyvoice/c41a6ebe3d584631b5d0c490a0f72343/` 的 stderr／PID／cancel 記錄。UI 快照 `speech-before.json`、`speech-submitted.json`、`speech-result.json` 與重新核對的 `acceptance-summary.json` 位於 `artifacts/desktop/computer-use-20261002-5484500/`。

worker stderr 有 ONNX CUDA provider 缺 `libcudnn.so.8`、ModelScope wetext revisions HTTP 403 及 frontend unavailable 訊息；最終生成成功不表示這些 provider／frontend 均健康。此輪未修改外部套件或模型環境，冷載入與 provider 診斷仍由 BASE-01／PERF-01 追蹤。

本輪 PASS 僅為新 request 的生成、播放 adapter 完成及 Transcript／退出生命週期。沒有獨立 CABLE 回錄、人耳聽評或 physical Mic，且未啟用新增 FX、未測 Breeze，因此 AUDIO-02 保持 PLANNED，完整路由／LIVE 仍 WAITING。

<a id="request-validation-module"></a>
## 2026-10-02：請求資料驗證模組

在已推送的 `2d3434c` 上，將 `_submit()` 的 request 資料檢查抽至 `services/tts/validation.py`。新模組僅依賴標準庫，接收 profile catalogue、預設 policy 與注入的 FX／route validators，回傳 `ValidatedRequest`；service 保留安全阻擋 → 資料驗證 → readiness → 鎖內接受／保存／排隊的順序。沒有改 queue policy、ACK、schema 或資料 writer，亦不更動 playback／模型生命週期。

`./.venv/Scripts/python.exe -m unittest services.tts.test_service services.tts.test_snapshot services.tts.test_validation -v`：**47 tests PASS**，最終版本 8.583 秒，無 skip；log 位於 `artifacts/desktop/snapshot-jitter-20261002/service-tests-final.log`（初稿 9.826 秒的 `service-tests.log` 亦保留）。新增案例驗文字 20,000 字元邊界、bool 不作整數 priority、拒絕 Agent、只接受 physical microphone STT、profile／engine 配對、metadata／profile 深拷貝、錯誤優先序與注入錯誤原樣傳遞。service 整合案例另驗拒絕時 ACK 保留 command ID、queue／DB 無新增，以及 cleanup 阻擋先於欄位檢查；既有 FIFO、取消、播放／持久化與程序回收回歸一併通過。

另以 `artifacts/desktop/snapshot-jitter-20261002/compare-validation.py` 比較 `2d3434c` 與目前的真實 `handle_command`：使用無 I/O store／adapter、無 constructor／worker 的隔離物件。77 組正常與錯誤輸入，僅將每次產生的 ID／時間正規化，ACK／accepted record 完全相同。三輪各 20 組交錯 batch、每 batch 100 次 command，最終每 command 的 before／after median 為 0.023267／0.024205、0.024102／0.025069、0.024610／0.024527 ms；第二輪 batch p95 仍增加 17.62%。這是有固定 stub 的 CPU 局部量測，**不能當端到端 latency 或整體效能 PASS**。

初稿 frozen dataclass 的 `validation-comparison.json` 保留；最終 `ValidatedRequest` 改用較輕的 NamedTuple，只固定欄位綁定，nested 資料仍靠既有深拷貝隔離。最終 raw report 為 `validation-comparison-tuple.json`，SHA-256 `8466b41397bf946e3d184686c2d852c70c5b19c84de70c4cc688888aaeeadd9e`；不以跨輪差異主張加速。當輪 `service.py` SHA-256 為 `4639243e0692a48a53e3bc24a5312c9dbc27c070d5f7bdf5e9b173f61716a024`，`validation.py` 為 `1c56737e2ff3d998b29de5b1b0248661cccbae57e56ebfd8ebea819806b8aa52`，report 也保存基準來源 hash。

`app/dev.ps1 -Test` 與 Agent 快速地圖、檔案索引、維護手冊同步新增測試與 owner。此輪用 fake generation／playback 與隔離資料，沒有新模型生成、實體裝置、GUI、CABLE 或 LIVE 證據，不覆蓋下列歷史音訊結果。原生測試整套未重跑。

2026-10-02 推送前另核對 16 個 production Python 模組的本機 import graph、UI → Rust → Python 的責任邊界與文件 owner，未發現本批新增的循環依賴。既有 VC `runner_service`／`rvc_runtime` 有函式內雙向依賴，兩種匯入順序均可完成且未載入 torch／sounddevice；這只排除該匯入情境的錯誤，仍須依[架構邊界](../../specs/app-architecture.md#modular-boundaries)的 MOD-04 處理耦合。審核記錄在 `artifacts/desktop/publication-review-20261002-67a3e2cf/architecture-evidence.json`。同輪重跑 `npm run test:contracts` PASS（六 manifest、state／Transcript／Session／ManualSpeechRequest／VoiceProfile／AgentReply 與負向 fixtures）；最終 service／validator hash 仍與上述 47 tests、77 組比較的證據一致，沒有把歷史結果寫成重新執行。

本次屬責任分離，沒有速度提升主張；前輪快照 p95 的[控制量測與限制](performance-baseline-latest.md#snapshot-jitter-controls)仍獨立追蹤，不因 47 tests PASS 而升級。回退 service 中的驗證呼叫、還原原驗證區段並同步測試入口即可，不需資料 migration。MOD-02 的 queue policy／執行協調／evidence 仍未拆完。

## 2026-10-01 以前的音訊與桌面驗證

2026-10-01 共用輸出／監聽與 RVC 整合後，TTS 的完整 35 項 service regression、contracts、preview／mock UI 及 Desktop build 再次 PASS；前一日真實 TTS 監聽音訊 artifact 保留。最新版根目錄 exe 與重啟方式見 [RVC 整合報告](../backends/vcclient-rvc-probe-latest.md)，以下 exe hash 是各輪歷史 build。

## 2026-09-30：獨立自己監聽

Manual TTS 新增預設關閉的「自己監聽」，開啟後選獨立耳機／喇叭。主輸出與監聽在 Python 各開一條 callback stream，不經 WebView 傳 PCM；監聽裝置失敗僅回報警告，主輸出完成不重播。Stop 同時取消兩條路徑；已接受的 request 保存監聽快照，開關套用下次提交。相同實體名稱不重複播放，監聽排除已知 CABLE／Voicemeeter 虛擬線路。一般主輸出仍為 8 項、監聽為 4 項，進階主輸出保留 58 項。Discord 沒有新增專用控制，僅在[線路操作手冊](../../guides/operation-guide.md#直接接-discord)補上輸入／輸出設定說明。

`python -m unittest services.tts.test_service` 的 34 項與後續新增的 monitor-open-blocked 單項均 PASS（合計 35 項）；涵蓋監聽 off／on、並行、不改主 route、同名裝置去重、失敗警告、Stop、driver timeout 有界／禁止重疊及 request／evidence 持久化。`npm run test:contracts`、`npm run test:manual-tts-ui`、TypeScript／Vite 與 `npm run tauri -- build --debug --no-bundle` 均 PASS。UI 以 Edge headless 在 `http://127.0.0.1:1420/` 檢查 Full `1040×740`、Compact `420×490`、Mini／Quick；監聽預設 off、選項排除虛擬線路、精確 submit route、重掃／切 layout 保留、失敗警告與 preview 禁止 send 均通過，console／page／network error 為 0。內建 Browser `1280×720` 複核實際 preview 的開關與說明版面；preview 不含原生裝置。截圖為 `output/playwright/self-monitor-mock.png` 與 `self-monitor-compact-mock.png`，只代表 mock UI。

音訊實測使用已生成的 1.76 秒 Breeze WAV，SHA-256 `2ed22842bf02ac7b2ecd7fe91b7af57cfa29cbcf3dab89e8b3102ed814722784`；此輪不重新載入模型。`app/tests/manual-playback-diagnostic.py` 將主輸出送至 `CABLE Input / Windows DirectSound`，另在 `CABLE Output / Windows DirectSound` 擷取。關閉監聽的擷取 RMS `0.037683`、開啟為 `0.041401`，皆 finite／nonzero、capture error 0。兩次主輸出各寫入 `84480` frames，underrun 0；開啟時 `喇叭 (HyperX QuadCast S) / MME` 監聽亦寫入完整 `84480` frames、underrun 0，首次 callback 與主輸出差 2 ms。report／capture／child log 保存在 `artifacts/desktop/self-monitor-off-20260930/`、`self-monitor-on-20260930/`，包括來源與擷取 hash。這是實際 CABLE 接收及 HyperX callback 證據，**不是原生新版 UI、耳機人耳聽評、Discord 接收或 LIVE PASS**。

可重跑同一組有限播放（第二個命令會把短語音送至 HyperX）：

```powershell
Set-Location D:\AetherTune
$ttsWav = 'artifacts/sessions/breeze-switch-check-b6ff37a14e23477bb53e25bc2b0570ab/jobs/0c3ddca3-26c8-4b25-ad30-063d149fd68e/0c3ddca3-26c8-4b25-ad30-063d149fd68e.wav'
& .\tools\venvs\seed-vc\Scripts\python.exe app/tests/manual-playback-diagnostic.py $ttsWav --output artifacts/desktop/self-monitor-off-recheck
& .\tools\venvs\seed-vc\Scripts\python.exe app/tests/manual-playback-diagnostic.py $ttsWav --output artifacts/desktop/self-monitor-on-recheck --monitor-output '喇叭 (HyperX QuadCast S)' --monitor-host-api MME
```

根目錄 `AetherTune.exe` 已更新並與此輪 debug build 核對 SHA-256：`5D242BD44C7AB166B23CFF93CDA95C859705E77B3452C46B5D00D20C43FF6434`；前一個清單精簡版備份為 `artifacts/desktop/AetherTune-before-self-monitor-20260930.exe`。PID `37876` 仍是舊 App 的已載入映像，沒有強制停止或重啟既有 Breeze。**須 Tray → Exit，再重新開啟根目錄 exe**，才看得到精簡清單與監聽開關；關閉視窗只收進 Tray。當前工具未提供可用的原生視窗控制，因此新版 WebView2 操作、重啟預設與 Discord 通話接收保持 `WAITING`；下節 exe hash 是前一版歷史紀錄。

## 2026-09-30：輸出裝置清單精簡

本機 PortAudio 原始清單有 58 個 output；主要是 14 個 Windows 播放端點經不同 Host API 重複列出，另外含系統音效對應表與 WDM-KS 原始端點。Voicemeeter 額外輸入與 CABLE 16ch 是驅動內建端點，沒有證據顯示為 AetherTune 測試建立。一般 Manual TTS 選單縮為 8 個裝置，進階選項保留完整 58 項；沒有卸載／停用 Windows 音訊裝置或更動預設播放端。選中的進階 route 收起後仍保留 exact name／Host API。

`npm run build`、`npm run test:manual-tts-ui` 與 `npm run tauri -- build --debug --no-bundle` 均 PASS。實際 inventory 對照結果保存在 `artifacts/desktop/output-device-cleanup.json`，8 個一般選項包含 HyperX、螢幕音訊、Realtek 喇叭／數位輸出、VB-CABLE 與 Voicemeeter 的主／AUX／VAIO3 輸入。所有 selectable 原始 route 都通過保留檢核；有歧義的 MME prefix 不合併、僅有 WDM-KS 或未知 API 時仍保留裝置。

Playwright 使用 Edge headless，`http://127.0.0.1:1420/`，Full `1040×740`、Compact `420×490`、Mini／Quick `420×74`／`420×260`；preview／mock IPC PASS，console/page error 與 request failure 均 0。mock 驗證一般清單去重、進階展開／收起、重新掃描與 submit payload 的 exact route；內建 Browser 複核文字發聲頁的輸出控制與進階選項版面。此輪未重新驗證原生 WebView2 的實體播放，不將 UI PASS 升格音訊或 LIVE。

根目錄 `AetherTune.exe` 已更新，與 debug build SHA-256 相同：`D76C5B5FFF0CBE04FFB6DBBFC2904EF6378D81ABBD1DA7D895BD55C80FB67187`。舊檔備份在 `artifacts/desktop/AetherTune-before-output-cleanup-20260930.exe`；執行中的 App PID `37876` 保持原樣，沒有重啟或中斷已載入的 Breeze。下一次完整 Exit 後重新開啟根目錄 exe，才套用新選單。原生新版裝置選擇仍 `WAITING`；截圖 `output/playwright/output-device-cleanup-mock.png` 只代表 mock UI。

## 2026-09-30：雙引擎常駐、中文參考聲音與單一設定入口

本輪將 Desktop Manual TTS 的 CosyVoice2／Breeze TTS 2 都改為 service 持有的 WSL worker。第一句載入模型，後續同引擎句子在同一 process 推論；切換引擎或關閉 Desktop service 時清理前一個 worker。這只適用於當前 Desktop service 存活期間；重新啟動程式後仍須首次載入。兩引擎仍先產生完整 WAV 再播放，沒有 chunk streaming。

`AETHERTUNE_RESIDENT_TTS_SMOKE=1` 執行 `tools/venvs/seed-vc/Scripts/python.exe app/tests/resident-tts-smoke.py`，report 為 `artifacts/sessions/resident-smoke-8ab12b6f-29ff-4a17-a066-d734dea1f2b4/report.json`。CosyVoice2 首句／次句生成 `62.869／4.096 秒`、模型載入 `25.407／0 秒`；Breeze 為 `170.370／8.197 秒`、模型載入 `86.101／0 秒`。各引擎兩句均有 finite／nonzero WAV 與 SHA-256，次句 `runtime_reused=true` 且 worker PID／token 與首句相同；兩個 worker 的 close audit 均為 identity verified、無殘留。此數字是本機本次實測，不是每次生成的保證或物理播放證據。

本次 model fingerprint：CosyVoice2 `204861ce8b518b73fd5c36e4dab0641cfa326ae7ef8d554810d853a3c0f08d60`，Breeze `972153a41d5cee95e94b97ba37be4a0803473f84c62172e10fe0f7bbfeef57e7`；兩者均在 WSL `Ubuntu`、RTX 5060 Ti CUDA 環境推論。CosyVoice2 使用 `tools/external/CosyVoice/asset/zero_shot_prompt.wav`（SHA-256 `c7b31d6dbe7cc6a716dded00550db5b50940bf209e424e4ad207b12e657c8ff6`）；Breeze 使用 `dataset/reference-voices/female-sister-f003.wav`（SHA-256 `2BCF3F197045799A90CB63DA02E94F2E8237E5C074304E5D00E8322F4FAF3053`）及來源原文。輸出 SHA-256 與各 request path 見 report；離線 smoke 沒有開啟 Windows 音訊裝置。

舊 `reference-female`／`reference-male` 的 prompt transcript 是日語；本輪在 UI 明確標記為日語參考，CosyVoice2 預選官方中文樣本，Breeze 預選授權標為 CC BY-NC-ND 4.0 的本機中文女聲樣本，供非商業試用。新增樣本的人耳語言與音質聽評仍 `WAITING`。WORKSPACE 先顯示聲音與引擎，再顯示輸入及輸出裝置；Speech settings 僅在 SETTINGS。生成開始時間在 Queue 進入 `generating` 時即送到前端，畫面顯示等待秒數。

原生 WebView2 使用根目錄 `AetherTune.exe`，在 `1300×900` 視窗選 CosyVoice、官方中文樣本、系統預設 `喇叭 (HyperX QuadCast S)`／`MME`，由 `AETHERTUNE_NATIVE_AUDIO_SMOKE=1` 的 `node app/tests/manual-tts-native-smoke.mjs` 在同一程式連續送兩次 `今天測試中文語音。`。session `71f7dbf2-2d6e-4c90-930c-d9f93586f6a6` 的 request `b2e17d67-31e2-4f5e-a675-d8795d34b4c2` 與 `957a44e5-8cf0-42c2-8989-b4a834eed00e` 均走完 `queued → generating → playing → completed`，WebView2 console error `0`、播放 callback `2.84／2.72 秒`、WAV RMS `0.0451／0.0439`，且生成中 snapshot 有 `generation_started_at`。報告在 `artifacts/desktop/ui/manual-tts-native-smoke-cold.json`、`artifacts/desktop/ui/manual-tts-native-smoke.json`；各 request 的 evidence 在該 session 目錄。

原生首句生成 `182.460 秒`、其中模型載入 `75.644 秒`；第二句生成 `3.297 秒`、`load_seconds=0`、`runtime_reused=true`，兩句的 worker PID `36844`、token `0b66996222cb4c3b8060f3df50d45d0c`、模型 fingerprint 完全一致。首句約 3 分鐘確實偏久，不能稱為正常固定等待；這次改動解決了每句重載，首次載入、WSL 啟動及準備工作仍待進一步優化。新版原生截圖為 `output/playwright/manual-tts-native-smoke.png`。另以瀏覽器預覽 `http://127.0.0.1:1420/`、`1280×720` 視窗複核聲音控制排在文字輸入前；新分頁的 SETTINGS 只顯示一份送出設定。Playwright 預覽與 mock IPC 測試均 PASS。

最後檢核命令：`app/dev.ps1 -Test`（contract、engine 6、cache 6、TTS 26、Rust 4 全 PASS）、在 `app/` 執行 `npm run test:manual-tts-ui` 與 `npm run test:ui`（Playwright preview／mock IPC PASS）、`app/dev.ps1 -Build`（成功並複製根目錄 exe，SHA-256 `E06C67DEB9F7E469F147291CF6EE72D15DD81994E6240DBECF32245F2662FE43`）。原生視窗使用上述 smoke 兩次，`1300×900`、`tauri.localhost`，輸出路由如上；console error `0`，沒有 network 異常回報。音訊 smoke 與預覽測試使用不同頁面與能力，不能互相替代。

原生測試證明 WAV 有限且非零、指定音訊端點的播放 callback 完成；`playback_verified=false`、`route_status=WAITING`，未做物理 loopback 或人耳語言／音質聽評。中文 prompt/reference 降低再次用日語樣本的可能，但不能據此宣稱已確認聽感為標準中文。Mic STT、VC 即時音訊、外部 Rack 與 LIVE gate 仍 `WAITING`。

## 2026-09-30：首次使用回報、裝置選擇與原生單句複核

使用者回報 Speak 送出後看似無作用、裝置須手填，且 `LIVE`／`VOICE`／`TRANSCRIPT` 三個分頁沒有差別。當時 session `3e218dfc-40f0-4d30-bcf2-8e046b159fb7` 的三筆 request 都已被 Queue 接受，但 evidence 均為 `cancelled`，沒有完成 WAV／播放；畫面當時的 `CURRENT · generating` 是尚在生成完整 WAV。舊 UI 沒有顯示等待時間，且輸出預設為 `CABLE Input`，不會由實體喇叭直接發聲。不能把這三筆紀錄稱為生成失敗，也不能稱為音訊成功。

修正：PortAudio 以有界查詢列出實際 input/output 與 Host API，同 Host API 重名端點不供選取。Streaming VC 的麥克風、輸出與 Host API 改為下拉選單；Manual TTS 在 Composer 旁顯示輸出下拉選單，預選系統預設播放端並提供重掃。Mic STT 尚未實作，文字來源的麥克風選項停用。Queue 顯示生成已等待秒數與該 request 的輸出路由；重複／空白分頁暫收起，只顯示 `WORKSPACE`／`SETTINGS`。

本輪命令與結果：`app/dev.ps1 -Build` exit `0`，根目錄 `AetherTune.exe` SHA-256 `EF9E36FF7085EF4D8C872F2C956600CE255E746C016E4F6590EB08CFD4686786`；`app/dev.ps1 -Test` exit `0`（contract／engine／cache／TTS 24 tests／Rust 4 tests）；`npm run test:manual-tts-ui` 和 `npm run test:ui` 均 `PASS`（browser preview／mock IPC）。原生 WebView2 以 `AETHERTUNE_NATIVE_AUDIO_SMOKE=1` 執行 `node tests/manual-tts-native-smoke.mjs`，最終版 session `7a094b60-74a7-4643-8107-be05cd2a8cab`、request `25e2b112-9023-4407-b7e3-b85df562f257` 走過 `queued → generating → playing → completed`，console error `0`，Transcript 為 `completed`。另在原生 VC 畫面看到 5 組 Host API、DirectSound 下 12 個輸入與 16 個輸出選項；[TTS 選擇畫面](../../../output/playwright/manual-tts-native-smoke.png)、[VC 裝置畫面](../../../output/playwright/native-vc-device-dropdowns.png)已目視複核。

這筆原生 request 的 route 是 `喇叭 (HyperX QuadCast S)`／`MME`，生成延遲 `79071.506 ms`，播放 callback 首音時間 `2026-09-29T16:34:26Z`，播放長度 `4.44 s`。生成 WAV 為 `106560` frames、`24000 Hz` mono、finite、RMS `0.0381664559`、peak `0.2388000488`；檔案 SHA-256 `de92565e57687dee6610b54a604a7e4d51dc4a5e378a4f698d4533fb374b988e` 與 evidence 相符。report 在 `artifacts/desktop/ui/manual-tts-native-smoke.json`，request evidence 在 `artifacts/sessions/7a094b60-74a7-4643-8107-be05cd2a8cab/25e2b112-9023-4407-b7e3-b85df562f257.evidence.json`。這證明本機文字生成非零 WAV 與指定實體端點的播放 callback 完成；未做喇叭實際聲壓／人耳聽評或物理 loopback，`route_status`／`playback_verified` 仍為 `WAITING`／`false`。實體 Mic、VC 即時音訊、外部 Rack、LIVE gate 亦未在本輪通過。

> **入口更新（2026-09-30）：**本頁下方 2026-09-28 的命令與測試結果為當時紀錄；目前圖形入口是根目錄 `AetherTune.exe`，舊 Tk 控制台已移除。新的啟動修復見[App 驗證](app-verification-latest.md)。

**文件邊界：**本報告保存 2026-09-27～28 與 2026-09-30 Desktop Manual TTS 的 service／Queue／生成／播放／Transcript 驗收命令與 evidence，不作完整操作手冊、產品需求或 LIVE 結論。第一次使用讀[快速說明](../../guides/quick-start.md)，建置與排錯讀[Desktop 手冊](../../guides/desktop-user-guide.md)，跨層維護讀[Agent 維護手冊](../../../.agent/reference/agent-maintenance-guide.md)。

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

生成狀態與播放狀態分開；TTS state 使用 `IDLE / QUEUED / GENERATING / BUFFERING / PLAYING / STOPPING / ERROR`。Request 使用 `queued / generating / ready / playing / completed / cancelled / failed`。runner 為完整 WAV，`supports_streaming_tts=false`，TTFA 為本 adapter 首個可用 buffer 的時間；真正 chunk streaming 尚未交付。這段原始紀錄寫於 2026-09-27～28，當時的 warm model residency 也尚未交付；2026-09-30 已加入。

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

2026-09-27～28 的測試證明 offline Manual TTS 的 20-request 穩定性與 profile/reference 切換；Breeze 當時仍是前述單次真實鏈路驗證。當時每句重載模型，沒有 warm residency 或真正 chunk streaming，不能將約 30 分鐘批次執行當作連續 600 秒 realtime／LIVE PASS；2026-09-30 的重用結果見本頁頂端。

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
