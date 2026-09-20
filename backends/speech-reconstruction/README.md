# 語音重建：STT → TTS

這條路線不是直接保留原始聲學內容的 VC，而是：

```text
來源音檔 → STT transcript → TTS（文字 + 參考聲音）→ 重建音檔
```

用途是比較內容重建、跨語言、語氣控制與聲線相似度。原始笑聲、呼吸、停頓與說話節奏可能被改寫，所以要和 RVC／Seed-VC 分開評估。

## TTS backends

- **CosyVoice 2 0.5B**：官方開源、Apache-2.0 model card；支援 zero-shot voice cloning、中文／英文與串流。先作為本專案的通用 TTS 基線。
- **Breeze TTS 2**：支援中文／英文、voice clone、voice design、voice direction；官方 model weights 與 self-hosted outputs 為 research/non-commercial，且目前 quick start 以 Linux + CUDA 為支援環境。Windows 端建議 WSL2，不把它標成原生 Windows PASS。

## STT

STT 是獨立步驟，先預留 Faster-Whisper 或 FunASR。參考聲音若要送入 CosyVoice／Breeze 的 voice clone，必須保留與 reference audio 相符的 transcript；不能把空白或猜測文字當成有效證據。

## 本機狀態

CosyVoice2-0.5B 目前在 `models/speech-reconstruction/cosyvoice/` 有 12 個必要模型檔案（3,864,103,224 bytes），並建立 WSL2 Ubuntu 的 `tools/venvs/cosyvoice-wsl` Python 3.10.20 environment。官方 requirements 已安裝，Torch 已對齊到 `2.7.1+cu128`；官方 zero-shot TTS 已在 RTX 5060 Ti 產生可解碼 WAV，狀態為 `PASS`。完整 STT→TTS 尚未完成，因為 STT 與個人 reference 的 exact transcript 尚未接入。詳見 [`docs/cosyvoice-verification-latest.md`](../../docs/cosyvoice-verification-latest.md)。

## 官方起始命令

以下命令在 WSL2／Linux 的各自環境執行，不要直接安裝到現有 RVC `.venv`：

### CosyVoice 2

```bash
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git tools/external/CosyVoice
cd tools/external/CosyVoice
conda create -n cosyvoice -y python=3.10
conda activate cosyvoice
pip install -r requirements.txt
python -c "from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')"
```

官方 API 使用 `inference_zero_shot(text, prompt_text, prompt_audio)`；本專案以 `tools/cosyvoice-infer.py` 封裝，`prompt_text` 必須由 STT 後人工抽查，不能猜測。預設推論環境會移除 DeepSpeed；若要訓練，請以 `tools/cosyvoice-setup.ps1 -Training` 建立／調整獨立環境並準備 CUDA toolkit。

可直接重跑官方 zero-shot fixture：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'set -e; unset CUDA_VISIBLE_DEVICES; export PYTHONPATH=/mnt/d/AetherTune/tools/external/CosyVoice:/mnt/d/AetherTune/tools/external/CosyVoice/third_party/Matcha-TTS; export HF_HUB_OFFLINE=1; /mnt/d/AetherTune/tools/venvs/cosyvoice-wsl/bin/python -u /mnt/d/AetherTune/tools/cosyvoice-infer.py --model-dir /mnt/d/AetherTune/models/speech-reconstruction/cosyvoice --prompt-audio /mnt/d/AetherTune/tools/external/CosyVoice/asset/zero_shot_prompt.wav --prompt-text-file /mnt/d/AetherTune/tools/fixtures/cosyvoice/prompt-text.txt --text-file /mnt/d/AetherTune/tools/fixtures/cosyvoice/target-text.txt --output /mnt/d/AetherTune/artifacts/speech-reconstruction/cosyvoice-official-zero-shot.wav --fp16'
```

### Breeze TTS 2

```bash
git clone https://github.com/breezeblue-ai/breeze-tts.git tools/external/breeze-tts
cd tools/external/breeze-tts
python -m pip install -r requirements.txt
python infer.py /path/to/Breeze-TTS-2 \
  --ref-audio /path/to/reference.wav \
  --ref-text "reference audio 的 exact transcript" \
  --text "要重建的文字" \
  --output outputs/reconstructed.wav
```

Breeze TTS 2 的官方權重與 self-hosted outputs 是 research/non-commercial；目前官方 quick start 是 Linux + CUDA，這裡仍保留為 `planned`，直到 WSL2 實際輸出與 license 邊界完成驗證。

## 驗收

至少保存：`input.wav` hash、STT model/revision、transcript、TTS backend/model、reference hash、輸出 WAV hash、語言、裝置、RTF 與人工聽測。CosyVoice、Breeze 與 STT 應各自使用獨立環境，不與現有 RVC `.venv` 混裝。
