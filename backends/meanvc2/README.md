# MeanVC2（研究候選）

狀態：`installed / candidate`；Windows／RTX 5060 Ti、雙向 CUDA file-driven streaming WAV `PASS`。完整 LIVE `WAITING`。

研究來源：[ASLP-lab/MeanVC2](https://github.com/ASLP-lab/MeanVC2) 與 [arXiv:2606.09050](https://arxiv.org/abs/2606.09050)。上游 repo 標示 Apache-2.0，README 記載 Python 3.11、PyTorch／TorchAudio 2.5.1 CUDA 12.1 與模型初始化流程；README 報告的 40 ms chunk、約 110 ms first-packet latency 是上游數字，不能套用到 RTX 5060 Ti、Windows、AetherTune audio-rack 或完整 virtual routing。

## 研究順位

MeanVC2 已完成下載、隔離 Python 3.10／Torch 2.7.1+cu128、40ms 與 120ms model 的雙向 file-driven CUDA WAV；從 3.11 遷移後的 40ms WAV hash 與原測試一致。ASR JIT 在 CPU，VC／speaker／vocoder 在 CUDA；沒有宣稱整條 pipeline 都在 GPU。code revision `13acf84c1bf135ea5edad9c245b345289b06b33e`；HF snapshot `39cdd19522fe896c227da691314d9a0e3b995486`。安裝證據見 [`backend-install-test-latest.md`](../../docs/backend-install-test-latest.md)，Python 與 UI 見 [`python-ui-verification-latest.md`](../../docs/python-ui-verification-latest.md)。

```powershell
& tools/venvs/meanvc2/Scripts/python.exe tools/meanvc2-run.py --source dataset/reference-voices/voice-male-m1.wav --target dataset/reference-voices/voice-female-f1.wav --output artifacts/meanvc2/my-test.wav --model 40ms
```

`--model 120ms` 使用另一組已下載模型。來源／reference 需可解碼 WAV；輸出為 16 kHz WAV 與 `<檔名>.run-evidence.json`。`--realtime --target <WAV>` 可進入官方互動式裝置選擇，但本輪實測範圍是 file mode，mic 與 route 尚待驗收。

## 不可提前宣稱

- 不下載 checkpoint 就不能寫成 runtime PASS。
- 上游 110 ms 不能寫成 AetherTune LIVE PASS。
- repo 的 Apache-2.0 標示只涵蓋程式碼授權範圍；checkpoint、訓練資料及衍生權重須分別核對使用條款和來源。
- 官方提供的 Windows standalone 是 CPU-only executable；AetherTune 已另以隔離 Python 3.10／Torch 2.7.1+cu128 驗證 RTX 5060 Ti 雙向 file-driven CUDA WAV。這仍不代表 physical mic、audio-rack 或完整 routing 的 LIVE PASS。
- 官方依賴包含 S3PRL、Fairseq、FunASR、SoX／PyWorld 與 pedalboard 等元件；本機 code/model revision、isolated runtime 與基本音訊驗證見 [`backend-install-test-latest.md`](../../docs/backend-install-test-latest.md)。新增 revision、checkpoint 或平台 profile 時仍須重新審核依賴、授權與平台支援。
- source／revision／模型條款／Windows runtime 等 intake gate 見 [`docs/streaming-vc-candidate-intake-2026-09-26.md`](../../docs/streaming-vc-candidate-intake-2026-09-26.md)。
- 需要與 RVC、Seed-VC realtime、後續候選使用同一固定 corpus、同一 rack、同一 gate。

## 後續完整 LIVE 驗收順序

1. source、revision、license、checkpoint hash 與 dependency inventory 已固定；變更時重新審核。
2. Windows／RTX 5060 Ti isolated runtime 與雙向 CUDA file-driven WAV 已 `PASS`；它只證明該固定 profile 的離線／headless 音訊輸出。
3. 以同一固定 corpus 建立 backend → audio-rack → routing 的 paired evidence。
4. 完成 physical capture → backend → audio-rack → routing → loopback 的 `LIVE_GATE`。
5. 完成 acoustic objective 與 human blind listening；缺任何一層都不能下完整 LIVE 或自然度結論。
