# X-VC

**文件邊界：**本頁負責 X-VC 固定 profile、CLI、資產與輸出契約；本機安裝、CUDA WAV 與 LIVE 狀態只看[後端驗證](../../docs/verification/backends/backend-install-test-latest.md)及[LIVE gate](../../docs/specs/live-gate.md)。

官方程式碼：[Jerrister/X-VC](https://github.com/Jerrister/X-VC)，code revision `49df8c591eafc48b096e466d96f9839f9c0dd739`；主模型：[chenxie95/X-VC](https://huggingface.co/chenxie95/X-VC)，snapshot `9e54747d8c4d1ef544b903e2300a4ba040dcc126`。code 與 model card 標示 MIT；GLM tokenizer 有自己的 LICENSE，不能把所有 helper 的用途都視為同一授權。

隔離 runtime：`tools/venvs/xvc`，Python 3.10、Torch 2.7.1+cu128；不需 DeepSpeed 或訓練。主 checkpoint、GLM-4 Voice Tokenizer、ERes2Net 存在 `models/xvc`，必要權重 hash 由 downloader 驗證。設定副本存於輸出 artifacts，不改 upstream YAML。

```powershell
& tools/venvs/xvc/Scripts/python.exe tools/xvc-run.py --source dataset/reference-voices/voice-male-m1.wav --target dataset/reference-voices/voice-female-f1.wav --output-dir artifacts/xvc/my-test
```

來源與 reference 為可解碼 WAV；輸出為 16 kHz WAV 與 `run-evidence.json`。預設 `current=160ms / chunk=2400ms / future=80ms / smooth=20ms`，`--current 0` 為 offline（本輪使用 streaming）。output directory 必須沒有舊 WAV。

CLI 保留檔案轉換。Desktop START 另使用 `services/engines/stream_runtime.py`，直接開啟明確麥克風與輸出；`streaming_adapters.py` 重用官方 `run_stream_chunk_forward`，同一 session 常駐模型與 reference conditions。rolling window 等待 smooth/future，再取 current 區段；48 kHz host PCM 與 16 kHz codec PCM 分開重取樣，current/chunk/future 要對齊 80 ms codec hop。`current=0` 只可用於 CLI offline。Desktop 所需 `sounddevice` 由 setup 安裝；監聽與 Post-FX 操作見 [Desktop 手冊](../../docs/guides/desktop-user-guide.md)，實測 hash／速度與限制見 [Desktop VC 驗證](../../docs/verification/desktop/realtime-vc-verification-latest.md)。
