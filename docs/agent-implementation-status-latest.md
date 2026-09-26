# Agent 實作與測試總表

更新日期：2026-09-26（Asia/Taipei）

這份文件回答「目前哪些可以直接使用、哪些仍需要補條件」。`PASS` 只代表指定 gate 有可重跑證據；不代表音質一定符合個人偏好。`WAITING` 是尚未完成或需要人工／系統條件；`BLOCKED` 是目前有明確錯誤，不能當作可用。Seed-VC 開箱操作及本輪 readiness 見 [`seed-vc-readiness-latest.md`](seed-vc-readiness-latest.md)。

## 既有驗證工作狀態

| # | 工作 | 目前狀態 | 可以直接做什麼 | 尚未完成／限制 | 主要證據 |
|---:|---|---|---|---|---|
| 1 | 修復 VCClient packaged RVC 無效 WAV、實際角色模型 | `BLOCKED`／`DEGRADED` | 可用官方 repair 與 register 工具重現問題；RVC 專案離線路線可用 | 最新 Sage slot 7 v2 post-gate probe 已核對 requested／active／initial=`7/7/7`，30 chunks 僅 2 個 valid、28 個 invalid（全零 28）；仍不能用於穩定即時通話 | [`vcclient-packaged-repair-latest.md`](vcclient-packaged-repair-latest.md) |
| 2 | RVC latency、buffer、斷音、10 分鐘矩陣 | `DEGRADED`／`BLOCKED` | 可執行 bounded 矩陣並取得 p50/p95、invalid/dropout、RMS，且報告 slot 核對證據 | Sage slot 7 v2 的 0.25／0.50／0.75／1.00 秒短測 invalid/dropout 為 58/60、28/30、19/20、15/15；1.00 秒為 `0/15` valid，stability=`stability_seconds=0` 為 `BLOCKED`，尚非 600 秒證據 | [`vcclient-rvc-latency-matrix-latest.md`](vcclient-rvc-latency-matrix-latest.md) |
| 3 | Seed-VC realtime tiny、長音檔與 GUI 設定 | 60 秒 headless `PASS`；2026-09-26 一般 Windows session 官方 Tcl/Tk repair + per-user junction 後，Tcl 8.6.12、Tk package 8.6.12、setup preflight、GUI preflight `PASS`；四案 GUI settings／backend／CABLE loopback `PASS`；完整 live gate `WAITING` | 離線男女互轉、60 秒長檔、200 block headless GPU stream 可用；四個 reference 均 17/17 GUI 欄位成功更新，backend 和 VB-CABLE loopback 全案 finite／非零；此為本機修復後狀態，不是新機 bootstrap PASS | 尚未完成真實麥克風 E2E、人工聽感、Light Host full-chain、10 分鐘穩定性與完整 mic → backend → rack → route latency；新機／新使用者 Tcl/Tk bootstrap 尚未驗證 | [`seed-vc-verification-latest.md`](seed-vc-verification-latest.md)、[`wiring-verification-latest.md`](wiring-verification-latest.md)、[`seed-vc-gui-userflow-test.py`](../tools/seed-vc-gui-userflow-test.py) |
| 4 | 四方法批次音質／音量／取樣率比較 | signal-level `PASS` | 可比較 11 個 WAV 的取樣率、RMS、peak、clipping、silence、DC 與 hash；BLOCKED row 不會被彙總成 PASS | 這不是 MOS、音色相似度或人工聽測；不同方法本來就有 22.05／24／40／48 kHz 差異 | [`audio-quality-comparison-latest.md`](audio-quality-comparison-latest.md) |
| 5 | RVC 模型來源、授權、訓練版本與 metadata | hash／配對 `PASS`；provenance `WAITING` | 可用 audit 查看四組模型的檔案與 hash；checkpoint sample rate/version 已核對為 40/48 kHz、v2 | 現有四組仍是 `candidate`；source、license、f0、revision、dataset、trained-at 與 verification evidence 仍為 unknown；不得升成 `ready` | [`rvc-model-audit-latest.md`](rvc-model-audit-latest.md) |
| 6 | Breeze `sox`、`flash-attn`、`fast-all`、project-local UI | eager UI resident runtime `PASS`；fast-all `PASS`；project-local SoX `PASS`；flash-attn `WAITING` | Breeze eager CLI、project-local UI、`-FastAll` 與 local SoX runtime 可用；同一 UI session 第二次生成已證明可重用模型 | system SoX 尚未安裝；`flash-attn==2.8.3` 尚未成功 import；人工聽測未完成；切換 fast-all／attention 會重新載入 | [`breeze-tts2-verification-latest.md`](breeze-tts2-verification-latest.md) |
| 7 | CosyVoice frontend cuDNN 8 GPU／官方 UI | partial `PASS`；官方 upload UI flow `PASS` | 主模型 CUDA；官方 Gradio upload clone 已產生 24 kHz WAV；持久化專案 wrapper 可重跑隔離 cuDNN 8 probe | 預設主流程不載入隔離 cuDNN 8；CampPlus 上游明確固定 CPU；瀏覽器 microphone permission denied，因此錄音路徑仍 `WAITING` | [`cosyvoice-verification-latest.md`](cosyvoice-verification-latest.md) |
| 8 | RVC training data audit、訓練命令、模型註冊 | tooling `PASS`；資料 `BLOCKED` | 可依 guide audit、dry-run register、驗證 hash、provenance 與 verification evidence | `dataset/raw` 目前沒有 WAV，audit 正確回傳 exit 2；ready gate 負向回歸會拒絕 unknown metadata、缺失或 FAIL artifact；必須放入有授權乾聲並補完整 metadata 才能訓練／ready | [`model-training-guide.md`](model-training-guide.md)、[`rvc-model-audit-latest.md`](rvc-model-audit-latest.md) |

## 本輪架構調整狀態

| 工作 | 狀態 | 已完成 | 尚未完成 |
|---|---|---|---|
| Research Workbench 定義與 backend 分組 | `PASS`（文件） | README、`docs/architecture.md`、`docs/voice-conversion-architecture.md` 已改為 Streaming VC／Speech Reconstruction 分層 | 文件重構不代表任何新 backend runtime PASS |
| Common `audio-rack/` | 契約／route smoke `PASS`；runtime `WAITING` | 已登記 `seed-vc-neutral` preset、Graillon 3.2 profile、Seed-VC virtual route 與 `rack-evidence-v1` schema；VB-CABLE 與 Voicemeeter virtual route smoke 可重跑 | Light Host 實體 bypass/full-chain、plugin Δ latency、完整 backend → rack → route loopback 尚未完成 |
| `LIVE_GATE <= 5s` | validator contract regression `PASS`；真實 evidence `WAITING` | `docs/live-gate.md` 與 `tools/live-gate-validate.py` 可分類 `LIVE/LIVE_CANDIDATE/OFFLINE/WAITING/BLOCKED`；核對本 run WAV/metrics hashes 與 run/model/GPU/device/route identity | 尚無完整 mic → backend → rack → virtual route 的本機 evidence；synthetic source 只可 WAITING |
| Seed-VC realtime fork | `PLANNED`／`candidate` | 完成 source／scope intake 文件 | 尚未固定本機 revision、建立獨立 environment 或驗證 |
| MeanVC2 | `priority candidate / PLANNED` | 完成官方來源交叉檢查與驗收契約文件 | 尚未固定本機 revision、下載 checkpoint、安裝、確認 Windows／RTX 5060 Ti 或 E2E |
| X-VC／新 streaming VC | `research-candidate` | 官方 X-VC 程式碼與 streaming profile 已登錄來源審核；已定義後續滾動 intake 條件 | 尚未固定 revision、確認 checkpoint 條款／依賴或建立本機 runtime |
| CosyVoice3 | `PLANNED`／`candidate` | 在 speech-reconstruction backend 登記 A/B 方向 | 尚未安裝、確認 license／model snapshot 或本機 benchmark |
| 三層 benchmark | `PLANNED` | 建立 `benchmarks/corpus/live/quality/subjective/` 契約 | 固定 corpus、paired output、客觀比較與人工盲測尚未完成 |

## 本輪工具契約修正與可重跑檢查

- `tools/rvc-ready-gate-regression.ps1`：PASS；register 與 audit 都拒絕 ready 的 unknown metadata、缺失、malformed、FAIL／DEGRADED artifact、錯誤 model／index path／hash 與 input／output hash。
- `tools/vcclient-rvc-chunk-validation-regression.ps1`：PASS；逐 chunk 拒絕 empty、short、unaligned、全零、NaN 與 Infinity，只接受 finite non-zero float32 response。
- `tools/rvc-model-audit.py`：現有四列仍為 `WAITING`／`candidate`；ready 需要可解析且 `status=PASS` 的 verification JSON，並核對 model／index／input／output 路徑與 SHA-256。
- `tools/vcclient-rvc-probe.ps1` 與矩陣：最新 post-gate v2 artifact `artifacts/vcclient-rvc-test-postgate-v2/c0d00306-ce10-4746-9b81-9f0cff5d3ed5/vcclient-rvc-probe.json` 已保存 requested／active／initial slot 與 model evidence；Sage slot `7` runtime probe 為 `DEGRADED`（2/30 valid、28/30 invalid，且 28 個全零）。bounded 矩陣 `artifacts/vcclient-rvc-latency-matrix-postgate-v2/524e1a71-c00c-49c0-9127-82ae23aca119/vcclient-rvc-latency-matrix.json` 的短測 invalid/dropout 為 58/60、28/30、19/20、15/15，1.00 秒與 stability row 維持 `BLOCKED`。v1 Sage 與舊 Wukong／600 秒矩陣只作 historical/full-gate evidence。
- `tools/speech-reconstruction-run.ps1`：`TextFile` 與 `ReferenceTextFile` 分流；不同 source/reference 音檔未提供 reference transcript 時，另做 reference STT draft；caller text 預設是 `caller_provided_unverified`，只有明確 `-ReferenceTextVerified` 才標 verified，workflow 保存 `reference_text_verified` 與 manual review gate。
- `tools/audio-quality-batch-regression.py`：PASS；同一 backend 的 `PASS + BLOCKED` 彙總為 `BLOCKED`，`PASS + DEGRADED` 彙總為 `DEGRADED`。
- `tools/audio-output-validation-regression.py`：PASS；共用 helper 與檔案 gate 覆蓋空檔、零 frame、非 finite、錯誤取樣率、PCM16 與有效訊號；CosyVoice／Breeze runner 的原始 chunk gate 另在實際 runner 執行時生效。
- `tools/audio-runner-entry-regression.py`：PASS；實際啟動 Breeze／CosyVoice runner subprocess，覆蓋 `--help` 保留 stale PASS、四個明確 output 別名 (`--output`／`--out`／`--outp`／`--o`) 的分開與 `=` 形式（含 `--outp=path`、`--o path`）、重複 output 只清理最後目標、`--` 終止符、四個分開空值與既有 `--out=` 空值在 parser exit 2 時保留 stale output/manifest、非 0 parse failure 的 FAIL manifest 入口，以及 top-level dependency-safe import AST 契約。
- `tools/audio-rack-evidence-regression.py`：本輪 contract regression `PASS`；建立隔離 tone fixture 核對 source/bypass/full-chain WAV、SHA-256、run/model/hardware/route identity、metrics hash、delta；未配對為 `WAITING`，缺檔/hash/identity/delta mismatch／silence 為 `BLOCKED`、超過 5 秒為 `OFFLINE`，同一 rack fixture 交給 live gate 仍 `WAITING`。這些 fixture 不是 corpus、mic evidence 或 LIVE 成績。
- 本機 Tcl/Tk root-cause：官方 Python 3.10.11 Tcl/Tk MSI repair exit `0`，repair log SHA-256 `364414613B6E315AFEF0349FC3E1A56B6C421F6CD31B74EE58E53F50D6F2A3BE`，顯示 Tcl/Tk Support configuration completed；`tcl\tk8.6\pkgIndex.tcl` 嘗試從 `Python310\bin\tk86t.dll` 載入，但官方安裝 DLL 位於 `Python310\DLLs`。在目標原本不存在時，主控依安裝授權建立 per-user `Python310\bin` junction → `DLLs`；未覆寫既有路徑或修改 DLL。其後一般 Windows session 證明 Tcl `8.6.12`、Tk package `8.6.12`、`tools/seed-vc-setup.ps1 -PreflightOnly` exit `0`、`seed-vc-gui-run.ps1 -PreflightOnly` exit `0`；CUDA、MME mic/output inventory、realtime checkpoint/VAD hashes 均核對，且沒有開 GUI 或音訊 stream。這是本機安裝修復後 PASS，乾淨新機 bootstrap 仍 `WAITING`。
- `tools/seed-vc-gui-userflow-test.py --preflight`：受控非沙箱執行可核對 source、checkpoint、config、HF cache、reference、裝置配對與 `FreeSimpleGUI` import；本機最新 GUI preflight 另有上述 runtime evidence。受限 sandbox 的 Tcl lookup failure 是 sandbox-only `WAITING`，不覆蓋 host-session PASS。preflight 不啟動 GUI 或 stream；`--help` 與 `py_compile` 均通過。
- Seed-VC 官方 GUI settings／callback user-flow：2026-09-26 受控非沙箱實測 `PASS`；MME input `麥克風 (HyperX QuadCast S)`、CUDA backend、output `CABLE Input (VB-Audio Virtual C)`。四個 reference 每案 17/17 widget 更新、無 event mismatch；backend 與同步 WASAPI `CABLE Output` 四案都錄到 finite／非零且不同於注入輸入的訊號。最新 artifact 為 `artifacts/seed-vc/gui-userflow/20260926-after-tcl-repair/gui-userflow-report.json`。partial timing 含首案 model warmup，不是完整 first-packet latency；此測試仍不包含實體麥克風 E2E、Light Host full-chain、人工聽測或完整 LIVE evidence。
- Voicemeeter virtual route：`tools/virtual_cable_loopback.py` 以 WASAPI 合成音實測 `Voicemeeter Input → B1 → Voicemeeter Out B1` `PASS`，144000/144000 frames、RMS `0.0824916288`；`tools/voicemeeter-route-check.py` 另以 Remote API 讀取 `Strip[2].B1=1`、未 mute、15 個非零內部 level，並保存 `artifacts/voicemeeter-b1-route-check.json`。這是 virtual route smoke，不是實體麥克風、VST full-chain 或 `LIVE <= 5s` 證據。
- `tools/speech-reconstruction-failure-regression.ps1`：PASS；缺少輸入音檔時仍先移除精確的舊 workflow，且不啟動 WSL／模型。
- `tools/speech-reconstruction-run.ps1 -VoiceDesign`：Breeze wrapper smoke PASS；實際產生 24 kHz、10.48 秒非零 WAV，workflow 記錄 `voice_design=true` 與 `not_applicable_voice_design`。預設未加 switch 的 clone smoke 行為保留。
- 最新 runner smoke：Breeze `artifacts/speech-reconstruction/breeze-output-gate-v2.json` 為 24 kHz／11.52 秒、`run_id` 與 `output_validation` 通過；CosyVoice `artifacts/speech-reconstruction/cosyvoice-output-gate-v2.json` 為 24 kHz／10.28 秒、`run_id` 與 `output_validation` 通過。兩者仍不是人工音質或 realtime E2E 證據。

可重跑：

```powershell
Set-Location D:\AetherTune
& .\tools\rvc-ready-gate-regression.ps1
& .\tools\vcclient-rvc-chunk-validation-regression.ps1
& .\.venv\Scripts\python.exe .\tools\rvc-model-audit.py --fail-on-waiting
& .\.venv\Scripts\python.exe .\tools\audio-quality-batch-regression.py
& .\.venv\Scripts\python.exe .\tools\audio-output-validation-regression.py
& .\.venv\Scripts\python.exe .\tools\live-gate-regression.py
& .\.venv\Scripts\python.exe .\tools\audio-rack-evidence-regression.py
```

這一行只驗證 classifier 契約；它不產生真實 LIVE evidence。實際 gate 要把真實 JSON 路徑傳給 `tools/live-gate-validate.py`，沒有 evidence 時不要用虛構資料補 PASS。

## 目前可直接使用的路線

在目前證據範圍內，可以直接使用：

1. RVC 專案離線推論：`tools/rvc-fcpe-gpu-infer.py`，使用 `FCPE + cuda:0`，輸入自己的 WAV 與現有 `candidate` 模型。
2. Seed-VC 離線轉換：`tools/seed-vc-run.ps1`，用 male／female reference WAV 做雙向測試。
3. CosyVoice2 離線 TTS／reference clone：`tools/speech-reconstruction-run.ps1 -Backend cosyvoice`。
4. Breeze TTS 2 離線 Voice Design／reference clone：同一 wrapper 使用 `-Backend breeze-tts-2`；Voice Design 加 `-VoiceDesign -Instruction`，reference clone 需要人工核對 transcript。

5. Breeze TTS 2 project-local UI：啟動 `tools/breeze-tts2-webui.py` 後，在 `http://127.0.0.1:50081` 使用文字、instruction、CFG、seed、reference audio 與 exact transcript；同一 eager／Fast-all 設定會重用 resident runtime。
6. CosyVoice2 官方 Gradio UI：啟動 `tools/external/CosyVoice/webui.py` 後，在 `http://127.0.0.1:50080` 使用 upload reference clone；瀏覽器麥克風錄音需另外處理權限與 frontend 限制。

其中第 1 項是「可測試」而不是「模型已獲授權的 ready preset」；第 2～4 項是離線輸出路線，不等於麥克風即時變聲。

## Agent 還能繼續做的工作

- VCClient：可繼續追查上游 packaged binary／版本相容性，或改用另一個已支援 RTX 5060 Ti 的 runtime；在沒有新 binary 或 source 修復前，不能由文件把 `BLOCKED` 改成 `PASS`。
- RVC realtime：可在 VCClient 修復後重跑矩陣；目前短測 dropout 已足以阻擋 10 分鐘測試，不應反覆把同一份失敗證據重命名成通過。
- Seed-VC：可補 PortAudio／官方 GUI、實體 loopback 與長時間穩定性；目前 headless 測試不涵蓋麥克風權限與裝置 buffer。
- Seed-VC GUI：2026-09-26 Python 3.10.11 官方 Tcl/Tk Support repair 後，preflight 與四案 GUI settings／backend／CABLE loopback user-flow `PASS`；目前可確認測試 GUI 操作會成功套用各項設定。之後可接 Light Host audio-rack、bypass/full-chain、實體麥克風 first-packet timing、10 分鐘穩定性與人工聽測。不得以 deterministic callback 或 synthetic route `PASS` 取代完整 LIVE evidence。
- 四方法比較：可加入人工聽測表或固定評分規則，但需要使用者實際聽音與確認評分，不應由 Agent 代填主觀音質結論。
- 共用 audio-rack：先以 Seed-VC 作第一個 mic／loopback candidate，分別測 `bypass` 與 `full-chain`，再把同一 profile 套到其他 backend。
- MeanVC2：下一順位 priority candidate；先驗來源、授權、revision、依賴與隔離環境，再用同一 corpus 與 Seed-VC 比較。X-VC／新 streaming zero-shot VC 在 MeanVC2 矩陣後 intake；Seed-VC realtime fork 另作執行路徑比較。未完成 intake 前不下載大型權重或改正式主線。
- RVC provenance：可在使用者提供有授權的 raw WAV、來源、license、訓練設定後重新 audit、register 與 ready gate。
- Breeze／CosyVoice：system SoX、flash-attn、人工音質與預設 runtime 仍有可選優化；CosyVoice 隔離 cuDNN 8 probe 已有可重跑 GPU 證據，但不會覆蓋預設 PyTorch cuDNN 9 runtime。

## 建議下一步

若目標是「現在先用」，先讀根目錄 [`README.md`](../README.md) 的 Seed-VC offline／已驗證 GUI settings flow 或 STT → TTS 命令；若目標是「建立真正 Live 主線」，延伸 Seed-VC 測試到實體 mic → audio-rack → virtual route 與 `LIVE_GATE`，再做 MeanVC2 priority intake，接著比較 X-VC／新候選。RVC packaged conversion 的 HTTP 500／全零輸出仍保留為 baseline 阻塞，不應被新架構文件掩蓋。
