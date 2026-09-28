# AetherTune backends

**文件邊界：**這一層只索引各語音 backend 的獨立操作契約；實際命令、資產與限制由各子目錄 README 擁有，安裝／音訊狀態由對應[驗證報告](../docs/README.md)擁有。第三方原始碼、虛擬環境、模型權重與輸出音檔留在 ignored 本機位置。

| 後端／profile | 功能 | 是否需要訓練 | 詳細入口 |
|---|---|---:|---|
| [`rvc/`](rvc/README.md) | 訓練角色模型的 voice conversion | 是，需角色 `.pth`／`.index` | RVC 與 VCClient 對照入口 |
| [`seed-vc/`](seed-vc/README.md) | Zero-shot reference VC | 否 | Seed-VC upstream offline／GUI 入口 |
| [`seed-vc-realtime/`](seed-vc-realtime/README.md) | 獨立 realtime fork 候選 | 否 | 候選 intake 邊界 |
| [`meanvc2/`](meanvc2/README.md) | low-latency streaming zero-shot VC | 否 | MeanVC2 runner 契約 |
| [`xvc/`](xvc/README.md) | codec-space zero-shot streaming VC | 否 | X-VC runner 契約 |
| [`speech-reconstruction/`](speech-reconstruction/README.md) | STT → TTS 重建文字與聲線 | 否，可用 reference | CosyVoice／Breeze 入口 |

每個 backend/profile 都要分開記錄 source/revision、license、隔離環境、model/reference、實際 provider、輸出 hash 和人工聽測；具體 handoff 欄位由[多後端契約](../docs/specs/voice-conversion-architecture.md)擁有。候選文件不代表已安裝或已通過。
