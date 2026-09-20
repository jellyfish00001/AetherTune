# 本機環境盤點

盤點日期：2026-09-19（Asia/Taipei）

## Repository

- 工作目錄：`D:\AetherTune`
- 遠端：`https://github.com/jellyfish00001/AetherTune.git`
- 狀態：空倉庫，`main` 尚無 commit；本次建立第一批文件與目錄骨架。

## 已觀察到的能力

| 項目 | 結果 | 意義 |
|---|---|---|
| GPU | NVIDIA GeForce RTX 5060 Ti，16,311 MiB；NVIDIA-SMI/KMD 610.88；CUDA UMD 13.3 | 硬體方向符合 RTX 50 系列候選，但不代表 PyTorch CUDA 已可用 |
| 既有 Python | 3.11.15，`C:\Users\User\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe` | 保持不動，不與 AetherTune 共用 |
| 專案 Python | `D:\AetherTune\.venv\Scripts\python.exe`，Python 3.12.10 | 已建立隔離環境並完成 RVC 依賴安裝 |
| Python launcher | `py -0p` 在本次 shell 未列出 3.12 | 以專案 venv 絕對路徑為準；新 shell 再重新確認 launcher |
| FFmpeg | Gyan FFmpeg 9.0.1；`ffmpeg.exe` 與 `ffprobe.exe` 已以絕對路徑執行驗證 | 已補齊執行檔；當前 shell 的 `ffmpeg` PATH 尚未刷新，需新 shell 再驗證 |
| 音訊裝置 | Windows/FFmpeg 已列舉 `VB-Audio Virtual Cable`、`VB-Audio Voicemeeter VAIO` 與 `HyperX QuadCast S` 麥克風 | 虛擬端點與實體麥克風已存在；仍需做實際 loopback |
| VCClient | `2.1.4-alpha cuda` 已解壓並完成首次初始化；`127.0.0.1:18000` 回應 HTTP 200 | UI/服務層通過；角色模型 GPU 推論仍待 `.pth/.index` 實測 |
| VST 線路 | Light Host Modern `v1.3.1` portable 與 Graillon Free `3.2` VST3/VST2 已部署 | 尚需在 host 內掃描插件、選 input/output 並完成 loopback |

## 尚未證實的項目

- HuBERT/RMVPE 權重是否可下載、載入與完成 f0 推論。
- VCClient 2.1.4-alpha 內建 PyTorch 對 RTX 5060 Ti `sm_120` 的實際角色模型推論；啟動時已出現相容性警告。
- RMVPE 權重下載、f0 推論與端到端延遲。
- 實體麥克風與虛擬音訊裝置的實際取樣率、buffer 與驅動模式。
- Discord/OBS/其他通訊軟體是否能收到後製後訊號。

## 已驗證檔案指紋

安裝位置：`C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\`

| 檔案 | SHA-256 |
|---|---|
| `ffmpeg.exe` | `57C56E369D5B4873B4D93FC1A1D833CB7CD8BC9325C14B05C34CE60B22842D8A` |
| `ffprobe.exe` | `AFE05347CAAABE479B3C4EAE71992B6EC1E11C57266A1D665DEB0F9FE9847208` |

## RVC 依賴與 runtime smoke test

- 上游倉庫：`tools/external/Retrieval-based-Voice-Conversion-WebUI`
- 固定 revision：`81eed5e8f68b6bed1789f682fe78cdd324495afc`
- 依賴檔：`requirments_cu128_py312.txt`
- 依賴檔 SHA-256：`F68F1CD32868C4EF5D3B22B9C654CF82317DA6B991D166207A5A7AC844DFFCA5`
- RVC 訓練資產 HF revision：`e6d0c1a17da07c33557852f9dfa2bd44cc75737d`；重建命令不得改回浮動的 `main`。
- Torch：`2.7.1+cu128`；TorchAudio：`2.7.1+cu128`
- `pip check`：通過，沒有 broken requirements。
- CUDA smoke test：`torch.cuda.is_available() = True`、device count `1`、裝置 `NVIDIA GeForce RTX 5060 Ti`、capability `(12, 0)`。
- ONNX Runtime providers：`TensorrtExecutionProvider`、`CUDAExecutionProvider`、`CPUExecutionProvider`。
- 核心 `infer.rtrvc` import：在 RVC repo root 執行成功。
- 直接 import `webui.py` 不作為成功條件：該上游檔案沒有 main guard，import 會進入 server launch；本次已確認並清理由測試產生的兩個背景程序。
- smoke test 曾出現 Matplotlib cache 權限警告與 Gradio `pkg_resources` deprecation warning；兩者未阻止依賴/核心 import，但尚未做 UI 啟動驗證。

## RVC runtime 資產

以下檔案依 RVC 官方 README 下載到固定 clone；它們是通用 runtime 資產，不是使用者角色模型：

| 檔案 | 大小（約） | SHA-256 |
|---|---:|---|
| `assets/hubert_base/config.json` | 1.5 KB | `0346950779DFB7F9316FA74ED846E2B8A22A08EEDFDC5387B73F327CB1A4A7CF` |
| `assets/hubert_base/preprocessor_config.json` | 225 B | `7C1976A680FB7ACC757CD36FB08EEF878FA36C70B4C9D2D595DF9C608BBBBF0E` |
| `assets/hubert_base/pytorch_model.bin` | 189 MB | `CC8C20F4B90A520757260197A3FF2505705A7ADBD20AD9EEAA4E1A9B38442EF5` |
| `assets/rmvpe/rmvpe.pt` | 181 MB | `6D62215F4306E3CA278246188607209F09AF3DC77ED4232EFDD069798C4EC193` |

### 模型載入 smoke test

- HuBERT：CUDA `cuda:0`、`float16`、輸出 shape `(1, 49, 768)`。
- RMVPE：對記憶體中的 1 秒、220 Hz 合成正弦波產生 101 個 frame，101 個 voiced frame，中位數 `220.08 Hz`。
- 這只證明 runtime 資產與 GPU 推論路徑可載入；尚未證明真實人聲、RVC `.pth`、`.index` 或即時延遲。

## 已完成的部署證據

- RVC 訓練資產：`assets/pretrained/` 12 個、`assets/pretrained_v2/` 12 個、`logs/mute/` 11 個檔案。
- VCClient package SHA-256：`58CED135E0768A9F382461FAB13A8967520FDE2D307D39C0AB4B830040F9C70F`。
- Light Host Modern portable ZIP SHA-256：`39BD85FBC1EED130E3B48B5950A82FC7850349A0A99805B42967CAE92DAFBFD8`。
- Graillon Free 3.2 ZIP SHA-256：`D9ED254BD6AC89D5C5E670383DEC2CB1ACF43A72C62EBF2E4401D039FF6BDA18`。
- VB-CABLE Driver Pack 45 ZIP SHA-256：`B950E39F01AF1D04EA623C8F6D8EB9B6EA5C477C637295FABF20631C85116BFB`。
- 最新綜合唯讀檢查：`docs/wiring-verification-latest.md`，目前 `PASS=15 / WAITING=6 / BLOCKED=0`；WAITING 包含 4 組角色模型 register、VCClient embedded CUDA、Light Host Graillon chain、Voicemeeter B1 訊號、VCClient localhost 與 ONNX CUDA provider。

## 下一個環境步驟

1. 在新 PowerShell 驗證專案 venv 與 `ffmpeg -version`；若 PATH 未刷新，沿用報告中的絕對路徑。
2. 放入具授權乾聲，完成 audit、切片與訓練前檢查。
3. 訓練並把角色 `.pth/.index` 登記到 `models/`。
4. 以角色模型實測 VCClient；若 CUDA 警告導致推論失敗，切換相容的 ONNX/DirectML 或更新前端版本，再做 P2/P3 驗收。
