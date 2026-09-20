# AetherTune Agent Reference

這是 AetherTune 專案的 Agent 導航與邊界。人類先讀根目錄 `README.md`；Agent 先讀本檔，再讀與任務直接相關的 `docs/` 或 `backends/` 文件。

## 1. 專案目的

AetherTune 管理四個 backend、三條語音路線：

| backend | 輸入→輸出 | 是否訓練 | 主要入口 |
|---|---|---:|---|
| RVC + FCPE/RMVPE | source／麥克風 → 即時變聲 → VCClient／虛擬音訊 | 要訓練角色模型 | `docs/model-training-guide.md`、`docs/operation-guide.md` |
| Seed-VC | source WAV + reference WAV → output WAV | 不要 | `tools/seed-vc-setup.ps1`、`tools/seed-vc-run.ps1` |
| CosyVoice2 | source WAV → reference clone TTS → output WAV | 不要一般角色訓練 | `tools/cosyvoice-infer.py` |
| Breeze TTS 2 | text／reference → Voice Design 或 clone → output WAV | 不要一般角色訓練 | `tools/breeze-tts2-run.ps1` |

不要把 Seed-VC 或 TTS checkpoint 放進 RVC `.pth/.index` 流程，也不要把 STT → TTS 的重建輸出描述成保留原始聲學表演。

## 2. 讀取順序與 source of truth

1. `README.md`：人類快速入口、選路線與目前缺口。
2. `docs/user-guide.md`：完整人類操作順序。
3. `docs/model-training-guide.md`：RVC 資料與訓練。
4. `docs/operation-guide.md`：RVC/VCClient/VST/虛擬路由。
5. `backends/<name>/README.md`：後端輸入契約、命令與限制。
6. `docs/*verification-latest.md`：實際驗證證據與剩餘風險。
7. `models/*-register.csv`、`dataset/manifests/*`：模型、音訊、來源與 hash 的結構化紀錄。
8. `docs/agent-implementation-status-latest.md`：本輪 Agent 工作的集中狀態表；它不能取代各驗證文件。

若文件與 runtime 證據衝突，以最新可重跑 artifact、實際命令輸出與 verifier 為準，並修正文檔；不要用「模型檔存在」覆蓋 runtime WAITING。

## 3. 目前已知狀態

- RVC：四組角色模型已透過專案 RVC WebUI pipeline 完成 `FCPE + cuda:0` 離線推論並產生非零 WAV；模型 hash／配對 audit `PASS`，但仍是 `candidate`，來源、授權、訓練 metadata、dataset audit 與 VCClient 即時鏈路尚未完成。模型 audit 見 `docs/rvc-model-audit-latest.md`。
- Seed-VC：`offline-v1` 男→女／女→男、60 秒長音檔與 `realtime-tiny` headless GPU block benchmark 已 PASS；官方 GUI、PortAudio 麥克風端到端、人工聽測與長時間 realtime 仍 WAITING。
- CosyVoice2：WSL2 Ubuntu 24.04.4 LTS、Python 3.10、模型 snapshot 與 CUDA TTS 輸出已完成；主模型 CUDA PASS，隔離 cuDNN 8 probe 證明 speech tokenizer Node 可用 CUDA，但 CampPlus 上游固定 CPU，因此 frontend 仍是 partial CUDA。
- Breeze TTS 2：WSL2 Python 3.10、Torch 2.9.1+cu128、模型 snapshot、Voice Design／男女 reference clone 與 `fast-all` CUDA graph 輸出已 PASS；flash-attn、SoX、人工音質評估仍 WAITING。`fast-all` 本機 RTF `11.4196`，不能套用 H100 benchmark。

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
- 新增 backend 先更新 `README.md`、本檔、`docs/voice-conversion-architecture.md`、對應 `backends/` README 與 register，再新增工具。
- 不把下載成功、import 成功、Web UI HTTP 200、provider 清單或模型檔存在寫成音訊 E2E PASS。
- 驗證結果必須寫出實際命令、輸入／模型 hash、device/provider、輸出 artifact、PASS/WAITING/BLOCKED 與未解事項。
- 不保存 API key、密碼、cookie、token 或私人聲音授權資料。

## 6. 回報格式

完成任務時至少回報：

1. 改了哪些檔案與目的。
2. 執行了哪些驗證命令及其結果。
3. 哪些項目是 `PASS`、`WAITING`、`PLANNED`。
4. 使用者下一步應讀哪一份文件或執行哪一個命令。
