# Breeze TTS 2 local model directory

這是 BreezeBlue `Breeze-TTS-2` checkpoint 的本機模型目錄；權重、tokenizer 與其他下載檔案由 `.gitignore` 排除，不進 Git。

- 官方模型：[BreezeBlue/Breeze-TTS-2](https://huggingface.co/BreezeBlue/Breeze-TTS-2)
- 官方 source：[breezeblue-ai/breeze-tts](https://github.com/breezeblue-ai/breeze-tts)
- 本機測試：WSL2、Python 3.10、Torch 2.9.1 + cu128、RTX 5060 Ti
- 已驗證：Voice Design 男／女、reference clone 男／女、24 kHz WAV
- 已知限制：目前使用 eager CUDA/manual PyTorch path；flash-attn、fast-all 與人工音質評估仍未完成
- 授權邊界：model weights、derivatives 與 self-hosted outputs 受 BreezeBlue Research and Non-Commercial License 限制；詳見官方模型 `LICENSE`

安裝與執行入口：

- `tools/breeze-tts2-setup.ps1`
- `tools/breeze-tts2-run.ps1`
- `backends/speech-reconstruction/README.md`
- `docs/breeze-tts2-verification-latest.md`
