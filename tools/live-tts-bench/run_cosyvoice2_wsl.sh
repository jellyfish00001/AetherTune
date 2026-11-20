#!/bin/bash
# PC1 WSL：用 D:\AetherTune 既有 CosyVoice2 環境（唯讀）跑 stream=True 量測。
# 用法：bash run_cosyvoice2_wsl.sh [combos]，例如 "qwen-zh:spk,qwen-zh:nospk,f1:nospk"
set -e
export PYTHONPATH=/mnt/d/AetherTune/tools/external/CosyVoice:/mnt/d/AetherTune/tools/external/CosyVoice/third_party/Matcha-TTS
export HF_HUB_OFFLINE=1
cd "$(dirname "$0")"
COMBOS="${1:-qwen-zh:spk,qwen-zh:nospk,f1:spk,f1:nospk}"
/mnt/d/AetherTune/tools/venvs/cosyvoice-wsl/bin/python -u bench_cosyvoice2.py \
  --model-dir /mnt/d/AetherTune/models/speech-reconstruction/cosyvoice \
  --ref-src f1=/mnt/d/AetherTune/dataset/reference-voices/voice-female-f1.wav \
  --ref-src qwen-zh=/mnt/d/AetherTune-exp/dataset/reference-voices/qwen3-tts-clone_1.wav \
  --out-dir /mnt/d/AetherTune-exp/artifacts/live-tts-bench/cosyvoice2 \
  --combos "$COMBOS" ${EXTRA_ARGS}
echo ALLDONE