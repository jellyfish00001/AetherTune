# AetherTune backends

這一層只放各語音後端的操作契約與驗證方式；第三方原始碼、虛擬環境、模型權重與輸出音檔放在被 `.gitignore` 排除的本機位置。

| 後端 | 功能 | 是否需要訓練 | 目前入口 |
|---|---|---:|---|
| `rvc/` | 即時／離線 voice conversion | 是，需角色 `.pth`／`.index` | 既有 VCClient + `tools/operation-guide.md` |
| `seed-vc/` | Zero-Shot VC，以參考聲音轉換 | 否 | `tools/seed-vc-run.ps1` |
| `speech-reconstruction/` | `STT → TTS`，重建內容與聲線 | 否，可用參考聲音 | CosyVoice／Breeze TTS 2 的獨立環境 |

每個後端都要分開記錄：source/revision、license、Python environment、model path、reference audio、transcript、實際 provider、輸出 hash 與人工聽測結果。
