# Python 統一與操作入口驗證

更新：2026-09-27（Asia/Taipei）；Windows／RTX 5060 Ti 16GB。

Seed-VC callback 狀態補充（2026-09-27）：本頁較早的 `python-ui-final` run 曾得到非零 callback WAV／CABLE loopback；後續官方 GUI callback 重跑的兩份報告未通過 finite/non-zero gate，整體最新狀態維持 `WAITING`。前一結果只代表其特定 run，不覆蓋後續缺口；詳見 [`seed-vc-verification-latest.md`](../backends/seed-vc-verification-latest.md)。

## Python：PASS

專案管理的七個環境統一 **Python 3.10.x**；Windows 3.10.11、WSL 3.10.20。根目錄 `.python-version` 固定 minor version；各 backend 保留自己的 venv，避免 Gradio、Transformers、x-transformers 套件衝突。不更動其他專案、系統 Python 或 VCClient 內嵌 runtime。

| Backend | Python 路徑 | Python | CUDA／pip check |
|---|---|---|---|
| RVC | `.venv/Scripts/python.exe` | 3.10.11 | PASS；Torch 2.7.1+cu128 |
| Seed-VC | `tools/venvs/seed-vc/Scripts/python.exe` | 3.10.11 | PASS；Torch 2.7.1+cu128／Tk 8.6.12 |
| MeanVC2 | `tools/venvs/meanvc2/Scripts/python.exe` | 3.10.11 | PASS；Torch 2.7.1+cu128 |
| X-VC | `tools/venvs/xvc/Scripts/python.exe` | 3.10.11 | PASS；Torch 2.7.1+cu128 |
| CosyVoice2 | `tools/venvs/cosyvoice-wsl/bin/python` | 3.10.20 | PASS；Torch 2.7.1+cu128 |
| Breeze TTS 2 | `tools/venvs/breeze-tts-wsl/bin/python` | 3.10.20 | PASS；Torch 2.9.1+cu128 |
| Faster-Whisper STT | `tools/venvs/stt-wsl/bin/python` | 3.10.20 | PASS；CTranslate2 4.8.2／CUDA device count > 0 |

唯讀重跑（指定 `OutFile` 才保存報告）：

```powershell
& tools/external/powershell/pwsh.exe -NoProfile -File tools/python-runtime-check.ps1 -OutFile artifacts/python310/my-runtime-report.json
```

本輪 exit 0，7/7 PASS：`artifacts/python310/runtime-report-pass.json`；console `artifacts/python310-runtime-report-pass.log`。這表示版本、CUDA 可見與套件一致性，音訊證據另列下面。

MeanVC2 改用 3.10 相容的 SciPy 1.12.0／Matplotlib 3.7.5。RVC 沿用固定 upstream `81eed5e8f68b6bed1789f682fe78cdd324495afc` 的直接依賴 ranges，resolver 選 3.10 wheels；requirements 歷史檔名的 `py312` 不代表實際版本。RVC 安裝入口為 `tools/rvc-setup.ps1`。

WSL 三個環境補齊 `ensurepip`。CosyVoice 舊 `openai-whisper==20231117` 的 `triton<3` 與 Torch 2.7.1 所需 3.3.1 衝突，改官方 `20250625`，未降低 CUDA Torch；[Whisper 官方依賴](https://github.com/openai/whisper/blob/main/pyproject.toml) 已放寬為 `triton>=2`，setup 保留相容性修正。

## 遷移後實際音訊：PASS

輸入 `dataset/reference-voices/voice-male-m1.wav` SHA-256 `3A4A5A048154CFF60D717FC1FCE929EBEBC887F7C9222C56222DAD48ADB60662`。Mean reference `voice-female-f1.wav` SHA-256 `37976F69F73FB13D6FEFAF80268794D545D6E19BE5059437DB067455A795F406`。

| 測試 | Device | WAV／RMS | 結果與 SHA-256 |
|---|---|---|---|
| MeanVC2 40ms 男→女 | VC／speaker／vocoder CUDA 0；ASR CPU | `artifacts/python310/meanvc2/output.wav`；RMS 0.063649 | PASS；`A976AA1993C64BEFA1AC5529564135A951759B6016C3301C91DFAB3380866ED3`，與 3.11 相同 |
| RVC Sage FCPE | CUDA 0 | `artifacts/python310/rvc/Sage.wav`；14.86s／48kHz／finite／RMS 0.074640 | PASS；`BC82BFDA82B0BB3718D6ACC7B069A529C05C279A0AC5DD79C3FDE5AB42503015` |
| CosyVoice2 Whisper 更新後 zero-shot | 主模型 CUDA，frontend partial CUDA | `artifacts/python310/cosyvoice/output.wav`；10.76s／24kHz／RMS 0.072311 | PASS；`E92B0516F2EAEE16911FE248832695A331398B0D1B8CB5D26A3EF42C9603908B` |

實際命令（exit 0）：

```powershell
& tools/venvs/meanvc2/Scripts/python.exe tools/meanvc2-run.py --source dataset/reference-voices/voice-male-m1.wav --target dataset/reference-voices/voice-female-f1.wav --output artifacts/python310/meanvc2/output.wav --model 40ms
& .venv/Scripts/python.exe tools/rvc-fcpe-gpu-infer.py --model models/weights/Sage_CN_HeroicFemale.pth --index models/indexes/Sage_CN_HeroicFemale.index --input dataset/reference-voices/voice-male-m1.wav --output artifacts/python310/rvc/Sage.wav
```

模型 hash／revision／device 見 `output.run-evidence.json` 與 `Sage.json`；console 為 `artifacts/{meanvc2,rvc}-python310-infer.log`。RVC 模型 SHA-256 `57C2A770211A7F08C7AE973E6343006547CA4400752CE4DA17842117E1E556AD`，index `4D9DDA9D71D9BB6A65283718F0390AA45951A818E69F57B8686583AC31BB9AF9`，權重未更換。

CosyVoice 重跑命令：

```powershell
wsl.exe -d Ubuntu -- env PYTHONPATH=/mnt/d/AetherTune/tools/external/CosyVoice:/mnt/d/AetherTune/tools/external/CosyVoice/third_party/Matcha-TTS HF_HUB_OFFLINE=1 /mnt/d/AetherTune/tools/venvs/cosyvoice-wsl/bin/python -u /mnt/d/AetherTune/tools/cosyvoice-infer.py --model-dir /mnt/d/AetherTune/models/speech-reconstruction/cosyvoice --prompt-audio /mnt/d/AetherTune/tools/external/CosyVoice/asset/zero_shot_prompt.wav --prompt-text-file /mnt/d/AetherTune/tools/fixtures/cosyvoice/prompt-text.txt --text-file /mnt/d/AetherTune/tools/fixtures/cosyvoice/target-text.txt --output /mnt/d/AetherTune/artifacts/python310/cosyvoice/output.wav --fp16
```

CosyVoice prompt SHA-256 `C7B31D6DBE7CC6A716DDED00550DB5B50940BF209E424E4AD207B12E657C8FF6`；`llm.pt` SHA-256 `B144EF55B51CE8CFB79A73C90DBBA0BDABA4E451C0EBCFAB20F769264F84A608`。完整驗證 `artifacts/python310/cosyvoice/output.json`，console `artifacts/python310-cosyvoice-infer.log`。未把 frontend 部分 CPU 改稱全 CUDA。

## 回復方式

舊環境保留於 `tools/venvs/meanvc2-py311-backup` 與 `.venv-py312-backup`，全部 ignored。需回復時先關閉本專案工作，將新環境改名保存，再將 backup 改回原名；不需刪權重或重新下載。

## UI 功能與實測

操作入口 `AetherTune.cmd`／`tools/aethertune-ui.py`。使用標準庫 Tkinter，後端仍由各自 Python 子程序執行；不新增常駐服務、Web framework、資料庫或全域 registry。

1. Seed-VC：選 Reference、Host API、input/output 與八項參數，按控制台「啟動」開官方 GUI，再按 `Start Voice Conversion`；通話結束按官方 `Stop Voice Conversion`，再關官方視窗。
2. MeanVC2／X-VC：選 source／Reference；Mean 選 40ms／120ms，X 設 current／chunk／future／smooth；按「啟動」，完成 PASS 後可「開啟 WAV」或「開啟結果資料夾」。此控制台的兩條路線是檔案轉換。
3. 控制台「停止」清理自己啟動且仍存活的 PID 樹；不會停止其他專案。偏好存在 ignored `artifacts/ui/settings.json`，每次輸出在獨立 UUID 目錄。

要在耳機直接聽變聲，Seed output 選耳機／喇叭；要送往通話程式，output 選 `CABLE Input`，通話程式麥克風選 `CABLE Output`。VB-CABLE 本身不自動提供耳機監聽；不必先更動 Windows 預設音訊裝置。

| 本輪測試 | 結果／證據 |
|---|---|
| `AetherTune.cmd` 一般 Windows 實開 | PASS；從 `C:/Users/User`、machine/user PATH 執行 `cmd /c D:/AetherTune/AetherTune.cmd`，Tk 視窗與 Reference、裝置、八參數、四按鈕可見；`artifacts/ui-tests/cmd-launch-report.json`；截圖 `C:/Users/User/AppData/Local/Temp/codex-shot-2026-09-27_07-38-05.png`。入口改 ASCII／CRLF，修正舊 UTF-8 batch 解析失敗 |
| MeanVC2 真實 Tk 啟動按鈕、120ms | PASS；`artifacts/ui-tests/mean-report.json`；14.75s／RMS 0.079083／hash `846614B8FBB40E7ABACA33883FBD4617C309BE98E5DDA463B899478298950D3E`；output/evidence 在 `artifacts/ui/6117ef5b-92c6-48f4-840e-5cbde3bb610e/` |
| X-VC 真實 Tk 啟動按鈕、160/2400/80/20 | PASS；`artifacts/ui-tests/xvc-report.json`；14.88s／RMS 0.034192／hash `A51DADB11B608651B96FED4DC2DCC518DC97B417FD49AFA7C39BB01FDFE47CCF`；output/evidence 在 `artifacts/ui/dde4b7ad-9491-47cb-b8fc-824b009d5826/` |
| Seed 控制台 → 官方 GUI，普通 machine/user PATH | PASS；沒有 Codex PATH；本機 PowerShell 啟動。MME／HyperX／CABLE／Reference 和 10/.7/3/.3/.04/5/.5/.02 八參數核對；`artifacts/ui-tests/seed-ordinary-path-test.log`、`seed-report.json`、`seed-ui.log`；官方 GUI 截圖 `C:/Users/User/AppData/Local/Temp/codex-shot-2026-09-27_07-22-59.png` |
| 停止程序與最新版面 | PASS；`artifacts/ui-tests/final-layout-stop/stop-report.json`；1000×684，四按鈕可見；按鈕 y=708，底部 733，小於工作列安全界線 804；已停止的子程序無殘留 |
| 開啟有效 WAV／結果資料夾 | PASS；兩個 Tk button invoke 返回 1，已交給系統預設程式／Explorer；`artifacts/ui-tests/result-buttons-report.json`。這不代替人工聽評 |
| 無效 Seed slider 範圍／CE < DiT | BLOCKED（預期拒絕）；valid preflight exit 0，兩負案 exit 1，`artifacts/python310/seed-settings-*.log` |
| X smooth > current | BLOCKED（預期拒絕）；argparse exit 2，不載入模型，`artifacts/ui-tests/invalid-smooth.log` |

檔案轉換只在 exit 0 且 backend、輸出路徑、SHA-256、finite／RMS／duration 和 WAV header 均吻合時才顯示 PASS；沒有用 exit 0 或 GUI 可開啟代替有效音訊。Mean／X code／model／input hash 與 device 在各 `run-evidence.json`；模型與 source/reference 未更換。

較早的 tiny GUI callback／CABLE run（`python-ui-final`）exit 0：17/17 設定、CUDA 0、4 CPU worker、非零 finite 音訊且與輸入不同。Callback RMS `0.015999486`／hash `32C3333E14215BB2801D44FEE11DDE5E1B9A0B503B98A4FF022655B5A1E321FA`；CABLE RMS `0.013963485`／hash `A6466E8F77B5F2F9CD73C036DFB40FAEB0CC8920D5CA95E988C8AFB8B00251B3`。checkpoint hash `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`，source revision `51383efd921027683c89e5348211d93ff12ac2a8`。輸入為前述 male-m1 注入 callback，reference female-young-f004；來源不是本次使用者實體說話。後續 `20260927-phase2-0ad07c8e` 兩次 callback 重跑分別未通過 finite/non-zero gate，故當前有效輸出狀態是 `WAITING`，見 [`seed-vc-verification-latest.md`](../backends/seed-vc-verification-latest.md)。

```powershell
& tools/venvs/seed-vc/Scripts/python.exe -u tools/seed-vc-gui-userflow-test.py --profile realtime-tiny --case female-young-f004 --capture-loopback --output artifacts/seed-vc/python-ui-final
# 可重跑的真實 Tk 控制台檔案轉換／停止測試（每次指定新 output）
& tools/venvs/seed-vc/Scripts/python.exe tools/aethertune-ui-userflow-test.py --backend mean --output artifacts/ui-tests/my-mean
& tools/venvs/seed-vc/Scripts/python.exe tools/aethertune-ui-userflow-test.py --backend xvc --output artifacts/ui-tests/my-xvc
& tools/venvs/seed-vc/Scripts/python.exe tools/aethertune-ui-userflow-test.py --backend stop --output artifacts/ui-tests/my-stop
```

Seed artifacts：`artifacts/seed-vc/python-ui-final/gui-userflow-report.json` 與 case WAVs；console `artifacts/ui-tests/seed-callback-loopback-final.log`；執行中實際 GUI 截圖 `C:/Users/User/AppData/Local/Temp/codex-shot-2026-09-27_07-26-27.png`。本次第一個非零 callback `10.176 秒`，不保證每次冷啟動 <= 5 秒。

## PowerShell 啟動依賴

本機原本只有 Codex 環境可解析 PowerShell 7；為一般 Windows session 安裝 [Microsoft 官方 portable ZIP](https://github.com/PowerShell/PowerShell/releases/tag/v7.6.6) 到 ignored `tools/external/powershell`。版本 7.6.6，ZIP SHA-256 `02FE458BE20493FBDF43F61EA20610B811EE6C738AB1676C61B9CFCD1A33C860`（官方 release digest）；未修改系統 PATH。UI 優先使用此 runtime，其次已安裝的 pwsh。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/powershell-setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/powershell-setup.ps1 -VerifyOnly
```

實際安裝 exit 0／版本檢查 PASS：`artifacts/ui-tests/powershell-setup-final.log`。新 `.cmd` 入口的一般 Windows 實開也已 PASS；控制台留在待命狀態，沒有自動開始麥克風轉換。

## 邊界

本機基本安裝、設定、有效模型音訊與 synthetic VB-CABLE 已 PASS。完整實體 mic → backend → rack → route、600 秒無 dropout 與人工音質仍 WAITING；Mean／X UI 沒有宣稱 mic 模式。全新 Windows 主機的完整 bootstrap 另驗，Git 不含模型／WAV／venv。
