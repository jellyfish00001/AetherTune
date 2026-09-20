# RVC + FCPE + GPU 最新驗證

日期：2026-09-21（Asia/Taipei）

## 結論

目前四組本機 RVC 角色模型都已透過專案 RVC WebUI pipeline 完成真正的 `FCPE + cuda:0` 離線推論，產生非零 WAV。這是 RVC 角色模型與 FCPE GPU 的 `PASS`；尚不代表即時 Discord／OBS 音訊鏈路與長時間 latency 已驗收。

## 最新實測矩陣

測試輸入：`dataset/reference-voices/voice-male-m1.wav`；index rate `0.75`；pitch `0`。

| 角色模型 | 狀態 | sample rate | 輸出 bytes | RTF | 輸出 SHA-256 |
|---|---|---:|---:|---:|---|
| Chinese_Narrator_Uncle | PASS | 40,000 | 1,188,844 | 1.0561 | `6f57d0e2fcaf328115095315b9e6eb827d25e75f515f6cf397c09fd63d4e071f` |
| Kafka_CN_Yujie | PASS | 40,000 | 1,188,844 | 0.2965 | `bea7c386d79578e4dbae85505933b8502ec22ca2ee626a842d3da172123e94b7` |
| Sage_CN_HeroicFemale | PASS | 48,000 | 1,426,604 | 0.2846 | `130b9eabbc388f509c5a71da25a83b76554b9ac1427033f7841f7268110b12e7` |
| Wukong_HeroicMale | PASS | 40,000 | 1,188,844 | 0.2569 | `226ae043e49d9fd8dddabbf177ce9ba24ce9372e8ed3dac74640977fcc54b28d` |

共同 runtime 證據：

- `f0_method=fcpe`
- `device=cuda:0`
- GPU：`NVIDIA GeForce RTX 5060 Ti`
- Torch：`2.7.1+cu128`
- 四組 `.pth/.index` SHA-256 與 `models/model-register.csv` 一致

## 可重跑命令

單一角色：

```powershell
Set-Location D:\AetherTune
& .\.venv\Scripts\python.exe tools\rvc-fcpe-gpu-infer.py `
  --model .\models\weights\Sage_CN_HeroicFemale.pth `
  --index .\models\indexes\Sage_CN_HeroicFemale.index `
  --input .\dataset\reference-voices\voice-male-m1.wav `
  --output .\artifacts\rvc-fcpe-gpu\Sage_CN_HeroicFemale.wav
```

每次輸出旁會寫入同名 JSON，記錄模型／index／input／output hash、FCPE、CUDA device、RTF 與 sample rate。四組矩陣使用的入口是 `tools/rvc-fcpe-gpu-infer.py`，不依賴 VCClient packaged ONNX provider。

## 與 VCClient 的關係

- `tools/vcclient-rvc-probe.ps1` 仍可測試官方 ONNX sample slot，但該 sample 是 `RMVPE ONNX`，目前 settings 會使用 `CPUExecutionProvider`；它不是本次 `FCPE + GPU` 證據。
- 本次 FCPE GPU PASS 證明 RVC WebUI offline pipeline 與四組角色模型可用；VCClient 即時前端仍需另測相容性、buffer、VST、VB-CABLE／Voicemeeter、Discord／OBS。
- 四組模型的來源、授權、訓練 revision 與 dataset metadata 仍應由使用者補齊；runtime PASS 不會自動把 provenance 補成已知。

## 尚未完成

1. Light Host／Graillon 實際 chain 與 bypass／active loopback。
2. VCClient realtime path 使用 FCPE、p50/p95 latency、斷音與 10 分鐘穩定性。
3. Discord／OBS 實際收音與人工聽測。
