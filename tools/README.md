# tools

放置 AetherTune 自有的小工具與外部工具的啟動/驗證腳本。

第三方原始碼、預編譯包與模型不要直接提交到此目錄；請在 `docs/source-audit.md` 登記上游 URL、revision、授權與本機安裝位置。

目前工具：

- `dataset_audit.py`：唯讀掃描 `dataset/raw/` 的 WAV metadata、SHA-256 與 provenance manifest。
- `verify_wiring.ps1`：唯讀檢查 venv、RVC 資產、角色模型、Windows 音訊端點、VCClient localhost、VST 檔案與 CUDA runtime。
- `onnx_runtime_probe.py`：用固定合成特徵實際執行 sample RVC ONNX 一次，記錄真正使用的 provider 與輸出摘要。
- `virtual_cable_loopback.py`：用 440 Hz 合成音測試指定 WASAPI 虛擬播放／錄音端點，不使用實體麥克風；同時產生 metrics JSON 與 WAV hash。找不到端點或 stream 失敗時也會覆寫當次 `FAIL` JSON/WAV，避免沿用舊 PASS 證據。
- `voicemeeter-route-check.py`：唯讀連線 Voicemeeter Remote API，記錄 B1／Mute／Gain 設定與內部 level meter，同時以合成音驗證 `Voicemeeter Input → B1 → Voicemeeter Out B1`；不呼叫任何設定寫入 API。
- `audio-rack-evidence-validate.py`：分類 `audio-rack/evidence-v1` 的 PASS／OFFLINE／WAITING／BLOCKED；只檢查契約，不建立假 artifact。
- `audio-rack-evidence-regression.py`：回歸測試 rack evidence 分類、hash gate、Δ latency 缺失與超過 5 秒情況。
- `voice-backend-check.ps1`：唯讀檢查 RVC venv、Seed-VC source／isolated environment／checkpoint、男／女 reference voice 與 CosyVoice/Breeze TTS 2 模型狀態；不代表端到端品質通過。
- `seed-vc-run.ps1`：檢查輸入、checkpoint、config 與 SHA-256 後呼叫官方 Seed-VC offline inference，並寫出可追溯的 `seed-vc-run.json`；輸出仍須人工聽測與另行登錄。
- `seed-vc-setup.ps1`：建立獨立 Python 3.10 Seed-VC environment，使用 Torch `2.7.1+cu128` 對齊目前 GPU runtime，再安裝 Seed-VC 其餘依賴。
- `cosyvoice-setup.ps1`：在 WSL2 Ubuntu 建立 CosyVoice Python 3.10 environment、安裝官方依賴與下載 CosyVoice2-0.5B；搭配 `cosyvoice-infer.py` 做 zero-shot／reference clone。
- `breeze-tts2-setup.ps1`：在 WSL2 Ubuntu 建立 Breeze TTS 2 Python 3.10 environment 與下載官方 checkpoint；模型受 research/non-commercial license 限制。
- `breeze-tts2-run.ps1`／`breeze-tts2-infer.py`：使用 UTF-8 text file、reference audio／transcript 或 voice design 產生 24 kHz WAV 與 JSON manifest。
- `audio_output_validation.py`：供 CosyVoice／Breeze runner 共用的 WAV 輸出 gate；會在編碼前拒絕 raw chunk 的 NaN/Infinity，並拒絕空檔、無 frame、非 finite、錯誤取樣率與全零輸出；失敗重跑會寫 `FAIL` manifest。
- `audio_runner_failure.py`：不依賴模型／音訊套件的 runner 啟動保護；兩個 runner 使用固定的 `--output`／`--out`／`--outp`／`--o` 別名、停用隱式縮寫，helper 按最後值解析分開或 `=` 形式，尊重 `--`，把分開與 `=` 空值交由 parser 在 stale cleanup 前以 exit 2 拒絕，再清除指定輸出與寫入失敗 manifest。
- `audio-quality-batch.py`／`audio-quality-batch-regression.py`：四 backend 的 signal-level 比較與狀態彙總 regression；任何 BLOCKED row 不得被彙總成 PASS。
- `audio-output-validation-regression.py`：WAV 輸出 gate 的空值、非 finite 與有效訊號 regression。
- `audio-runner-entry-regression.py`：實際啟動兩個 TTS runner subprocess，驗證 help 保留舊檔、四個明確 output 別名的分開與 `=` 形式、重複 output 只清理最後目標、`--` 終止符、四個分開空值與既有 `--out=` 空值在 parser exit 2 時保留 stale output/manifest、parse failure 清理與 FAIL manifest；另保留 top-level import AST regression。
- `speech-reconstruction-failure-regression.ps1`：不啟動模型的 wrapper stale workflow failure regression。
- `stt-setup.ps1`／`stt-transcribe.py`：建立 Faster-Whisper STT environment，對 reference 產生 draft transcript 與 JSON evidence；正式 clone 前仍需人工核對。
- `rvc-fcpe-gpu-infer.py`：直接使用 RVC WebUI pipeline，以 FCPE + CUDA 對角色模型做離線推論並寫出 manifest。
- `vcclient-rvc-probe.ps1`：對已啟動的 VCClient REST endpoint 做官方 sample 短 WAV → RVC chunk probe；目前只能證明 chunk request 被接受，舊 artifact 的輸出不是有效 WAV，不能代替 RVC WebUI 的 FCPE + GPU role matrix。
- `vcclient-rvc-chunk-validation-regression.ps1`：離線回歸 empty、short、unaligned、全零、finite non-zero、NaN 與 Infinity chunk gate。
- `speech-reconstruction-run.ps1`：一鍵執行 `STT → CosyVoice2/Breeze TTS 2`；未提供文字時會先產生 STT draft，輸出 WAV、後端 JSON 與 workflow manifest。`-ReferenceTextFile` 預設是 `caller_provided_unverified`；人工逐字核對後再明確加 `-ReferenceTextVerified`。
- `external/`：本機第三方 repo、整合包與下載檔，已由 `.gitignore` 排除。

驗收命令：

```powershell
Set-Location D:\AetherTune
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\wiring-verification-latest.md
```
