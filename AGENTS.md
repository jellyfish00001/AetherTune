# AetherTune Agent Reference

這是 AetherTune 專案的 Agent 導航與邊界。人類先讀根目錄 `README.md`；Agent 先讀本檔，再讀與任務直接相關的 `docs/` 或 `backends/` 文件。

## 1. 專案目的

AetherTune 同時管理三條語音路線：

| backend | 輸入→輸出 | 是否訓練 | 主要入口 |
|---|---|---:|---|
| RVC + FCPE/RMVPE | source／麥克風 → 即時變聲 → VCClient／虛擬音訊 | 要訓練角色模型 | `docs/model-training-guide.md`、`docs/operation-guide.md` |
| Seed-VC | source WAV + reference WAV → output WAV | 不要 | `tools/seed-vc-setup.ps1`、`tools/seed-vc-run.ps1` |
| STT → TTS | source WAV → transcript → CosyVoice／Breeze + reference → output WAV | 不要一般角色訓練 | `backends/speech-reconstruction/README.md` |

不要把 Seed-VC 或 TTS checkpoint 放進 RVC `.pth/.index` 流程，也不要把 STT → TTS 的重建輸出描述成保留原始聲學表演。

## 2. 讀取順序與 source of truth

1. `README.md`：人類快速入口、選路線與目前缺口。
2. `docs/user-guide.md`：完整人類操作順序。
3. `docs/model-training-guide.md`：RVC 資料與訓練。
4. `docs/operation-guide.md`：RVC/VCClient/VST/虛擬路由。
5. `backends/<name>/README.md`：後端輸入契約、命令與限制。
6. `docs/*verification-latest.md`：實際驗證證據與剩餘風險。
7. `models/*-register.csv`、`dataset/manifests/*`：模型、音訊、來源與 hash 的結構化紀錄。

若文件與 runtime 證據衝突，以最新可重跑 artifact、實際命令輸出與 verifier 為準，並修正文檔；不要用「模型檔存在」覆蓋 runtime WAITING。

## 3. 目前已知狀態

- RVC：基礎環境與 FCPE/RMVPE probe 已有證據；四組角色模型存在但 `models/model-register.csv` 尚無資料列。
- Seed-VC：`offline-v1` 男→女與女→男已產生 WAV，manifest 在 `artifacts/seed-vc/`；realtime tiny 與人工聽測尚未完成。
- CosyVoice：WSL2 Ubuntu 24.04.4 LTS、Python 3.10、模型 snapshot 已建立；WSL CUDA tensor gate WAITING，不能宣稱 TTS 可用。
- Breeze TTS 2：PLANNED。

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
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\wiring-verification-latest.md
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
