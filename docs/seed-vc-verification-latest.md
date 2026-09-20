# Seed-VC 最新驗證

更新日期：2026-09-20

## 結論

`offline-v1` 已在本機 RTX 5060 Ti 上完成男聲／女聲雙向實際推論，兩次均產生 WAV 並留下輸入、checkpoint、Torch runtime 與輸出 SHA-256 manifest。這是「可執行並產檔」的 PASS，不等同聲音品質、即時性或長時間穩定性已驗收。

| 測試 | 狀態 | RTF | 輸出 | manifest |
|---|---|---:|---|---|
| 男聲 → 女聲 | PASS | 0.3383 | `artifacts/seed-vc/male-to-female/vc_voice-male-m1_voice-female-f1_1.0_30_0.7.wav` | `artifacts/seed-vc/male-to-female/seed-vc-run.json` |
| 女聲 → 男聲 | PASS | 0.3997 | `artifacts/seed-vc/female-to-male/vc_voice-female-f1_voice-male-m1_1.0_30_0.7.wav` | `artifacts/seed-vc/female-to-male/seed-vc-run.json` |

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
- 尚未執行 `realtime-tiny` 官方 GUI／即時延遲測試。
- 尚未做人工聽測、MOS／相似度比較、長音檔與多說話者測試。
- CosyVoice、Breeze TTS 2 與 STT 尚未安裝或執行；它們維持 `PLANNED`，不列入本次 PASS。
