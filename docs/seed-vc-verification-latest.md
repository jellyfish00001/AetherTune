# Seed-VC 最新驗證

更新日期：2026-09-21

## 結論

`offline-v1` 已在本機 RTX 5060 Ti 上完成男聲／女聲雙向實際推論，並完成 60 秒長音檔測試；`realtime-tiny` 已完成 3 block smoke 與 200 block／60 秒連續 headless GPU streaming。這些是「可執行並產檔」的 PASS，不等同 PortAudio 麥克風端到端或官方 GUI 裝置鏈路已驗收。

| 測試 | 狀態 | RTF | 輸出 | manifest |
|---|---|---:|---|---|
| 男聲 → 女聲 | PASS | 1.1239 | `artifacts/seed-vc/latest-male-to-female/vc_voice-male-m1_voice-female-f1_1.0_30_0.7.wav` | `artifacts/seed-vc/latest-male-to-female/seed-vc-run.json` |
| 女聲 → 男聲 | PASS | 0.3672 | `artifacts/seed-vc/latest-female-to-male/vc_voice-female-f1_voice-male-m1_1.0_30_0.7.wav` | `artifacts/seed-vc/latest-female-to-male/seed-vc-run.json` |

`offline-v1` 另外以 60 秒男聲輸入 → 女聲 reference 測試通過：RTF `0.3165`，輸出為 `artifacts/seed-vc/long/male-to-female/vc_source-60s_voice-female-f1_1.0_30_0.7.wav`，manifest 為同資料夾的 `seed-vc-run.json`。

| 測試 | 狀態 | 實測結果 | 證據 |
|---|---|---|---|
| realtime-tiny headless GPU | PASS | 3 個 0.3 秒 block 均 finite／non-zero；warmup 後 p50 `190.6 ms`，steady-state RTF 約 `0.633` | `artifacts/seed-vc/realtime-tiny/seed-vc-realtime-tiny-test.json` |
| realtime-tiny 60 秒連續 headless GPU | PASS | 200 個 0.3 秒 block；p50 `122.0 ms`、p95 `146.6 ms`、mean RTF `0.4312`、200/200 finite／non-zero | `artifacts/seed-vc/realtime-long-60s/seed-vc-realtime-tiny-test.json` |
| realtime-tiny warmup | INFO | 首個 block 約 `9.34 s`；模型載入約 `38.69 s`，不可當成穩態延遲 | 同上 |
| PortAudio／麥克風端到端 | WAITING | headless 測試刻意繞過 PortAudio，尚未驗證實際音訊裝置與回聲／斷音 | 同上 `audio_device_e2e` |

Runtime：`tools/venvs/seed-vc`、Python 3.10、Torch `2.7.1+cu128`、CUDA available `True`。Checkpoint SHA-256：`8EC8841B20BB46DF9F7E8E570A6946A4B87B940133C7F0E778487FF33841F720`。

## 可重跑命令

```powershell
Set-Location D:\AetherTune
& .\tools\seed-vc-setup.ps1
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-male-m1.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\male-to-female `
  -Fp16
```

反向測試只需交換 `-Source`／`-Target` 並改用另一個 `-OutputDir`。腳本不會覆蓋輸入檔。

## 已知警告與未完成項目

- 上游推論流程提示應明確傳入 `sampling_rate`；目前仍能產生結果，但應在後續 wrapper 修補或向上游確認。
- checkpoint 載入時略過 `estimator.input_pos` 與 `estimator.f0_embedder.weight` 兩個 shape mismatch keys；本次沒有因此中止，但尚未完成品質回歸。
- `realtime-tiny` wrapper 現在 local-first 並預設離線；本機 cache 包含 CampPlus、HiFT 與 Whisper assets。若 cache 不完整，需明確加 `--allow-network-assets`。
- `realtime-tiny` 已完成 60 秒／200 block headless streaming latency 測試；官方 GUI、PortAudio、實際麥克風與回放端到端仍未驗證。
- 尚未做人工聽測、MOS／相似度比較、10 分鐘以上 realtime 穩定性與多說話者測試；60 秒 headless PASS 不能替代實體裝置 E2E。
- 這個 PASS 只涵蓋離線 WAV 產生；CosyVoice2 與 Breeze TTS 2 也已各自完成 CUDA TTS 輸出，但人工音質與即時 latency 仍需分開評估。
