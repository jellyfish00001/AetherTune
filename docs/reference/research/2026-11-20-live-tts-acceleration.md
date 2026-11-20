# 直播 TTS 加速矩陣（2026-11-20，PC1 RTX 5060 Ti 16GB）

分支 exp/live-tts-bench。量測方法同 `2026-11-20-live-tts-bench.md`（同參考音、短中長三句、1 暖機 + 3 次）。加速套件（含 triton-windows）只裝在實驗 venv，不動系統/PATH/全域 Python；系統層級需求標 BLOCKED 交 parent。CER 為 faster-whisper small 轉寫，主觀描述**不是真人評聽**。

| 後端 | 組合 | 首包 p50 ms（短/中/長） | RTF p50 | VRAM | CER | 可行性 / 狀態 | 證據等級 |
|---|---|---|---|---|---|---|---|
| GSV-TTS-Lite | 不加速（預設，SDPA efficient）@rvc-sage | 124 / 87 / 128 | 0.10–0.13 | 0.58 GiB | 0 / 0.08 / 0.23 | 已量 | A 本機實測 |
| GSV-TTS-Lite | boost_first_chunk=False @rvc-sage | 172 / 148 / 185 | 0.10–0.12 | 0.58 GiB | 0 / 0.08 / 0.25 | 已量；首包變慢、無品質增益 | A |
| GSV-TTS-Lite | use_bert @qwen-zh | 247 / 247 / 246 | 0.13–0.16 | 1.19 GiB | 0.20 / 0.31 / 0.52 | 已量；無增益 | A |
| VoxCPM2 | 不加速 t10 @qwen-zh | 138–155 | 1.10–1.15 | 5.5 GiB | 0–0.06 | 已量 | A |
| VoxCPM2 | 降步數 t6 @qwen-zh | 103 / 101 / 127 | 0.76–0.78 | 5.5 GiB | 0 / 0.04 / 0.06 | 已量；RTF<1 | A |
| VoxCPM2 | 降步數 t4 @qwen-zh | 151 / 117 / 145 | 0.84–0.87 | 5.5 GiB | 0 / 0.04 / 0.06 | 已量；不比 t6 快 | A |
| VoxCPM2 | torch.compile（triton-windows，實驗 venv） | — | — | — | — | 待量（等 GPU 鎖） | — |
| CosyVoice2 | 不加速 fp32 + 預建 speaker ID（WSL /mnt/d） | 4400–7100 | ≈0.93 | 2.6 GiB | 0.35–0.5 | 已量（第一輪獨占） | A |
| CosyVoice2 | fp16 | 5100–9200 | — | — | — | 已量；首包更慢 | A |
| CosyVoice2 | JIT / TensorRT / vLLM / Windows 原生 venv / ext4 | — | — | — | — | 待量 | — |
| Qwen3-TTS | 不加速 0.6B bf16 sdpa（非串流） | 6100–24200 | 1.69–1.82 | — | 0–0.08 | 已量 | A |
| Qwen3-TTS | 1.7B / flash-attn / 低精度 / 串流實作 | — | — | — | — | 待量 | — |
