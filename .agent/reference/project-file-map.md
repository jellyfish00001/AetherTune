# AetherTune Git 檔案地圖

本索引對應 Git 管理檔案。先由 [Agent 控制中心](../README.md)讀規則，再從[文件入口](../../docs/README.md)選任務；單一檔案職責才以 `rg` 搜尋本索引。本索引不判定功能就緒；PASS／WAITING 以分項驗證與可重跑 artifact 為準。

## 導覽規則

- 根目錄保存使用入口與 Agent 邊界；本機 `AetherTune.exe` 由 `app/dev.ps1 -Build` 產生且不進 Git。`app/` 是 Tauri/React Desktop orchestration，`services/` 是既有 runner 與 Manual TTS service，`contracts/` 是 engine、voice、request、state 與 transcript 的資料契約。
- `audio-rack/` 與 `benchmarks/` 是跨 backend 的後製、路由與驗收基礎設施；`backends/`、`models/`、`dataset/`、`tools/` 和 `docs/` 分別保存後端契約、模型登錄、素材 provenance、可重跑工具與證據文件。
- 修改程式或契約時，先讀本表列出的主要同步文件，再用對應的 test、regression、validator 或 verification 命令核對；不要以檔案存在取代 runtime 或音訊證據。
- 逐步載入原則：先以 `AGENTS.md` 確認邊界，從 `.agent/reference/agent-quick-map.md` 找 owner，再用 `rg -n` 查直接相依；不要為單一修改載入整庫或整份本表。

## 保留資料夾應放的內容

已移除根目錄完全空白、且未被專案 source 使用的 `checkpoints/`、`model_dir/`、`settings/`、`tmp_dir/`、`upload_dir/`。這些是舊工具可能產生的**根目錄**空資料夾；第三方 repo 內同名路徑（例如 VCClient 的 `model_dir/`）不在清理範圍。保留的資料夾如下，README 或 register 即使目前沒有音訊／權重，也代表明確的放置契約，不應因看起來空而刪除。

| 路徑 | 應放內容；為何保留 |
|---|---|
| `.git/` | Git 版本庫中繼資料；由 Git 管理，不是專案輸出。 |
| `.playwright-cli/` | 本機瀏覽器測試暫存與記錄；ignored，不是產品 source 或測試 PASS 本身。 |
| `.venv/`、`.venv-py312-backup/` | 現有隔離 Python 環境與舊版備份；不進 Git，未確認替代環境前不能清除。 |
| `app/` | React/Tauri Desktop source、tests、build 設定；`node_modules/`、`dist/`、`target/` 是可重建但不屬 Git 的本機產物。 |
| `artifacts/` | 每輪 logs、WAV、metrics、證據、TTS SQLite／session；是本機 runtime 資料，**不能**因 ignored 就刪。 |
| `artifacts/desktop-toolchain/rustup/downloads/`、`tmp/` | Rustup 安裝／更新時的下載與暫存落點；即使當下空白也由本機 toolchain 管理。 |
| `artifacts/seed-vc/gui-session*/hf-home/`、`modelscope/`、`checkpoints/.locks/` | 官方 GUI session 隔離的 Hugging Face／ModelScope cache 與 checkpoint 鎖；可暫時為空，不當成過期輸出清除。 |
| `artifacts/seed-vc/*/session/checkpoints/` | Seed-VC 驗證 session 的 checkpoint 落點；由該輪 runtime／證據管理，不以空白 leaf 判定可刪。 |
| `audio-rack/`、`benchmarks/` | 跨 backend 後製／路由契約，以及 Live／客觀訊號／人工聽測規則。 |
| `backends/` | 每個 backend 的版本、輸入輸出、runner 與限制 README。 |
| `contracts/`、`services/` | UI／Rust／Python 共用 machine-readable 契約，以及既有 VC／TTS service。 |
| `dataset/raw/` | 具來源和授權的原始乾聲；目前 README 是放置契約，音檔不進 Git。 |
| `dataset/sliced/`、`dataset/augmented/` | 可回溯 parent hash 的切片與擴增衍生資料；不覆寫 raw。 |
| `dataset/reference-voices/`、`dataset/manifests/` | 已授權 reference 音訊及來源／hash／audit 登錄；兩者互相對照。 |
| `docs/` | 根目錄只放入口與狀態；`guides/`、`specs/`、`reference/`、`verification/{desktop,backends,audio}/`、`archive/` 分別放操作、規格、來源與決策、分項證據、歷史快照。每份權責看[文件地圖](../../docs/README.md)。 |
| `models/weights/`、`models/indexes/` | 已配對並登錄的 RVC `.pth`／`.index`；權重不進 Git。 |
| `models/seed-vc/`、`models/speech-reconstruction/`、`models/meanvc2/`、`models/xvc/` | 各模型獨立 checkpoint、snapshot、必要 tokenizer；依各 README／register 核對，不能混入 RVC。 |
| `models/shared/` | 僅放已決定跨 backend 共用、且有來源／hash 登錄的資產；目前保留 README 契約，未批准前不可隨意複製 checkpoint。 |
| `tools/` | 可重跑 setup、run、probe、verify 腳本與 fixtures；`external/`、`venvs/`、`cache/` 存本機第三方／runtime，不當作自有 source。 |

## 根目錄

根目錄負責專案入口、跨 Agent 規則、Python 版本與 Git 邊界。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [.gitignore](../../.gitignore) | 排除根目錄 `AetherTune.exe`、venv、模型權重、音訊、第三方 upstream、artifacts、前端 build 與本機 secrets，並保留必要 README。 | 新增生成路徑前檢查是否誤把證據或敏感資料納入 Git；與本表的 ignored-folder 索引同步。 |
| [.python-version](../../.python-version) | pyenv 類工具使用的專案 Python minor version，內容固定為 `3.10`。 | 變更時同步各隔離 runtime、`tools/python-runtime-check.ps1` 與環境文件。 |
| [AGENTS.md](../../AGENTS.md) | Codex 薄入口，指向 `.agent/` 的共用規則與路由。 | `.agent/` 入口變更時核對連結。 |
| [README.md](../../README.md) | 對外快速定位與操作文件入口；不複製詳細命令或當次測試表。 | 路線或文件入口變更時同步對應手冊、`AGENTS.md` 與本表。 |
| [start_vcclient.bat](../../start_vcclient.bat) | 以 `%~dp0` 為 root，切到被忽略的 `tools/external/VCClient/2.1.4-alpha/dist/main`，開啟 `http://127.0.0.1:18000/` 後執行 `main.exe start --https false`。 | VCClient 版本、dist 路徑、port 或啟動參數變更時同步 `docs/specs/vcclient-runtime-gate.md`；不可將 HTTP 200 當作音訊 PASS。 |

## `.agent/` 與根目錄薄入口

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [.agent/README.md](../README.md) | 跨 Agent 讀取路由與資料放置邊界。 | 同步根 `AGENTS.md` 和 `docs/README.md` 的入口。 |
| [.agent/rules/project.md](../rules/project.md) | 專案必讀邊界、修改與證據規則。 | 契約、source 或驗收邊界變更時核對對應權威。 |
| [.agent/skills/doc-routing/SKILL.md](../skills/doc-routing/SKILL.md) | 共用文件定位與更新流程。 | 文件 owner 或目錄改動時同步路由連結。 |
| [.agent/reference/agent-quick-map.md](agent-quick-map.md) | 程式 owner 與最小讀取路徑。 | owner 或測試入口變更時同步本索引與對應驗證。 |
| [.agent/reference/agent-maintenance-guide.md](agent-maintenance-guide.md) | Desktop／Manual TTS 跨層維護、測試與排錯。 | IPC、service 或檢核命令變更時同步契約與測試。 |
| [.agent/reference/project-file-map.md](project-file-map.md) | Git 檔案用途索引。 | 新增、刪除、更名 Git 管理檔案時更新。 |

## `app/`

`app/` 負責 Tauri 2 原生 shell、React UI、IPC bridge、Desktop probes 與 UI/contract regression；不重寫 backend 模型或 PCM pipeline。

### App 專案設定與前端入口

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [app/app-icon.svg](../../app/app-icon.svg) | 前端 favicon 與原生 icon 的向量來源，繪製 AetherTune 波形標誌。 | 同步 `app/index.html` favicon 與 Tauri icon 產物；視覺變更需重建 app icon。 |
| [app/dev.ps1](../../app/dev.ps1) | Desktop 開發入口；為本次 process 設定 portable Cargo/toolchain，`-Build` 成功後複製根目錄 `AetherTune.exe` 並核對 hash，不改系統 PATH。 | 同步 `app/package.json`、Tauri toolchain 與 `.agent/reference/agent-maintenance-guide.md` 的開發命令。 |
| [app/index.html](../../app/index.html) | Vite HTML shell，設定 `zh-Hant`、favicon、title 與 `src/main.tsx` module entry。 | 同步 React root、favicon 與 `app/src/main.tsx`。 |
| [app/package-lock.json](../../app/package-lock.json) | npm lockfile，固定 Vite、React、Tauri API、Playwright、AJV 等前端依賴解析結果。 | 只由 `npm install`/依賴變更更新，與 `app/package.json` 一起跑 build/test。 |
| [app/package.json](../../app/package.json) | Desktop frontend package metadata 與 `dev`、`build`、`test:contracts`、`test:ui`、`test:manual-tts-ui` scripts。 | 依賴或命令變更同步 lockfile、`app/dev.ps1` 與驗證文件。 |
| [app/tsconfig.json](../../app/tsconfig.json) | TypeScript strict/noEmit 設定，允許 JSON contract imports，涵蓋 `app/src`。 | 變更 compiler boundary 時重跑 `npm run build`，並檢查 JSON/React 類型。 |
| [app/vite.config.ts](../../app/vite.config.ts) | Vite dev/build 設定，指定 1420 dev server 與 Tauri 友善的 host 行為。 | 同步 `app/src-tauri/tauri.conf.json` 的 `devUrl`、`app/dev.ps1` 與 UI test URL。 |

### Tauri 原生層

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [app/src-tauri/Cargo.toml](../../app/src-tauri/Cargo.toml) | Rust Tauri package、Windows Job/process、global shortcut、serde 與 window/tray 依賴定義。 | 與 `Cargo.lock`、`src/main.rs`、`src/process_manager`、Tauri config 同步；跑 cargo check/build。 |
| [app/src-tauri/Cargo.lock](../../app/src-tauri/Cargo.lock) | Cargo 解析後的 Rust dependency lockfile。 | 只在 Cargo 依賴變更時更新，與 `Cargo.toml` 一起驗證。 |
| [app/src-tauri/build.rs](../../app/src-tauri/build.rs) | Tauri build script，呼叫 `tauri_build::build()` 產生原生 bundle metadata。 | 與 Tauri major version、`tauri.conf.json` 一起檢查。 |
| [app/src-tauri/capabilities/main.json](../../app/src-tauri/capabilities/main.json) | 主視窗 capability allowlist；`identifier=main`、`windows=[main]`，只給 `core:default` 與 `core:window:allow-start-dragging`，沒有額外 shell/process/speech permission。 | 新增 command/permission 前同步 Rust invoke surface 與安全審查。 |
| [app/src-tauri/tauri.conf.json](../../app/src-tauri/tauri.conf.json) | Tauri app identity、無框透明視窗尺寸、Vite dev URL、frontend dist、bundle 設定。 | 同步 `app/vite.config.ts`、`app/dev.ps1`、React shell sizing 與 UI/native 驗證。 |
| [app/src-tauri/src/lib.rs](../../app/src-tauri/src/lib.rs) | 只有 `pub mod engine_manager; pub mod process_manager; pub mod speech_manager;` 三個 module declaration；不是 Tauri entrypoint 或 command 執行器。 | 新增或搬動 module 時同步 `main.rs`、Rust tests 與本表；entry/lifecycle 行為看 `main.rs`。 |
| [app/src-tauri/src/main.rs](../../app/src-tauri/src/main.rs) | Tauri application entry；管理 tray、hotkeys、window shell、single engine guard、VC commands、speech status/action commands 與 event emission。 | 同步 `app/src/services/desktop.ts`、`speech.ts`、Shell serde、Tauri config 及 app verification。 |
| [app/src-tauri/src/engine_manager/mod.rs](../../app/src-tauri/src/engine_manager/mod.rs) | discover/validate/start/stop/status/logs 的單一 active engine manager，啟動既有 runner 並保存 backend state。 | 同步 `contracts/engines/*.json`、`services/engines/runner_service.py` 與 Desktop IPC tests；不可把 process lifecycle 當 audio PASS。 |
| [app/src-tauri/src/process_manager/mod.rs](../../app/src-tauri/src/process_manager/mod.rs) | Windows Job Object process owner；spawn、JSONL stdin/stdout、graceful stop、crash detection 與子程序回收。 | 同步 engine/speech manager 的 process assumptions，跑 Rust process tests。 |
| [app/src-tauri/src/speech_manager/mod.rs](../../app/src-tauri/src/speech_manager/mod.rs) | Manual TTS service process bridge；啟動 Python service、保存 snapshot/ack、等待 bounded action response 並轉發 speech events。 | 同步 `services/tts/service.py` protocol、`app/src/services/speech.ts` 與 `speech-probe`。 |
| [app/src-tauri/src/bin/desktop-probe.rs](../../app/src-tauri/src/bin/desktop-probe.rs) | 無視窗 EngineManager probe，驗證 manifest/request、啟停或等待 runner 結束，不宣稱 audio E2E。 | 同步 `engine_manager` request schema 與 `docs/verification/desktop/app-verification-latest.md`。 |
| [app/src-tauri/src/bin/speech-probe.rs](../../app/src-tauri/src/bin/speech-probe.rs) | 無視窗正式 SpeechManager probe；以 voice profile、UTF-8 text、count/cancel mode 驗證 TTS service 控制鏈。 | 同步 `speech_manager` action schema、`contracts/voices`、`services/tts` 與 Manual TTS verification。 |

### 原生 icon assets

以下檔案都是 Tauri bundle 的同一套 AetherTune raster icon 變體；修改任一尺寸後應由 icon source 重新產生並跑 `npm run build`，不能單獨把 icon 存在視為 UI/runtime 驗收。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [app/src-tauri/icons/128x128.png](../../app/src-tauri/icons/128x128.png) | 128×128 Windows/Linux app icon。 | 與 icon source、其他 raster 變體及 Tauri bundle 同步。 |
| [app/src-tauri/icons/128x128@2x.png](../../app/src-tauri/icons/128x128@2x.png) | 128×128 @2x 高密度 icon。 | 同上。 |
| [app/src-tauri/icons/32x32.png](../../app/src-tauri/icons/32x32.png) | 32×32 小尺寸 tray/task icon。 | 同上；以實際 tray 顯示檢查。 |
| [app/src-tauri/icons/64x64.png](../../app/src-tauri/icons/64x64.png) | 64×64 raster icon。 | 同上。 |
| [app/src-tauri/icons/Square107x107Logo.png](../../app/src-tauri/icons/Square107x107Logo.png) | Windows square tile 107×107 logo。 | 同上。 |
| [app/src-tauri/icons/Square142x142Logo.png](../../app/src-tauri/icons/Square142x142Logo.png) | Windows square tile 142×142 logo。 | 同上。 |
| [app/src-tauri/icons/Square150x150Logo.png](../../app/src-tauri/icons/Square150x150Logo.png) | Windows square tile 150×150 logo。 | 同上。 |
| [app/src-tauri/icons/Square284x284Logo.png](../../app/src-tauri/icons/Square284x284Logo.png) | Windows high-density square tile 284×284 logo。 | 同上。 |
| [app/src-tauri/icons/Square30x30Logo.png](../../app/src-tauri/icons/Square30x30Logo.png) | Windows square tile 30×30 logo。 | 同上。 |
| [app/src-tauri/icons/Square310x310Logo.png](../../app/src-tauri/icons/Square310x310Logo.png) | Windows square tile 310×310 logo。 | 同上。 |
| [app/src-tauri/icons/Square44x44Logo.png](../../app/src-tauri/icons/Square44x44Logo.png) | Windows square tile 44×44 logo。 | 同上。 |
| [app/src-tauri/icons/Square71x71Logo.png](../../app/src-tauri/icons/Square71x71Logo.png) | Windows square tile 71×71 logo。 | 同上。 |
| [app/src-tauri/icons/Square89x89Logo.png](../../app/src-tauri/icons/Square89x89Logo.png) | Windows square tile 89×89 logo。 | 同上。 |
| [app/src-tauri/icons/StoreLogo.png](../../app/src-tauri/icons/StoreLogo.png) | Windows Store-style logo asset。 | 同上。 |
| [app/src-tauri/icons/icon.ico](../../app/src-tauri/icons/icon.ico) | Windows ICO container，供 executable/window identity 使用。 | 同步 PNG variants 與 Tauri bundle。 |
| [app/src-tauri/icons/icon.png](../../app/src-tauri/icons/icon.png) | 256×256 general Tauri icon source/preview。 | 同步 `app/app-icon.svg` 與所有 raster variants。 |

### React UI 與 service client

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [app/src/main.tsx](../../app/src/main.tsx) | React root；保留 VC mode/engine/shell/native controls，並列舉音訊端點供 VC input/output 與獨立 TTS route 下拉選擇。 | 同步 `desktop.ts` IPC、`SpeechWorkspace.tsx` props、`style.css` layout 與 `app/tests/ui.mjs`。 |
| [app/src/components/SpeechWorkspace.tsx](../../app/src/components/SpeechWorkspace.tsx) | Manual TTS workspace；Input source、CosyVoice/Breeze、profile、composer、queue actions、settings、recent/favorites、transcript 與 Mini quick popup。 | 同步 `speech.ts` snapshot/action types、Rust speech protocol、`manual-tts.mjs`；不得把 WAITING audio 寫成 READY。 |
| [app/src/components/RvcControls.tsx](../../app/src/components/RvcControls.tsx) | 依 RVC manifest 呈現登錄角色、Mic／WAV、F0、音高與進階 block 參數。 | 同步 RVC manifest、runner validation 與 UI request 測試。 |
| [app/src/components/VcAudioControls.tsx](../../app/src/components/VcAudioControls.tsx) | 四 VC 共用 reference、裝置與監聽 controls；音效編輯由設定頁擁有。 | 同步 main request、音訊裝置與 UI tests。 |
| [app/src/components/AudioEffectsSettings.tsx](../../app/src/components/AudioEffectsSettings.tsx) | SETTINGS 六引擎音效編輯、數值草稿、單項重設與保存提示。 | 同步 audio-effects storage、main requests、音效 UI test 與 Desktop 手冊。 |
| [app/src/services/audio-effects.ts](../../app/src/services/audio-effects.ts) | 六引擎獨立音效記錄、範圍校驗、預設與舊 VC 設定移轉。 | 同步 Python postfx defaults/bounds、AudioEffectsSettings 與持久化測試。 |
| [app/src/services/i18n.tsx](../../app/src/services/i18n.tsx) | 共用語言 context、設定控制、即時切換、HTML lang、偏好保存與系統匣同步。 | 同步共用文案、原生 set_ui_language 與雙語測試。 |
| [app/src/locales/messages.json](../../app/src/locales/messages.json) | React 與 Rust 系統匣唯一的繁中／英文文案，每筆依序為 zh-TW／en。 | 新增文案補齊兩語與相同插值，重建前端／原生並跑 i18n test。 |
| [app/src/services/desktop.ts](../../app/src/services/desktop.ts) | Tauri `invoke/listen` wrapper、default Shell、engine manifest JSON imports 與 browser/native boundary。 | 同步 `main.tsx`、Rust commands/events、`contracts/engines/*.json` 與 UI tests。 |
| [app/src/services/speech.ts](../../app/src/services/speech.ts) | Speech snapshot/action types、contract voice fallback、snapshot/error normalization、nested enqueue IPC 與 speech-event filtering。 | 同步 `contracts/voices/*.json`、`tts-state`/speech request schema、Rust speech manager、Manual TTS tests。 |
| [app/src/style.css](../../app/src/style.css) | Full/Compact/Mini shell、TTS controls、queue、composer、settings、transcript 與 quick popup 的 visual/layout rules。 | 修改 layout 後跑 `app/tests/ui.mjs`、`manual-tts.mjs`，並複核 1040×740、420×490、420×260。 |

### App tests、fixtures 與 probes

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [app/tests/rvc-audio-smoke.py](../../app/tests/rvc-audio-smoke.py) | 正式 EngineManager 的 RVC CUDA WAV／虛擬輸入 duplex callback smoke；獨立記錄路由擷取，未讀實體麥克風。 | 同步 desktop-probe、RVC runtime evidence 與 RVC 分項報告；callback 不升格 LIVE。 |
| [app/tests/vc-native.mjs](../../app/tests/vc-native.mjs) | 根目錄 exe 四 VC 的原生 START／metrics／STOP、載入取消與可見操作證據。 | 需要 WebView2 CDP；完成後恢復實體輸出，不能替代人耳聽評。 |
| [app/tests/audit-speech-processes.py](../../app/tests/audit-speech-processes.py) | 只讀稽核正式 speech probe 記錄的 Windows service PID、WSL process-group PID 與 evidence host PID；只查已知 owned IDs，不做全機 inventory 或 kill，輸出 `process-audit.json`。 | 同步 `manual-audio-smoke.py`/speech service PID artifacts 與 process ownership；存活不等於音訊 PASS。 |
| [app/tests/cleanup.ps1](../../app/tests/cleanup.ps1) | 由指定 Desktop PID 建出本次 process tree，呼叫 `control.mjs exit` 後 bounded 等待所有 owned process 消失，輸出 cleanup report；不刪其他 backend。 | 修改 Exit/lifecycle 或 process ownership 時同步 `main.rs`、`process_manager`、`control.mjs`。 |
| [app/tests/contracts.mjs](../../app/tests/contracts.mjs) | AJV 驗證 engine/backend/session/transcript schema 及負面 state/audio boundary fixtures。 | 同步 `contracts/schemas`，跑 `npm run test:contracts`。 |
| [app/tests/control.mjs](../../app/tests/control.mjs) | 透過 Tauri CDP/IPC 驗證 shell 與 command response；`devices` 只讀核對 VC input/output 下拉選單並切回 TTS。 | 同步 `main.tsx` command names、Rust commands、native WebView test prerequisites。 |
| [app/tests/engines.mjs](../../app/tests/engines.mjs) | Playwright/IPC engine lifecycle、manifest、validate/start/stop 與 bounded probe flow。 | 同步 `engine_manager`、manifest JSON 與 `app-verification-latest.md`。 |
| [app/tests/exit-running.mjs](../../app/tests/exit-running.mjs) | 驗證 exit/tray path 對正在跑的 runner 仍能 bounded cleanup。 | 同步 `main.rs`、`process_manager`、`cleanup.ps1`。 |
| [app/tests/fixtures/manual-queue.txt](../../app/tests/fixtures/manual-queue.txt) | Manual TTS queue probe 使用的多句 UTF-8 text fixture。 | 若修改文字或句數，同步 `speech-probe` 與 evidence 的 request count。 |
| [app/tests/fixtures/manual-text.txt](../../app/tests/fixtures/manual-text.txt) | 單句 Manual TTS probe 的 UTF-8 input fixture。 | 同步 `speech-probe`、runner command 與 transcript evidence。 |
| [app/tests/hit-target.html](../../app/tests/hit-target.html) | Click-through regression 的簡單點擊計數底板；只在真正收到 click 時增加 counter。 | 同步 native shell click-through/hide test，不用它推導音訊狀態。 |
| [app/tests/manual-audio-smoke.py](../../app/tests/manual-audio-smoke.py) | 正式 probe＋獨立 CABLE capture harness：啟動 `speech-probe.exe`，以 DirectSound 的 CABLE Output 逐 callback 收音，按每個播放時間窗驗 finite/non-zero、capture errors、probe exit，並寫 `probe.jsonl`、`cable-loopback.wav`、`audio-report.json`；不負責完整 artifact schema/hash/FIFO verifier。 | 同步 `speech-probe`/`manual-tts-verification-latest.md`、指定 CABLE route 與 `verify-speech-artifacts.mjs` 的責任分界；physical Mic、外部 Post-FX 仍另驗。 |
| [app/tests/manual-contracts.mjs](../../app/tests/manual-contracts.mjs) | Manual TTS contract schema test，載入 speech request/state/voice profile fixtures。 | 同步 `contracts/schemas`、`contracts/voices`；schema 變更需修正其 exact fixtures。 |
| [app/tests/manual-playback-diagnostic.py](../../app/tests/manual-playback-diagnostic.py) | 針對指定 TTS WAV 與 Windows host/output route 做 playback diagnostic，保存 route/audio evidence。 | 同步 `services/tts/playback.py` 與 manual TTS evidence；不修改預設裝置。 |
| [app/tests/manual-tts.mjs](../../app/tests/manual-tts.mjs) | Playwright preview + explicit mocked Tauri IPC regression；驗證 composer、IME、enqueue、profile、queue/error、Mini/Compact layout。 | 修改 TTS DOM/IPC 時必跑 `node tests/manual-tts.mjs`；mock 不是 live audio proof。 |
| [app/tests/manual-tts-native-smoke.mjs](../../app/tests/manual-tts-native-smoke.mjs) | 需明確旗標才執行的原生 WebView2 單句 TTS 驗證；使用系統預設實體輸出，記錄 Queue 狀態、播放 metrics、UI 截圖與 console error。 | 只在獲得真實音訊測試授權且目前 App 由本輪啟動時執行；另核對生成 WAV／evidence，不能把 native callback 當成人耳聽評。 |
| [app/tests/resident-tts-smoke.py](../../app/tests/resident-tts-smoke.py) | 明確旗標啟動 CosyVoice／Breeze 各兩筆真實 WAV，檢查同一 worker PID/token 與第二筆 `runtime_reused`；不播放。 | 修改常駐模型、WSL mailbox 或取消生命週期後重跑；另行驗證原生 UI／播放。 |
| [app/tests/probe-report.py](../../app/tests/probe-report.py) | 解析 `artifacts/desktop/integration/{seed-vc,meanvc2,xvc}-probe.jsonl`，確認同一 EngineManager 的 final `OFFLINE`、service 不存活與無 PID survivor，並比對既有 runner baseline 未被改寫；輸出 `probe-report.json`，保留 realtime audio `WAITING`。 | 同步 `desktop-probe.rs` event/output、engine lifecycle 與 `docs/verification/desktop/app-verification-latest.md`；這是 process/control report，不是 audio E2E。 |
| [app/tests/ui.mjs](../../app/tests/ui.mjs) | Playwright browser 或 optional Tauri CDP UI regression；驗證三種 shell 尺寸、mode/engine filtering、click-through/hide。 | 同步 `main.tsx`/`style.css`/Tauri window behavior；交叉複核 Browser 與 native evidence。 |
| [app/tests/audio-effects.mjs](../../app/tests/audio-effects.mjs) | Preview／原生音效設定、引擎隔離、移轉、reload、重設與 Compact 設定入口。 | 同步 audio-effects service/model 與 UI；原生測試後還原既有紀錄。 |
| [app/tests/i18n.mjs](../../app/tests/i18n.mjs) | 文案完整性、漏接 JSX、雙語／aria、偏好、六引擎、草稿與設定不變及原生選單專項。 | Native 僅 idle 時執行，完成後恢復原始偏好與 session；不測真實音訊。 |
| [app/tests/ui-text.mjs](../../app/tests/ui-text.mjs) | 測試共用的文案查找 helper；controls 用穩定 data-testid，顯示斷言用語系。 | 同步 locale catalog 與 UI tests，不能注入瀏覽器 fixture 作為 runtime 函式。 |
| [app/tests/verify-speech-artifacts.mjs](../../app/tests/verify-speech-artifacts.mjs) | 以 AJV 與 SHA-256 核對正式 probe 的 session/request/state/transcript schema、request/profile/reference/output/model/route evidence、WAV hash、FIFO、metrics、SQLite exports 與 `service_alive=false`；不做 Windows/WSL PID cleanup，該責任屬 `audit-speech-processes.py`。 | 同步 `speech-probe`、`manual-audio-smoke.py`、TTS service snapshot/contracts 與 Manual TTS verification。 |

## `audio-rack/`

`audio-rack/` 定義跨 backend 共用的 Post-FX、routing、plugin provenance 與配對 evidence；它不是第五個模型 backend。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [audio-rack/README.md](../../audio-rack/README.md) | 說明 backend output 經 corrective EQ、de-esser、compressor、saturation 後送往 route 的共用 rack 邊界。 | 同步 `docs/specs/architecture.md`、`docs/guides/operation-guide.md`、presets/routing 與 benchmark 文件。 |
| [audio-rack/benchmarks/README.md](../../audio-rack/benchmarks/README.md) | 定義 paired bypass/full-chain run 的 source type、WAV/metrics hash、latency、dropout 與 identity 要求。 | 同步 `rack-evidence-v1.schema.json`、`tools/audio-rack-evidence-validate.py` 與 `docs/specs/live-gate.md`。 |
| [audio-rack/benchmarks/rack-evidence-v1.schema.json](../../audio-rack/benchmarks/rack-evidence-v1.schema.json) | JSON Schema，約束 rack evidence 的 run、source、bypass/full-chain output、metrics、pair delta 與驗收欄位。 | schema 變更同步 validator、regression fixtures、`benchmarks/live/live-gate-v1.schema.json`。 |
| [audio-rack/plugin-profiles/README.md](../../audio-rack/plugin-profiles/README.md) | 規定每個 VST profile 要記錄版本、format、license、sample rate、buffer/lookahead、bypass/active latency 與 artifact。 | 同步 plugin JSON、`docs/reference/source-audit.md`、Light Host 與人工聽測 evidence。 |
| [audio-rack/plugin-profiles/graillon-free-3.2.json](../../audio-rack/plugin-profiles/graillon-free-3.2.json) | Graillon Free 3.2 VST2/VST3 profile，保存來源、license classification、裝置與 latency 欄位。 | 同步 plugin README、source audit、實際 host load/latency evidence。 |
| [audio-rack/presets/README.md](../../audio-rack/presets/README.md) | 說明 preset 只描述參數與驗證狀態，不代表 VST chain 已安裝或風格已人工批准。 | 同步 preset JSON、plugin profiles 與 verification docs。 |
| [audio-rack/presets/seed-vc-neutral.json](../../audio-rack/presets/seed-vc-neutral.json) | Seed-VC neutral preset，定義 bypass/full-chain 對照所需 rack 參數與狀態。 | 同步 Manual TTS/VC route metadata、rack validator 與 audio evidence。 |
| [audio-rack/routing/README.md](../../audio-rack/routing/README.md) | 定義 capture input、backend output、rack I/O、virtual device、loopback、sample rate/channel/buffer 與方向證據。 | 同步 route JSON、`docs/guides/operation-guide.md`、loopback/Voicemeeter checks。 |
| [audio-rack/routing/seed-vc-virtual-route.json](../../audio-rack/routing/seed-vc-virtual-route.json) | 登記 Seed-VC synthetic route 的 VB-CABLE/virtual endpoint identity 與參數；不修改 Windows 裝置。 | 同步 UI route metadata、`tools/virtual_cable_loopback.py` 與 wiring evidence。 |

## `backends/`

`backends/` 只保存各 voice backend 的操作契約、候選定位與驗證入口；第三方 source、venv、weights 與輸出在 ignored 路徑。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [backends/README.md](../../backends/README.md) | backend 總表，區分 RVC historical、Seed-VC established、realtime fork/MeanVC2/X-VC candidates 與 speech reconstruction。 | 同步 `AGENTS.md`、`docs/specs/voice-conversion-architecture.md`、各 backend README 與 engine manifests。 |
| [backends/rvc/README.md](../../backends/rvc/README.md) | 說明 RVC + FCPE/RMVPE 是既有 historical baseline，涵蓋模型登錄、VCClient、訓練與操作文件入口。 | 同步 `docs/guides/model-training-guide.md`、`models/model-register.csv`、VCClient probes。 |
| [backends/seed-vc/README.md](../../backends/seed-vc/README.md) | 定義 Seed-VC source/target 輸入契約、offline/realtime profile、輸出 hash 與實體 mic/rack 限制。 | 同步 Seed setup/run scripts、asset manifest、readiness/verification docs。 |
| [backends/seed-vc-realtime/README.md](../../backends/seed-vc-realtime/README.md) | 固定 Seed-VC realtime fork 為未安裝 `PLANNED / candidate`，說明與既有 upstream baseline 的隔離關係。 | 候選 intake 或 runtime 變更時同步 `docs/archive/streaming-vc-candidate-intake-2026-09-26.md`。 |
| [backends/meanvc2/README.md](../../backends/meanvc2/README.md) | MeanVC2 安裝/runtime、40/120 ms model、CUDA file-driven WAV 入口與完整 LIVE 限制。 | 同步 `tools/meanvc2-run.py`、streaming setup/download 與 backend verification。 |
| [backends/xvc/README.md](../../backends/xvc/README.md) | X-VC revision/model/runtime、CUDA file-driven runner 與必要權重/音訊 evidence 入口。 | 同步 `tools/xvc-run.py`、streaming setup/download 與 verification。 |
| [backends/speech-reconstruction/README.md](../../backends/speech-reconstruction/README.md) | 說明 STT → TTS 重新生成 acoustic performance，及 CosyVoice2/3、Breeze 的 offline/quality boundary。 | 同步 `tools/speech-reconstruction-run.ps1`、TTS backend docs 與 Manual TTS verification。 |

## `benchmarks/`

`benchmarks/` 分離 Live Technical、Acoustic Objective 與 Human Listening 三層證據，任何一層都不能代替另一層。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [benchmarks/README.md](../../benchmarks/README.md) | 定義三層 benchmark 的問題、固定 corpus/reference/hardware/rack policy 與不可互相升格的規則。 | 同步 `docs/specs/live-gate.md`、quality/subjective/live README 與 validators。 |
| [benchmarks/corpus/README.md](../../benchmarks/corpus/README.md) | 規定固定語料需涵蓋語速、氣音、笑聲、驚叫、語言混合、60 秒與 10 分鐘 stability，並記錄 provenance。 | 同步 `sample-register.csv`、dataset provenance 與人工盲測流程。 |
| [benchmarks/corpus/sample-register.csv](../../benchmarks/corpus/sample-register.csv) | Fixed test corpus 的 stable id、文字/語言、source hash、授權 provenance 與測試標籤登錄表。 | 填入實際 sample 前需完成 dataset/source audit；目前 header 不代表已有語料。 |
| [benchmarks/live/README.md](../../benchmarks/live/README.md) | 定義 physical capture → backend → rack → virtual route → loopback 的 live benchmark 及 bypass/full-chain evidence。 | 同步 `live-gate-v1.schema.json`、`tools/live-gate-validate.py`。 |
| [benchmarks/live/live-gate-v1.schema.json](../../benchmarks/live/live-gate-v1.schema.json) | LIVE gate artifact schema，約束 source/output WAV、timing、continuity、route/model identity、human review 與 600 秒穩定欄位。 | 同步 live validator/regression、`docs/specs/live-gate.md`。 |
| [benchmarks/quality/README.md](../../benchmarks/quality/README.md) | Acoustic Objective 層的 decode、finite、non-zero、sample rate、RMS、peak、silence、DC、clipping 檢查邊界。 | 同步 `tools/audio-quality-batch.py`、`audio_output_validation.py` 與 quality report。 |
| [benchmarks/subjective/README.md](../../benchmarks/subjective/README.md) | Human Listening 盲測欄位、A/B 匿名化、1–5 評分與不得寫入私人聲音/姓名的規則。 | 同步 `listening-template.csv`、人工聽測 artifact 與 verification docs。 |
| [benchmarks/subjective/listening-template.csv](../../benchmarks/subjective/listening-template.csv) | 空白人工盲測 header，包含自然度、音色相似、內容/情緒、noise artifacts、偏好與備註欄。 | 只填實際匿名盲測結果；不可填預測分數或個資。 |

## `contracts/`

`contracts/` 是 UI、Rust、Python service 與 evidence validator 共用的 machine-readable engine、voice、speech、session、state、transcript 與 Agent Reply 邊界。

### Engine manifests

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [contracts/engines/seed-vc.json](../../contracts/engines/seed-vc.json) | Seed-VC Streaming VC manifest，列 capabilities、required paths、adapter、parameters 與 limitations。 | 同步 `app/src/services/desktop.ts`、`engine-manifest.schema.json`、Seed tools/docs。 |
| [contracts/engines/meanvc2.json](../../contracts/engines/meanvc2.json) | MeanVC2 streaming candidate manifest，描述 runtime/weights requirements 與 file-driven adapter。 | 同步 desktop discovery、MeanVC2 runner/setup/docs。 |
| [contracts/engines/xvc.json](../../contracts/engines/xvc.json) | X-VC streaming candidate manifest，描述 runtime、tokenizer/checkpoint paths 與 limitations。 | 同步 desktop discovery、X-VC runner/setup/docs。 |
| [contracts/engines/rvc.json](../../contracts/engines/rvc.json) | RVC + FCPE Legacy manifest，保留第一輪 planned adapter 與 historical classification。 | 同步 RVC backend/model/VCClient docs，不得把 planned 描述成 active。 |
| [contracts/engines/cosyvoice.json](../../contracts/engines/cosyvoice.json) | CosyVoice TTS manifest，提供 Speech Reconstruction/Text → Voice capabilities、reference voices、runner path 與 offline limitation。 | 同步 `SpeechWorkspace` engine options、CosyVoice runner/docs。 |
| [contracts/engines/breeze.json](../../contracts/engines/breeze.json) | Breeze TTS 2 manifest，提供 TTS capabilities、reference voices、WSL runner path 與 non-streaming limitation。 | 同步 `SpeechWorkspace`、Breeze runner/docs。 |

### JSON schemas

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [contracts/schemas/engine-manifest.schema.json](../../contracts/schemas/engine-manifest.schema.json) | 約束每個 engine manifest 的 id/name/family/capabilities、adapter、classification、implementation、paths、parameters 與 limitations。 | 同步六個 engine JSON、`app/tests/contracts.mjs` 與 desktop discovery。 |
| [contracts/schemas/backend-state.schema.json](../../contracts/schemas/backend-state.schema.json) | 約束 backend state event、合法 lifecycle value、reason、engine id 與 `audio_verified` boundary。 | 同步 Rust EngineManager state、contract tests 與 app verification。 |
| [contracts/schemas/session.schema.json](../../contracts/schemas/session.schema.json) | 約束 session identity、mode/engine/model/profile/reference、parameters、devices、postfx、STT 與 export metadata。 | 同步 session storage/export、contract tests 與 docs/verification。 |
| [contracts/schemas/speech-request.schema.json](../../contracts/schemas/speech-request.schema.json) | 約束 Manual TTS queue request 的 id/session/text/engine/profile/source/priority/metadata/route 與 status。 | 同步 `services/tts/service.py`、Rust speech bridge、`manual-contracts.mjs`。 |
| [contracts/schemas/tts-state.schema.json](../../contracts/schemas/tts-state.schema.json) | 約束 `speech_snapshot` event、state vocabulary、queue/current request、transcript、profiles/settings/capabilities 與 audio WAITING。 | 同步 `speech.ts` normalization、Rust events、TTS service tests。 |
| [contracts/schemas/transcript-event.schema.json](../../contracts/schemas/transcript-event.schema.json) | 約束 transcript event 的 source/speaker/device/time/language/text/confidence/provider 欄位。 | 同步 transcription service/storage、`app/tests/contracts.mjs` 與 transcript UI filter。 |
| [contracts/schemas/voice-profile.schema.json](../../contracts/schemas/voice-profile.schema.json) | 約束 voice id/name/engines/status、review metadata、per-engine references 與 official CosyVoice sample。 | 同步 `contracts/voices/*.json`、TTS service profile loader、UI fallback/import tests。 |
| [contracts/schemas/agent-reply.schema.json](../../contracts/schemas/agent-reply.schema.json) | 約束未啟用的 future AgentReply text/emotion/actions/metadata payload；目前 service 拒絕 agent/system source。 | 同步 `contracts/agent_reply.py`、UI `agent_reply · PLANNED` 與 Manual TTS boundary。 |

### Python contract and voice records

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [contracts/agent_reply.py](../../contracts/agent_reply.py) | Agent Reply extension dataclasses、timing fields、provider protocol 與 `PLANNED` feature flag；不取得 TTS engine/playback handle。 | 同步 `agent-reply.schema.json`、service source rejection 與 UI capability。 |
| [contracts/voices/reference-female.json](../../contracts/voices/reference-female.json) | `reference-female` CosyVoice/Breeze voice profile，保存公開 sample provenance、per-engine audio/text paths 與 review notes。 | 修改 ID/engine/reference 時同步 `contracts/engines`、TTS UI fallback、Manual TTS evidence。 |
| [contracts/voices/reference-male.json](../../contracts/voices/reference-male.json) | `reference-male` CosyVoice/Breeze voice profile，保存公開 sample provenance、per-engine audio/text paths 與 review notes。 | 同上。 |
| [contracts/voices/official-cosyvoice-sample.json](../../contracts/voices/official-cosyvoice-sample.json) | Official CosyVoice zero-shot sample profile，只支援 CosyVoice，保留 official audio/text metadata status。 | 同步 CosyVoice manifest、TTS service profile validation 與 UI catalogue。 |
| [contracts/voices/reference-mandarin-female.json](../../contracts/voices/reference-mandarin-female.json) | 中文女聲本機非商業測試 profile，連到來源 register 的 exact source text 與音檔。 | 同步 reference register、文字 fixture、TTS UI catalogue 與使用手冊；人工聽評仍 WAITING。 |

## `dataset/`

`dataset/` 管理音訊素材的目錄責任、reference/source provenance 與 audit manifests；實際 WAV 通常被 `.gitignore` 排除。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [dataset/raw/README.md](../../dataset/raw/README.md) | 定義可合法使用的原始乾聲資料應記錄來源、授權、錄音者/角色、格式與噪音狀態；raw audio 不進 Git。 | 同步 `dataset/manifests/source-register.csv` 與 `tools/dataset_audit.py`。 |
| [dataset/augmented/README.md](../../dataset/augmented/README.md) | 定義變調/擴增輸出需保存來源檔名、半音數與處理工具版本，避免 leakage/recount。 | 同步 dataset manifest 與任何生成工具。 |
| [dataset/sliced/README.md](../../dataset/sliced/README.md) | 定義切片資料的保存責任與來源追溯；切片音檔不進 Git。 | 同步 dataset audit、manifest parent/derivation 欄位。 |
| [dataset/reference-voices/README.md](../../dataset/reference-voices/README.md) | 登記 Seed-VC、CosyVoice、Breeze 使用的男/女 reference sample 來源、用途與 transcript 核對限制。 | 同步 `contracts/voices`、`tools/fixtures` text、backend README 與 voice audit。 |
| [dataset/manifests/README.md](../../dataset/manifests/README.md) | 說明 source-register、raw-audit、manual_notes、SHA-256、provenance 與 `--fail-on-invalid` 填寫流程。 | 同步五個 CSV 與 `tools/dataset_audit.py`；人工 source register 不由工具推測。 |
| [dataset/manifests/raw-audit.csv](../../dataset/manifests/raw-audit.csv) | 機器產生的 raw WAV technical audit rows，保存 format、sample rate、channels、duration、volume、hash、source batch 與 review state。 | 由 audit 重產；音檔替換後重跑並確認 source hash。 |
| [dataset/manifests/raw-audit.example.csv](../../dataset/manifests/raw-audit.example.csv) | raw-audit 欄位與空值/狀態的填寫範例，不是實際資料證據。 | schema/欄位變更同步 `dataset/manifests/README.md` 與 audit script。 |
| [dataset/manifests/reference-register.csv](../../dataset/manifests/reference-register.csv) | reference voice label、file/provenance、transcript與 review metadata 的 register。 | 同步 `dataset/reference-voices/README.md`、`contracts/voices`。 |
| [dataset/manifests/source-register.csv](../../dataset/manifests/source-register.csv) | 人工維護的來源/授權/批次登記，包含 source SHA-256 與 derivation。 | 音檔或授權變更必須人工重登記；與 raw audit 一起跑 dataset gate。 |
| [dataset/manifests/source-register.example.csv](../../dataset/manifests/source-register.example.csv) | source-register 欄位與 provenance 寫法範例，避免把網路下載當作授權說明。 | 欄位變更同步 manifests README 與 source audit。 |

## `models/`

`models/` 只保存模型與 backend register、目錄責任及 provenance 規則；實際 checkpoint、weights、index、snapshot 與 Hugging Face cache 以資料夾層級索引，依 `.gitignore` 不逐檔納入 Git。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [models/README.md](../../models/README.md) | 模型目錄總索引，分開 backend register、RVC paired model register、Seed-VC、streaming backend 與 speech-reconstruction snapshot；主要給 backend/tools 維護者讀取。 | 同步各 backend README、`models/backend-register.csv`、`models/model-register.csv` 與 `docs/reference/source-audit.md`；不要把檔案存在寫成 runtime PASS。 |
| [models/backend-register.csv](../../models/backend-register.csv) | backend/profile register，保存 family、stage、source、revision、license、runtime 與 evidence 路徑，供 readiness audit 及人工 review 讀取。 | 新增或改 backend 時同步 `backends/*/README.md`、engine manifest、`docs/verification/backends/backend-install-test-latest.md` 與 source/license audit。 |
| [models/indexes/README.md](../../models/indexes/README.md) | RVC `.index` 目錄責任、模型配對、hash 與註冊規則；實際 index 檔不進 Git。 | 改 index 配對或路徑時同步 `models/model-register.csv`、`models/weights/README.md`、RVC register/audit tools。 |
| [models/model-register.csv](../../models/model-register.csv) | RVC `.pth`/`.index` paired model 的名稱、路徑、hash、sample rate、provenance 與狀態登錄，供 model audit 和 VCClient register 流程使用。 | 權重或 index 替換後先重算 hash，再同步 `tools/rvc-model-audit.py`、`tools/rvc-register-model.ps1`、`docs/reference/current-rvc-model-inventory.md`。 |
| [models/model-register.example.csv](../../models/model-register.example.csv) | RVC model register 空白欄位與填寫格式範例，不是實際模型證據。 | 欄位變更同步 `models/README.md`、`model-register.csv`、model audit/ready-gate scripts。 |
| [models/seed-vc/README.md](../../models/seed-vc/README.md) | Seed-VC checkpoint/profile 邊界，區分 `offline-v1` 與 `realtime-tiny` 路徑及其 evidence 限制。 | 同步 `tools/seed-vc-assets.json`、setup/run scripts、`docs/reference/seed-vc-assets.md` 與 readiness/verification reports。 |
| [models/shared/README.md](../../models/shared/README.md) | 共用 pretrained/tokenizer 資產的所有權與避免 backend 混用規則；不放 backend-specific checkpoint。 | 資產 ownership 或 cache 路徑變更時同步 `docs/reference/source-audit.md`、各 backend setup/preflight。 |
| [models/speech-reconstruction/README.md](../../models/speech-reconstruction/README.md) | CosyVoice/Breeze speech-reconstruction model snapshot 的目錄、runtime、license 與 provenance 邊界。 | 同步 `models/backend-register.csv`、speech reconstruction backend README、TTS setup/infer tools 與 verification docs。 |
| [models/speech-reconstruction/breeze-tts-2/README.md](../../models/speech-reconstruction/breeze-tts-2/README.md) | Breeze TTS 2 本機 snapshot 的 source/revision/license 與模型資料夾使用說明；權重和 tokenizer payload 不逐檔追蹤。 | 改 snapshot/revision 或 license 時同步 `tools/breeze-tts2-setup.ps1`、`tools/breeze-tts2-infer.py`、`docs/verification/backends/breeze-tts2-verification-latest.md`。 |
| [models/weights/README.md](../../models/weights/README.md) | RVC `.pth` 權重目錄及 paired `.index` policy；實際角色權重被 ignore。 | 改模型註冊規則時同步 `models/model-register.csv`、`models/indexes/README.md`、RVC audit/register tools。 |

## `services/`

`services/` 是可被 Desktop native shell 啟動的 Python orchestration/service layer；engine runner、TTS generation、playback、storage 與可取消 job 各自維持邊界，不把 PCM 直接塞入 frontend IPC。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [services/engines/__init__.py](../../services/engines/__init__.py) | engines package marker，讓 runner service、Seed cache 與 tests 以同一 package import。 | package layout 變更時同步 `services/engines/*` import、native service launcher 與 engine tests。 |
| [services/engines/runner_service.py](../../services/engines/runner_service.py) | JSONL engine control bridge；只協調既有 runner、以 stdout 傳狀態/ack，保留 backend runner ownership，不在 IPC 傳 PCM。 | command/event schema 變更同步 `contracts/schemas/backend-state.schema.json`、Rust EngineManager bridge、`app/src/services/desktop.ts` 與 runner service tests。 |
| [services/engines/rvc_runtime.py](../../services/engines/rvc_runtime.py) | RVC 已登錄模型 hash、FCPE／RMVPE CUDA、rolling block／SOLA、PortAudio stream、監聽及 evidence；重用固定 upstream 推論核心。 | 同步 RVC manifest、runner validation、音訊 smoke、backend README 及 source audit。 |
| [services/engines/stream_runtime.py](../../services/engines/stream_runtime.py) | Seed／Mean／X 共用 capture、推論 worker、bounded PCM queue、輸出／監聽、metrics 與 evidence。 | 同步 runner service、三 manifest、runtime queue tests、Desktop VC report。 |
| [services/engines/streaming_adapters.py](../../services/engines/streaming_adapters.py) | 三引擎 resident 模型、reference、source revision、rolling context 與 host/model 重取樣。 | 同步 backend README、processor tests 與真實 streaming smoke。 |
| [services/engines/postfx.py](../../services/engines/postfx.py) | 共用 EQ／壓縮／殘響／乾濕混合與範圍驗證。 | 同步 VC UI controls、四 runtime 接點與訊號 tests。 |
| [services/engines/test_postfx.py](../../services/engines/test_postfx.py) | bypass、乾聲、跨 block filter history、reverb tail 與 limiter regression。 | Post-FX 變更後重跑，不替代 physical listening。 |
| [services/engines/test_stream_runtime.py](../../services/engines/test_stream_runtime.py) | variable frame FIFO、bounded backlog 與不阻塞輸出 callback regression。 | 同步 capture/output queue 行為。 |
| [services/engines/test_streaming_adapters.py](../../services/engines/test_streaming_adapters.py) | X codec boundary、lookahead 與 rolling/fade regression。 | 同步三 processor 的參數與輸出契約。 |
| [services/engines/seed_cache.py](../../services/engines/seed_cache.py) | 只讀/受保護的 Seed cache asset resolution 與必要 repair，避免覆寫無關 cache 或暗中升級模型。 | asset revision/hash 或 repair policy 變更同步 `tools/seed-vc-assets.*`、Seed setup/preflight、`services/engines/test_seed_cache.py`。 |
| [services/engines/test_runner_service.py](../../services/engines/test_runner_service.py) | M2 engine adapter/JSONL boundary regression，使用 fixtures 驗 protocol 和 failure cleanup；不代表 CUDA、mic 或 audio E2E。 | runner protocol 或 fixture 改動同步 `runner_service.py`、backend-state schema 與 app contract tests。 |
| [services/engines/test_seed_cache.py](../../services/engines/test_seed_cache.py) | Seed cache repair 的 path/hash/link protection tests，不下載真模型、不覆寫外部 upstream。 | cache policy 或 manifest 欄位改動同步 `seed_cache.py`、Seed assets registry/preflight。 |
| [services/tts/__init__.py](../../services/tts/__init__.py) | TTS service package marker，供 adapters、storage、service 與 tests import。 | package layout 變更同步 TTS service entrypoint 與 tests。 |
| [services/tts/adapters.py](../../services/tts/adapters.py) | CosyVoice2/Breeze generation adapters；把 text/reference 轉成 validated WAV，generation 與 playback 分離且目前非 streaming。 | engine ids、reference contract 或 output manifest 變更同步 `contracts/engines/*.json`、voice profiles、TTS runner tools 與 Manual TTS verification。 |
| [services/tts/playback.py](../../services/tts/playback.py) | 獨立 playback adapter 與有界 PortAudio 裝置列舉；播放仍要求明確 output/host route，不負責模型生成。 | route/output semantics 變更同步 `services/tts/service.py`、`app/src/services/speech.ts`、Rust speech bridge 與 `docs/verification/desktop/manual-tts-verification-latest.md`。 |
| [services/tts/service.py](../../services/tts/service.py) | Manual TTS JSONL service，管理 speech snapshot、queue/profile/route/transcript/settings、generation/playback orchestration、ack 與 event。 | queue/state/transcript schema 變更同步 `contracts/schemas/tts-state.schema.json`、`speech-request.schema.json`、Rust speech commands、UI `speech.ts` 與 service tests。 |
| [services/tts/postfx.py](../../services/tts/postfx.py) | TTS 完整 WAV 共用音效，以固定 block 處理並保留原始檔、hash、取消與處理時間。 | 同步 engine PostFx、TTS service snapshot／playback 與音效驗證。 |
| [services/tts/test_postfx.py](../../services/tts/test_postfx.py) | 真實 WAV bypass、dry、rate/channels/frames、原始檔保留及取消 regression。 | TTS 音效修改後重跑；不代表真實模型生成或播放端。 |
| [services/tts/storage.py](../../services/tts/storage.py) | SQLite canonical TTS session/queue/transcript storage，並即時輸出 recent/favorites/settings/export records。 | storage schema、settings 或 transcript policy 變更同步 Manual TTS contract、service restore/export flow 與 verification doc。 |
| [services/tts/test_service.py](../../services/tts/test_service.py) | fake adapter orchestration regression，涵蓋 queue/state/SQLite/cancellation/process cleanup，並用 fake PortAudio 驗裝置清單預設與重名保護；不宣稱真模型或音訊 endpoint。 | service/adapters/storage contract 改動先更新此 regression，再同步 schema/UI contract tests。 |
| [services/tts/wsl_job.py](../../services/tts/wsl_job.py) | 可取消且可稽核的 WSL process-group job；以 token 驗證 `/proc` 後才 TERM/KILL，避免誤殺其他 backend。 | process lifecycle 或 cancellation policy 變更同步 TTS service、failure tests 與 Manual TTS verification。 |

## `tools/`

`tools/` 放置 AetherTune 自有的 setup、runner、probe、evidence validator 與 regression scripts；第三方 source、預編譯包和模型由 ignored/upstream 路徑保存，入口與驗收邊界以 `tools/README.md` 為準。

### UI、runtime 與通用音訊驗證

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [tools/README.md](../../tools/README.md) | 工具目錄 policy、主要 setup/runner/probe/evidence 入口和禁止把匯入/檔案存在寫成 PASS 的規則。 | 新增或改工具時補列用途、source/license 位置，並同步相關 `docs/*verification*.md`。 |
| [tools/powershell-setup.ps1](../../tools/powershell-setup.ps1) | 安裝/準備 portable project PowerShell，處理安全 execution policy 與前置檢核。 | setup prerequisite 變更同步根目錄啟動命令、runtime docs。 |
| [tools/python-runtime-check.ps1](../../tools/python-runtime-check.ps1) | 稽核七組 runtime、Python 3.10、CUDA、pip check 與保留的 WSL runtime；是環境檢核，不是 audio E2E。 | runtime matrix 變更同步 `tools/python-runtime-probe.py`、`docs/verification/desktop/python-ui-verification-latest.md`。 |
| [tools/python-runtime-probe.py](../../tools/python-runtime-probe.py) | read-only isolated Python 3.10/dependency/CUDA probe，輸出環境證據。 | probe 欄位或 provider 判定變更同步 runtime-check 和 docs，不能以 provider list 代替 GPU/audio proof。 |
| [tools/audio_output_validation.py](../../tools/audio_output_validation.py) | CosyVoice/Breeze 共用 WAV signal gate；拒絕 NaN/Infinity、空檔、錯 sample rate、全零或非 finite output，並寫 failure manifest。 | WAV gate 欄位同步 TTS adapters/runners、`benchmarks/quality` contract 與 regression。 |
| [tools/audio_runner_failure.py](../../tools/audio_runner_failure.py) | dependency-free runner output argument parser、stale output cleanup 與 FAIL manifest helper。 | output alias/parser policy 同步兩個 TTS runner 與 `audio-runner-entry-regression.py`。 |
| [tools/wav-evidence.py](../../tools/wav-evidence.py) | 用 WAV header/PCM payload 驗證實際 metadata、hash、finite/non-zero signal；不能取代 paired rack 或 LIVE gate。 | evidence 欄位同步 `tools/seed-vc-wav-check.py`、quality validators 與 verification reports。 |
| [tools/seed-vc-wav-check.py](../../tools/seed-vc-wav-check.py) | 驗證並 hash 單一新 Seed output WAV，提供離線 runner output 的最小 evidence。 | Seed output schema 或 validator 改動同步 `seed-vc-run.ps1`、Seed docs。 |

### Audio rack、quality 與 LIVE evidence

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [tools/virtual_cable_loopback.py](../../tools/virtual_cable_loopback.py) | 以 440 Hz synthetic signal 驗證指定 WASAPI virtual playback/record endpoints，輸出 metrics/WAV/hash，不改 mic/default device。 | route/metric 欄位同步 `tools/voicemeeter-route-check.py`、rack evidence schema 和 wiring verification。 |
| [tools/voicemeeter-route-check.py](../../tools/voicemeeter-route-check.py) | read-only Voicemeeter Remote/API + WASAPI B1 level meter 與 synthetic `Voicemeeter Input → B1 → Out B1` 檢查，不寫設定。 | route identity/metric 欄位同步 `audio-rack` docs、wiring validator。 |
| [tools/audio-rack-evidence-validate.py](../../tools/audio-rack-evidence-validate.py) | 驗證 paired rack A/B source、bypass/full-chain WAV/metrics、hash、run/model/hardware/route identity 與實測 delta；rack PASS 不能升格 LIVE。 | schema/metrics 變更同步 `tools/audio-rack-evidence-regression.py`、`docs/specs/live-gate.md`。 |
| [tools/audio-rack-evidence-regression.py](../../tools/audio-rack-evidence-regression.py) | 覆蓋 unpaired、missing、hash/identity/timing/continuity/output/delta mismatch、silence 和超過 5 秒等負測。 | validator 或 fixture contract 改動同步 `audio-rack-evidence-validate.py` 和 LIVE gate docs。 |
| [tools/live-gate-validate.py](../../tools/live-gate-validate.py) | 依 mic input/output artifact、timing/continuity、source type、human review identity/audio hash、run time/600 秒 stability 分類 LIVE、candidate、offline、waiting、blocked。 | gate schema/狀態或 evidence欄位變更同步 `benchmarks/live/live-gate-v1.schema.json`、`docs/specs/live-gate.md`。 |
| [tools/live-gate-regression.py](../../tools/live-gate-regression.py) | LIVE gate artifact/source/identity negative tests，確認 synthetic、不完整 review 或缺欄位不能通過。 | gate validator 改動時先同步此 regression 和 verification plan。 |
| [tools/portaudio-callback-telemetry.py](../../tools/portaudio-callback-telemetry.py) | 統計 callback/frame continuity、PortAudio status、ADC timestamp drift，不保存 audio samples。 | telemetry output 或 device selection 變更同步 `portaudio-callback-telemetry-regression.py`、Seed live evidence。 |
| [tools/portaudio-callback-telemetry-regression.py](../../tools/portaudio-callback-telemetry-regression.py) | callback status/frame continuity synthetic regression；不能代表實際裝置通過。 | telemetry 欄位或 threshold 變更同步 telemetry tool 和 live docs。 |
| [tools/audio-quality-batch.py](../../tools/audio-quality-batch.py) | 四 backend WAV 的 signal-level batch compare，檢查 hash、dBFS、finite/non-zero、clipping/silence/DC。 | quality 欄位同步 `audio-quality-batch-regression.py`、quality report/template。 |
| [tools/audio-quality-batch-regression.py](../../tools/audio-quality-batch-regression.py) | status aggregation regression，保證 BLOCKED row 不會彙總成 PASS。 | aggregation/status vocabulary 變更同步 batch tool 和 verification docs。 |
| [tools/audio-output-validation-regression.py](../../tools/audio-output-validation-regression.py) | WAV output gate 的空值、非 finite、有效訊號 negative/positive cases。 | output gate 改動同步 `audio_output_validation.py`、TTS adapters。 |
| [tools/audio-runner-entry-regression.py](../../tools/audio-runner-entry-regression.py) | 實際啟動兩個 TTS runner subprocess，測 help、output aliases、`--`、stale cleanup、parse exit 2 與 FAIL manifest。 | runner CLI 或 cleanup policy 變更同步 `audio_runner_failure.py`、Breeze/CosyVoice runners。 |

### Speech reconstruction、STT 與 TTS

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [tools/cosyvoice-setup.ps1](../../tools/cosyvoice-setup.ps1) | 在 WSL2 Ubuntu 建立 CosyVoice Python 3.10 environment、安裝官方依賴、下載 CosyVoice2。 | model/runtime revision 變更同步 `cosyvoice-infer.py`、models register、CosyVoice verification。 |
| [tools/cosyvoice-infer.py](../../tools/cosyvoice-infer.py) | CosyVoice2 dedicated WSL inference entry，支援 zero-shot/reference clone，輸出 WAV 與 manifest。 | input/reference/output contract 同步 `services/tts/adapters.py`、voice profiles、CosyVoice docs。 |
| [tools/tts-resident-worker.py](../../tools/tts-resident-worker.py) | CosyVoice／Breeze 的 WSL 常駐推論 worker；每筆 mailbox request 產生獨立 WAV、manifest 與結果，模型在同 Engine 連續請求間保留。 | 同步 `services/tts/adapters.py` 的 WSL group 清理、Breeze resident runtime、真實兩筆 smoke 與 Manual TTS 驗證。 |
| [tools/cosyvoice-frontend-probe.py](../../tools/cosyvoice-frontend-probe.py) | 以小輸入執行 CosyVoice speech-tokenizer ONNX，記錄 provider/profiling，區分 frontend probe 與完整 TTS。 | probe output 或 ONNX provider policy 同步 cudnn8 wrapper、verification docs。 |
| [tools/cosyvoice-frontend-cudnn8-probe.ps1](../../tools/cosyvoice-frontend-cudnn8-probe.ps1) | CosyVoice frontend CUDNN8 probe 的 WSL wrapper。 | WSL path/runtime 變更同步 frontend probe 和 CosyVoice verification。 |
| [tools/breeze-tts2-setup.ps1](../../tools/breeze-tts2-setup.ps1) | 在 WSL2 Ubuntu 建立 Breeze TTS 2 Python 3.10 environment 與官方 checkpoint。 | checkpoint/license/runtime 變更同步 Breeze infer/run/webui 和 verification。 |
| [tools/breeze-tts2-infer.py](../../tools/breeze-tts2-infer.py) | Breeze TTS 2 local runner，支援 UTF-8 text、reference audio/transcript、voice design，輸出 WAV/manifest。 | CLI/reference contract 同步 `breeze-tts2-run.ps1`、TTS adapters、Breeze docs。 |
| [tools/breeze-tts2-run.ps1](../../tools/breeze-tts2-run.ps1) | WSL wrapper，負責 Breeze path conversion、runtime invocation 與 output 執行。 | runner args/output aliases 同步 `breeze-tts2-infer.py`、failure regression。 |
| [tools/breeze-tts2-webui.py](../../tools/breeze-tts2-webui.py) | project-local UI wrapper，呼叫官方 Breeze runtime 並保留 generation/manifest boundary。 | UI controls 或 generation contract 同步 Breeze infer、app TTS route、verification docs。 |
| [tools/stt-setup.ps1](../../tools/stt-setup.ps1) | 建立 Faster-Whisper STT Python 3.10 WSL environment。 | STT runtime/revision 變更同步 `stt-transcribe.py`、speech reconstruction wrapper/docs。 |
| [tools/stt-transcribe.py](../../tools/stt-transcribe.py) | offline Faster-Whisper draft transcript 與 JSON evidence/hash；正式 clone 前仍需人工核對。 | transcript schema/provider 變更同步 `contracts/schemas/transcript-event.schema.json`、speech reconstruction docs。 |
| [tools/speech-reconstruction-run.ps1](../../tools/speech-reconstruction-run.ps1) | 一鍵 `STT → CosyVoice2/Breeze TTS 2` wrapper；可給 text/reference，輸出 WAV、backend JSON、workflow manifest。 | backend/reference verification policy 同步 adapters、TTS service、Manual TTS docs。 |
| [tools/speech-reconstruction-failure-regression.ps1](../../tools/speech-reconstruction-failure-regression.ps1) | 不啟動模型的 wrapper stale/missing input failure regression。 | wrapper error/cleanup 改動同步 speech reconstruction runner 和 failure manifest helper。 |

### `tools/fixtures/`

`tools/fixtures/` 保存可重現的純文字輸入；它們不是音訊證據，路徑或內容改動要同步各 inference runner 與 voice contract。

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [tools/fixtures/breeze-reference-female-text.txt](../../tools/fixtures/breeze-reference-female-text.txt) | Breeze female reference audio 的人工核對 transcript fixture。 | reference profile 或 transcript 改動同步 `contracts/voices`、Breeze docs/runner。 |
| [tools/fixtures/breeze-reference-male-text.txt](../../tools/fixtures/breeze-reference-male-text.txt) | Breeze male reference audio 的人工核對 transcript fixture。 | 同上。 |
| [tools/fixtures/breeze-target-text.txt](../../tools/fixtures/breeze-target-text.txt) | Breeze target utterance 的 deterministic UTF-8 text input。 | target test case 或 runner 變更同步 Breeze verification。 |
| [tools/fixtures/mandarin-female-reference.txt](../../tools/fixtures/mandarin-female-reference.txt) | 中文女聲樣本的來源原文；聲音逐字對齊仍待人工核對。 | 同步 `reference-mandarin-female.json`、reference register 與 TTS evidence。 |
| [tools/fixtures/cosyvoice/prompt-text.txt](../../tools/fixtures/cosyvoice/prompt-text.txt) | CosyVoice prompt/reference clone 的 prompt text fixture。 | voice profile/reference contract 變更同步 CosyVoice runner/docs。 |
| [tools/fixtures/cosyvoice/reference-female-text.txt](../../tools/fixtures/cosyvoice/reference-female-text.txt) | CosyVoice female reference audio 的 transcript fixture。 | 同步 `contracts/voices/reference-female.json` 與 dataset reference register。 |
| [tools/fixtures/cosyvoice/reference-male-text.txt](../../tools/fixtures/cosyvoice/reference-male-text.txt) | CosyVoice male reference audio 的 transcript fixture。 | 同步 `contracts/voices/reference-male.json` 與 dataset reference register。 |
| [tools/fixtures/cosyvoice/target-text.txt](../../tools/fixtures/cosyvoice/target-text.txt) | CosyVoice deterministic target text input。 | target test case 或 runner 變更同步 CosyVoice verification。 |

### Seed-VC setup、GUI 與 realtime evidence

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [tools/seed-vc-assets.json](../../tools/seed-vc-assets.json) | `realtime-tiny` required asset registry，保存 source/checkpoint revisions、size/hash/status；offline-v1 helper completeness 保持 waiting/out-of-scope。 | 任何 pin/hash/status 變更同步 `seed-vc-assets.ps1`、setup/gui preflight、`docs/reference/seed-vc-assets.md`。 |
| [tools/seed-vc-assets.ps1](../../tools/seed-vc-assets.ps1) | Seed asset manifest reader/path/hash/provenance strict validator。 | registry schema 或 validation policy 同步 assets JSON、setup/regression、readiness docs。 |
| [tools/seed-vc-assets-regression.ps1](../../tools/seed-vc-assets-regression.ps1) | synthetic 18-case manifest/setup/GUI preflight tests；不讀真模型、不啟 GUI/audio、不下載。 | asset/setup/GUI preflight 改動時維持 18 negative cases。 |
| [tools/seed-vc-setup.ps1](../../tools/seed-vc-setup.ps1) | Seed Python/Tcl-Tk/repo/assets/checkpoint setup/preflight，固定 realtime profile gate；不保證 offline helper 完整性。 | setup command、asset gate 或 runtime 變更同步 setup-preflight regression、assets docs。 |
| [tools/seed-vc-setup-preflight-regression.ps1](../../tools/seed-vc-setup-preflight-regression.ps1) | Windows PowerShell parser 與 synthetic setup preflight，確認缺 source/config/checkpoint/Python 在 mutation 前 BLOCKED。 | setup parser/preflight 變更同步 `seed-vc-setup.ps1`。 |
| [tools/seed-vc-run.ps1](../../tools/seed-vc-run.ps1) | Seed offline inference wrapper，保護 stale output、驗證 input/checkpoint/config/env，接受新 WAV 或 hash changed output。 | runner/preflight/output contract 同步 `seed-vc-run-preflight-regression.ps1`、seed-wav-check、Seed docs。 |
| [tools/seed-vc-run-preflight-regression.ps1](../../tools/seed-vc-run-preflight-regression.ps1) | 六種缺項的 offline runner preflight regression，確認舊 PASS 被新 BLOCKED manifest 取代。 | `seed-vc-run.ps1` preflight 變更同步此 regression 和 readiness docs。 |
| [tools/seed-vc-gui-run.ps1](../../tools/seed-vc-gui-run.ps1) | 手動官方 realtime-tiny GUI launcher；固定 FP32/CUDA 0、核對 manifest pin/size/SHA，使用 ignored session overlay，不自動 start stream。 | GUI launch flags、asset gate、overlay path 變更同步 GUI bootstrap/overlay/device tools 和 Seed verification。 |
| [tools/seed-vc-gui-bootstrap.py](../../tools/seed-vc-gui-bootstrap.py) | 在隔離 settings overlay 下啟動 pinned official Seed-VC GUI，保持 upstream 未修改。 | GUI command/config schema 變更同步 gui-run、overlay tools 與 docs。 |
| [tools/seed-vc-gui-overlay.ps1](../../tools/seed-vc-gui-overlay.ps1) | 建立/驗證 canonical session overlay cache junction，拒絕錯誤 target 或非 junction。 | link target policy 變更同步 overlay regression、gui-run。 |
| [tools/seed-vc-gui-overlay-regression.ps1](../../tools/seed-vc-gui-overlay-regression.ps1) | synthetic junction overlay regression，測錯 target/非 junction 且不刪既有內容。 | overlay behavior 變更同步 overlay tool。 |
| [tools/seed-vc-gui-device-selection.ps1](../../tools/seed-vc-gui-device-selection.ps1) | 依 direction/name/host API 解析 input/output endpoint，避免選錯 default device。 | device resolution 欄位同步 device-selection regression、GUI runner 與 user-flow docs。 |
| [tools/seed-vc-gui-device-selection-regression.ps1](../../tools/seed-vc-gui-device-selection-regression.ps1) | fake endpoint fixture，驗證 input/output resolution；不啟 GUI/audio。 | selection policy 變更同步 device-selection tool。 |
| [tools/seed-vc-gui-settings-regression.py](../../tools/seed-vc-gui-settings-regression.py) | fake widget regression，驗證設定套用以及缺 widget 必須回報 WAITING；不啟 Tcl/Tk/audio stream。 | GUI control names/settings 變更同步 gui user-flow/bootstrap。 |
| [tools/seed-vc-gui-userflow-test.py](../../tools/seed-vc-gui-userflow-test.py) | 官方 GUI event path、widget updates、可選 CABLE loopback 與 partial timing evidence；不等同 Light Host full-chain/LIVE。 | user-flow fields、capture flags、evidence schema 變更同步 GUI docs/live gate。 |
| [tools/seed-vc-live-capture.py](../../tools/seed-vc-live-capture.py) | 明確指定 physical mic、backend loopback、terminal loopback capture，輸出 WAV/callback evidence；不改 default device，onset delta 保持 WAITING。 | capture route/metrics 變更同步 PortAudio telemetry、live gate docs、Seed verification。 |
| [tools/seed-vc-realtime-tiny-test.py](../../tools/seed-vc-realtime-tiny-test.py) | 官方 realtime-tiny loader 的 headless GPU streaming benchmark；無 GUI/PortAudio，不能證明 mic E2E。 | benchmark parameters/output schema 同步 Seed assets/readiness docs。 |

### RVC、VCClient 與 streaming backend

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [tools/dataset_audit.py](../../tools/dataset_audit.py) | 掃描 raw WAV metadata、SHA-256、provenance manifest，支援 `--fail-on-invalid` gate。 | manifest 欄位或 audit policy 同步 `dataset/manifests/*`、model/source audit docs。 |
| [tools/fcpe_probe.py](../../tools/fcpe_probe.py) | FCPE synthetic CUDA probe，可選 VCClient API probe，輸出 JSON evidence；不是完整 realtime proof。 | probe parameters/provider fields 同步 RVC verification/wiring docs。 |
| [tools/rvc-fcpe-gpu-infer.py](../../tools/rvc-fcpe-gpu-infer.py) | RVC WebUI pipeline 的 FCPE + CUDA offline role inference，輸出 WAV/manifest。 | model/index/input contract 同步 model register、RVC audit、VCClient docs。 |
| [tools/rvc-model-audit.py](../../tools/rvc-model-audit.py) | 檢查 model register、檔案 integrity、hash/provenance 與 paired `.pth/.index`，未知 metadata 阻擋 ready。 | register欄位/ready semantics 同步 model-register、ready-gate、current inventory。 |
| [tools/rvc-register-model.ps1](../../tools/rvc-register-model.ps1) | 只在完成 verification 後登錄 RVC `.pth/.index`，保存 exact file/hash/provenance。 | registration policy 同步 model audit/register CSV、VCClient register。 |
| [tools/rvc-ready-gate-regression.ps1](../../tools/rvc-ready-gate-regression.ps1) | missing/unknown artifact metadata 的 ready-gate negative/positive fixtures。 | ready gate 或 register status 變更同步 RVC audit/docs。 |
| [tools/rvc-setup.ps1](../../tools/rvc-setup.ps1) | RVC Python 3.10/CUDA setup，不修改模型或 upstream。 | runtime setup 變更同步 Python checks、RVC backend docs。 |
| [tools/voice-backend-check.ps1](../../tools/voice-backend-check.ps1) | read-only 彙整 RVC venv、Seed source/environment/checkpoint、reference voices、CosyVoice/Breeze model/runtime state；檔案或 import 存在不等於端到端品質通過。 | backend/profile 清單或 status boundary 變更同步 `models/backend-register.csv`、各 backend README、`docs/verification/backends/backend-install-test-latest.md`。 |
| [tools/onnx_runtime_probe.py](../../tools/onnx_runtime_probe.py) | 以固定 synthetic feature 實際執行 sample RVC ONNX，記錄 execution provider/output summary。 | provider/output evidence 欄位同步 wiring verification；provider list 不能代替 audio proof。 |
| [tools/vcclient-runtime-repair.ps1](../../tools/vcclient-runtime-repair.ps1) | 修復/下載 VCClient official runtime assets 並 hash，不修改 Git/model registry。 | runtime package/revision 變更同步 `docs/verification/backends/vcclient-packaged-repair-latest.md`、runtime gate。 |
| [tools/vcclient-rvc-register.ps1](../../tools/vcclient-rvc-register.ps1) | 在 VCClient slot register `.pth/.index` 與 chunk upload，不 destructive initialize。 | register API/slot semantics 同步 VCClient probe、model register/docs。 |
| [tools/vcclient-rvc-probe.ps1](../../tools/vcclient-rvc-probe.ps1) | 對既有 VCClient REST endpoint 做 official sample short WAV → RVC chunk probe，不能代替 FCPE+GPU role matrix。 | REST/chunk fields 同步 chunk validation、latency matrix、VCClient docs。 |
| [tools/vcclient-rvc-chunk-validation.ps1](../../tools/vcclient-rvc-chunk-validation.ps1) | 驗證 VCClient response bytes/float32 finite/non-zero/alignment。 | chunk contract 變更同步 validation regression、probe。 |
| [tools/vcclient-rvc-chunk-validation-regression.ps1](../../tools/vcclient-rvc-chunk-validation-regression.ps1) | empty/short/unaligned/zero/finite/non-zero/NaN/Infinity chunk gate negative/positive regression。 | chunk gate policy 變更同步 validation tool 和 latency docs。 |
| [tools/vcclient-rvc-latency-matrix.ps1](../../tools/vcclient-rvc-latency-matrix.ps1) | bounded chunk latency/buffer/invalid/dropout matrix；短測 PASS 後才允許 600 秒 gate。 | thresholds/evidence 欄位同步 VCClient runtime/probe docs、live gate。 |
| [tools/verify_wiring.ps1](../../tools/verify_wiring.ps1) | read-only 檢查 venv、RVC assets/models、Windows endpoints、VCClient localhost、VST、CUDA，分離 file/runtime/device/audio evidence。 | 檢查項目或 flags 變更同步 `docs/verification/audio/wiring-verification-latest.md`、operation guide。 |
| [tools/streaming-backend-download.py](../../tools/streaming-backend-download.py) | 固定 revision 下載 MeanVC2/X-VC public inference assets 並驗必要 hash。 | upstream revision/license/hash 變更同步 `docs/reference/source-audit.md`、backend register。 |
| [tools/streaming-backend-setup.ps1](../../tools/streaming-backend-setup.ps1) | 隔離 MeanVC2/X-VC Python runtime/setup，不修改其他 backend。 | runtime/setup 變更同步 backend README、install/test verification。 |
| [tools/streaming_backend_evidence.py](../../tools/streaming_backend_evidence.py) | 共用 file-driven streaming WAV evidence/hash/metadata helper；不判 LIVE 或人工音質。 | evidence schema 同步 MeanVC2/X-VC runners、backend docs。 |
| [tools/meanvc2-run.py](../../tools/meanvc2-run.py) | 隔離 MeanVC2 upstream runtime 的 file-driven WAV adapter。 | adapter/config/output 變更同步 `backends/meanvc2/README.md`、streaming evidence。 |
| [tools/desktop-vc-smoke.py](../../tools/desktop-vc-smoke.py) | 注入 WAV → resident worker → Post-FX → PortAudio／CABLE 的可重跑 smoke。 | 同步 Desktop VC report；不升格 physical mic 或 LIVE。 |
| [tools/xvc-run.py](../../tools/xvc-run.py) | 隔離 X-VC CUDA inference，複製 config 到 artifact，避免修改 upstream。 | adapter/config/output 變更同步 `backends/xvc/README.md`、streaming evidence。 |

## `docs/`

`docs/` 保存研究架構、操作契約、來源/模型 provenance、verification evidence 與未決策；最新 verification 文件是狀態入口，歷史報告只描述其產生時的邊界。

### 規格、手冊與參考資料

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [docs/README.md](../../docs/README.md) | 按 Agent、開發者、一般使用者任務查找文件，並說明權威順序；不保存操作或測試數字。 | 新增、刪除、分拆文件時更新路由，再同步各入口與本索引。 |
| [docs/specs/architecture.md](../../docs/specs/architecture.md) | 系統研究目標、分層和跨路線不變條件；不保存 runtime 狀態。 | backend、rack 或 evidence boundary 改動同步 `AGENTS.md`、`voice-conversion-architecture.md`、相關 contracts。 |
| [docs/specs/voice-conversion-architecture.md](../../docs/specs/voice-conversion-architecture.md) | Streaming VC 與 Speech Reconstruction 的 adapter 分工、輸入輸出及下游 handoff；不保存當次狀態。 | 新增 backend/profile 時同步 `backends/README.md`、engine manifests、model/backend register。 |
| [docs/specs/app-requirements.md](../../docs/specs/app-requirements.md) | Desktop M0/M1/M2 及 Manual TTS 需求，包含 Mode → Engine → Voice → Devices 統一流程與功能邊界。 | UI/contract/native orchestration 變更同步 `app/src`、`contracts/schemas`、app verification。 |
| [docs/specs/app-architecture.md](../../docs/specs/app-architecture.md) | Desktop React/Tauri/Python orchestration、IPC 與 shell lifecycle 設計；測試命令在 Agent 維護手冊。 | app/native/service protocol 變更同步 `app/src/services/desktop.ts`、Rust commands、`docs/verification/desktop/app-verification-latest.md`。 |
| [docs/guides/user-guide.md](../../docs/guides/user-guide.md) | 人類 backend 路線選擇、共同 preflight／輸入與對應 CLI 文件入口；單一 backend 的細節由其 README 擁有。 | 路線或入口變更同步 README、對應 backend README。 |
| [docs/guides/quick-start.md](../../docs/guides/quick-start.md) | Desktop／Manual TTS 快速上手。 | 使用者流程變更時同步 Desktop 手冊與 UI。 |
| [docs/guides/desktop-user-guide.md](../../docs/guides/desktop-user-guide.md) | Desktop／Manual TTS 詳細操作。 | UI 與 route 變更時同步需求和分項驗證。 |
| [docs/guides/operation-guide.md](../../docs/guides/operation-guide.md) | Backend 後段 Windows audio rack、VCClient、VST、VB-CABLE／Voicemeeter 接線與排錯；不重述訓練。 | device/route 變更同步 `tools/verify_wiring.ps1`、rack evidence、wiring report。 |
| [docs/guides/model-training-guide.md](../../docs/guides/model-training-guide.md) | RVC dataset/training/register workflow、metadata、source/provenance gates。 | dataset/model register 或 RVC workflow 變更同步 `models/*register.csv`、dataset audit、RVC tools。 |
| [docs/specs/live-gate.md](../../docs/specs/live-gate.md) | LIVE/LIVE_CANDIDATE/OFFLINE/WAITING/BLOCKED 的嚴格分類、首包 <=5s、600 秒與 human evidence 要求。 | gate schema/validator 或 evidence 欄位變更同步 `benchmarks/live/live-gate-v1.schema.json`、LIVE tools。 |
| [docs/specs/verification-plan.md](../../docs/specs/verification-plan.md) | P0–P3 evidence levels 與 Definition of Done，區分環境/匯入/訊號/完整 live/人工驗收。 | 新驗收層或 gate 變更同步所有 verification docs、`AGENTS.md`。 |
| [docs/reference/decision-log.md](../../docs/reference/decision-log.md) | backend、runtime、routing 與 architecture choices 的原因、取捨及日期記錄。 | 重大架構或 source decision 先新增決策，再同步 architecture/source audit。 |
| [docs/reference/open-questions.md](../../docs/reference/open-questions.md) | 尚未決定的 backend/license/audio/runtime 問題與待釐清事項。 | 問題結案或狀態變更同步 decision log、相關 verification，不把 open item 改寫成 ready。 |

### Manual TTS、app 與 runtime verification

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [docs/verification/desktop/manual-tts-verification-latest.md](../../docs/verification/desktop/manual-tts-verification-latest.md) | Manual TTS service/queue/generation/playback/transcript 的命令、實際 evidence、限制與剩餘 boundary；TTS UI/native 維護者讀取。 | `services/tts`、Rust speech bridge、`app/src` 或 contract 改動後重跑對應 service/UI/native checks。 |
| [docs/verification/desktop/app-verification-latest.md](../../docs/verification/desktop/app-verification-latest.md) | M0/M1/M2 Desktop baseline、歷史檢核與 caveats；Manual TTS 最新證據另見 dedicated report。 | app launch/IPC/contract 或 UI test 變更同步 app architecture/requirements。 |
| [docs/verification/desktop/realtime-vc-verification-latest.md](../../docs/verification/desktop/realtime-vc-verification-latest.md) | Desktop 四 VC 無聲修復、Post-FX、當輪 streaming/route evidence 與剩餘 physical gate。 | 同步 stream/rvc runtime、manifest、UI、可重跑 smoke。 |
| [docs/verification/desktop/usability-audit-latest.md](../../docs/verification/desktop/usability-audit-latest.md) | Desktop 操作畫面審查、模式差異、未完成／多餘 UI 與修正證據。 | 同步 main/SpeechWorkspace、UI tests、Desktop 手冊；UI PASS 不升格實體音訊。 |
| [docs/verification/desktop/audio-effects-verification-latest.md](../../docs/verification/desktop/audio-effects-verification-latest.md) | 六引擎音效設定、獨立紀錄、TTS 處理與當輪 native／WAV／CABLE 證據。 | 同步 UI/storage、TTS/engine PostFx、schema、tests；實體音訊與 LIVE 另驗。 |
| [docs/verification/desktop/ui-language-verification-latest.md](../../docs/verification/desktop/ui-language-verification-latest.md) | 繁中／英文、語言保存、原生系統匣與雙語 UI 專項證據。 | 同步共用文案、i18n context、原生 command 與 UI tests；不升格音訊。 |
| [docs/verification/desktop/python-ui-verification-latest.md](../../docs/verification/desktop/python-ui-verification-latest.md) | 2026-09-27 Python 3.10 runtime 與已移除 Tk 控制台的歷史驗證；不能作為目前 UI 操作入口。 | runtime 變更看現行 runtime check；Desktop 操作以 user guide 與當輪 app verification 為準。 |
| [docs/status.md](../../docs/status.md) | 本輪 Agent implementation/test status 集中表，標示 PASS/WAITING/PLANNED 邊界；不能取代各 verifier。 | 每輪實作或驗證後同步相關詳細 report，維持狀態詞彙一致。 |
| [docs/archive/local-environment.md](../../docs/archive/local-environment.md) | 歷史本機 runtime/device/environment inventory，並指向現行 Python UI verification。 | 本機環境證據改動同步 current verification，不以歷史 inventory 覆蓋新 artifact。 |
| [docs/reference/parameter-matrix-template.csv](../../docs/reference/parameter-matrix-template.csv) | backend 比較用的 parameter/result template，供 reproducible run 填寫輸入、裝置、route、metrics 與 status。 | 欄位或 backend 增刪同步 benchmark README、quality/live evidence schema。 |

### Backend、模型與來源 verification

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [docs/verification/backends/backend-install-test-latest.md](../../docs/verification/backends/backend-install-test-latest.md) | backend setup、basic audio evidence、舊/新 status boundary 與可重跑命令；不把安裝當 E2E。 | backend/runtime/asset evidence 改動同步 backend README、model register、verification status。 |
| [docs/verification/backends/breeze-tts2-verification-latest.md](../../docs/verification/backends/breeze-tts2-verification-latest.md) | Breeze installation、CUDA/output evidence、license/RTF 與仍 waiting 的限制。 | Breeze tools/model snapshot/reference contract 改動後重跑相應 probes，更新 report。 |
| [docs/verification/backends/cosyvoice-verification-latest.md](../../docs/verification/backends/cosyvoice-verification-latest.md) | CosyVoice2/STT/reference clone/Gradio evidence、frontend CUDA caveats 與限制。 | CosyVoice tools/model/reference/probe 改動同步 report、backend register。 |
| [docs/reference/current-rvc-model-inventory.md](../../docs/reference/current-rvc-model-inventory.md) | 現行 RVC paired model inventory、hash/provenance 與 status caveats。 | model register/audit 或權重/index 替換後重建 inventory，不手寫檔案存在狀態。 |
| [docs/verification/backends/rvc-model-audit-latest.md](../../docs/verification/backends/rvc-model-audit-latest.md) | RVC register/file/hash/provenance audit；unknown metadata 會阻擋 ready。 | `models/model-register.csv`、audit/register tools 或 paired files 改動後重跑。 |
| [docs/reference/seed-vc-assets.md](../../docs/reference/seed-vc-assets.md) | Seed asset manifest 的 source/license/revision/hash policy 與 realtime preflight scope。 | `tools/seed-vc-assets.*`、setup 或 cache revision 改動同步本文件與 readiness report。 |
| [docs/verification/backends/seed-vc-readiness-latest.md](../../docs/verification/backends/seed-vc-readiness-latest.md) | Seed setup/readiness/LIVE boundary、操作步驟與使用者待完成 evidence。 | Seed runtime、GUI、asset 或 physical capture evidence 變更後更新 current report。 |
| [docs/archive/seed-vc-readiness-2026-09-26.md](../../docs/archive/seed-vc-readiness-2026-09-26.md) | 2026-09-26 dated Seed realtime readiness recheck，保留當日 evidence 與 historical context。 | 只在重現該日期 artifact 時修改；目前狀態以 latest report 為準。 |
| [docs/verification/backends/seed-vc-verification-latest.md](../../docs/verification/backends/seed-vc-verification-latest.md) | Seed GUI lifecycle、callback/CABLE partial evidence 與 mic/600s/listening limitations。 | GUI/user-flow/capture/route evidence 變更後重跑對應 checks，再更新最新報告。 |
| [docs/reference/source-audit.md](../../docs/reference/source-audit.md) | upstream source、license、revision、provenance 與採用/隔離決策的 authority。 | 新增或升級 source/backend/model 時先登錄 URL/revision/license，再同步 register/docs。 |
| [docs/reference/voicestudio-comparison.md](../../docs/reference/voicestudio-comparison.md) | VoiceStudio 固定 revision 唯讀比較與可採納工程方法。 | 上游版本或研究結論更新時核對 source；不表示安裝／音訊 PASS。 |
| [docs/archive/streaming-vc-candidate-intake-2026-09-26.md](../../docs/archive/streaming-vc-candidate-intake-2026-09-26.md) | MeanVC2/X-VC dated candidate intake、fixed source/license process 與候選 boundary。 | 僅在該 intake evidence 或 source decision 修訂時更新；current status 仍看 backend-install report。 |

### Audio、VCClient 與 wiring reports

| 檔案 | 用途與主要讀取者 | 修改同步檢核 |
|---|---|---|
| [docs/verification/audio/audio-quality-comparison-latest.md](../../docs/verification/audio/audio-quality-comparison-latest.md) | 歷史四 profile/11 WAV 的 signal-level comparison；不等同 MOS 或 human listening。 | 重新產生 batch evidence 時同步 `tools/audio-quality-batch.py`、quality benchmark，保留 report scope。 |
| [docs/verification/backends/vcclient-packaged-repair-latest.md](../../docs/verification/backends/vcclient-packaged-repair-latest.md) | VCClient packaged runtime repair/register/probe 結果及 blocked/degraded evidence。 | VCClient runtime package/register/probe 改動後重跑 repair/probe，再更新 report。 |
| [docs/specs/vcclient-runtime-gate.md](../../docs/specs/vcclient-runtime-gate.md) | VCClient embedded runtime compatibility、role-model 與 package gate；和 model/audio proof 分開。 | VCClient runtime repair、role model 或 gate policy 變更同步 tools 與 latest report。 |
| [docs/verification/backends/vcclient-rvc-latency-matrix-latest.md](../../docs/verification/backends/vcclient-rvc-latency-matrix-latest.md) | bounded VCClient chunk latency、buffer、invalid/dropout matrix 及 600 秒前置條件。 | latency/chunk validator 或 device route 改動後重跑 bounded matrix。 |
| [docs/verification/backends/vcclient-rvc-probe-latest.md](../../docs/verification/backends/vcclient-rvc-probe-latest.md) | RVC FCPE+CUDA Desktop block／callback 及歷史 offline output matrix；VCClient、physical Mic、LIVE 分開。 | RVC model、runtime、probe 或 output artifact 變更後更新，不能套用成 LIVE。 |
| [docs/archive/wiring-deployment-report.md](../../docs/archive/wiring-deployment-report.md) | 歷史 deployed software/device/route onboarding report，供追溯初始配置。 | 只有部署配置或 onboarding evidence 變更時更新；目前狀態另看 wiring verification。 |
| [docs/verification/audio/wiring-verification-latest.md](../../docs/verification/audio/wiring-verification-latest.md) | 最新 wiring verification，分離 file/runtime/device/service/audio evidence 並標記 PASS/WAITING/BLOCKED。 | `tools/verify_wiring.ps1`、device/route/service 或 probe 改動後重跑並附 artifact。 |
| [docs/archive/project-architecture-review-report-2026-09-27.md](../../docs/archive/project-architecture-review-report-2026-09-27.md) | 2026-09-27 architecture/opening review 的 counted scope、findings 與 remediation context。 | 只修訂該 review 的來源證據或明確後續；current architecture 以 `architecture.md` 為準。 |

## Ignored、generated 與 upstream 資料夾索引

以下路徑只做資料夾層級說明，不納入 Git 檔案逐檔索引；內容可能含模型、音訊、cache、runtime、上游 source 或測試 artifact，不能因未受 Git 管理就刪除：

- `artifacts/`：本機執行、logs、WAV、metrics、manifests、browser/native test evidence 與 TTS SQLite/export 等 generated output；其狀態以各 verification report 和實際 artifact 為準。
- `models/` 內被 ignore 的 checkpoint、weights、`.index`、safetensors、ONNX、tokenizer、Hugging Face cache 與 backend payload：目錄責任見上方 tracked README/register，實際檔案不在逐檔表中。
- `.venv/`、各 backend 專用 Python/WSL runtime、`__pycache__/`：環境與衍生 bytecode；由 runtime check/setup scripts 管理，不是 source contract。
- `upstream/`、`external/`、第三方整合包與下載 cache：依 `docs/reference/source-audit.md` 登記 source URL、revision、license 與本機位置，不直接提交第三方內容。
- `dataset/raw/`、`dataset/reference-voices/`、`dataset/sliced/`、`dataset/augmented/` 內的音檔及 generated batches：依 dataset manifests、source register 和 audit tools 追溯，不以檔案存在取代授權或 audio evidence。
