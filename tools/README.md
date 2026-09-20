# tools

放置 AetherTune 自有的小工具與外部工具的啟動/驗證腳本。

第三方原始碼、預編譯包與模型不要直接提交到此目錄；請在 `docs/source-audit.md` 登記上游 URL、revision、授權與本機安裝位置。

目前工具：

- `dataset_audit.py`：唯讀掃描 `dataset/raw/` 的 WAV metadata、SHA-256 與 provenance manifest。
- `verify_wiring.ps1`：唯讀檢查 venv、RVC 資產、角色模型、Windows 音訊端點、VCClient localhost、VST 檔案與 CUDA runtime。
- `onnx_runtime_probe.py`：用固定合成特徵實際執行 sample RVC ONNX 一次，記錄真正使用的 provider 與輸出摘要。
- `virtual_cable_loopback.py`：用 440 Hz 合成音測試指定 WASAPI 虛擬播放／錄音端點，不使用實體麥克風；同時產生 metrics JSON 與 WAV hash。找不到端點或 stream 失敗時也會覆寫當次 `FAIL` JSON/WAV，避免沿用舊 PASS 證據。
- `voice-backend-check.ps1`：唯讀檢查 RVC venv、Seed-VC source／isolated environment／checkpoint、男／女 reference voice 與 CosyVoice/Breeze TTS 2 模型狀態；不代表端到端品質通過。
- `seed-vc-run.ps1`：檢查輸入、checkpoint、config 與 SHA-256 後呼叫官方 Seed-VC offline inference，並寫出可追溯的 `seed-vc-run.json`；輸出仍須人工聽測與另行登錄。
- `seed-vc-setup.ps1`：建立獨立 Python 3.10 Seed-VC environment，使用 Torch `2.7.1+cu128` 對齊目前 GPU runtime，再安裝 Seed-VC 其餘依賴。
- `cosyvoice-setup.ps1`：在 WSL2 Ubuntu 建立 CosyVoice Python 3.10 environment、安裝官方依賴與下載 CosyVoice2-0.5B；搭配 `cosyvoice-infer.py` 做 zero-shot／reference clone。
- `breeze-tts2-setup.ps1`：在 WSL2 Ubuntu 建立 Breeze TTS 2 Python 3.10 environment 與下載官方 checkpoint；模型受 research/non-commercial license 限制。
- `breeze-tts2-run.ps1`／`breeze-tts2-infer.py`：使用 UTF-8 text file、reference audio／transcript 或 voice design 產生 24 kHz WAV 與 JSON manifest。
- `stt-setup.ps1`／`stt-transcribe.py`：建立 Faster-Whisper STT environment，對 reference 產生 draft transcript 與 JSON evidence；正式 clone 前仍需人工核對。
- `rvc-fcpe-gpu-infer.py`：直接使用 RVC WebUI pipeline，以 FCPE + CUDA 對角色模型做離線推論並寫出 manifest。
- `vcclient-rvc-probe.ps1`：對已啟動的 VCClient REST endpoint 做官方 sample 短 WAV → RVC chunk probe；目前只能證明 chunk request 被接受，舊 artifact 的輸出不是有效 WAV，不能代替 RVC WebUI 的 FCPE + GPU role matrix。
- `speech-reconstruction-run.ps1`：一鍵執行 `STT → CosyVoice2/Breeze TTS 2`；未提供文字時會先產生 STT draft，輸出 WAV、後端 JSON 與 workflow manifest。正式 voice clone 仍應提供人工核對的 `-ReferenceTextFile`。
- `external/`：本機第三方 repo、整合包與下載檔，已由 `.gitignore` 排除。

驗收命令：

```powershell
Set-Location D:\AetherTune
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\wiring-verification-latest.md
```
