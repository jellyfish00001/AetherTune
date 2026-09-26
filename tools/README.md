# tools

放置 AetherTune 自有的小工具與外部工具的啟動/驗證腳本。

第三方原始碼、預編譯包與模型不要直接提交到此目錄；請在 `docs/source-audit.md` 登記上游 URL、revision、授權與本機安裝位置。

目前工具：

- `dataset_audit.py`：唯讀掃描 `dataset/raw/` 的 WAV metadata、SHA-256 與 provenance manifest。
- `verify_wiring.ps1`：唯讀檢查 venv、RVC 資產、角色模型、Windows 音訊端點、VCClient localhost、VST 檔案與 CUDA runtime。
- `onnx_runtime_probe.py`：用固定合成特徵實際執行 sample RVC ONNX 一次，記錄真正使用的 provider 與輸出摘要。
- `virtual_cable_loopback.py`：用 440 Hz 合成音測試指定 WASAPI 虛擬播放／錄音端點，不使用實體麥克風；同時產生 metrics JSON 與 WAV hash。找不到端點或 stream 失敗時也會覆寫當次 `FAIL` JSON/WAV，避免沿用舊 PASS 證據。
- `voicemeeter-route-check.py`：唯讀連線 Voicemeeter Remote API，記錄 B1／Mute／Gain 設定與內部 level meter，同時以合成音驗證 `Voicemeeter Input → B1 → Voicemeeter Out B1`；不呼叫任何設定寫入 API。
- `audio-rack-evidence-validate.py`：讀取 rack A/B 的 source、bypass/full-chain WAV 與 metrics JSON，驗檔案、SHA-256、run/model/hardware/route identity 及實測 delta；rack PASS 不等於 LIVE。
- `audio-rack-evidence-regression.py`：涵蓋未配對、缺檔、hash/identity/timing/continuity/paired-run/output/delta mismatch、靜音與超過 5 秒；確認 rack fixture 送入 LIVE gate 仍是 WAITING。
- `live-gate-validate.py`／`live-gate-regression.py`：驗證本次 mic input/output artifact、metrics hash 綁定完整 timing/continuity/source type/human review identity+audio hashes+ratings、run 時間與 600 秒穩定性；synthetic source 不能通過 LIVE，不完整的 PASS human review 會 BLOCKED。
- `voice-backend-check.ps1`：唯讀檢查 RVC venv、Seed-VC source／isolated environment／checkpoint、男／女 reference voice 與 CosyVoice/Breeze TTS 2 模型狀態；不代表端到端品質通過。
- `seed-vc-run.ps1`：先以新 run_id 覆寫非 PASS preflight manifest，再檢查輸入、checkpoint、config 與 Seed-VC Python，之後呼叫官方 Seed-VC offline inference；只接受新 WAV 或內容 hash 有變化的本次輸出，stale WAV 不會沿用成 PASS，輸出驗證也使用同一個 Seed-VC venv Python。`seed-vc-run-preflight-regression.ps1` 覆蓋六種缺項並確認舊 PASS 被新 BLOCKED manifest 取代。
- `seed-vc-gui-userflow-test.py`：以官方 GUI event path 驗證 Seed-VC callback；加上 `--capture-loopback` 時同步錄取 WASAPI `CABLE Output`，並保存 `callback_first_input_ms`、`callback_first_nonzero_output_ms` 與 `cable_output_first_nonzero_after_backend_ms` 的 partial timing。每個 case 會記錄 widget update／event value 狀態；任何設定錯誤都會將該 case 降為 `WAITING`。這不代表 Light Host full-chain 或 LIVE。
- `seed-vc-gui-settings-regression.py`：用 fake widget 回歸設定套用成功及缺少控制項時必須回報 `WAITING`；不啟動 Tcl/Tk、GUI 或 audio stream。
- `seed-vc-assets.json`／`seed-vc-assets.ps1`：Seed-VC required-assets registry 與共用嚴格驗證器。此 manifest 的執行支援範圍固定為 `realtime-tiny`；offline-v1 metadata 僅保留來源追溯，offline helper completeness（含 Whisper/BigVGAN）為 `WAITING / out-of-scope`。官方 code/checkpoint pins、realtime GUI 所需 HF local snapshot revisions 與 observed hashes、ModelScope VAD local observed hashes 分層記錄；VAD resolved revision/license 維持 `UNKNOWN/WAITING`。Setup 和 GUI preflight 僅對 realtime profile 必要資產做 registry revision、exact size 與 SHA-256 gate。
- `seed-vc-setup.ps1`：先唯讀檢查 Python 3.10/Tcl-Tk、固定 repo revision、realtime GUI required source/config、realtime-tiny checkpoint、HF cache snapshot revision/size/SHA 與 ModelScope VAD size/SHA，再建立 Seed-VC 環境；缺項先完整列出，不 clone source 或下載 weights。這不是 offline-v1 helper/Whisper/BigVGAN 完整性保證；該 scope 明確 `WAITING / out-of-scope`。`-PreflightOnly` 只讀檢查。
- `seed-vc-assets-regression.ps1`：需 PowerShell 7.2 以上（使用 .NET 6 hash/link API）；在唯一 `$env:TEMP` fixture 對 setup 與 GUI 各測九案（18 個負測）：缺檔、HF snapshot revision/hash mismatch、錯 code/model repo revision、損壞 JSON、不合法 provenance、required source/HF dependency omission。另驗證 offline-v1 checkpoint/preset 與 `inference.py` 缺席時 realtime-only setup 可 PASS，GUI 正常啟動抵達 fake bootstrap 並建立隔離 config/cache junction/env；只用 synthetic files/runtime shim，不讀真實模型/cache、不啟真 GUI/audio、不安裝/下載。
- `seed-vc-setup-preflight-regression.ps1`：用 `$env:TEMP` 合成 fixture；先以 Windows PowerShell 5.1 parser 檢查完整 setup 腳本並載入 manifest，再讓第一個一般 setup invocation 以 Python/Tcl/Tk shim 通過 runtime probe，確認空 source/config 與無效 checkpoint 在 pip／venv mutation 前 `BLOCKED`；第二個 invocation 單獨檢查缺少 Python。沒有呼叫真實 Python、讀取權重、啟動裝置或安裝套件。
- `seed-vc-gui-run.ps1`／`seed-vc-gui-bootstrap.py`：PowerShell launcher 需 7.2+ 的 `pwsh`（.NET 6 `ResolveLinkTarget`）；預設採 setup 建立的 Seed-VC venv，只有使用自訂 venv 才傳 `-Python`。手動啟動官方 realtime-tiny GUI；固定 FP32/CUDA 0，精確核對 device/reference、離線驗證 realtime profile 所需 manifest pin/size/SHA 的本機 HF/ModelScope assets，並將 GUI 設定與 cache lock 放在 ignored `artifacts/seed-vc/gui-session/`。offline-v1 Whisper/BigVGAN helper completeness 為 `WAITING / out-of-scope`，不由 GUI manifest gate 證明。模型本體只讀現有 local snapshots，不隱性下載、不改 upstream repo/user profile/Windows default devices；啟動不注入音訊且不自動 start stream。資產 preflight PASS 不等於新機 bootstrap PASS；FSMN-VAD 上游 revision/license 仍 UNKNOWN/WAITING。
- `seed-vc-gui-overlay.ps1`／`seed-vc-gui-overlay-regression.ps1`：需 PowerShell 7.2 以上；只建立或驗證 session overlay cache junction；同一路徑第二次啟動會實際解析 link target，非 junction／錯誤 target 一律拒絕且不刪除既有內容。Regression 在 `$env:TEMP` 保留唯一 fixture。
- `seed-vc-readiness-latest.md`：目前開箱 readiness、架構候選、操作步驟、PASS/WAITING/PLANNED 邊界及真實 mic／600 秒／人工驗收說明。
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
