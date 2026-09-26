# MeanVC2（研究候選）

狀態：`installed / candidate`；Windows／RTX 5060 Ti、雙向 CUDA file-driven streaming WAV `PASS`。完整 LIVE `WAITING`。

研究來源：[ASLP-lab/MeanVC2](https://github.com/ASLP-lab/MeanVC2) 與 [arXiv:2606.09050](https://arxiv.org/abs/2606.09050)。上游將它描述為 streaming zero-shot voice conversion，並主張 40 ms chunk、約 110 ms first-packet latency 與 Apache-2.0；這些數字不能直接套用到 RTX 5060 Ti、Windows、AetherTune audio-rack 或完整 virtual routing。

## 研究順位

MeanVC2 已完成下載、隔離 Python 3.11／Torch 2.7.1+cu128、40ms 與 120ms model 的雙向 file-driven CUDA WAV。ASR JIT 在 CPU，VC／speaker／vocoder 在 CUDA；沒有宣稱整條 pipeline 都在 GPU。code revision `13acf84c1bf135ea5edad9c245b345289b06b33e`；HF snapshot `39cdd19522fe896c227da691314d9a0e3b995486`。操作與證據見 [`backend-install-test-latest.md`](../../docs/backend-install-test-latest.md)。

```powershell
& tools/venvs/meanvc2/Scripts/python.exe tools/meanvc2-run.py --source dataset/reference-voices/voice-male-m1.wav --target dataset/reference-voices/voice-female-f1.wav --output artifacts/meanvc2/my-test.wav --model 40ms
```

`--model 120ms` 使用另一組已下載模型。來源／reference 需可解碼 WAV；輸出為 16 kHz WAV 與 `<檔名>.run-evidence.json`。`--realtime --target <WAV>` 可進入官方互動式裝置選擇，但本輪實測範圍是 file mode，mic 與 route 尚待驗收。

## 不可提前宣稱

- 不下載 checkpoint 就不能寫成 runtime PASS。
- 上游 110 ms 不能寫成 AetherTune LIVE PASS。
- 研究程式碼與模型的實際 license、依賴、模型下載來源與 Windows 相容性要在 intake record 中逐項確認。
- 需要與 RVC、Seed-VC realtime、後續候選使用同一固定 corpus、同一 rack、同一 gate。

## 首次驗收順序

1. source/revision/license intake 與 dependency audit。
2. RTX 5060 Ti 16GB 的 isolated runtime smoke。
3. fixed corpus 的 offline／headless stream output validation。
4. real capture → backend → audio-rack → routing → loopback 的 `LIVE_GATE`。
5. acoustic objective 與 human blind listening；沒有這兩層不能下自然度結論。
