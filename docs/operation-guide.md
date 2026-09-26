# AetherTune 完整操作流程

文件版本：2026-09-26
目前狀態：`Seed-VC established baseline / real-mic and common rack evidence WAITING / MeanVC2 priority candidate PLANNED / RVC VCClient historical-degraded`

使用入口：先讀根目錄 `README.md`，依 `LIVE_GATE <= 5s`、是否保留原始表演與是否重建文字選擇路線。目前已建立的 Streaming VC baseline 是 Seed-VC；真實 mic、rack 與終端錄音仍 `WAITING`。MeanVC2 是後續 priority candidate，尚未 intake。本文件保留 RVC legacy 的 Windows 操作細節，同時定義所有 backend 共用的 audio-rack、virtual route、loopback 與驗收邊界。RVC 資料準備與訓練請先讀 [`model-training-guide.md`](model-training-guide.md)；共用 gate 讀 [`live-gate.md`](live-gate.md)。

## 0. 共用研究流程

所有需要播放或直播輸出的 backend 都應依下列順序建立 paired evidence：

```text
capture/source → backend adapter → audio-rack bypass
                              → audio-rack full-chain
                              → virtual route → loopback
```

先測 `Post-FX bypass`，再測 `full-chain`，並實測 `delta_latency_ms`。不要用「掛了幾個 VST 增加幾毫秒」推估延遲；lookahead compressor、linear-phase EQ、pitch correction、convolution ambience 都可能改變 latency。

只有完整 capture → backend → rack → virtual route 的 `e2e_first_packet_ms <= 5000` 才能分類為 `LIVE`。Seed-VC headless、RVC offline、CosyVoice/Breeze runtime 或 UI 可開啟都不能直接通過這個 gate。

## Seed-VC 日常即時使用

Seed-VC upstream GUI 已有一般使用 launcher；它啟動官方 realtime-tiny/Hifi-GAN profile，不經 callback harness，也不會在 launcher 自動開音訊 stream。第一次使用前先檢查依賴與裝置：

```powershell
Set-Location D:\AetherTune
& .\tools\seed-vc-setup.ps1 -PreflightOnly
pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly
```

GUI launcher 要求 PowerShell 7.2 以上（`pwsh`，其 junction 驗證使用 .NET 6 API）；預設使用 setup 建立的 Seed-VC venv。`-Python310 <base-python.exe>` 只給 setup；若 GUI 改用自訂 venv，才傳 `-Python <venv\Scripts\python.exe>`。

第一個 preflight 檢查 Python 3.10、固定 upstream revision、Tcl/Tk、`realtime-tiny` GUI 所需 checkpoint/config，以及 [`tools/seed-vc-assets.json`](../tools/seed-vc-assets.json) 登記的 realtime snapshot revision、exact size、SHA-256。第二個 preflight 另查 Python runtime、CUDA device 0、GUI 依賴、可唯一解析的 input/output endpoints，並依同一 manifest 重驗 realtime checkpoint 與 GUI 所需 HF/ModelScope 檔案；ModelScope FSMN-VAD 只有本機 observed hash，官方完整 revision/license 仍 `UNKNOWN/WAITING`。此 manifest/setup/GUI gate 不保證 `offline-v1` helper 完整性；Whisper/BigVGAN 資產與 offline helper completeness 維持 `WAITING / out-of-scope`。任何 realtime 必需檔案或 hash 不符都先列出並停止，不會下載模型或改裝置；asset integrity PASS 不代表 clean-machine bootstrap PASS。

啟動一般 GUI 時可傳入明確裝置名稱與 reference：

```powershell
pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 `
  -InputDeviceName '麥克風裝置完整名稱' `
  -OutputDeviceName 'CABLE Input (VB-Audio Virtual Cable)' `
  -HostApi 'Windows DirectSound' `
  -ReferenceWav .\dataset\reference-voices\voice-female-f1.wav
```

本範例的完整 endpoint 名稱與 `Windows DirectSound` Host API 已在目前主機 PortAudio inventory 唯一匹配 1 個 output。其他電腦請換成該機 preflight 列出的完整名稱與 Host API；不可照抄截斷或近似名稱。

沒有參數時會讀 `artifacts/seed-vc/gui-session/configs/inuse/config.json`；初次使用則採當下唯一的 Windows 預設 input/output endpoint，但不修改 Windows 預設。Host API 優先序為 CLI `-HostApi` > 此隔離 session 已保存的 `sg_hostapi` > 首次執行時由唯一／default endpoint 推導；input/output 仍須各自唯一匹配且在同一 Host API。若不唯一、缺失或輸入／輸出方向不符，launcher 會停止並指出原因。`-ReferenceWav` 可省略並於 GUI 選取，`-ClearReference` 清掉隔離設定中的舊 reference。

Launcher 固定 FP32、CUDA device 0、realtime-tiny checkpoint 和官方 XLS-R/Hifi-GAN config。設定在 ignored `artifacts/seed-vc/gui-session/`；模型 cache 以本機 snapshot directory junction 和 cache lock overlay 讀取，ModelScope `fsmn-vad` 由 bootstrap 映射至 preflight 驗過的本機目錄並關閉 update，HF/Transformers 設為 offline。Launcher 不改 upstream repo、user profile 或 cache。若畫面顯示裝置／reference 與預期不同，先在 GUI 修正，確認 meters/route 後再按 `Start VC`；結束按 `Stop VC` 再關閉。

實際麥克風驗收要在一般 Windows session 由使用者操作：選本人有權使用的聲線 reference，接上物理 input 與明確的虛擬 output，做短句和持續測試並錄下 input/output WAV、PortAudio status/dropout/underrun、backend checkpoint/config hash、裝置/driver/route identity 及每案 run id。先完成 bypass/full-chain paired run 並量 Δ latency，再驗證最終 Voicemeeter B1／Discord/OBS endpoint。deterministic callback user-flow、合成 route tone 和畫面 meter 都不能代替此驗收；聲音品質及授權需另外由人工核對。

## 1. 先看結論

目前 Streaming VC baseline 是 Seed-VC。先前官方 Tcl/Tk repair 與 per-user junction 後的一般 Windows session setup/GUI preflight `PASS`，是尚未加入本輪 manifest gate 的舊版 launcher host evidence；本輪加入 realtime-only manifest 後的 setup/GUI 重驗在受限 sandbox 為 `WAITING`，詳見 [`seed-vc-readiness-latest.md`](seed-vc-readiness-latest.md)。兩者都只證實啟動前檢查；手動 GUI `Start VC`/`Stop VC`、真實 mic E2E、audio-rack paired run 與最終收音仍為 `WAITING`。`offline-v1` 的先前推論紀錄不等於本輪 realtime setup 對 Whisper/BigVGAN 或 offline helper completeness 的保證；該範圍仍 `WAITING / out-of-scope`。MeanVC2 為下一個 priority candidate，尚未 intake。RVC/VCClient 是 historical/degraded 對照，不是目前推薦日常路線。工作區另有 4 組未註冊 RVC 角色模型：

1. 具授權的乾聲資料與切片。
2. 訓練輸出的角色 `.pth` 與 `.index`。
3. 若需要 RVC historical 對照，再將角色模型載入 VCClient，完成真實模型的 P2/P3 聽測與延遲矩陣。
4. Light Host 的實際裝置選擇、Graillon 掃描與 loopback 設定仍需第一次由使用者依畫面完成。

因此目前可以說「軟體與虛擬端點已部署、可開始準備素材」，但不能說「角色變聲品質與 Discord/OBS 全鏈路已驗收」。

## 2. 目前規格基線

### 已選定或已固定

| 區域 | 目前基線 | 狀態 |
|---|---|---|
| 作業系統 | Windows | 已確認工作環境 |
| GPU | NVIDIA GeForce RTX 5060 Ti，約 16 GB VRAM | 已確認 |
| Python | 專案 `.venv`，Python 3.12.10 | 已完成 |
| GPU framework | Torch `2.7.1+cu128`、TorchAudio `2.7.1+cu128` | 已完成 |
| RVC | 官方 WebUI，固定 revision `81eed5e8f68b6bed1789f682fe78cdd324495afc` | 已 clone/驗證 |
| f0 | FCPE（推薦首選）/ RMVPE（備用） | FCPE 與 RMVPE runtime 皆已通過 CUDA smoke test |
| runtime 資產 | HuBERT base + `rmvpe.pt` + `torchfcpe` (FCPE) | 已內建/下載完成並通過推論探針 |
| 音訊工具 | FFmpeg 9.0.1、FFprobe 9.0.1 | 已安裝；目前 shell PATH 仍需刷新 |
| Dataset gate | `tools/dataset_audit.py` + CSV manifest | 工具已完成，尚無真實資料 |
| 虛擬音訊 | VB-CABLE + Voicemeeter Standard | 已安裝；Windows endpoint 與 FFmpeg DirectShow 可見 |
| 即時前端 | Seed-VC upstream GUI | established baseline；真實 mic / rack / 終端 E2E `WAITING` |
| RVC 即時前端 | VCClient `2.1.4-alpha cuda` | historical/degraded；服務/UI 存在不代表即時推論通過 |
| VST 宿主 | Light Host Modern `v1.3.1` portable | 已解壓、程序可啟動 |
| 修音插件 | Auburn Sounds Graillon Free `3.2` | 已安裝 VST3/VST2；尚未完成 host 內掃描與聽測 |

### 尚未定案的候選參數

| 參數 | 候選 | 不應直接視為結論 |
|---|---|---|
| 訓練取樣率 | 40 kHz 或 48 kHz | 需和 RVC 設定、模型與音訊裝置一致 |
| Pitch | `+6 / +9 / +12` | 男變女不等於固定 `+12` |
| Index rate | `0.5 / 0.7` | 需用咬字與音色 A/B 決定 |
| chunkSec / extraFrameSec | `0.25 / 0.50 / 0.75 s` 與 `0.04 / 0.08 / 0.12 s` | 兩欄分開做單因子測試 |
| VST 修音 | Chromatic、40–80 ms、30–50% | Graillon 已安裝；host chain 與人工聽測待完成 |

## 3. 完整流程

### Phase 0：一次性環境準備

已完成：

```powershell
Set-Location D:\AetherTune
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

預期：Torch 為 `2.7.1+cu128`、CUDA build 為 `12.8`、GPU 可用。

RVC 訓練基礎資產已下載到固定 RVC repo root；之後不需要重複下載。若重建環境，再使用官方命令：

```powershell
Set-Location D:\AetherTune\tools\external\Retrieval-based-Voice-Conversion-WebUI
& D:\AetherTune\.venv\Scripts\hf.exe download lj1995/VoiceConversionWebUI --revision e6d0c1a17da07c33557852f9dfa2bd44cc75737d --include "pretrained/*" "pretrained_v2/*" --local-dir assets
& D:\AetherTune\.venv\Scripts\hf.exe download lj1995/VoiceConversionWebUI mute.zip --revision e6d0c1a17da07c33557852f9dfa2bd44cc75737d --local-dir .model-downloads
& D:\AetherTune\.venv\Scripts\python.exe -m zipfile -e .model-downloads\mute.zip logs
```

這些檔案屬於訓練基礎資產，不是使用者角色模型。工作區另有 4 組 `.pth/.index`，已完成 `models/model-register.csv` 的檔案路徑與 hash candidate 登錄；checkpoint 內嵌取樣率與 v2 version 已核對，但來源、授權、f0 演算法、revision、dataset metadata 與 ready gate 仍待補齊，因此不能直接視為 ready。VCClient 的實際短音檔 conversion probe 另見 [`vcclient-rvc-probe-latest.md`](vcclient-rvc-probe-latest.md)。

### Phase 1：資料準備

1. 只放入本人或已取得授權的乾聲資料到 `dataset/raw/`。
2. 執行 audit：

```powershell
Set-Location D:\AetherTune
& .\.venv\Scripts\python.exe tools\dataset_audit.py `
  --root dataset\raw `
  --manifest dataset\manifests\raw-audit.csv `
  --fail-on-invalid
```

3. 先在 `dataset/manifests/source-register.csv` 登記來源、授權／使用權、資料批次、父檔、衍生關係與目前 WAV 的 `source_sha256`；音檔替換後必須重新登記 hash。
4. 人工確認 manifest 的來源、授權、雜訊、殘響、聲道、音量與取樣率。
5. 若需要，才做去噪、去殘響或變調；所有衍生檔放到 `dataset/sliced/` 或 `dataset/augmented/`，不可覆寫 raw。
6. 使用固定 RVC revision 內的 `train/dataset/slicer2.py` 切成約 5–15 秒；抽查短句、子音、尾音與長停頓。
7. 建立保留測試集，不要把所有語句都放進訓練資料。

TTS 生成資料只能作為明確標記的補充實驗，不應默認等同於真人乾聲；聲線與輸出用途也要另行確認授權。

### Phase 2：RVC 訓練

1. 在 `tools/external/Retrieval-based-Voice-Conversion-WebUI` 啟動 WebUI。
2. 指定訓練資料目錄、角色名稱、取樣率與 f0 method `rmvpe`。
3. 先以小批次確認 preprocess、f0 extraction、HuBERT feature extraction 都成功。
4. 再執行約 150–300 epochs 的候選訓練；epoch 不是品質保證，需看保留測試集。
5. 訓練 checkpoint 先留在外部 RVC repo；完成 extraction 後，把 `assets/weights/<name>.pth` 與相同 experiment 的 `logs/<experiment>/added_*.index` 複製到 `models/weights/` 與 `models/indexes/`。
6. 依 `models/model-register.example.csv` 建立 `models/model-register.csv`，登記 `.pth/.index` 配對、各自 SHA-256、取樣率、f0、RVC version、資料批次、RVC revision、訓練時間與狀態。

### Phase 3：離線推論驗證

用未參與訓練的固定語句做 A/B：

1. 載入 `.pth` 與 `.index`。
2. f0 先用 RMVPE。
3. 測試 `+6/+9/+12`、index `0.5/0.7`。
4. 比較音高穩定、咬字、齒音、破音、金屬聲、延遲與自然度。
5. 只有離線結果穩定，才進入即時鏈路。

### Phase 4：RVC／VCClient historical-degraded 對照

以下只供維護舊 RVC 路徑或做 historical latency／失真比較，不是一般使用者目前的日常即時路線。VCClient 最新 REST probe 被 packaged API error 阻塞，且其 PyTorch 對 RTX 5060 Ti `sm_120` 有相容性警告；真實模型載入、GPU 推論與 mic E2E 尚未驗收。Streaming VC 主線仍是 Seed-VC established baseline，後續 priority candidate 為 MeanVC2（尚未安裝）。

已部署的入口：

```text
D:\AetherTune\tools\external\VCClient\2.1.4-alpha\dist\main\start_http.bat
```

啟動後開啟 `http://127.0.0.1:18000/`。工作區角色模型已完成檔案與 hash 的 `candidate` register；VCClient 仍要逐一透過 slot/upload path 建立，並完成實際推論驗證。這一版最新 REST probe 被 packaged API error 阻塞，請先看 [`vcclient-rvc-probe-latest.md`](vcclient-rvc-probe-latest.md)。

舊路徑待驗收流程是：

```text
實體麥克風 → VCClient/RVC → 第一個虛擬輸出
```

先固定同一個角色模型與同一段未參與訓練的測試句；以下矩陣一次只改一個參數。`chunkSec` 與 `extraFrameSec` 是秒，不能再混成沒有單位的 `Chunk/Extra`：

| 階段 | 固定值 | 唯一變動值 | 目的 |
|---|---|---|---|
| baseline | pitch +9、chunkSec 0.50 s、extraFrameSec 0.08 s、index 0.50 | 無 | 建立共同基線 |
| chunk | 其他同 baseline | chunkSec 0.25 / 0.50 / 0.75 s | 找延遲與斷音折衷 |
| extra | 其他同 baseline | extraFrameSec 0.04 / 0.08 / 0.12 s | 找穩定度與延遲折衷 |
| pitch | 其他同 baseline | +6 / +9 / +12 | 找自然音域，不預設 +12 |
| index | 其他同 baseline | 0.00 / 0.50 / 0.70 | 比較音色特徵與咬字 |
| VST | 同一組最佳 RVC 設定 | Graillon bypass / active | 分離修音本身的影響 |

每列記錄時間、model_id、`.pth/.index` hash、測試句 ID、取樣率、backend、持續時間、p50/p95 延遲、underrun、斷音次數、artifact 與人工聽測備註；欄位範本見 `docs/parameter-matrix-template.csv`。暫定日常 gate：連續 10 分鐘零斷音、零 underrun，p95 延遲不超過 250 ms；若實測無法達成，記錄取捨，不把門檻當成已證明的產品保證。

### Phase 5：共用 VST 微量後製

已部署的流程是：

```text
Seed-VC GUI output (CABLE Input) → CABLE Output → Light Host Modern input
Light Host Modern + Graillon VST3 → Voicemeeter / 第二個虛擬輸出
```

VCClient output 僅供上一節 RVC historical/degraded 對照。VST bypass/full-chain A/B 必須對明確選定的 backend 使用同 source、同 model、同 hardware、同 route 的成對 run。

Light Host Modern 可攜版位置：`tools/external/LightHostModern/app/Light Host Modern.exe`。
Graillon VST3 預設位置：`C:\Program Files\Common Files\VST3\Auburn Sounds Graillon 3.vst3`。
首次使用時在 Light Host 的 Audio 選擇輸入／輸出與 buffer，在 Plugins 掃描上述 VST3 資料夾，再把 Graillon 加入 chain。修音只做微量 A/B，不先追求明顯 Auto-Tune 效果；Graillon 是免費授權第三方，不是開源元件。

### Phase 6：虛擬路由與終端應用

目前 Windows 已出現 `VB-Audio Virtual Cable`、`VB-Audio Voicemeeter VAIO`，FFmpeg DirectShow 也可列出其 endpoint。實際使用時建立：

```text
實體麥克風 → Seed-VC GUI → CABLE Input → CABLE Output → VST host → Voicemeeter B1 → Discord／遊戲／OBS
```

建議路由：Seed-VC GUI output 選 preflight inventory 中唯一的 `CABLE Input`；Light Host input 選對應的 `CABLE Output`；Light Host output 選 `Voicemeeter Input`；在 Voicemeeter Standard 接收該虛擬輸入的 strip 啟用 UI 上的 `B` bus；Discord/OBS 的麥克風選 inventory 中實際列舉的 `Voicemeeter Out B1`。若要監聽才另外啟用 `A`。本機完整名稱會依 Host API 有差異，必須照 PortAudio／Windows inventory 的完整字串指定，不要照抄截斷名稱；同一 Host API 下 endpoint 必須唯一。裝置方向要以 Windows 實際列舉為準，並避免同時監聽造成 feedback。

### Phase 7：完成驗收

Seed-VC offline/headless、GUI settings 與 synthetic route 各自有既有範圍 PASS；這些不等於真實 mic E2E。仍需 P2 source/reference 人工聽測，以及實體麥克風 → Seed-VC → Light Host full-chain → virtual route 的 P3 延遲、600 秒穩定性與 Discord/OBS 收音證據。只看到 UI、只成功載入模型或只通過 synthetic route，不算完整完成 LIVE。

## 4. 日常 Seed-VC baseline 操作（LIVE 驗收仍 WAITING）

1. 選擇實體麥克風。
2. 依本文件 Seed-VC GUI 步驟，使用建立好的 Seed-VC venv 啟動 launcher，確認唯一 input/output、Host API 與 reference，再由使用者按 `Start VC`。
3. 如需後處理，啟動 VST host；先做 bypass，再執行 full-chain paired measurement。
4. 啟動虛擬路由，確認 meter 有訊號且沒有 feedback。
5. 在 Discord/OBS 選最終虛擬輸出。
6. 以固定測試句做短時驗收；真實 mic、600 秒穩定性與人耳聽評完成前仍維持 `WAITING`，不得把此操作步驟視為 LIVE certification。

## 5. 目前不能宣稱的事項

- 尚無角色聲音模型品質結論。
- 尚無真實麥克風端到端延遲數字。
- 尚未由 Light Host 完成實際 VST chain 與 loopback 聽測。
- 尚無 Discord/OBS 收音證據。
- VCClient 2.1.4-alpha 的啟動輸出顯示其內建 PyTorch 對 RTX 5060 Ti `sm_120` 有相容性警告；此外最新重啟曾遺失 module/sample 檔案並退出。因此目前只把它標成「服務/UI 可用」，GPU 角色推論仍須在模型載入後驗證，必要時改用 ONNX/DirectML 或更新版前端。
- 「100% 開源免費」不成立；核心可開源，路由與部分插件是免費但可能閉源。
