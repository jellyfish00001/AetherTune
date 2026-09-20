# CosyVoice 最新驗證

更新日期：2026-09-20

## 狀態

目前是 `WAITING`，不是可用 PASS。

已完成：

- 官方 source `FunAudioLLM/CosyVoice` 已 clone，revision `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc`。
- WSL2 Ubuntu 24.04.4 LTS、Python 3.10.20 與 `tools/venvs/cosyvoice-wsl` 已建立。
- 官方 requirements 已安裝；Torch 已調整為 `2.7.1+cu128`、torchaudio `2.7.1+cu128`。
- `FunAudioLLM/CosyVoice2-0.5B` snapshot 已下載到 `models/speech-reconstruction/cosyvoice/`：19 個檔案、約 4,856,505,002 bytes。
- 模型主要檔案 `llm.pt`、`flow.pt`、`hift.pt`、`speech_tokenizer_v2.onnx` 與 `cosyvoice2.yaml` 均存在。

未完成：

- Torch 能辨識 RTX 5060 Ti、CUDA `12.8` 與 capability `(12, 0)`，wheel 也包含 `sm_120`；但最小 CUDA tensor allocation 在 WSL 中卡住，尚未取得穩定 GPU kernel PASS。
- 尚未載入 CosyVoice model 產生 TTS WAV。
- 尚未取得兩個 reference voice 的 exact transcript；STT 候選文字不能直接當作 zero-shot prompt 的通過證據。
- Breeze TTS 2 與完整 STT pipeline 尚未安裝，仍是 `PLANNED`。

## 可重跑 setup

```powershell
Set-Location D:\AetherTune
& .\tools\cosyvoice-setup.ps1 -DownloadModel
```

這個 setup 只寫入 WSL 的 `tools/venvs/cosyvoice-wsl`、`tools/external/CosyVoice` 與模型資料夾，不會修改現有 RVC `.venv` 或 Seed-VC environment。

## 驗收門檻

只有以下項目全部完成，才可把 CosyVoice backend 改為 `candidate/verified`：

1. 在 WSL GPU 上完成 CUDA tensor smoke test。
2. `AutoModel(model_dir=...)` 成功載入且無未處理 exception。
3. 使用人工核對的 reference transcript 執行 `inference_zero_shot` 並產生 WAV。
4. 保存 source/reference/model/output hash、runtime、RTF 與人工聽測備註。
