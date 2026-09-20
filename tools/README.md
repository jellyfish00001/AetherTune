# tools

放置 AetherTune 自有的小工具與外部工具的啟動/驗證腳本。

第三方原始碼、預編譯包與模型不要直接提交到此目錄；請在 `docs/source-audit.md` 登記上游 URL、revision、授權與本機安裝位置。

目前工具：

- `dataset_audit.py`：唯讀掃描 `dataset/raw/` 的 WAV metadata、SHA-256 與 provenance manifest。
- `verify_wiring.ps1`：唯讀檢查 venv、RVC 資產、角色模型、Windows 音訊端點、VCClient localhost、VST 檔案與 CUDA runtime。
- `onnx_runtime_probe.py`：用固定合成特徵實際執行 sample RVC ONNX 一次，記錄真正使用的 provider 與輸出摘要。
- `virtual_cable_loopback.py`：用 440 Hz 合成音測試指定 WASAPI 虛擬播放／錄音端點，不使用實體麥克風；同時產生 metrics JSON 與 WAV hash。找不到端點或 stream 失敗時也會覆寫當次 `FAIL` JSON/WAV，避免沿用舊 PASS 證據。
- `external/`：本機第三方 repo、整合包與下載檔，已由 `.gitignore` 排除。

驗收命令：

```powershell
Set-Location D:\AetherTune
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\wiring-verification-latest.md
```
