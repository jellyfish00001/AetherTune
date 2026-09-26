# X-VC

狀態：`installed / candidate`；Windows、RTX 5060 Ti、雙向 CUDA file-driven streaming 音訊 `PASS`。完整 mic／rack／600 秒與人工聽評仍 `WAITING`。

官方程式碼：[Jerrister/X-VC](https://github.com/Jerrister/X-VC)，code revision `49df8c591eafc48b096e466d96f9839f9c0dd739`；主模型：[chenxie95/X-VC](https://huggingface.co/chenxie95/X-VC)，snapshot `9e54747d8c4d1ef544b903e2300a4ba040dcc126`。code 與 model card 標示 MIT；GLM tokenizer 有自己的 LICENSE，不能把所有 helper 的用途都視為同一授權。

隔離 runtime：`tools/venvs/xvc`，Python 3.10、Torch 2.7.1+cu128；不需 DeepSpeed 或訓練。主 checkpoint、GLM-4 Voice Tokenizer、ERes2Net 存在 `models/xvc`，必要權重 hash 由 downloader 驗證。設定副本存於輸出 artifacts，不改 upstream YAML。

```powershell
& tools/venvs/xvc/Scripts/python.exe tools/xvc-run.py --source dataset/reference-voices/voice-male-m1.wav --target dataset/reference-voices/voice-female-f1.wav --output-dir artifacts/xvc/my-test
```

來源與 reference 為可解碼 WAV；輸出為 16 kHz WAV 與 `run-evidence.json`。預設 `current=160ms / chunk=2400ms / future=80ms / smooth=20ms`，`--current 0` 為 offline（本輪使用 streaming）。output directory 必須沒有舊 WAV。

官方本機入口為 CLI，本輪沒有新增 GUI 或常駐 web server。完整實際命令、hash 與限制見 [`backend-install-test-latest.md`](../../docs/backend-install-test-latest.md)。
