# AetherTune Agent Reference

這是 AetherTune 專案的 Agent 導航與邊界。人類先讀根目錄 `README.md`；Agent 先讀本檔，再讀與任務直接相關的 `docs/` 或 `backends/` 文件。

## 1. 專案目的

AetherTune 管理兩個研究分組與多個 backend/profile：Streaming VC（保留來源表演）與 Speech Reconstruction（重新生成聲學表演）。`audio-rack/` 與 `benchmarks/` 是跨 backend 的共用基礎設施，不是第五個模型 backend：

| backend/profile | 輸入→輸出 | 是否訓練 | 主要入口／定位 |
|---|---|---:|---|
| RVC + FCPE/RMVPE | source／麥克風 → 即時變聲 → VCClient／虛擬音訊 | 要訓練角色模型 | `docs/model-training-guide.md`；`historical-baseline` |
| Seed-VC upstream | source WAV + reference WAV → output WAV/stream | 不要 | `tools/seed-vc-setup.ps1`、`tools/seed-vc-run.ps1`；`established-baseline` |
| Seed-VC realtime fork | mic → realtime VC → output route | 不要 | `backends/seed-vc-realtime/README.md`；`candidate / PLANNED` |
| MeanVC2 | streaming source + reference → output stream | 不要 | `backends/meanvc2/README.md`；`candidate / PLANNED` |
| CosyVoice2 / CosyVoice3 | text + reference → output WAV | 不要一般角色訓練 | `tools/cosyvoice-infer.py`；2 baseline、3 candidate |
| Breeze TTS 2 | text／reference → Voice Design 或 clone → output WAV | 不要一般角色訓練 | `tools/breeze-tts2-run.ps1`；offline candidate |

不要把 Seed-VC、MeanVC2 或 TTS checkpoint 放進 RVC `.pth/.index` 流程，也不要把 STT → TTS 的重建輸出描述成保留原始聲學表演。所有路線都要接到共用 [`audio-rack/`](audio-rack/) 與 benchmark 契約，但不能因此把尚未實測的 rack 寫成 PASS。

## 2. 讀取順序與 source of truth

1. `README.md`：人類快速入口、選路線與目前缺口。
2. `docs/user-guide.md`：完整人類操作順序。
3. `docs/model-training-guide.md`：RVC 資料與訓練。
4. `docs/operation-guide.md`：Windows audio-rack、VCClient/VST/虛擬路由操作。
5. `docs/live-gate.md`：`LIVE`／`OFFLINE`／`WAITING`／`BLOCKED` 分類。
6. `backends/<name>/README.md`：後端輸入契約、命令與限制。
7. `audio-rack/`、`benchmarks/`：共用 Post-FX、routing 與三層 benchmark 契約。
8. `docs/*verification-latest.md`：實際驗證證據與剩餘風險。
9. `models/*-register.csv`、`dataset/manifests/*`：模型、音訊、來源與 hash 的結構化紀錄。
10. `docs/agent-implementation-status-latest.md`：本輪 Agent 工作的集中狀態表；它不能取代各驗證文件。

若文件與 runtime 證據衝突，以最新可重跑 artifact、實際命令輸出與 verifier 為準，並修正文檔；不要用「模型檔存在」覆蓋 runtime WAITING。

## 3. 目前已知狀態

- RVC：四組角色模型已透過專案 RVC WebUI pipeline 完成 `FCPE + cuda:0` 離線推論並產生非零 WAV；模型 hash／配對 audit `PASS`，但仍是 `candidate`，來源、授權、訓練 metadata、dataset audit 與 VCClient 即時鏈路尚未完成。模型 audit 見 `docs/rvc-model-audit-latest.md`。
- Seed-VC：`offline-v1` 男→女／女→男、60 秒長音檔、`realtime-tiny` 3 block smoke 與 200 block／60 秒 headless GPU benchmark 已 PASS；官方 GUI、PortAudio 麥克風端到端、人工聽測與 10 分鐘以上 realtime 仍 WAITING。
- CosyVoice2：WSL2 Ubuntu 24.04.4 LTS、Python 3.10、模型 snapshot 與 CUDA TTS 輸出已完成；主模型 CUDA PASS，隔離 cuDNN 8 probe 證明 speech tokenizer Node 可用 CUDA，但 CampPlus 上游固定 CPU，因此 frontend 仍是 partial CUDA。
- Breeze TTS 2：WSL2 Python 3.10、Torch 2.9.1+cu128、模型 snapshot、Voice Design／男女 reference clone、`fast-all` CUDA graph 與 project-local SoX runner 已 PASS；flash-attn、system SoX、人工音質評估仍 WAITING。`fast-all` 本機 RTF 約 `11.4196`，不能套用 H100 benchmark。
- MeanVC2、Seed-VC realtime fork、CosyVoice3：目前只有 candidate intake；沒有本機模型、runtime 或 LIVE evidence。
- `LIVE_GATE` validator 已建立，但尚未有完整 mic → backend → audio-rack → virtual route 的本機 PASS。

狀態必須使用 `PASS`、`WAITING`、`PLANNED` 或更明確的 `candidate / unregistered`；不得把未驗證項目改成 `ready`。

## 4. 常用命令

```powershell
Set-Location D:\AetherTune

# 唯讀總覽；只表示檔案／環境存在，不是 E2E 品質驗收
& .\tools\voice-backend-check.ps1

# Seed-VC 已可用的離線路線
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-male-m1.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\male-to-female `
  -Fp16

# RVC 環境與 FCPE 探針
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe tools\fcpe_probe.py --skip-vcclient --artifact artifacts\fcpe-probe.json
& .\.venv\Scripts\python.exe tools\rvc-fcpe-gpu-infer.py `
  --model .\models\weights\Sage_CN_HeroicFemale.pth `
  --index .\models\indexes\Sage_CN_HeroicFemale.index `
  --input .\dataset\reference-voices\voice-male-m1.wav `
  --output .\artifacts\rvc-fcpe-gpu\Sage_CN_HeroicFemale.wav
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\wiring-verification-latest.md

# STT → TTS；不提供 -TextFile 時先跑 Faster-Whisper draft
& .\tools\speech-reconstruction-run.ps1 `
  -InputWav .\dataset\reference-voices\voice-male-m1.wav `
  -Backend cosyvoice `
  -Output cosyvoice-from-stt.wav
# Breeze 使用 -Backend breeze-tts-2；正式 clone 請提供人工核對的 -ReferenceTextFile
```

資料 audit：

```powershell
& .\.venv\Scripts\python.exe tools\dataset_audit.py `
  --root dataset\raw `
  --manifest dataset\manifests\raw-audit.csv `
  --source-register dataset\manifests\source-register.csv `
  --fail-on-invalid
```

## 5. Agent 修改規則

- 先讀取現況與 `git status --short --untracked-files=all`，保留使用者既有變更。
- 只修改任務範圍；權重、音訊、第三方 repo、`.venv`、WSL env 與 artifacts 不應提交。
- 文件用繁體中文；官方上游名稱、命令、revision、license 保持原文。
- 本機檔案編輯使用 `apply_patch`；不要用 shell redirect 覆寫文件。
- 新增 backend/profile 先更新 `README.md`、本檔、`docs/architecture.md`、`docs/voice-conversion-architecture.md`、對應 `backends/` README 與必要 register；候選 intake 不得冒充已安裝 backend。
- 不把下載成功、import 成功、Web UI HTTP 200、provider 清單或模型檔存在寫成音訊 E2E PASS。
- 驗證結果必須寫出實際命令、輸入／模型 hash、device/provider、輸出 artifact、PASS/WAITING/BLOCKED 與未解事項。
- 不保存 API key、密碼、cookie、token 或私人聲音授權資料。

## 6. 回報格式

完成任務時至少回報：

1. 改了哪些檔案與目的。
2. 執行了哪些驗證命令及其結果。
3. 哪些項目是 `PASS`、`WAITING`、`PLANNED`。
4. 使用者下一步應讀哪一份文件或執行哪一個命令。
