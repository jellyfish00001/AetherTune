# AetherTune backends

這一層只放各語音後端的操作契約與驗證方式；第三方原始碼、虛擬環境、模型權重與輸出音檔放在被 `.gitignore` 排除的本機位置。

| 後端／profile | 功能 | 是否需要訓練 | 目前定位／入口 |
|---|---|---:|---|
| `rvc/` | 即時／離線 voice conversion | 是，需角色 `.pth`／`.index` | historical baseline；既有 VCClient + verifier |
| `seed-vc/` | Zero-Shot VC，以參考聲音轉換 | 否 | established baseline；`tools/seed-vc-run.ps1` |
| `seed-vc-realtime/` | maintained realtime fork 候選 | 否 | `PLANNED / candidate`；尚未安裝 |
| `meanvc2/` | low-latency streaming zero-shot VC 候選 | 否 | `PLANNED / candidate`；尚未安裝 |
| `speech-reconstruction/` | `STT → TTS`，重建內容與聲線 | 否，可用參考聲音 | CosyVoice2 baseline、CosyVoice3 candidate、Breeze |

每個 backend/profile 都要分開記錄：source/revision、license classification、Python environment、model path、reference audio、transcript、實際 provider、完整鏈路 timing、輸出 hash 與人工聽測結果。候選文件不代表已安裝或已通過。
