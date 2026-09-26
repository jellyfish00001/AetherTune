# MeanVC2（研究候選）

狀態：`PLANNED / candidate / not installed`。

研究來源：[ASLP-lab/MeanVC2](https://github.com/ASLP-lab/MeanVC2) 與 [arXiv:2606.09050](https://arxiv.org/abs/2606.09050)。上游將它描述為 streaming zero-shot voice conversion，並主張 40 ms chunk、約 110 ms first-packet latency 與 Apache-2.0；這些數字不能直接套用到 RTX 5060 Ti、Windows、AetherTune audio-rack 或完整 virtual routing。

## 研究順位

MeanVC2 是 Seed-VC established baseline 之後，AetherTune 下一順位要 intake 的 Streaming VC 候選；通過同一 corpus、audio-rack 與 LIVE_GATE 後，才和後續 X-VC／新 streaming zero-shot 候選做 A/B。它不是目前主線，也尚未完成來源／模型／環境／GPU／音訊 E2E 驗證。

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
