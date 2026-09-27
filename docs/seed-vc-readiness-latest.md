# AetherTune／Seed-VC 開箱與 LIVE readiness

2026-09-27 最新結果：Seed-VC GUI lifecycle 與設定保存 `PASS`；realtime-tiny GUI callback backend WAV／同步 CABLE loopback `WAITING`。既有四案 settings/callback/loopback PASS 使用 offline-v1，不代表 realtime-tiny。完整 LIVE 仍待另外驗收。

更新日期：2026-09-27（Asia/Taipei）

## 結論

**AetherTune 尚未達成一般使用者可直接照做、且已證明 LIVE 的整體狀態。** Seed-VC 是目前已建立的 Streaming VC baseline；離線轉換、headless GPU block 有既有 PASS 證據。四案 GUI 設定/callback 與 synthetic cable loopback PASS 來自固定 offline-v1 checkpoint/config 的 harness，不是 realtime-tiny 推論或真實麥克風到最終通訊端的完整鏈路。

Seed-VC setup、一般使用者 GUI launcher 與 evidence validator 已有可重現操作路徑；目前 manifest-enabled gate 僅支援 `realtime-tiny`，offline-v1 helper completeness（含 Whisper/BigVGAN）仍 `WAITING / out-of-scope`。最新的 2026-09-27 一般 Windows user session／approved non-sandbox shell 中，manifest-enabled setup 與 GUI preflight 均 `PASS`：setup 核對 Python 3.10.11 x64、Tcl/Tk 8.6.12、`missing=[]`；GUI 核對 CUDA `true`、RTX 5060 Ti、realtime checkpoint SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`、VAD SHA-256 `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5` 與 `missing=[]`。明確 Windows DirectSound 配對為 `麥克風 (HyperX QuadCast S)` index 26 → `CABLE Input (VB-Audio Virtual Cable)` index 40。Computer Use 另開啟官方 GUI 並目視確認 reference、裝置及參數顯示；未按 `Start Voice Conversion`，沒有執行音訊串流。這些結果只代表目前修復主機的啟動前檢查與 GUI 顯示通過，不證明 clean-machine bootstrap 或真實麥克風 E2E；2026-09-26 的一般 Windows host PASS 保留為歷史證據。
Seed-VC setup、一般使用者 GUI launcher 與 evidence validator 已有可重現操作路徑；目前 manifest-enabled gate 僅支援 `realtime-tiny`，offline-v1 helper completeness（含 Whisper/BigVGAN）仍 `WAITING / out-of-scope`。2026-09-27 一般 Windows user session 的 manifest-enabled setup／GUI preflight 均 `PASS`：setup 核對 Python 3.10.11 x64、Tcl/Tk 8.6.12、`missing=[]`；GUI 核對 CUDA `true`、RTX 5060 Ti、realtime checkpoint SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`、VAD SHA-256 `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5` 與 `missing=[]`。明確 Windows DirectSound 配對為 `麥克風 (HyperX QuadCast S)` index 26 → `CABLE Input (VB-Audio Virtual Cable)` index 40。Computer Use 先目視確認啟動前設定，之後受控 GUI run 完成 Start → Stop → Start → Stop；stream log 停止增長且 launcher 關閉，保存的 reference 在同 SessionRoot 重啟後成功載入。新 realtime-tiny synthetic callback 的設定套用 `PASS`，但 backend WAV／該次 CABLE loopback 為 `WAITING`；獨立 synthetic VB-CABLE smoke `PASS` 只證明線路。這些結果不證明 clean-machine bootstrap 或真實麥克風 E2E。2026-09-26 的一般 Windows host PASS 保留為歷史證據。

Python 3.10.11 的 Tk 問題根因是 `tcl\tk8.6\pkgIndex.tcl` 以相對路徑載入 `..\..\bin\tk86t.dll`，但官方 Python 安裝中的 DLL 位於 `DLLs\tk86t.dll`；Tcl/Tk scripts (`init.tcl`、`tk.tcl`) 本身存在。官方 Tcl/Tk MSI repair exit `0`（repair log SHA-256 `364414613B6E315AFEF0349FC3E1A56B6C421F6CD31B74EE58E53F50D6F2A3BE`）後，主控依既有安裝授權建立 per-user `Python310\bin` junction 指向 `DLLs`，未覆寫既有路徑或修改 DLL。受限 Codex sandbox 的 Tcl `init.tcl` lookup failure 是獨立的 sandbox-only `WAITING`，不覆蓋上述正常 host-session PASS，也不代表主機 runtime 失敗。

新機的最小官方修復順序是以 Python 官方 installer Repair/Modify 確認 Tcl/Tk Support 已安裝，再於一般 Windows user session 驗證 `tkinter.Tcl()` 與 `package require Tk`，最後重跑 setup/GUI preflight。若官方安裝的 `pkgIndex.tcl` 與 DLL 位置仍不一致，採用使用者擁有的獨立 Python 3.10 install location 重裝並重驗；只有在 per-user `bin` 路徑不存在且有安裝授權時，才考慮建立指向現有 `DLLs` 的 junction。不得覆寫既有路徑、複製／改名 DLL 或修改第三方 Tcl/Tk scripts。這些步驟尚未在乾淨新機執行，因此 bootstrap 維持 `WAITING`。

## 分類摘要

2026-09-27 MME + HyperX 有界診斷在 stream start 前 `BLOCKED`：MME output 清單找不到指定 CABLE endpoint，因此沒有 callback、backend WAV 或 loopback metrics。紀錄與 SHA-256 見 [`seed-vc-verification-latest.md`](seed-vc-verification-latest.md)。

| 狀態 | 項目 | 證據與限制 |
|---|---|---|
| `PASS` | 2026-09-27 Phase 1 import isolation／reference preflight regression（approved Windows host） | `pwsh -NoProfile -File .\tools\seed-vc-assets-regression.ps1 -PythonRuntime D:\AetherTune\tools\venvs\seed-vc\Scripts\python.exe`：exit `0`。實際 CPython 3.10.11 foreign-CWD fixture 重現 `tkinter.py`／`torch.py` shadow；無隔離時 sentinel 被載入，`-I -B` 使用正式 Tcl/Tk／Torch。setup 真 Python preflight 與 synthetic GUI bootstrap 從 foreign CWD 通過；bootstrap 只從明確加入的 fixture upstream repo 匯入。Saved reference 缺檔、相對路徑、CLI override、clear、CLI 與 clear 同時指定、drive-relative、錯誤型別、malformed JSON 均按規則 PASS/BLOCKED；preflight 未建立 overlay，fake normal bootstrap 將相對 saved reference 保存為絕對路徑。沒有載入 checkpoint、啟動 GUI 或 audio stream。 |
| `PASS` | 2026-09-27 Phase 1 修正後 GUI host preflight | 使用 D: Seed-VC 3.10.11 runtime/source/checkpoint/config、ModelScope cache、worktree manifest 與新的 TEMP SessionRoot，明確指定 DirectSound、HyperX mic、VB-CABLE output。`-I -B` 下 exit `0`，CUDA 可用、RTX 5060 Ti、兩 endpoint 唯一解析、checkpoint/VAD SHA-256 通過、`missing=[]`；只做 preflight，沒有 GUI 視窗或 audio stream。 |
| `PASS` | Seed-VC upstream baseline | 固定 source revision `51383efd921027683c89e5348211d93ff12ac2a8`；離線雙向轉換、長音檔與 headless GPU block 有既有本機證據。僅代表該項離線／headless 範圍。 |
| `PASS` | 2026-09-26 offline-v1 GUI 設定與 synthetic loopback（歷史證據） | 四個 reference case 各 17/17 GUI 欄位套用；backend／VB-CABLE synthetic route 有非零音檔。原始報告 `artifacts/seed-vc/gui-userflow/20260926-after-tcl-repair/gui-userflow-report.json` SHA-256 `1EB604F1A778FCEEFE73AB2D341A82DA274F08D31FF8342280DCA80FD963262E`。這是 WAV callback 注入，不是真人聲或真實麥克風，也不代表 realtime-tiny GUI output。 |
| `PASS` | GUI 啟動架構 | launcher 將官方 GUI 放在 `artifacts/seed-vc/gui-session/` runtime overlay，配置其所需 `configs/hifigan.yml` 與 `configs/inuse/config.json`；model cache junction 指向經 manifest 固定 snapshot revision、size、SHA-256 驗證的本機 HF snapshots；VAD 由 bootstrap 在程序內映射至通過本機 hash 檢查的 ModelScope cache，並停用隱式更新。不寫第三方 source、原 cache 或 user profile。該 gate 僅涵蓋 realtime-tiny GUI；offline-v1 helper completeness（含 Whisper/BigVGAN）維持 `WAITING / out-of-scope`。資產 gate PASS 不證明未知的 VAD 上游授權或 clean-machine bootstrap。 |
| `PASS` | manifest realtime 資產 integrity contract | `tools/seed-vc-assets.json` 分別記錄 official Seed-VC code revision、兩個 profile 的 official model-repo revision/LFS metadata（但執行 gate 只要求 realtime-tiny checkpoint）、三個 realtime GUI 所需 HF 本機 snapshot revisions 與 observed size/hash、四個 VAD 檔案 observed size/hash。18 個隔離負測與 offline-v1 checkpoint/preset 缺席的成功 realtime-only smoke 均通過；此 PASS 只代表 realtime gate 與 manifest 登記 bytes 相符，不代表 offline-v1 helper 完整。 |
| `PASS` | 2026-09-26 歷史 manifest-enabled host preflight | setup 與 GUI preflight 曾在正常 Windows user session 通過；保留為歷史 PASS。本日 2026-09-27 的最新 approved non-sandbox 結果見下列新證據。 |
| `PASS` | 2026-09-27 manifest-enabled setup preflight（approved non-sandbox Windows session） | `& .\tools\seed-vc-setup.ps1 -PreflightOnly`：exit `0`；JSON `status=PASS`、`profile_scope=realtime-tiny`、`offline_v1_helper_completeness=WAITING`、`asset_manifest_clean_machine_status=WAITING`；Python 3.10.11、64-bit；Tcl 8.6.12、Tk `available`；`missing=[]`、`would_download_models=false`。這是目前主機 realtime preflight，不代表 clean-machine bootstrap 或 offline helper 完整。 |
| `PASS` | 2026-09-27 manifest-enabled GUI preflight（approved non-sandbox Windows session） | `pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly`：exit `0`；JSON `status=PASS`、`profile_scope=realtime-tiny`；runtime Python 3.10.11、`cuda_available=true`、GPU NVIDIA GeForce RTX 5060 Ti；Host APIs MME／Windows DirectSound／Windows WASAPI／Windows WDM-KS；selected input DirectSound index 26 `麥克風 (HyperX QuadCast S)`、selected output DirectSound index 40 `CABLE Input (VB-Audio Virtual Cable)`；checkpoint SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`；VAD SHA-256 `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5`；`missing=[]`。 |
| `PASS` | 2026-09-27 GUI 視窗與設定目視核對（Computer Use） | 1110×660 截圖：`artifacts/seed-vc/gui-userflow/20260927-manifest-host-ui/seed-vc-gui.png`（ignored 本機 artifact；SHA-256 `E3FF99E1EC0E935B29C14D0D55DBCC86BC4A2C66B8ECF36C41493DB5EE182AED`）。Reference loaded；DirectSound、HyperX QuadCast S mic、VB-Audio CABLE output、MME／DirectSound／WASAPI／WDM-KS dropdown、參數與按鈕均可見。未按 `Start Voice Conversion`、未執行音訊串流；以 Escape 關閉 dropdown、Alt+F4 關閉視窗，之後確認視窗已關閉。這不證明 callback、實體 mic E2E、rack 或 LIVE PASS。 |
| `PASS` | 2026-09-27 realtime-tiny GUI lifecycle 與設定保存 | 一般 Windows session 中手動完成 Start → Stop → Start → Stop；CUDA stream log 有持續更新，Stop 後停止增長，Alt+F4 關閉後 launcher 結束。以相同 SessionRoot 不帶 reference override 重啟 preflight，`reference_source=saved`、effective reference 為 `voice-male-m1.wav`、`missing=[]`。證據 stdout SHA-256：`B770F4EF2AC1B3E661131099F66BDB5B43BF4CAE774BFE803FCA695A182F23A6` 與 `4EC50FB849DFE649E46C2AE44EC81B499F50E12971D01593481FD5E6910D4917`。來源與 output 均是本機 VB-CABLE endpoints，沒有實體 mic sample。 |
| `WAITING` | 2026-09-27 realtime-tiny GUI callback audio output | 官方 GUI event path 的 17/17 欄位套用與 CUDA RTX 5060 Ti runtime `PASS`；但原始與 gain-staged deterministic callback 兩次 backend output 都未達 finite/non-zero gate，回錄的 `CABLE Output` 也全零。報告路徑為 `artifacts/seed-vc/gui-userflow/20260927-phase2-0ad07c8e/realtime-tiny-callback/gui-userflow-report.json` 與 `.../realtime-tiny-callback-normalized/gui-userflow-report.json`；SHA-256：`0E8B6CD51C304C5D26F8D2D7DD4414DB3E41B37CDCDCD9220D1F0568E198A964`、`628FB08C0C9391CF34DA0DE487EFAEBDE21CFEDD9E94BFBC88C02189041EBD04`。這是新的 GUI audio-path 缺口，不能由 CUDA inference log 覆蓋。 |
| `PASS` | 2026-09-27 獨立 synthetic VB-CABLE smoke | WASAPI `CABLE Input → CABLE Output` 3 秒成功擷取 144000/144000 frames，RMS `0.082621`；只證明兩個 endpoint 可傳音，不證明 GUI backend output。report SHA-256 `5E875CE172ABDA11EFCB7E93B47D6F2681AE71347EABE8C1C31557073B73E1A9`。 |
| `WAITING` | 受限 Codex sandbox setup/GUI preflight | 同兩個 preflight 命令在受限 Codex sandbox 各 exit `1`、JSON `status=BLOCKED`，`missing` 原因為 Tcl `init.tcl` lookup failure。這是 sandbox-only WAITING；不能覆蓋上述 approved normal-session PASS，也不表示主機 runtime 失敗。 |
| `PASS` | 明確 Windows DirectSound 裝置配對 preflight | 選擇 `麥克風 (HyperX QuadCast S)` index `26` → `CABLE Input (VB-Audio Virtual Cable)` index `40`；唯讀 preflight 本身未啟動 GUI 視窗或 audio stream。 |
| `WAITING` | offline-v1 helper completeness | 本輪 setup/GUI gate 明確只涵蓋 `realtime-tiny`。offline-v1 的 Whisper/BigVGAN checkpoint、preset 與 helper dependencies 不在此 manifest gate 範圍；先前離線推論 evidence 保留為既有結果，但不作為本輪 clean-machine/offline bootstrap PASS。 |
| `WAITING` | 新機／新使用者 clean-machine bootstrap | 目前主機依賴本機 per-user Python310 junction；該修復不隨 repository 移植。尚未在乾淨新機驗證 Python/Tcl/Tk、source 與 realtime assets 的完整取得及 GUI preflight，不可將本機 PASS 推廣為 bootstrap PASS。 |
| `WAITING` | realtime-tiny GUI backend output 與真實 mic → Seed-VC → audio-rack → virtual route／B1 | GUI lifecycle 已測，但新的 deterministic callback 未產生可驗證非零 output；完整鏈路 `e2e_first_packet_ms <= 5000` 也尚未實測。LIVE 另需 physical mic artifact、run/model/device/route/hardware identity、600 秒零 dropout／underrun 與人工聽評；headless／synthetic route PASS 不能補此缺口。 |
| `WAITING` | 600 秒穩定性與人工聽評 | 尚未完成真實麥克風 600 秒零 dropout／underrun 測試及使用者人工聽評。 |
| `WAITING` | Light Host／VST bypass 與 full-chain paired A/B | 已有 preset/profile 與 evidence schema；實體 plugin chain 尚無同 source、同 model、同 route、同硬體的成對音檔與實測 delta latency。 |
| `PASS` | MeanVC2、X-VC 安裝與基本音訊 | 已下載固定 code/model revision、建立隔離 venv，雙向 CUDA file-driven WAV 與必要權重 hash `PASS`；完整 mic／rack／LIVE 仍 `WAITING`。 |
| `PLANNED` | Seed-VC realtime fork、CosyVoice3 | 保持隔離 intake 候選；尚未安裝／驗證。 |
| `PLANNED` | 固定 special-speech corpus、acoustic comparison 與盲聽 | 尚未建立經授權且固定 hash 的 corpus 或人工評分；不得以測試訊號推估 MOS、音色相似或自然度。 |

## 本輪 launcher 修正與驗證

2026-09-27 Phase 1 恢復 project-root path resolver，讓 setup／GUI 從 foreign CWD 啟動仍以專案根目錄解析相對參數，且 preflight 保留呼叫者 CWD。Python launcher、Tcl/Tk probe、GUI runtime/device probe 與 bootstrap 都使用 isolated import mode (`-I -B`)；bootstrap 將 manifest 核對過的 Seed-VC upstream repo 明確插入 import path，不依賴呼叫者 CWD 或 `PYTHONPATH`。

GUI preflight 在輸出結果前讀取設定、解析並驗證 effective reference。優先序是 CLI `-ReferenceWav` → `-ClearReference` → saved reference；`requested_reference` 保留呼叫者輸入，`effective_reference` 記錄最終絕對路徑。遺失檔案、drive-relative 路徑、非字串設定或 malformed config 會在建立 cache junction、session overlay 或改變 process environment 前回報 `BLOCKED`；CLI override 與 clear 都可處理失效的 saved reference。

完整回歸命令（從 repository root 執行）：`pwsh -NoProfile -File ./tools/seed-vc-assets-regression.ps1 -PythonRuntime D:\AetherTune\tools\venvs\seed-vc\Scripts\python.exe`。它會用真實 CPython 3.10.11 驗證 `torch.py`／`tkinter.py` CWD shadow 控制組、Tcl/Tk setup probe、setup preflight 與 isolated GUI bootstrap；另測 foreign-CWD path resolver、reference 優先序與 preflight 零 overlay mutation。Model/audio inference、GUI 視窗與 stream 不在這個回歸範圍。

## 使用者操作流程

先做唯讀 preflight；通過後才在已核對的 Windows 音訊工作階段啟動 GUI：

```powershell
Set-Location D:\AetherTune
& .\tools\seed-vc-setup.ps1 -PreflightOnly
pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly
pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 `
  -InputDeviceName '麥克風 (HyperX QuadCast S)' `
  -OutputDeviceName 'CABLE Input (VB-Audio Virtual Cable)' `
  -HostApi 'Windows DirectSound' `
  -ReferenceWav .\dataset\reference-voices\voice-female-f1.wav
```

範例兩個名稱均是本機 PortAudio inventory 的完整字串；`Windows DirectSound` 下 input/output 各唯一匹配 1 個 endpoint。其他電腦必須改成當機 preflight 列出的名稱與 Host API。

GUI launcher 與 junction overlay 需 PowerShell 7.2 以上（`pwsh`，依賴 .NET 6 `ResolveLinkTarget`）。若 setup 找不到 Python 3.10 base interpreter，只對 `seed-vc-setup.ps1` 指定 `-Python310 <base-python.exe>`；GUI launcher 預設使用 setup 建立且含 GUI dependencies 的 `tools\venvs\seed-vc\Scripts\python.exe`。若使用自訂 venv，才傳 `-Python <venv\Scripts\python.exe>` 給 GUI launcher。兩個 preflight 都讀取 [`tools/seed-vc-assets.json`](../tools/seed-vc-assets.json)，核對 source revision、realtime-tiny checkpoint 的官方固定 size/SHA-256、HF 本機 `refs/main` revision 與 realtime GUI 所需檔案 hash、ModelScope VAD 本機 observed hash，再檢查 Python 3.10 x64/Tcl/Tk、GUI dependency 與 CUDA 0。任何 realtime 必需項目缺失都在 pip、GUI、cache overlay 或 audio stream 前停止；流程不 clone source、不下載模型、不更改 Windows default device。manifest 明確將 code revision 與 model repo revision 分開；HF 依賴的 revision/hash 是本機觀測值，FSMN-VAD 上游完整 revision/license 仍 `UNKNOWN/WAITING`，因此這些檢查不能升格成 clean-machine bootstrap `PASS`。offline-v1 helper completeness（含 Whisper/BigVGAN）明確為 `WAITING / out-of-scope`。

要在不讀真實模型或安裝套件的情況下回歸 setup 對空檔與缺項的阻擋行為，可執行 `pwsh -NoProfile -File .\tools\seed-vc-setup-preflight-regression.ps1`。Manifest 資產 gate 的缺檔、錯 code/model revision、錯 HF snapshot、同大小錯 hash、損壞 JSON、不合法 provenance，以及遺漏 `requirements.txt`／XLS-R `preprocessor_config.json` 測試則執行 `pwsh -NoProfile -File .\tools\seed-vc-assets-regression.ps1`；兩者都只驗 preflight contract，不代表 clean-machine bootstrap runtime `PASS`。

GUI 開啟後，使用者先目視核對 reference、input/output endpoint、Host API 與 CUDA device，再由使用者按 `Start VC`。結束時按 `Stop VC` 並關閉視窗。若改用其他 output endpoint，需據實更新下游路由記錄。日常 launcher 不注入 WAV；`seed-vc-gui-userflow-test.py` 仍是隔離的 deterministic callback 測試 harness。

### 真實麥克風驗收步驟（目前 `WAITING`）

1. 選定有使用權的乾淨 reference；保存其來源、license/use scope 與 SHA-256。指定唯一 microphone／output endpoint 和 Host API，不改 Windows default devices。
2. 依 [`docs/operation-guide.md`](operation-guide.md) 接 Seed-VC → audio-rack → virtual route → Voicemeeter B1 或實際通訊應用的錄音端。確認沒有 loopback feedback，開始前檢查各裝置 meter。
3. 以全新 `run_id` 保存 microphone capture 與最終 route loopback WAV；對輸入、輸出及 metrics 計算 SHA-256。記錄模型 id/revision/checkpoint hash、GPU/device、driver、sample rate/channels、route identity、callback continuity、每段 first-packet timing、dropout／underrun。Validator 必須看到本次 run 產生的檔案，不接受輸出資料夾的舊 WAV。
4. 先做短時 smoke，再做完整 600 秒連續測試。不要把 warm-up 前的 cold latency 和穩態 warm latency 合併平均。既有測量約 cold output `14.96 s`、warm `1.95–2.39 s`；它們不是本輪重新測量，也不是完整 mic → rack → route E2E。cold 首包已高於 5 秒 hard cap；warm 數字只有在完整真實鏈路重測後才可比較。
5. 由使用者人工聽 source/reference/bypass/full-chain 的盲化配對輸出，記錄自然度、目標音色相似度、原始表演保留、內容正確性、噪音／破音與接受度；填寫 reviewer id/date 和 output hashes。Agent 不代填主觀分數。
6. 執行 `tools/live-gate-validate.py <evidence.json>`。在真實 mic artifact、完整鏈路 timing、600 秒零失敗與人工聽評都齊全前，結果維持 `WAITING` 或 `LIVE_CANDIDATE`；不得以 GUI widget、callback、合成音、model load 或設備存在改成 `LIVE`。

## 分層架構與研究範圍

研究目標是 Windows、本地 RTX 5060 Ti 16 GB，品質排序固定為 **自然度 → 目標音色相似度 → 原始表演／情緒保留**。完整 capture → backend → 共用 audio-rack → virtual route 的首個有效封包 `<= 5,000 ms` 是 `LIVE` 硬門檻；此門檻只分類延遲，並不代表音質合格。Streaming VC 與 Speech Reconstruction 分組比較，但共用 source/reference、audio-rack、routing 與 benchmark 契約。

| 路線 | 現況／優先順序 | Intake／驗收邊界 |
|---|---|---|
| RVC + FCPE/RMVPE | `historical-baseline / degraded` | 已保留舊專案及離線 evidence；VCClient 即時證據仍 `BLOCKED/DEGRADED`。不回寫成一般 ready 路線。 |
| Seed-VC upstream | `established-baseline` | 固定 revision；既有離線/headless 範圍 PASS；四案 GUI settings/callback harness 固定 offline-v1 checkpoint/config，不能作為 realtime-tiny 推論 evidence；完整 mic LIVE WAITING。 |
| Seed-VC realtime fork | `candidate / PLANNED`，獨立執行路徑 | 需分開核對 fork/source/revision/license/dependencies、worker/device/VAD，再和 baseline 以同 corpus 實測。 |
| MeanVC2 | `installed / candidate`，基本音訊 `PASS` | 40ms／120ms 模型、固定 code/HF revision、雙向 CUDA file-driven WAV 已完成；mic／rack／LIVE 仍 `WAITING`。 |
| X-VC | `installed / candidate`，基本音訊 `PASS` | 主模型、GLM tokenizer、ERes2Net 已下載並核對 hash；雙向 CUDA file-driven streaming WAV `PASS`；mic／rack／LIVE `WAITING`。新 streaming 方法另行 intake。 |
| RT-VC | `paper candidate / PLANNED` | 保留原研究追蹤；目前未核實可執行上游 source、固定 revision、權重或 Windows intake 條件，不寫成可安裝 backend。 |
| CosyVoice2 | `offline reconstruction baseline` | TTS/reconstruction 產生新聲學表演；不能描述為保留 source performance。現有 WSL2 runtime evidence 不構成 LIVE。 |
| CosyVoice3 | `candidate / PLANNED` | 先核對官方 source、model license、依賴與隔離測試；不與 CosyVoice2 資產或結論混用。 |
| Breeze TTS2 | `offline candidate` | Voice Design／reference clone 是 speech reconstruction；本機 RTF/runtime 不構成 mic LIVE 或原始表演保留。模型與衍生輸出依 research/non-commercial 條款審核。 |

所有候選透過同一套 cross-backend audio-rack profile，不把 rack 當第五個 backend。實體 preset 必須分別實測 `bypass` 與 `full-chain`，固定同 source/reference/model/hardware/route，並保存兩組實際輸出與 `delta_latency_ms = full-chain e2e - bypass e2e`。新增的 rack evidence `PASS` 只代表成對技術測量檔通過結構、hash、訊號與 identity 驗證，永不等同 LIVE。

## 三層驗收與 corpus

1. **Technical**：實際 file decode、finite/non-zero、sample rate/channel、source/output/metrics SHA-256、model/revision、GPU/provider、input/output endpoint、route、first-packet p50/p95、continuity/dropout/underrun、bypass/full-chain delta。
2. **Acoustic objective**：固定 source/reference 與輸出對，檢查內容正確性 proxy、響度、RMS/peak、clipping、silence、DC、SNR/noise 等可量指標。結果不能推導自然度或 MOS。
3. **Human listening**：盲化並以隨機播放順序，由真人按自然度、目標音色相似、原始表演保留、內容正確、噪音/破音與可接受度評分；保留匿名化 reviewer、規則、run/output hashes 與分歧紀錄。

固定 special-speech corpus 尚未建立。建立時需至少由合法來源涵蓋一般敘述、塞音/擦音/齒音、音域與音量變化、語速及停頓、疑問/強調/情緒語調、非語音呼吸或笑聲等；逐 clip 記錄 speaker consent、source provenance、license/use scope、transcript 狀態、sample rate、duration、hash 與 train/test split。當前狀態一律 `UNKNOWN / WAITING`，不得從現有 reference samples 假定用途授權或填入人工成績。

## 來源與授權分類

每個元件分別登錄程式碼、model weights、dataset/reference speaker、輸出聲音、VST/virtual routing 的來源與使用範圍。至少區分 `OPEN_SOURCE`、`OPEN_WEIGHT`、`RESEARCH_NON_COMMERCIAL`、`THIRD_PARTY_FREE/CLOSED`、`PROPRIETARY`、`UNKNOWN`；模型程式 license 不會自動授予權重、reference voice 或生成結果的商用權。Unknown license 不得升級為可商用或已獲聲音本人授權。

## 本輪可重跑驗證與 evidence 限制

Realtime-only 正向 fixture 刻意不提供 offline-v1 checkpoint/preset 與 `inference.py`；這些離線檔案不是 GUI setup gate 的必要項目。

本輪將下列工具視為 contract regression，不啟動模型或真實 audio device：

| 命令 | 本輪結果 | 分類意義 |
|---|---|---|
| `& .\.venv\Scripts\python.exe .\tools\live-gate-regression.py` | exit `0`; regression `PASS` | 外層 capture sample-rate/channel 改值、外層 `dropouts=false`、metrics-only WAV metadata `channels=true`、WAV header 改變並重算 file hash，以及既有 timing/continuity/human identity/hash/ratings mismatch 均=`BLOCKED`；缺人評仍 `CANDIDATE`，synthetic source=`WAITING`；首包 >5s=`OFFLINE`。 |
| `& .\.venv\Scripts\python.exe .\tools\audio-rack-evidence-regression.py` | exit `0`; regression `PASS` | paired fixture 僅能 rack `PASS`；source type/header mismatch、outer `dropouts=false`、metrics-only WAV metadata `channels=true`、重算 WAV hash 的 header 變更，以及 timing/continuity/paired identity/delta mismatch 均=`BLOCKED`；unpaired=`WAITING`；>5s=`OFFLINE`；synthetic fixture 交給 LIVE gate 仍 `WAITING`。 |
| `& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-gui-settings-regression.py` | exit `0`; 2 tests `PASS` | GUI setting/callback semantics，不是真實 mic。 |
| `& .\.venv\Scripts\python.exe .\tools\audio-output-validation-regression.py` | exit `0`; `PASS` | WAV 結構/訊號 gate，不是聲學或主觀驗收。 |
| Python AST + 2 JSON Schema Draft 2020-12 | exit `0`; `PASS` | 對 live/rack validators、regressions、GUI bootstrap 做 AST parse；檢查兩個 schema 並驗證 live/rack fixture；不代表硬體 E2E。 |
| PowerShell 7 AST parser：GUI launcher/device-selection helper+regression/overlay helper+regression、offline runner/preflight regression、setup/preflight regression | exit `0`; 九檔 `PARSE_PASS` | GUI launcher、overlay helper/regression 與 asset regression 要求 `pwsh` 7.2+（.NET 6 API）；setup 腳本仍可由 Windows PowerShell 5.1 解析與執行。語法檢查不是 GUI/device/runtime E2E；setup parser PASS 不等於新機安裝或 Tcl/Tk runtime PASS。 |
| `pwsh -NoProfile -File .\tools\seed-vc-gui-device-selection-regression.ps1` | exit `0`; `PASS` | 四種 Host API 有同名 input；首次 CLI 選 MME 後，第二次省略 CLI 仍採 saved MME；CLI DirectSound 可覆蓋；失效 saved API=`BLOCKED` 並提示 `-HostApi`；另核對 unique/default inference。僅隔離 inventory/settings fixture，不啟動 GUI 或 audio stream。 |
| `pwsh -NoProfile -File .\tools\seed-vc-gui-overlay-regression.ps1` | exit `0`; `PASS` | 在 `$env:TEMP` 唯一 fixture 上連續執行兩次：第一次建立且實際 ResolveLinkTarget；第二次辨識正確既有 junction；錯誤 target 被拒絕，fixture marker 存在且無任何資料刪除。 |
| `pwsh -NoProfile -File .\tools\seed-vc-setup-preflight-regression.ps1` | exit `0`; `PASS` | 先由 Windows PowerShell 5.1 parser 檢查完整 setup 腳本並載入 manifest；一般 setup invocation 使用 Python/Tcl/Tk shim、不帶 `-PreflightOnly`；fixture 中空 Hifi-GAN config 與目錄型 realtime checkpoint 精確 `BLOCKED`，刻意缺席的 offline-v1 checkpoint/preset/`inference.py` 不增加 finding；另一次 invocation 驗證缺少 Python。synthetic HF/VAD fixture 也不符 manifest pin。未建立 venv／進入 pip mutation，不讀真實模型／不下載資產。 |
| `pwsh -NoProfile -File ./tools/seed-vc-assets-regression.ps1 -PythonRuntime D:\AetherTune\tools\venvs\seed-vc\Scripts\python.exe` | exit `0`; `PASS`（2026-09-27 approved Windows host） | 18 個既有 manifest 負測、foreign-CWD project-root path／CWD-preservation、resolver 的 drive／UNC／volume-root boundary 均通過。實際 Seed-VC CPython 3.10.11 對 `tkinter.py` 與 `torch.py` sentinel 完成未隔離失敗／`-I -B` 通過對照；真 Tcl/Tk setup probe 與 setup preflight 通過；fake GUI bootstrap 驗證 isolated import 由明確 upstream repo 提供。7 種 saved／CLI／clear／path／type reference case 加 malformed JSON 均按預期 BLOCKED 或 PASS；失敗 preflight 沒建立 overlay，valid relative saved reference 在 fake normal launch 後保存為絕對路徑。沒有載入模型或開啟 GUI/audio。 |
| `pwsh -NoProfile -File .\tools\seed-vc-run-preflight-regression.ps1` | exit `0`; `PASS` | 6 種 source/target/repo/checkpoint/config/Python 缺項均將預置舊 PASS manifest 覆寫成新 run_id、`BLOCKED`。腳本另檢查 offline output validator 使用 `$resolvedPython`（Seed-VC venv），非根 `.venv`；未執行模型推論。 |
| Seed-VC venv PortAudio inventory 唯一性 probe | exit `0`; input/output 各 `1` 筆 | `Windows DirectSound` + `麥克風 (HyperX QuadCast S)` input，及 `Windows DirectSound` + `CABLE Input (VB-Audio Virtual Cable)` output；這不是 MME 字串（MME 列舉會截斷名稱），因此範例明確指定 DirectSound。 |
| `tools/seed-vc-run.ps1` stale-output guard | PowerShell AST + preflight regression `PASS`; 不重跑模型 | 新 run manifest 在任何輸入／checkpoint precondition 前落為非 PASS；成功推論後比較 WAV path/hash snapshot；只驗本次新增或改變的 WAV。模型 inference 未重跑，不宣稱本輪 offline runtime PASS。 |
| 本機官方 Python 3.10.11 Tcl/Tk repair + per-user junction | MSI exit `0`; Tcl/Tk runtime `PASS` | `pkgIndex.tcl` 預期 `Python310\bin\tk86t.dll`，實檔位於 `Python310\DLLs`；repair log 顯示 Tcl/Tk Support configuration completed。主控在目標原本不存在時建立 `bin` junction 指向 `DLLs`，沒有改 DLL。這是已修復主機狀態，不是新機安裝證據。 |
| Host manifest-enabled setup／GUI／DirectSound preflights（2026-09-26，一般 Windows session；歷史證據） | exit `0`; 三項 `PASS` | setup：Python 3.10.11 x64、Tcl/Tk 8.6.12、`missing=[]`。GUI：CUDA `true`、RTX 5060 Ti、checkpoint SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`、VAD SHA-256 `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5`、`missing=[]`。明確 DirectSound 配對為 HyperX QuadCast S index 26 → CABLE Input index 40。當時未開 GUI 或 audio stream；乾淨機器 bootstrap 仍 `WAITING`。 |
| `& .\tools\seed-vc-setup.ps1 -PreflightOnly`（2026-09-27 approved normal Windows session） | exit `0`; JSON `PASS` | `profile_scope=realtime-tiny`；`offline_v1_helper_completeness=WAITING`；`asset_manifest_clean_machine_status=WAITING`；Python 3.10.11 64-bit；Tcl 8.6.12／Tk available；`missing=[]`；`would_download_models=false`。 |
| `pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly`（2026-09-27 approved normal Windows session） | exit `0`; JSON `PASS` | `profile_scope=realtime-tiny`；runtime Python 3.10.11；`cuda_available=true`；NVIDIA GeForce RTX 5060 Ti；Host APIs MME、Windows DirectSound、Windows WASAPI、Windows WDM-KS；input DirectSound #26 `麥克風 (HyperX QuadCast S)`；output DirectSound #40 `CABLE Input (VB-Audio Virtual Cable)`；checkpoint SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`；VAD SHA-256 `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5`；`missing=[]`。 |
| Computer Use GUI 視覺核對（2026-09-27） | 視窗／設定顯示 `PASS`; audio stream 未啟動 | 截圖 `artifacts/seed-vc/gui-userflow/20260927-manifest-host-ui/seed-vc-gui.png`，1110×660，ignored 本機 artifact。Reference、DirectSound、HyperX mic、VB-Audio CABLE output、MME／DirectSound／WASAPI／WDM-KS dropdown、參數與按鈕可見；未按 `Start Voice Conversion`、沒有音訊串流。Escape 收起 dropdown，Alt+F4 關閉視窗，並確認視窗已關閉。 |
| `tools/seed-vc-gui-userflow-test.py` source review | scope clarification | harness 的 `CHECKPOINT_PATH` 指向 offline-v1 checkpoint，`REALTIME_CONFIG_PATH` 指向 Whisper/BigVGAN preset；既有四案 settings/callback/VB-CABLE loopback PASS 不構成 realtime-tiny backend inference PASS。 |
| 受限 Codex sandbox Tcl/Tk rerun | `WAITING / sandbox execution only` | sandbox 的 Python Tcl `init.tcl` lookup failure 不等於 host runtime failure；一般 Windows session manifest-enabled preflights 已另行 `PASS`。 |
| `& .\tools\seed-vc-setup.ps1 -PreflightOnly`（受限 Codex sandbox） | exit `1`; JSON `BLOCKED` / `WAITING` | Tcl `init.tcl` lookup failure；此 sandbox-only 結果不得覆蓋 approved normal-session PASS。 |
| `pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly`（受限 Codex sandbox） | exit `1`; JSON `BLOCKED` / `WAITING` | Tcl `init.tcl` lookup failure；此 sandbox-only 結果不得覆蓋 approved normal-session PASS。 |
| `git diff --check` | exit `0`; `PASS` | Git 只提示工作樹 LF→CRLF normalization；無 whitespace error。 |

上列 setup／GUI preflight 結果由本機一般 Windows user session 實測；本輪 contract regressions 另於隔離 temp fixture 執行，不能當成 corpus 音檔或 runtime 成績。overlay regression 會在 `$env:TEMP` 建立唯一名稱的 junction fixture 並保留，以免刪除任何資料。離線權重/音訊、third-party repo、venv 及 generated artifacts 不納入 Git。

## 下一步

1. 新機／新使用者需重做官方 Tcl/Tk runtime、setup 與 GUI preflight；不可假定本機 Python310 junction 隨 repo 安裝或可移植。
2. 使用者檢查實際 endpoint 與 reference 後，手動啟動 GUI、短時測試、停止並保存完整 run telemetry。
3. 完成同一 source 的 rack bypass/full-chain pair，再做真實 mic 600 秒測試與 human listening review。
4. MeanVC2／X-VC 已完成安裝與基本 CUDA WAV 測試，接著用固定 corpus 比較 Seed-VC／MeanVC2／X-VC，補 source/reference consent/license/register。新 streaming 方法另行 intake；RT-VC／CosyVoice3 保持候選。

操作細節見 [`README.md`](../README.md)、[`docs/user-guide.md`](user-guide.md)、[`docs/operation-guide.md`](operation-guide.md)、[`docs/live-gate.md`](live-gate.md) 與 [`backends/seed-vc/README.md`](../backends/seed-vc/README.md)。
