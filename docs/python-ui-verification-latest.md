# Python 統一與操作入口驗證

更新：2026-09-27（Asia/Taipei）；Windows／RTX 5060 Ti 16GB。

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
pwsh -NoProfile -File tools/python-runtime-check.ps1 -OutFile artifacts/python310/my-runtime-report.json
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

## UI

控制視窗正在整合與實測；本節未列完成前，不把新 UI 當已驗證。Seed-VC 現有官方 GUI／有效 callback／CABLE loopback PASS 見 [`backend-install-test-latest.md`](backend-install-test-latest.md)。
