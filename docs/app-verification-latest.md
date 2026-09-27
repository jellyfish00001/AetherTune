# Desktop App 第一輪驗證 — 2026-09-27

本輪範圍：M0 + M1 + M2 skeleton。實作在現有 `D:\AetherTune` 主工作樹；開始時 HEAD `cb15ff0`、工作樹乾淨。**整體 PARTIAL；尚非日常即時音訊 MVP。** 以下保留首次交付的驗證基線；階段性 Git 發布及後續補測另列於本文件後續更新與當次回報。

## 目前版本封存與後續合併測試

使用者要求先提交目前版本，正在使用電腦期間暫停桌面操作；後續新需求完成後，再合併執行 UI／即時音訊驗收。本次封存只檢視既有 diff、log 與 report，不重新啟動 App、模型或瀏覽器。本節優先於下方首次驗證基線；**未完成項目仍為 WAITING，不宣告整體 PASS。**

第一個階段已推送 `main`：`49581f58fc068cbedb39f08ef1029b62d8bcf5f5`，當時本機 HEAD、`origin/main` 與 `git ls-remote` SHA 一致。本次封存包含以下八個補測程式檔及本文件：

- `services/engines/seed_cache.py`／`test_seed_cache.py`：只補既有登記的三個 Seed dependency cache。固定 revision、size 與 SHA-256；不同 ref／既有損壞內容不覆寫，預設唯讀，下載需明確參數。模型內容與 cache 不提交 Git，上游 provenance 不變。
- `app/src-tauri/src/main.rs`：將 Tray／hotkey／hide／shell 動作寫入本機 JSONL，並輸出唯讀原生狀態快照；沒有新增網路控制端點。後續用實際操作對照 flags 與 log。
- `app/src-tauri/src/bin/desktop-probe.rs`：增加 `--complete` 等待 runner 完成、ERROR 或 timeout；不將程序完成視為即時音訊 PASS。
- `app/dev.ps1`：加入 cache 修復安全測試。
- `app/tests/engines.mjs`／`probe-report.py`：修正預檢 ERROR 的等待條件與載入 timeout；彙整 probe 時不再覆寫其他 integration report。
- `app/tests/hit-target.html`：受控點擊計數底板；僅新增測試材料，原生穿透送達尚未驗收。

### 已有證據與待測範圍

| 項目 | 封存狀態／證據 |
|---|---|
| Seed cache 修復 | PASS（檔案驗證）；[seed-cache-report.json](../artifacts/desktop/integration/seed-cache-report.json)。XLS-R 三檔重用既有相同 snapshot，其餘兩檔下載既有登記 revision；沒有升級 checkpoint |
| Seed 原 launcher 預檢 | PASS；`-PreflightOnly` exit 0、`missing=[]`，DirectSound input `麥克風 (HyperX QuadCast S)`／output `CABLE Input (VB-Audio Virtual Cable)`；[seed-preflight.log](../artifacts/desktop/integration/seed-preflight.log)。原 cache BLOCKED 已解除；Desktop → GUI Start／Stop 重新驗收 WAITING |
| MeanVC2 完整 WAV runner | PASS（file-driven CUDA）；`desktop-probe.exe meanvc2 180 --complete` 完成、exit 0，Stop 後 `service_alive=false`。完整事件見 [meanvc2-complete.jsonl](../artifacts/desktop/integration/meanvc2-complete.jsonl)，輸出與模型 hash／device 見 [output.run-evidence.json](../artifacts/desktop/runs/745323b509a34e94b269dab308134e84/output.run-evidence.json)；Mic／虛擬輸出／人工聽測仍 WAITING |
| X-VC 完整 WAV probe | WAITING；本次補測載入期間受桌面操作中斷，清理自有測試程序。不得把截斷的 [xvc-complete.jsonl](../artifacts/desktop/integration/xvc-complete.jsonl) 視為完成；首次 start／stop 證據仍保留 |
| Build 與程式測試 | 前次 `app/dev.ps1 -Build` PASS；六個 manifest／schema negative fixtures、Python Adapter 6 tests + cache 6 tests、Rust cleanup 3 tests PASS。debug exe 最後建置 2026-09-27 22:04:33，SHA-256 `B9ACA8E1B3CED5A0B988487E4719A74B3A6EFA483E24D2DCC2945E5E06537DA3`；本次封存未重跑 |
| Edge 預覽回歸 | 前次 `npm run test:ui` PASS：三個 viewport、mode filtering、planned engine／browser Start disabled、無偽造 metrics、console/network errors 為空；[preview-report.json](../artifacts/desktop/ui/preview-report.json)。內建 Browser 也開啟 localhost 複核；原生 Overlay 驗收不由預覽取代 |
| 原生診斷輸出 | 新 build 已實際啟動並寫出 [native-state.json](../artifacts/desktop/native-state.json)；這是退出前的快照，讀取時須核對 PID 與 timestamp，不能當成目前仍在執行 |
| Tray／Hotkey／Opacity／Click-through | WAITING（完整原生 E2E）；診斷程式與底板已準備，新增動作紀錄的完整驗收尚未做。遊戲全螢幕、滑鼠送達與半透明觀感保留待測 |

MeanVC2 本次 source SHA-256 `3a4a5a048154cff60d717fc1fce929ebebc887f7c9222c56222dad48adb60662`，reference SHA-256 `37976f69f73fb13d6fefaf80268794d545d6e19be5059437db067455a795f406`。40ms model SHA-256 `01caafec9a3991a5514df9412952d24ae3370406358a01e20e03df41f2f5d515`；VC／speaker／vocoder `cuda:0`，ASR `cpu`。輸出 `output.wav` SHA-256 `a976aa1993c64befa1ac5529564135a951759b6016c3301c91dfab3380866ed3`，14.87 秒、16 kHz、finite=true、RMS=0.0636489。這是已有 file-driven verifier 的證據，沒有新增即時 callback／loopback 或聽評證據。

後續合併新需求後重驗順序：Full／Compact／Mini → Tray → 預設／自訂 Hotkey → opacity／lock／受控底板 click-through → Seed GUI migration start／stop → Mean／X 完整 runner 與 cleanup → 實際 headless Mic／Output 音訊。M3 動態參數／Preset、M4 STT 等仍依既有 milestone 排程；本版本不提前宣告已實作。

以下章節是首次交付歷史基線，其中 Seed cache BLOCKED 與「未補 cache」描述已由本節更新，不代表目前仍有相同阻塞。

## 交付檔案與架構

| 檔案／目錄 | 內容 |
|---|---|
| [app-requirements.md](app-requirements.md) | v1 產品基準、M0–M8、MVP、Non-Goals 與本輪邊界 |
| [app-architecture.md](app-architecture.md) | 層級、程序所有權、協定、狀態語意、開發／測試入口 |
| `contracts/engines/{seed-vc,meanvc2,xvc,rvc,cosyvoice,breeze}.json` | 六個 Engine manifest；TTS／RVC 只宣告規格 |
| `contracts/schemas/` | Engine Manifest、Backend State、Transcript Event、Session 四個 JSON schema |
| `app/src/` | React／TypeScript：Mode → Engine、Full／Compact／Mini、native IPC、狀態與 Diagnostics |
| `app/src-tauri/src/` | Rust：Window／Tray／hotkeys／single instance、EngineManager、ProcessManager、限定 commands |
| `services/engines/` | stdlib JSONL Adapter；呼叫既有 runner，不搬動或重寫模型 |
| `app/tests/` | contract、DOM／原生 flag、三 Adapter、程序清理與真實 EngineManager probe |
| `app/dev.ps1`、兩份 lockfile、Tauri config／icons | 開發、重建、測試與 Windows app 資源；不含 installer |
| 根 `.gitignore`／`README.md`／`AGENTS.md` | 忽略 build/cache、增加 Desktop 文件導航 |

UI → Tauri commands → EngineManager → Windows Job Object → Python JSONL bridge → 既有 Seed／Mean／X runner。沒有 PCM 經 WebView；沒有將所有 backend 合併至單一 venv。STT／Session／DeviceRegistry 預留獨立邊界，尚未實作。Engine 參數目前使用 manifest defaults，分級動態表單／Preset 留 M3。

`git diff -- tools backends benchmarks audio-rack` 為空；五個既有 Tk／runner 與 HEAD 正規化換行後逐 byte 相同，原始檔 SHA-256 存在 [probe-report.json](../artifacts/desktop/integration/probe-report.json)。

完整逐檔清單：[git-status.txt](../artifacts/desktop/git-status.txt)（涵蓋 untracked）；最後 build 的路徑、時間與 hash：[build-report.json](../artifacts/desktop/build-report.json)。screenshots／reports／build 位於 ignored artifacts 或 target，不隨 source Git 發布。

## 安裝與啟動

| 項目 | 結果 |
|---|---|
| Node/npm、C++ tools、WebView2 | 沿用本機既有環境 |
| Rust MSVC stable 1.98.1 | 本輪下載／安裝至 ignored `artifacts/desktop-toolchain/`；不更改系統 PATH |
| React／Tauri／TypeScript 依賴 | npm 安裝與兩份 lockfile 完成；build PASS |
| Python／模型 | 沿用各 Engine 原有 venv；未升級、未統一、未補模型 cache |
| Tauri App | 原生 debug exe 實際啟動 PASS；無 installer／portable package |

雙擊本機 [aethertune-desktop.exe](../app/src-tauri/target/debug/aethertune-desktop.exe)。開發／重建：

```powershell
Set-Location D:\AetherTune\app
npm ci
.\dev.ps1 -Build
.\dev.ps1           # Tauri dev
```

此 exe 依賴目前完整 checkout，不能拿 build 成功推導另一台 PC 已就緒。舊 `AetherTune.cmd`／Tk engineering console 保留。

## UI 與原生視窗驗證

使用三層：Codex 內建 Browser 目視 localhost、Playwright Edge DOM／console／network 回歸、Computer Use 操作實際 Windows exe；另外曾以原生 WebView2 CDP 核對 native flags。

| 項目 | 狀態／證據 |
|---|---|
| Full／Compact／Mini 切換 | PASS；原生按鈕與 Expand 實際操作，三張目前畫面見下方 |
| 尺寸／Frameless | PASS；logical 1040×740、420×490、420×74；125% DPI 原生 physical 1300×925、525×613、525×93 |
| Always on Top | PASS（原生 flags）；Compact／Mini true，Full 預設 false、可設定 |
| 透明與 opacity | 透明視窗／CSS opacity、Settings slider 已實作；截圖用 100% 避免背後私人畫面。遊戲疊圖／不同背景的半透明觀感 WAITING |
| Drag | PASS；原生自動化：Full 從 (200,145) → (300,245)，80 logical pixels 對應 100 physical pixels。標準 drag region 未成功，改用 pointer capture + Rust `set_position` |
| Lock Position | PASS；鎖定後相同拖曳，Compact 的位置保持 (300,117)；前端與 Rust 都限制移動 |
| Click-through | PASS（native `WS_EX_TRANSPARENT` on/off）；原生 UI 點擊開關並用 Ctrl+Alt+A 回到可操作視窗。遊戲滑鼠點擊送達／不干擾操作 WAITING |
| Tray | PASS（註冊、關閉／hide、single-instance reveal）；實際 taskbar 圖示選單逐項點擊 WAITING，未把 `tray_registered` 當完整 Tray E2E |
| Hotkey | Ctrl+Alt+A 的 click-through 復原已操作；Ctrl+Alt+V／自訂快捷鍵衝突與重新註冊 E2E WAITING |
| Mode／Engine filtering | PASS；兩個 TTS Mode 共用 CosyVoice／Breeze 契約，planned Engine 的 Start disabled |
| Console／Network | Playwright Edge 預覽與先前 native CDP report 均無 console error／request failure；backend 原有 Torch deprecation warnings 留 log |

原生 URL `http://tauri.localhost/`；預覽 URL `http://127.0.0.1:1420/`。預覽 viewport 1040×740、420×490、420×74，Start／Stop disabled，不具程序控制能力。最新 DOM 報告：[preview-report.json](../artifacts/desktop/ui/preview-report.json)。先前 native flags 報告：[native-report.json](../artifacts/desktop/ui/native-report.json)，其截圖不是最後 CSS／drag revision；最後外觀與拖曳以 Computer Use 為準。原生 CDP 複跑的 debug-port 啟動命令遭自動審核拒絕，未提供更具體理由；改用無 debug port 的原生 UI 與 Rust probe，未重試相同命令。

原生截圖：[Full](../artifacts/desktop/native/full.jpg) · [Compact](../artifacts/desktop/native/compact.jpg) · [Mini](../artifacts/desktop/native/mini.jpg)。其他證據：[位置鎖定](../artifacts/desktop/native/lock-test.jpg)、[Mean 載入](../artifacts/desktop/native/meanvc2-loading.jpg)、[X 載入](../artifacts/desktop/native/xvc-loading.jpg)、[Seed 阻塞](../artifacts/desktop/native/seed-blocked.jpg)。

## 三個 Adapter 與 cleanup

| Adapter | Start／Stop 證據 | 音訊／產品狀態 |
|---|---|---|
| Seed-VC | JSONL service、預檢 ERROR、cleanup PASS；舊 launcher 實際嘗試後因 cache 缺失 exit 1，現改為先回 MODEL_NOT_FOUND；原生 UI Start → ERROR → Stop → OFFLINE 已操作 | upstream GUI Start **BLOCKED**；TEMPORARY branch，Desktop Start 不自動開 stream；即時音訊 WAITING |
| MeanVC2 | 真實 EngineManager probe 及原生 UI Start → LOADING → Stop → OFFLINE PASS；原生 runner PID 24588 結束，log 有 ASR／VC／vocoder／speaker load | 本輪 WAV runner；完整轉換結果／Mic／Output／headless realtime WAITING |
| X-VC | 真實 EngineManager probe 及原生 UI Start → LOADING → Stop → OFFLINE PASS；原生 runner PID 29380 結束 | 本輪 WAV streaming runner；完整轉換結果／Mic／Output／headless realtime WAITING |
| 程序 cleanup | Job Object stop、crash、孫程序三個 Rust tests PASS；App Exit 時 13 個自有程序全部結束，survivors=[] | 包含 WebView2、venv launcher、衍生 Python；僅稽核自有程序，不掃殺其他 backend |

Seed 缺少現有 launcher 預檢要求的三個 HF `refs/main`：

```text
tools/external/seed-vc/checkpoints/models--facebook--wav2vec2-xls-r-300m/refs/main
tools/external/seed-vc/checkpoints/models--funasr--campplus/refs/main
tools/external/seed-vc/checkpoints/models--FunAudioLLM--CosyVoice-300M/refs/main
```

未自行下載、合成或改寫這些 cache。Mean／X 測試使用既有 `dataset/reference-voices/voice-male-m1.wav`／`voice-female-f1.wav`，輸出只寫本輪 `artifacts/desktop/runs/`。

證據：[probe-report.json](../artifacts/desktop/integration/probe-report.json)、三個 `*-probe.jsonl`、[cleanup-report.json](../artifacts/desktop/integration/cleanup-report.json)、`artifacts/desktop/logs/*.jsonl`。曾使用錯誤的 async Playwright predicate 的 Engine 報告已標 `INVALIDATED`；不引用該次 PASS。修正後的 `engines.mjs` 保留可重跑，但本輪最後 CDP integration run 未執行，以上真實 Rust probe 與原生操作才是交付證據。

## 可重跑測試與未解項目

```powershell
Set-Location D:\AetherTune\app
.\dev.ps1 -Test      # 六個 manifest + schema negatives；Python 6 tests；Rust 3 tests
# 另一個終端 npm run dev，然後：
npm run test:ui      # Edge preview；截圖與 JSON report

# dev.ps1 可準備本機 cargo 環境；直接使用同一個 EngineManager 的 probe：
$env:CARGO_HOME='D:\AetherTune\artifacts\desktop-toolchain\cargo'
$env:RUSTUP_HOME='D:\AetherTune\artifacts\desktop-toolchain\rustup'
Set-Location src-tauri
& "$env:CARGO_HOME\bin\cargo.exe" build --bin desktop-probe
.\target\debug\desktop-probe.exe meanvc2 20
.\target\debug\desktop-probe.exe xvc 20
.\target\debug\desktop-probe.exe seed-vc 2
```

**M0 PASS。M1 部分 PASS（Tray 選單／遊戲點擊／快捷鍵完整 E2E WAITING）。M2 skeleton 程序控制 PASS，Seed upstream BLOCKED，三個即時音訊 integration WAITING。** 不做整體音訊 PASS 或 LIVE 宣告。

下一個 milestone：先補 M1 剩餘原生驗收，再完成 M2 的三個 headless runner readiness、canonical AudioDeviceRegistry 與非零 callback／loopback 音訊證據；再進 M3 動態分級參數與 Preset。本輪不擴增 STT、TTS、Audio Rack、自訂 VST host、Diarization 或 installer。
