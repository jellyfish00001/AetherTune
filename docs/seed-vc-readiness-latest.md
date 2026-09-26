# AetherTune／Seed-VC 開箱與 LIVE readiness

更新日期：2026-09-26（Asia/Taipei）

## 結論

**AetherTune 尚未達成一般使用者可直接照做、且已證明 LIVE 的整體狀態。** Seed-VC 是目前已建立的 Streaming VC baseline；離線轉換、headless GPU block、GUI 設定流程與 synthetic cable loopback 有既有 PASS 證據。這些證據不涵蓋真實麥克風到最終通訊端的完整鏈路。

Seed-VC setup、一般使用者 GUI launcher 與 evidence validator 已有可重現操作路徑；目前 manifest-enabled gate 僅支援 `realtime-tiny`，offline-v1 helper completeness（含 Whisper/BigVGAN）仍 `WAITING / out-of-scope`。Python 3.10.11 的 Tk 問題根因是 `tcl\tk8.6\pkgIndex.tcl` 以相對路徑載入 `..\..\bin\tk86t.dll`，但官方 Python 安裝中的 DLL 位於 `DLLs\tk86t.dll`；Tcl/Tk script (`init.tcl`、`tk.tcl`) 本身存在。官方 Tcl/Tk MSI repair exit `0`（repair log SHA-256 `364414613B6E315AFEF0349FC3E1A56B6C421F6CD31B74EE58E53F50D6F2A3BE`）後，主控依既有安裝授權建立 per-user `Python310\bin` junction 指向 `DLLs`，未覆寫既有路徑或修改 DLL。之後一般 Windows user session 的 Tcl 8.6.12、Tk package 8.6.12、舊版 setup preflight 與 GUI preflight 均 `PASS`；GUI 視窗與音訊 stream 沒有啟動。這是先前主機修復後、manifest-enabled gate 前的 host 驗證，不證明新機／新使用者可直接 bootstrap。受限 sandbox 的 Tcl probe 仍是獨立環境結果，不得拿來推翻舊 host-session PASS，也不得解讀成主機 runtime 失敗。

新機的最小官方修復順序是以 Python 官方 installer Repair/Modify 確認 Tcl/Tk Support 已安裝，再於一般 Windows user session 驗證 `tkinter.Tcl()` 與 `package require Tk`，最後重跑 setup/GUI preflight。若官方安裝的 `pkgIndex.tcl` 與 DLL 位置仍不一致，採用使用者擁有的獨立 Python 3.10 install location 重裝並重驗；只有在 per-user `bin` 路徑不存在且有安裝授權時，才考慮建立指向現有 `DLLs` 的 junction。不得覆寫既有路徑、複製／改名 DLL 或修改第三方 Tcl/Tk scripts。這些步驟尚未在乾淨新機執行，因此 bootstrap 維持 `WAITING`。

## 分類摘要

| 狀態 | 項目 | 證據與限制 |
|---|---|---|
| `PASS` | Seed-VC upstream baseline | 固定 source revision `51383efd921027683c89e5348211d93ff12ac2a8`；離線雙向轉換、長音檔與 headless GPU block 有既有本機證據。僅代表該項離線／headless 範圍。 |
| `PASS` | GUI 設定與 synthetic loopback | 四個 reference case 各 17/17 GUI 欄位套用；backend／VB-CABLE synthetic route 有非零音檔。原始報告 `artifacts/seed-vc/gui-userflow/20260926-after-tcl-repair/gui-userflow-report.json` SHA-256 `1EB604F1A778FCEEFE73AB2D341A82DA274F08D31FF8342280DCA80FD963262E`。這是 WAV callback 注入，不是真人聲或真實麥克風。 |
| `PASS` | GUI 啟動架構 | launcher 將官方 GUI 放在 `artifacts/seed-vc/gui-session/` runtime overlay，配置其所需 `configs/hifigan.yml` 與 `configs/inuse/config.json`；model cache junction 指向經 manifest 固定 snapshot revision、size、SHA-256 驗證的本機 HF snapshots；VAD 由 bootstrap 在程序內映射至通過本機 hash 檢查的 ModelScope cache，並停用隱式更新。不寫第三方 source、原 cache 或 user profile。該 gate 僅涵蓋 realtime-tiny GUI；offline-v1 helper completeness（含 Whisper/BigVGAN）維持 `WAITING / out-of-scope`。資產 gate PASS 不證明未知的 VAD 上游授權或 clean-machine bootstrap。 |
| `PASS` | manifest realtime 資產 integrity contract | `tools/seed-vc-assets.json` 分別記錄 official Seed-VC code revision、兩個 profile 的 official model-repo revision/LFS metadata（但執行 gate 只要求 realtime-tiny checkpoint）、三個 realtime GUI 所需 HF 本機 snapshot revisions 與 observed size/hash、四個 VAD 檔案 observed size/hash。18 個隔離負測與 offline-v1 checkpoint/preset 缺席的成功 realtime-only smoke 均通過；此 PASS 只代表 realtime gate 與 manifest 登記 bytes 相符，不代表 offline-v1 helper 完整。 |
| `PASS` | 先前主機 setup／GUI preflight（manifest-enabled 變更前） | 官方 Tcl/Tk MSI repair exit `0`；核對 Python 3.10.11 安裝下 `tk86t.dll` 實在 `DLLs`，而 `pkgIndex.tcl` 預期 `bin`；在未覆寫既有目標時建立 per-user `Python310\bin` junction → `DLLs`。其後 Tcl/Tk 8.6.12、舊版 setup `-PreflightOnly` exit `0` 與 GUI `-PreflightOnly` exit `0` 通過，CUDA、MME input/output inventory、checkpoint/VAD hashes 已核對。GUI 與 stream 未開啟；這不是本輪 manifest-enabled host 重驗，也不代表另一台主機或新使用者 bootstrap 通過。 |
| `WAITING` | 本輪 realtime-only manifest-enabled host preflight 重驗 | 此執行環境的 setup/GUI `-PreflightOnly` 在資產檢查後僅因受限 sandbox 找不到 Python `init.tcl` 而 exit `1`；realtime 資產 manifest 本身無 mismatch。這是 sandbox execution `WAITING`，不能推翻先前一般 Windows session 的舊 launcher host PASS；仍需於一般使用者 session 重跑本輪新 script 才算當前 manifest-enabled host preflight 重驗。 |
| `WAITING` | offline-v1 helper completeness | 本輪 setup/GUI gate 明確只涵蓋 `realtime-tiny`。offline-v1 的 Whisper/BigVGAN checkpoint、preset 與 helper dependencies 不在此 manifest gate 範圍；先前離線推論 evidence 保留為既有結果，但不作為本輪 clean-machine/offline bootstrap PASS。 |
| `WAITING` | 新機／新使用者 bootstrap 與受限 sandbox Tcl probe | 目前 host 是經本機 per-user junction 修復後驗證；sandbox 環境仍可能無法定位 Tcl/Tk native assets。不可將 host `PASS` 推廣到乾淨安裝，也不可把 sandbox lookup error 當成主機失敗。 |
| `WAITING` | 真實 mic → Seed-VC → audio-rack → virtual route／B1 | 尚無涵蓋全部節點的有效音檔、run/model/device/route identity 與同步 timing evidence。synthetic loopback 不能補此缺口。 |
| `WAITING` | 600 秒穩定性與人工聽評 | 尚未完成真實麥克風 600 秒零 dropout／underrun 測試及使用者人工聽評。 |
| `WAITING` | Light Host／VST bypass 與 full-chain paired A/B | 已有 preset/profile 與 evidence schema；實體 plugin chain 尚無同 source、同 model、同 route、同硬體的成對音檔與實測 delta latency。 |
| `PLANNED` | MeanVC2、X-VC、Seed-VC realtime fork、CosyVoice3 | 保持隔離 intake 候選；不下載大型權重、不宣稱已安裝或可執行。 |
| `PLANNED` | 固定 special-speech corpus、acoustic comparison 與盲聽 | 尚未建立經授權且固定 hash 的 corpus 或人工評分；不得以測試訊號推估 MOS、音色相似或自然度。 |

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
| Seed-VC upstream | `established-baseline` | 固定 revision；既有離線/headless/GUI synthetic 範圍 PASS，完整 mic LIVE WAITING。 |
| Seed-VC realtime fork | `candidate / PLANNED`，獨立執行路徑 | 需分開核對 fork/source/revision/license/dependencies、worker/device/VAD，再和 baseline 以同 corpus 實測。 |
| MeanVC2 | `priority candidate / PLANNED` | 下一個 Streaming VC intake；先核對來源、revision、weights/model 條款、license、相依性及 Windows/CUDA，再做同 corpus、同 rack/route 比較。上游延遲宣稱不是本機證據。 |
| X-VC／新 streaming zero-shot | `research-candidate / PLANNED` | MeanVC2 同矩陣之後再 intake；需要固定 revision、權重來源/授權、可重現環境與實測 profile。 |
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
| `pwsh -NoProfile -File .\tools\seed-vc-assets-regression.ps1` | exit `0`; `PASS` | 隔離 TEMP synthetic fixture 對 setup/GUI 各跑九案（共 18 個負測）：required asset 缺檔、HF `refs/main` revision mismatch、同尺寸 hash mismatch、錯 code revision、錯 model repo revision、損壞 JSON、不合法 VAD provenance、manifest 遺漏 `requirements.txt`、manifest 遺漏 XLS-R `preprocessor_config.json`。另有正向 scope smoke：offline-v1 checkpoint/preset 缺席時 realtime setup preflight PASS，GUI normal startup 到 fake bootstrap，驗證 session config/cache junction/env overlay。假 Python 截獲啟動，沒有真 GUI/audio；正向 smoke 不建立 venv 或下載。這是 manifest contract 測試，不是 clean-machine bootstrap。 |
| `pwsh -NoProfile -File .\tools\seed-vc-run-preflight-regression.ps1` | exit `0`; `PASS` | 6 種 source/target/repo/checkpoint/config/Python 缺項均將預置舊 PASS manifest 覆寫成新 run_id、`BLOCKED`。腳本另檢查 offline output validator 使用 `$resolvedPython`（Seed-VC venv），非根 `.venv`；未執行模型推論。 |
| Seed-VC venv PortAudio inventory 唯一性 probe | exit `0`; input/output 各 `1` 筆 | `Windows DirectSound` + `麥克風 (HyperX QuadCast S)` input，及 `Windows DirectSound` + `CABLE Input (VB-Audio Virtual Cable)` output；這不是 MME 字串（MME 列舉會截斷名稱），因此範例明確指定 DirectSound。 |
| `tools/seed-vc-run.ps1` stale-output guard | PowerShell AST + preflight regression `PASS`; 不重跑模型 | 新 run manifest 在任何輸入／checkpoint precondition 前落為非 PASS；成功推論後比較 WAV path/hash snapshot；只驗本次新增或改變的 WAV。模型 inference 未重跑，不宣稱本輪 offline runtime PASS。 |
| 本機官方 Python 3.10.11 Tcl/Tk repair + per-user junction | MSI exit `0`; Tcl/Tk runtime `PASS` | `pkgIndex.tcl` 預期 `Python310\bin\tk86t.dll`，實檔位於 `Python310\DLLs`；repair log 顯示 Tcl/Tk Support configuration completed。主控在目標原本不存在時建立 `bin` junction 指向 `DLLs`，沒有改 DLL。這是已修復主機狀態，不是新機安裝證據。 |
| `& .\tools\seed-vc-setup.ps1 -PreflightOnly`（舊版，一般 Windows user session） | exit `0`; `PASS` | 修復後 Tcl 8.6.12 與 Tk package 8.6.12 可載入；舊版 setup 預檢通過。沒有以此證明本輪 manifest-enabled setup。 |
| `pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly`（舊版，一般 Windows user session） | exit `0`; `PASS` | CUDA/RTX 5060 Ti、MME mic/output inventory、realtime checkpoint 與 ModelScope VAD hashes 均核對；沒有啟動 GUI 視窗或 audio stream。沒有以此證明本輪 manifest-enabled GUI launcher。 |
| 受限 sandbox Tcl/Tk probe | exit `1`; `WAITING / sandbox execution only` | sandbox 自身的 Tcl lookup failure 不等於 host runtime failure；主機修復後的上述 user-session PASS 為目前主機證據。 |
| `git diff --check` | exit `0`; `PASS` | Git 只提示工作樹 LF→CRLF normalization；無 whitespace error。 |

上列 setup／GUI preflight 結果由本機一般 Windows user session 實測；本輪 contract regressions 另於隔離 temp fixture 執行，不能當成 corpus 音檔或 runtime 成績。overlay regression 會在 `$env:TEMP` 建立唯一名稱的 junction fixture 並保留，以免刪除任何資料。離線權重/音訊、third-party repo、venv 及 generated artifacts 不納入 Git。

## 下一步

1. 新機／新使用者需重做官方 Tcl/Tk runtime、setup 與 GUI preflight；不可假定本機 Python310 junction 隨 repo 安裝或可移植。
2. 使用者檢查實際 endpoint 與 reference 後，手動啟動 GUI、短時測試、停止並保存完整 run telemetry。
3. 完成同一 source 的 rack bypass/full-chain pair，再做真實 mic 600 秒測試與 human listening review。
4. 先補 corpus、source/reference consent/license/register；然後以 Seed-VC 建立比較底線，再按 MeanVC2 → X-VC/新 streaming 候選 intake。RT-VC 先留在 paper/source research；CosyVoice3 只列 reconstruction candidate。

操作細節見 [`README.md`](../README.md)、[`docs/user-guide.md`](user-guide.md)、[`docs/operation-guide.md`](operation-guide.md)、[`docs/live-gate.md`](live-gate.md) 與 [`backends/seed-vc/README.md`](../backends/seed-vc/README.md)。
