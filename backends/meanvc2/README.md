# MeanVC2（研究候選）

狀態：`PLANNED / candidate / not installed`。

研究來源：[ASLP-lab/MeanVC2](https://github.com/ASLP-lab/MeanVC2) 與 [arXiv:2606.09050](https://arxiv.org/abs/2606.09050)。上游 repo 標示 Apache-2.0，README 記載 Python 3.11、PyTorch／TorchAudio 2.5.1 CUDA 12.1 與模型初始化流程；README 報告的 40 ms chunk、約 110 ms first-packet latency 是上游數字，不能套用到 RTX 5060 Ti、Windows、AetherTune audio-rack 或完整 virtual routing。

## 研究順位

MeanVC2 是 Seed-VC established baseline 之後，AetherTune 下一順位要 intake 的 Streaming VC 候選；通過同一 corpus、audio-rack 與 LIVE_GATE 後，才和後續 X-VC／新 streaming zero-shot 候選做 A/B。它不是目前主線，也尚未完成來源／模型／環境／GPU／音訊 E2E 驗證。

## 不可提前宣稱

- 不下載 checkpoint 就不能寫成 runtime PASS。
- 上游 110 ms 不能寫成 AetherTune LIVE PASS。
- repo 的 Apache-2.0 標示只涵蓋程式碼授權範圍；checkpoint、訓練資料及衍生權重須分別核對使用條款和來源。
- 官方提供的 Windows standalone 是 CPU-only executable；不能據此推論 native Python GPU runtime 不可行或可行。Windows／RTX 5060 Ti Python runtime 尚未驗證。
- 官方依賴包含 S3PRL、Fairseq、FunASR、SoX／PyWorld 與 pedalboard 等元件；固定 revision 後須先做依賴、平台與 license inventory，再建立隔離環境。
- source／revision／模型條款／Windows runtime 等 intake gate 見 [`docs/streaming-vc-candidate-intake-2026-09-26.md`](../../docs/streaming-vc-candidate-intake-2026-09-26.md)。
- 需要與 RVC、Seed-VC realtime、後續候選使用同一固定 corpus、同一 rack、同一 gate。

## 首次驗收順序

1. source/revision/license intake 與 dependency audit。
2. RTX 5060 Ti 16GB 的 isolated runtime smoke。
3. fixed corpus 的 offline／headless stream output validation。
4. real capture → backend → audio-rack → routing → loopback 的 `LIVE_GATE`。
5. acoustic objective 與 human blind listening；沒有這兩層不能下自然度結論。
