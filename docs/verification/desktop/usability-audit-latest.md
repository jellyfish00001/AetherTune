# Desktop 操作與畫面審查

最新更新：2026-10-03（Asia/Taipei）。本頁擁有 Desktop 畫面問題、修正與原生操作證據；各節保留測試日期。操作以 [Desktop 手冊](../../guides/desktop-user-guide.md)為準；模型、串流與回錄由 [四 VC 驗證](realtime-vc-verification-latest.md)與 [Manual TTS 驗證](manual-tts-verification-latest.md)擁有。2026-10-01 畫面審查未生成語音；2026-10-03 的新 TTS request 另見對應報告，兩輪均未做實體聽評。

2026-10-01 後續更新：音效已移至 SETTINGS，六引擎獨立保存與完整 App 重啟驗證由[音效設定報告](audio-effects-verification-latest.md)擁有；繁中／英文與系統匣語言由[介面語言報告](ui-language-verification-latest.md)擁有。歷史 hash／截圖保留當輪身分，目前 exe hash 見下方最新補驗。

最新補驗：2026-10-02～03 已依使用者授權執行 [Computer Use 原生操作](#computer-use-20261003)，拖曳、快捷鍵、Quick Input 與 Settings Exit 通過；系統匣選單實際點擊仍 WAITING。2026-10-02 的[視窗回歸補驗](#window-regression-20261002)及下方 2026-10-01 畫面審查保留原日期與範圍。

<a id="computer-use-20261003"></a>
## 2026-10-02～03：UI-01 Computer Use 原生操作

基準 `5484500318234cac22740c1125ff44568e2bf7dd`；本批程式差異只有 [UI 測試](../../../app/tests/ui.mjs)的 CDP 輸入隔離，未更改 runtime、UI 或資料契約。使用官方 Computer Use `@oai/sky` 實際點擊／鍵盤／拖曳，搭配 WebView2 CDP 唯讀狀態與 Playwright 回歸。中斷後重新列舉並選取當前唯一 AetherTune 視窗，未沿用過期座標。

測試 App PID `34772`，根目錄 exe SHA-256 `924b8db161a4c0f3fab54c18e022e8c57068a3474fbf8332a5fe2626bd41b815`；本輪未重建 exe。原生 URL `http://tauri.localhost/`、DPR 1.25；Full／Compact／Mini 為 1040×740／420×491／420×75 CSS（原生 1300×925／525×613／525×93），Quick Input 為 420×260 CSS。像素取整造成 Compact／Mini 比設計尺寸多約 1 CSS px。

證據目錄：`artifacts/desktop/computer-use-20261002-5484500/`（以下檔名皆相對此目錄）；`identity.json`、`observations.json`、各步驟 PNG 與 `acceptance-summary.json` 保存身分、動作後狀態及判定。38 筆觀察不是 38 個獨立測試案例；`finalize-evidence.py` 可重新核對保存的報告、設定、WAV 與退出證據，不能代替重新操作桌面。

| 實際操作 | 結果／斷言 | 證據 |
|---|---|---|
| Full／Compact／Mini 切換、拖曳、Mini 展開 | PASS；三版面可見，實際拖曳後位置改變；Compact 鎖定後位置不變 | `01`～`09` 截圖與 native position；Full 完整畫面另見 `27-full-fit-0.png`、`34-restored-visible-0.png` |
| Click-through 及 Ctrl+Alt+A | PASS；啟用後 native flag=true，快捷鍵解除為 false；再次隱藏後，在其他應用程式前景按快捷鍵可恢復 | `10`～`13`；hidden 狀態保存在 JSON，不以不可見截圖當畫面證據 |
| Mini Quick Input | PASS；開啟、focus、文字輸入、Shift+Enter 換行、關閉／重開保留草稿；按 Speak accepted 後收合，最後 completed | `16`～`24`；真實新生成 WAV、Transcript 與冷載入限制見 [Manual TTS 補驗](manual-tts-verification-latest.md#native-quick-input-20261003) |
| Ctrl+Alt+V 的未啟動／停止／重啟 | PASS；尚無先前 VC request 時顯示操作提示；RVC File 按開始後可於 VALIDATING 停止，再用快捷鍵重啟至 RUNNING，最後停止至 OFFLINE、service_alive=false | `25`、`28`～`33`；run `945cbc3e9e904e0fb3ca2d7b32907d88`、`0ad14a60bcf24378966980539cd8173e`。來源 `dataset/reference-voices/voice-male-m1.wav`、Sage_CN_HeroicFemale／FCPE／CUDA 0、FX bypass；只驗控制生命週期，未驗完整輸出品質／physical Mic |
| 右上角關閉至系統匣，再啟動同一 exe | PASS；按 × 後 visible=false、原 PID 仍在；single-instance 恢復同一視窗及 PID | `35-close-to-tray` JSON、`36-close-recovery-0.png`；不是 Tray 選單點擊 |
| Settings「結束 AetherTune」 | PASS；實際按鈕退出，14 個 owned Windows 程序均消失；WSL worker PID／group 388 由存在變為不存在，沒有殘留視窗 | `38-exit-visible-0.png`、`exit-action.json`、`owned-before-exit.json`、`cleanup-report.json`、`wsl-before-exit.json`／`wsl-after-exit.json`、`exit-window-check.json` |
| Tray 選單 Open／Overlay／恢復／Exit | WAITING；工具列舉未提供可選取的 Windows 工作列／系統匣視窗，未實際點擊選單 | tray_registered=true 只代表註冊；不以 IPC、Settings Exit 或快捷鍵替代此項 |

### 可見視窗 CDP 拖曳干擾與修正

本輪原生 `test:ui` 先失敗兩次，記錄在 `native-ui.log`、`native-ui-traced.log`。pointer trace 顯示：第一步 CDP 拖曳使原生視窗移動後，Windows 從實體游標位置送入 `buttons=0` 的 pointermove，接著 lostpointercapture；後續 CDP 移動已有 `buttons=1`，卻失去 capture，導致第 2 步位移斷言失敗。這與前輪的 client／screen 座標累加問題不同；同輪 Computer Use 的真實拖曳通過。

測試在三版面截圖完成後，先記錄 visibleBefore，再 hide 並斷言 visible=false，隔離實體游標與 CDP 合成事件，才測拖曳。原有逐步位移、2 px 容差、lock 與 click-through 斷言全部保留；沒有更動產品拖曳 handler。修正後 `native-ui-isolated.log` PASS；位置 `(1108,68)` → `(1159,92)`，locked 後不變。兩份 `native-pointer-trace-{before,after}.json` 保留診斷。

| 回歸能力／命令（工作目錄 `app/`） | 結果與界線 |
|---|---|
| Playwright Edge preview：`npm run test:ui`，`http://127.0.0.1:1420/` | PASS；Full 1040×740、Compact 420×490、Mini 420×74；`automated/preview-report.json` 與三版面 PNG；console／network errors=[] |
| `npm run test:manual-tts-ui` | PASS；preview＋explicit mock IPC，涵蓋草稿、IME、Queue／取消及錯誤；`automated/manual-tts-report.json`、mock-actions 與 PNG；mock 結果不代表模型發聲 |
| `AETHERTUNE_CDP=http://127.0.0.1:9223` 下執行 `node tests/ui.mjs` | PASS；`automated/native-report.json` 中三版面 visible=true，拖曳段 visibleDuring=false；三版面 PNG、console／network errors=[]。真實可見拖曳另由上表 Computer Use 證明 |

測試後精確恢復原始 localStorage／sessionStorage、Full／opacity／hotkeys／lock／click-through，見 `preferences-restored.json`、`shell-before.json`；RVC 回到原先 microphone 配置，沒有啟動麥克風測試。新 TTS request／Transcript 留作驗收紀錄。退出後停止本輪 Vite，1420／9223 監聽已結束；無重建環境或修改 Windows 音訊裝置。

UI-01 保持 WAITING，只追蹤本輪仍缺的 Tray 實際選單路徑；自訂快捷鍵組合、全部透明度與多螢幕組合未在這輪重新窮舉，不將上述預設操作擴張為所有配置通過。AUDIO-02、physical／CABLE／聽評／600 秒與效能門檻均未因此升級。後續入口為 [UI-01 任務列](../../status.md)與 [Agent 維護手冊](../../../.agent/reference/agent-maintenance-guide.md)。

## 2026-10-01 畫面審查（歷史範圍）

## 能否每個項目都按 START 說話

不能將所有可切換的項目解讀為麥克風變聲，也不能以 START enabled 或預檢 PASS 當成實體開箱驗收。

| 畫面選項 | 實際操作／本機證據 | 未通過的範圍 |
|---|---|---|
| Streaming VC：RVC／MeanVC2／X-VC／Seed-VC | 麥克風模式按 START，等待 RUNNING；先前四引擎原生 START／metrics／STOP PASS，短時間音訊與路由分項證據見四 VC 報告 | 實體說話→實際耳機、人耳音質、600 秒、Discord／外部 Rack 全鏈；所有角色與所有進階參數組合未逐一驗收 |
| RVC 的來源 WAV | START 轉換並播放指定音檔，沒有讀麥克風；File＋FX＋CABLE 已有音訊證據 | 不能由此推論 Mic 全鏈通過 |
| Text → Voice：CosyVoice／Breeze TTS 2 | 輸入文字後按 Speak；完整 WAV 生成後播放 | 不是麥克風即時變聲；本輪只重驗 UI，原生語音證據見 Manual TTS 報告 |
| Speech Reconstruction | 目前沿用同一套文字發聲流程；介面明確標為「目前僅文字」 | 麥克風 STT→TTS、即時字幕及 Agent Reply 尚未完成 |

本輪裝置保存值為 HyperX QuadCast S 麥克風與喇叭、Windows DirectSound。裝置可以開啟不代表使用者耳機接在 HyperX 上；實際耳機／喇叭接點尚未由使用者確認。若耳機接 Realtek、USB／藍牙或螢幕，必須選對播放端；虛擬線路則須設定接收端或自己監聽。沒有將自動選擇裝置稱為已完成實體路由。

## 畫面發現與修正

修正前後均先保存畫面；所有證據位於 `artifacts/desktop/usability-audit-20261001/`，不納入 Git。

| 優先度 | 修正前問題／影響 | 處理與結果 |
|---|---|---|
| P1 | Full 的 START 在首屏以外：1040×740 下 RVC bottom=1022.4，其他三個 bottom=834.4；必須捲動才能開始 | START／STOP 移至 Mode／Engine 與來源提示後。修正後四引擎 bottom=439.6，原生首屏可見且 enabled |
| P1 | RVC File 在 Compact 沒說明來源差異，Mini 錯標 Mic | Full／Compact 顯示 WAV 不讀麥克風；Mini 顯示 WAV，Mic 模式恢復後才顯示 Mic |
| P1 | Speech Reconstruction 名稱容易被當成麥克風流程；TTS footer 顯示 VC 的 OFFLINE | 加上目前僅文字標示與 Speak 提示；TTS footer 使用「文字發聲」 |
| P2 | `M2 skeleton`、空白 `Transcript M4`、重複 Audio WAITING 佔位讓頁面顯得未接通 | 移除工程佔位與空面板；驗收限制保留在可展開說明，沒有將分類升成 LIVE-ready |
| P2 | Mini 的 RVC 名稱／長裝置文字擠壓操作，VC 還有無作用的 `[T]` | 簡短引擎／Mic／WAV 標示並保留 tooltip；文字快輸入按鈕僅 TTS 顯示 |

## 仍未完成或需要調整

- 實體聽評、600 秒與整條路由驗收尚未完成，故保留 Candidate／WAITING。四引擎的預設測試配置有輸出，不代表每個模型與所有設定都已開箱驗收。
- 引擎 START／切換仍會 cold-load；先前原生 session 實測載入＋預熱約 11.7～95.8 秒且會波動。沒有 ETA、熱切換或取消後常駐保證，使用者須等待 RUNNING。
- Streaming VC 的 Reference WAV 仍為路徑欄位；完整 Voice Library、VC preset 保存／切換，以及 Seed／Mean／X 進階參數 UI 尚未提供。現有預設可執行，不需要先完成這些進階功能。
- Speech Reconstruction 與 Text → Voice 仍共用文字工作區；保留產品模式並明確標示目前邊界，不能宣稱兩者已有不同麥克風流程。即時字幕／ME／REMOTE 紀錄與 Agent Reply 仍未提供。
- RVC index blend 覆蓋與聲音品質待調整，Voicemeeter B1 的 RVC duplex 擷取仍 WAITING，精確數值由四 VC 報告擁有。
- 2026-10-01 畫面審查時，完整原生 `test:ui` 於拖曳位移斷言失敗；後續測試座標修正及剩餘原生操作條件見[視窗回歸補驗](#window-regression-20261002)。不能將 UI 專項 PASS 稱為所有視窗／快捷鍵／Tray 測試 PASS。

## 驗證範圍與產物

| 能力／命令 | 結果與範圍 |
|---|---|
| Codex 內建 Browser：`http://127.0.0.1:1420/`、1280×720 | 修正前後畫面複核；預覽無程序控制，不能測音訊。`01-browser-vc.png`、`13-browser-vc-after.png` |
| Edge Playwright preview：`npm run test:ui` | PASS：模式／引擎篩選、裝置／音效欄位、首屏 START、File Mini WAV 與 VC 無文字快輸入按鈕 |
| `npm run test:manual-tts-ui` | PASS：文字輸入、IME、Queue／取消／錯誤、三種視窗與 mocked IPC；同步舊 RVC 專用監聽 selector 至共用標籤。Mock 不代表真實發聲 |
| 原生 WebView2 CDP：`http://tauri.localhost/`、1040×740、DPR 1.25 | 修正前 `capture-native.mjs` 與修正後 `check-after.mjs` PASS；四引擎 validate／START 可見 enabled、File Full／Compact／Mini、兩個文字模式與最後設定恢復；console／network errors=[] |
| `npm run build`、`cargo build --bins --features tauri/custom-protocol` | PASS；根目錄獨立 exe 已更新，不依賴 Vite |
| 文件本機連結與 `git diff --check` | PASS：79 份 Markdown、713 個本機連結；無 whitespace error |

根目錄 `AetherTune.exe` SHA-256：`9719cb6b65b50a43db14eb9bc56066bcffc1f7cb29d82968e40fab6b5f7354a2`。日常啟動不保留測試 CDP port。審查後恢復 Full／Streaming VC／RVC Mic／實體 HyperX 路由、音效 bypass，沒有留下 File 或 CABLE 測試設定。

原生修正前 `native-audit.json`、修正後 `after/report.json` 保存斷言與 viewport；畫面：`after/rvc-full.png`、`after/meanvc2-full.png`、`after/rvc-file-compact.png`、`after/rvc-file-mini.png`、`after/speech-reconstruction.png`、`after/ready.png`。這些檔案支持 UI 結論，不升級音訊或 LIVE gate。

<a id="window-regression-20261002"></a>
## 2026-10-02：UI-01 視窗回歸補驗

基準為 `d478ee2`，修改僅在 [app/tests/ui.mjs](../../../app/tests/ui.mjs)，未更動產品拖曳程式、UI 或 exe。自動化執行於 2026-10-01，2026-10-02 整理並嘗試補原生實際操作；使用者正在使用電腦，已明確要求跳過 Computer Use。UI-01 保持 WAITING，不能用 CDP 通過取代實際桌面操作。

### 根因與修正

CDP 的 `page.mouse` 接受相對 WebView 的座標；產品以 `screenX/Y` 計算視窗移動。舊測試在視窗已移動後繼續增加 client 座標，會把視窗位移再次累加進游標軌跡。實測 CSS 位移目標 40×20，在 125% DPI 下原生視窗卻由 `(50,223)` 移到 `(329,362)`；pointer trace 保留在 `artifacts/desktop/baseline-20261001/drag-cdp-before.json`。

測試現在逐步讀取當前原生位置，以固定螢幕軌跡換算 client 座標；每一步等待 IPC 完成，並在放開滑鼠前重新換算。保留且加強 X／Y 位移與鎖定位置斷言，沒有刪除失敗檢查。修正後原生位置由 `(329,362)` 到 `(379,386)`，符合期望 physical 位移 50×25 的 2 px 容差；locked 時位置不變。

### 已驗證與剩餘範圍

| 能力／命令 | 場景與結果 | 證據及限制 |
|---|---|---|
| Edge headless preview：`npm run test:ui` | PASS；`http://127.0.0.1:1420/`，Full 1040×740、Compact 420×490、Mini 420×74；模式／引擎／路由欄位與首屏操作斷言 | `artifacts/desktop/ui/preview-report.json`、`preview-{full,compact,mini}.png`；console／network errors=[]，沒有 backend 音訊 |
| 原生 WebView2 CDP：設定 `AETHERTUNE_CDP=http://127.0.0.1:9223` 後執行 `node tests/ui.mjs` | PASS；`http://tauri.localhost/`，DPR 1.25；三模式 physical 尺寸 1300×925、525×613、525×93；拖曳／lock／click-through flag on/off／hide | `artifacts/desktop/baseline-20261001/native-ui-after.json`、`native-ui-after.log`；console／network errors=[]。該輪各模式 `visible=false`，只證明 DOM／IPC／原生狀態斷言，不能當成原生可視畫面驗收 |
| 修正前回歸 | FAIL 已保留；原拖曳位移斷言失敗 | 同目錄 `native-ui-before.log` 與 `drag-cdp-before.json`；不能刪除舊失敗來宣稱一直通過 |
| 內建 Browser／Computer Use 交叉複核 | WAITING；先前內建 Browser 查過 preview Full／Compact 狀態，尚未補足修正後完整原生操作 | 不操作使用者桌面；下次從 fresh window state 開始，驗實際拖曳／lock、click-through 解除、Tray 顯示／隱藏、Ctrl+Alt+A／V 及 Quick Input |

2026-10-02 新啟動的測試 App PID 18128 尚未完成 Computer Use 操作即停止；不能算新一輪原生 PASS。已核對測試唯一留下的 VC 偏好差異為 RVC `source_mode=file`，只恢復成原值 `microphone`；Full／透明度／hotkeys 與原始備份相同。透過既有 `cleanup.ps1` 的 App Exit 回收 10 個 owned processes，沒有 survivor；見 `artifacts/desktop/baseline-20261001/preference-restore.json`、同目錄 `recheck-cleanup.json`。此輪核對根目錄 exe SHA-256 為 `924b8db161a4c0f3fab54c18e022e8c57068a3474fbf8332a5fe2626bd41b815`，不把舊報告的 build hash 當成目前版本。

重跑入口與啟動／cleanup 命令由 [Agent 維護手冊](../../../.agent/reference/agent-maintenance-guide.md)擁有。剩餘條件只在 [UI-01 任務列](../../status.md)追蹤；本次沒有模型生成、錄音、聽評或 LIVE 升級。
