# CosyVoice 最新驗證

更新日期：2026-09-21（Asia/Taipei）

## 結論

- CosyVoice2 官方 zero-shot TTS：`PASS`，已在 WSL2 RTX 5060 Ti 產生可解碼 WAV。
- Faster-Whisper STT：`PASS`（CPU draft），男女 reference 均成功辨識為日文。
- CosyVoice2 男／女 reference clone：`PASS`（runtime）；transcript 仍標為 STT draft，尚需人工逐字確認。
- Breeze TTS 2：另見 [`breeze-tts2-verification-latest.md`](breeze-tts2-verification-latest.md)，已完成安裝與輸出測試。

因此現在可以直接試 CosyVoice2 的離線 TTS、男女 reference clone 與統一 STT → TTS wrapper；完整流程的剩餘品質 gate 是人工確認 STT transcript 與聽測。

## 實際證據

| Gate | 結果 | 證據 |
|---|---|---|
| WSL Python／Torch | PASS | Python 3.10.20、Torch `2.7.1+cu128` |
| GPU runtime | PASS | `torch.cuda.is_available=True`；`NVIDIA GeForce RTX 5060 Ti` |
| CosyVoice2 class import | PASS | `from cosyvoice.cli.cosyvoice import CosyVoice2` |
| Model load | PASS | 本機 `CosyVoice2-0.5B` 載入成功；`speakers=[]` 對 zero-shot 是預期狀態 |
| Zero-shot TTS | PASS | [cosyvoice-official-zero-shot.wav](/D:/AetherTune/artifacts/speech-reconstruction/cosyvoice-official-zero-shot.wav)；24 kHz、10.76 秒、516,558 bytes |
| Male reference clone | PASS（runtime） | `cosyvoice-clone-male.wav`；24 kHz、12.64 秒；SHA-256 `6b43f5a6d59e0c1d6d64d364415f13aa9df3606020b323e1d6bb187f0acb9712` |
| Female reference clone | PASS（runtime） | `cosyvoice-clone-female.wav`；24 kHz、14.72 秒；SHA-256 `6679331a48fc0f4e79c4840945b2a257185c64bb726fb5a621b3f94f103145b6` |
| Output hash | PASS | `e92b0516f2eaee16911fe248832695a331398b0d1b8cb5d26a3ef42c9603908b` |
| Inference speed | PASS（離線） | load 30.13 s、inference 12.98 s、RTF `1.2059` |
| FFmpeg decode | PASS | WAV 可解碼，無 error |
| ONNX frontend CUDA provider | WAITING（非阻塞） | `libcudnn.so.8` 缺失，frontend fallback 到 CPU；主模型仍以 CUDA 完成輸出 |
| Faster-Whisper STT | PASS（draft） | `artifacts/stt/voice-male-m1.json`、`voice-female-f1.json`；language=`ja` |
| Exact transcript 人工核對 | WAITING | 女聲 STT 有「いっている／言っている」文字差異；clone smoke 已完成，但正式 voice clone 仍應人工聽核 |
| Unified `speech-reconstruction-run.ps1` | PASS | `cosyvoice-wrapper-smoke-fixed.wav`、24 kHz、CUDA runtime、workflow manifest |

## 可重跑命令

以下命令在 PowerShell 執行；需要 WSL2 Ubuntu、CosyVoice 模型與專用 venv：

```powershell
Set-Location D:\AetherTune
wsl.exe -d Ubuntu -- bash -lc 'set -e; unset CUDA_VISIBLE_DEVICES; export PYTHONPATH=/mnt/d/AetherTune/tools/external/CosyVoice:/mnt/d/AetherTune/tools/external/CosyVoice/third_party/Matcha-TTS; export HF_HUB_OFFLINE=1; /mnt/d/AetherTune/tools/venvs/cosyvoice-wsl/bin/python -u /mnt/d/AetherTune/tools/cosyvoice-infer.py --model-dir /mnt/d/AetherTune/models/speech-reconstruction/cosyvoice --prompt-audio /mnt/d/AetherTune/tools/external/CosyVoice/asset/zero_shot_prompt.wav --prompt-text-file /mnt/d/AetherTune/tools/fixtures/cosyvoice/prompt-text.txt --text-file /mnt/d/AetherTune/tools/fixtures/cosyvoice/target-text.txt --output /mnt/d/AetherTune/artifacts/speech-reconstruction/cosyvoice-official-zero-shot.wav --fp16'
```

輸入契約：

- `--prompt-audio` 和 `--prompt-text-file` 必須是同一段 reference 的 audio／exact transcript。
- `--text-file` 是要重新說出的文字；可換成自己的 UTF-8 文字檔。
- runner 會在輸出 WAV 旁寫入同名 JSON，保存 input／output hash、runtime、RTF。
- 不要用猜測文字、空白文字或不相符的 transcript 充當 voice clone 證據。

## Setup 與訓練邊界

```powershell
Set-Location D:\AetherTune
& .\tools\cosyvoice-setup.ps1 -DownloadModel
```

預設 setup 是 inference mode，會從專用 `tools/venvs/cosyvoice-wsl` 移除 DeepSpeed，避免沒有 CUDA toolkit 時 import 直接失敗。CosyVoice 的訓練不是本專案目前的 PASS；若要研究訓練，使用 `-Training` 並準備獨立 CUDA toolkit／`CUDA_HOME` 環境，不要修改 RVC `.venv`。

CosyVoice source 需要把下列兩個路徑放入 `PYTHONPATH`：

```text
/mnt/d/AetherTune/tools/external/CosyVoice
/mnt/d/AetherTune/tools/external/CosyVoice/third_party/Matcha-TTS
```

## 尚未完成

1. 人工逐字聽核男女 reference transcript，確認 draft 是否為 exact transcript。
2. 完成 CosyVoice 男／女輸出人工聽測與相似度備註。
3. 若需要 ONNX frontend GPU 加速，在 WSL 安裝相容 cuDNN 8；目前 CPU fallback 可用但不是 GPU frontend PASS。
