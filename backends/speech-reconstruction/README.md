# 語音重建：STT → TTS

這條路線是：

```text
來源音檔 → STT transcript → TTS（文字 + 參考聲音）→ 重建音檔
```

它會重新生成笑聲、呼吸、停頓與節奏，不應和 RVC／Seed-VC 用同一套品質標準比較。

## 目前狀態

| 元件 | 狀態 | 已驗證內容 |
|---|---|---|
| Faster-Whisper STT | PASS（CPU） | small model 成功辨識男／女 reference，輸出 JSON transcript |
| CosyVoice2 0.5B | PASS（CUDA） | 官方 zero-shot 與男／女 reference clone 都產生 24 kHz WAV |
| Breeze TTS 2 | PASS（CUDA） | Voice Design 男／女與 reference clone 男／女均產生 24 kHz WAV |

模型與環境分開保存：

- CosyVoice：`tools/venvs/cosyvoice-wsl`、`models/speech-reconstruction/cosyvoice/`
- Breeze：`tools/venvs/breeze-tts-wsl`、`models/speech-reconstruction/breeze-tts-2/`
- STT：`tools/venvs/stt-wsl`、模型由 Faster-Whisper cache 管理

不要把這些依賴安裝到現有 RVC `.venv`。

## 直接使用

### 一鍵 STT → TTS

未提供 `-TextFile` 時，wrapper 會先用 Faster-Whisper 對輸入音檔產生 draft transcript，再呼叫指定後端。未提供 `-ReferenceAudio` 時，會暫時把輸入音檔當作 reference，適合 smoke test；正式 clone 請明確提供人工核對的 `-ReferenceTextFile`。

```powershell
Set-Location D:\AetherTune
& .\tools\speech-reconstruction-run.ps1 `
  -InputWav .\dataset\reference-voices\voice-male-m1.wav `
  -Backend cosyvoice `
  -Output cosyvoice-from-stt.wav
```

`-Backend` 可選 `cosyvoice` 或 `breeze-tts-2`。輸出預設位於 `artifacts/speech-reconstruction/`，旁邊會有後端 JSON 與 `.workflow.json`；workflow 會保留 STT draft 與 `manual_review_required=true`。

### CosyVoice2

```powershell
Set-Location D:\AetherTune
wsl.exe -d Ubuntu -- bash -lc 'set -e; unset CUDA_VISIBLE_DEVICES; export PYTHONPATH=/mnt/d/AetherTune/tools/external/CosyVoice:/mnt/d/AetherTune/tools/external/CosyVoice/third_party/Matcha-TTS; export HF_HUB_OFFLINE=1; /mnt/d/AetherTune/tools/venvs/cosyvoice-wsl/bin/python -u /mnt/d/AetherTune/tools/cosyvoice-infer.py --model-dir /mnt/d/AetherTune/models/speech-reconstruction/cosyvoice --prompt-audio /mnt/d/AetherTune/dataset/reference-voices/voice-male-m1.wav --prompt-text-file /mnt/d/AetherTune/tools/fixtures/cosyvoice/reference-male-text.txt --text-file /mnt/d/AetherTune/tools/fixtures/breeze-target-text.txt --output /mnt/d/AetherTune/artifacts/speech-reconstruction/cosyvoice-clone-male.wav --fp16'
```

女聲測試只需交換 `voice-male-m1.wav`、`reference-male-text.txt` 與輸出檔名。

### Breeze TTS 2

Voice clone：

```powershell
Set-Location D:\AetherTune
& .\tools\breeze-tts2-run.ps1 `
  -TextFile .\tools\fixtures\breeze-target-text.txt `
  -ReferenceAudio .\dataset\reference-voices\voice-male-m1.wav `
  -ReferenceTextFile .\tools\fixtures\breeze-reference-male-text.txt `
  -Output .\artifacts\speech-reconstruction\breeze-clone-male.wav
```

Voice Design 不需要 reference：

```powershell
& .\tools\breeze-tts2-run.ps1 `
  -TextFile .\tools\fixtures\breeze-target-text.txt `
  -Instruction '一位溫柔明亮的成年女性，聲音清晰自然，語氣親切而帶有溫暖笑意。' `
  -CfgScale 4 `
  -Output .\artifacts\speech-reconstruction\breeze-design-female.wav
```

每次輸出旁會產生同名 JSON，記錄模型、reference hash、裝置、RTF 與輸出 hash。

### 安裝／重新建立環境

```powershell
& .\tools\stt-setup.ps1
& .\tools\cosyvoice-setup.ps1 -DownloadModel
& .\tools\breeze-tts2-setup.ps1 -DownloadModel
```

Breeze 官方 source revision、model snapshot 與 license 證據見 [`docs/breeze-tts2-verification-latest.md`](../../docs/breeze-tts2-verification-latest.md)。Breeze model weights、derivatives 與 self-hosted outputs 只限 research/non-commercial；不可當成商用授權。

## Transcript 規則

Faster-Whisper 的輸出是 `STT draft`，voice clone 前仍應人工核對 reference audio。不能用空白、猜測或不相符文字。現有男女 reference 的 STT evidence 位於 `artifacts/stt/`，fixture 位於 `tools/fixtures/`。

## 已知限制

- Breeze eager 與 `-FastAll` CUDA graph 都已在本機 RTX 5060 Ti 產生 WAV；`fast-all` 實測 RTF `11.4196`，官方 H100 benchmark 的 RTF 不適用本機。
- Breeze `flash-attn==2.8.3` 已嘗試安裝但仍無法 import，現在使用 manual PyTorch path；不要把 `-AttentionImplementation flash_attention_2` 當成可用預設。
- Breeze system SoX 仍未安裝（sudo 需要密碼），但已完成 `artifacts/sox-local/` 的 SoX `14.4.2` portable extraction；runner 會自動注入 local PATH／LD_LIBRARY_PATH，該目錄不存在時才回到系統 SoX。
- CosyVoice 主模型 CUDA 已 PASS；`tools/cosyvoice-frontend-cudnn8-probe.ps1` 可用隔離 cuDNN 8 library path 重跑 speech tokenizer 的實際 ONNX Node provider CUDA 證據，但上游 CampPlus embedding 明確固定 CPU，因此目前是 partial frontend GPU，不是全 frontend GPU。證據見 [`docs/cosyvoice-verification-latest.md`](../../docs/cosyvoice-verification-latest.md)。
