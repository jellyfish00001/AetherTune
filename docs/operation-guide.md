# AetherTune 完整操作流程

文件版本：2026-09-20
目前狀態：`Wiring deployed / role model candidate / VCClient conversion blocked`

使用入口：先讀根目錄 `README.md` 選擇 RVC／Seed-VC／STT → TTS；本文件只負責 RVC 選定後的 Windows 即時路由與驗收。RVC 資料準備與訓練請先讀 [`model-training-guide.md`](model-training-guide.md)。

## 1. 先看結論

目前基礎線路已建立，工作區已有 4 組未註冊角色模型，剩下主要是素材／模型 provenance、模型載入與最後的實際聲音驗收：

1. 具授權的乾聲資料與切片。
2. 訓練輸出的角色 `.pth` 與 `.index`。
3. 將角色模型載入 VCClient 後，完成真實模型的 P2/P3 聽測與延遲矩陣。
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
| 即時前端 | VCClient `2.1.4-alpha cuda` | 已解壓、初始化、本機 Web UI `HTTP 200` |
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

這些檔案屬於訓練基礎資產，不是使用者角色模型。工作區另有 4 組 `.pth/.index`，已完成 `models/model-register.csv` 的檔案路徑與 hash candidate 登錄；來源、授權、訓練取樣率、f0、revision 與 dataset metadata 仍待補齊，因此不能直接視為 ready。VCClient 的實際短音檔 conversion probe 另見 [`vcclient-rvc-probe-latest.md`](vcclient-rvc-probe-latest.md)。

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

### Phase 4：VCClient 即時變聲

已部署的入口：

```text
D:\AetherTune\tools\external\VCClient\2.1.4-alpha\dist\main\start_http.bat
```

啟動後開啟 `http://127.0.0.1:18000/`。工作區角色模型已完成檔案與 hash 的 `candidate` register；VCClient 仍要逐一透過 slot/upload path 建立，並完成實際推論驗證。這一版最新 REST probe 被 packaged API error 阻塞，請先看 [`vcclient-rvc-probe-latest.md`](vcclient-rvc-probe-latest.md)。

完成後的流程是：

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

### Phase 5：VST 微量後製

已部署的流程是：

```text
VCClient output → VB-CABLE → Light Host Modern input
Light Host Modern + Graillon VST3 → Voicemeeter / 第二個虛擬輸出
```

Light Host Modern 可攜版位置：`tools/external/LightHostModern/app/Light Host Modern.exe`。
Graillon VST3 預設位置：`C:\Program Files\Common Files\VST3\Auburn Sounds Graillon 3.vst3`。
首次使用時在 Light Host 的 Audio 選擇輸入／輸出與 buffer，在 Plugins 掃描上述 VST3 資料夾，再把 Graillon 加入 chain。修音只做微量 A/B，不先追求明顯 Auto-Tune 效果；Graillon 是免費授權第三方，不是開源元件。

### Phase 6：虛擬路由與終端應用

目前 Windows 已出現 `VB-Audio Virtual Cable`、`VB-Audio Voicemeeter VAIO`，FFmpeg DirectShow 也可列出其 endpoint。實際使用時建立：

```text
麥克風 → VCClient/RVC → VST host → 虛擬音訊輸出 → Discord／遊戲／OBS
```

建議的第一次路由設定：VCClient output 選 `CABLE Input (VB-Audio Virtual Cable)`；Light Host input 選 `CABLE Output (VB-Audio Virtual Cable)`；Light Host output 選 `Voicemeeter Input (VB-Audio Voicemeeter VAIO)`；在 Voicemeeter Standard 接收該虛擬輸入的 strip 啟用 UI 上的 `B` bus；Discord/OBS 的麥克風選本機實際列舉的 `Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)`。若要監聽才另外啟用 `A`。裝置方向要以 Windows 實際列舉為準，並避免同時監聽造成 feedback。

### Phase 7：完成驗收

目前 P1 軟體／裝置證據已寫入 `docs/wiring-verification-latest.md`；仍需 P2 角色模型離線輸出與人工聽測，以及 P3 loopback、延遲與 Discord/OBS 收音證據。只看到 UI、只成功載入模型或只通過 mock，不算完整完成。

## 4. 日常使用流程（完成後）

1. 選擇實體麥克風。
2. 啟動 VCClient，載入角色 `.pth`/`.index`。
3. 設定 f0、pitch、chunk、index rate。
4. 啟動 VST host，載入修音 preset。
5. 啟動虛擬路由，確認 meter 有訊號且沒有 feedback。
6. 在 Discord/OBS 選最終虛擬輸出。
7. 用固定測試句確認聲音與延遲，再開始通話或錄製。

## 5. 目前不能宣稱的事項

- 尚無角色聲音模型品質結論。
- 尚無真實麥克風端到端延遲數字。
- 尚未由 Light Host 完成實際 VST chain 與 loopback 聽測。
- 尚無 Discord/OBS 收音證據。
- VCClient 2.1.4-alpha 的啟動輸出顯示其內建 PyTorch 對 RTX 5060 Ti `sm_120` 有相容性警告；此外最新重啟曾遺失 module/sample 檔案並退出。因此目前只把它標成「服務/UI 可用」，GPU 角色推論仍須在模型載入後驗證，必要時改用 ONNX/DirectML 或更新版前端。
- 「100% 開源免費」不成立；核心可開源，路由與部分插件是免費但可能閉源。
