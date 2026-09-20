# AetherTune

低延遲、自然微電音即時變聲系統的專案骨架與驗證文件。

目前狀態：`Wiring deployed / role dataset and model pending`

## 目標管線

```text
實體麥克風
  → RVC 訓練／推論
  → VCClient 即時轉換
  → VB-CABLE
  → VST host 微量後製
  → 虛擬音訊路由
  → Discord／遊戲語音／OBS
```

本倉庫只保存設定、工具腳本、來源審核與可重現驗證紀錄。原始音訊、模型權重、索引檔與第三方執行包預設留在本機，不進 Git。

## 目錄

```text
dataset/
  raw/          # 有授權的原始乾聲（不進 Git）
  sliced/       # 5–15 秒切片（不進 Git）
  augmented/    # 變調或其他擴增結果（不進 Git）
models/
  weights/      # .pth（不進 Git）
  indexes/      # .index（不進 Git）
  model-register.csv # 模型配對、版本、批次與 hash
tools/          # 本專案可重用的小工具與外部工具說明
docs/           # 架構、來源、環境與驗證文件
```

資料進入後，先執行：

```powershell
& .\.venv\Scripts\python.exe tools\dataset_audit.py --root dataset\raw --manifest dataset\manifests\raw-audit.csv --source-register dataset\manifests\source-register.csv --fail-on-invalid
```

此命令只建立 metadata manifest，不會修改原始音檔。

## 目前證據

- 本機 GPU：NVIDIA GeForce RTX 5060 Ti，16,311 MiB 顯存；`nvidia-smi` driver/KMD 610.88、CUDA UMD 13.3。
- 專案隔離 Python：`.venv\Scripts\python.exe`，Python 3.12.10；既有 Hermes agent venv 保持不動。
- FFmpeg：Gyan FFmpeg 9.0.1 已安裝並以絕對路徑驗證 `ffmpeg`/`ffprobe`；目前執行中的 PowerShell 尚未刷新 PATH。
- RVC：官方倉庫已固定到 `81eed5e8f68b6bed1789f682fe78cdd324495afc`，CUDA 12.8 依賴已安裝且 Torch 可識別 RTX 5060 Ti。
- RVC runtime：HuBERT base 與 RMVPE 已下載並完成 hash/合成音 f0 smoke test；尚無角色 `.pth`/`.index`。
- VB-CABLE、Voicemeeter、Light Host Modern、Graillon Free 3.2：已安裝並完成存在性／裝置列舉驗證。
- VCClient `2.1.4-alpha cuda`：已解壓、首次初始化、本機 Web UI `HTTP 200`；尚未載入本專案角色 `.pth/.index`。
- VCClient embedded Torch：`2.7.0+cu118`；RTX 5060 Ti `sm_120` 的角色推論仍需獨立驗證，不能以專案 `.venv` 的 `cu128` PASS 代替。
- Git 倉庫：空倉庫，尚無 commit；本次只建立規格與驗證骨架。

詳細結果見 [`docs/local-environment.md`](docs/local-environment.md)、[`docs/source-audit.md`](docs/source-audit.md) 與 [`docs/verification-plan.md`](docs/verification-plan.md)。

完整操作順序見 [`docs/operation-guide.md`](docs/operation-guide.md)；模組替代方案與選擇理由見 [`docs/decision-log.md`](docs/decision-log.md)。

## 重要邊界

規格中的「100% 開源免費」需拆開表述：RVC、Audio Slicer、UVR、Carla 等可採開源元件；MAutoPitch、Voicemeeter、VB-CABLE 等則應視為免費／免費授權的第三方元件，不應宣稱全部為開源。所有聲音資料、模型與角色聲線都必須先確認使用權。

## 下一階段

1. 由使用者確認資料來源與聲音使用權。
2. 將乾聲放入 `dataset/raw/`，完成 audit、切片與 RVC 訓練。
3. 將訓練產出的 `.pth` 與 `.index` 放入 `models/weights/`、`models/indexes/`。
4. 依 [`docs/operation-guide.md`](docs/operation-guide.md) 啟動 VCClient、Light Host、路由，再做 P3 loopback/Discord/OBS 驗收。

可重跑的唯讀檢查：

```powershell
Set-Location D:\AetherTune
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\wiring-verification-latest.md
```

最新檢查報告見 [`docs/wiring-verification-latest.md`](docs/wiring-verification-latest.md)；部署與限制報告見 [`docs/wiring-deployment-report.md`](docs/wiring-deployment-report.md)。
