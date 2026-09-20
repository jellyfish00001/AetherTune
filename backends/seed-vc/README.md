# Seed-VC／Zero-Shot VC

Seed-VC 是不需先訓練角色模型的 voice conversion 路線：來源音檔提供內容與表現，參考音檔提供目標聲線。官方同時提供離線 VC 與即時 GUI；本專案已先完成 `offline-v1` 的獨立環境與男／女雙向實際推論，`realtime-tiny` 仍保留給下一階段即時延遲測試。

## 輸入契約

- `source`：要保留內容的來源語音。
- `target`：1–30 秒、乾淨、單一說話者的參考語音。
- 建議先用 `dataset/reference-voices/` 的男聲與女聲各跑一次。
- 輸出必須記錄 source/target hash、checkpoint、設定、裝置與輸出 hash。

## 模型選擇

| profile | 官方模型 | 用途 | 大小／限制 |
|---|---|---|---|
| `realtime-tiny` | `Plachta/Seed-VC` 的 `DiT_uvit_tat_xlsr_ema.pth` | 即時 VC | 約 142 MB；官方 README 的 real-time 路線 |
| `offline-v1` | `seed-uvit-whisper-small-wavenet` | 離線 VC | 約 440 MB checkpoint；品質優先 |
| `v2` | `hubert-bsqvae-small` | accent／speaker disentanglement | 需同時下載 CFM/AR 資產，延後處理 |

## 使用

`tools/seed-vc-setup.ps1` 會建立獨立的 `tools/venvs/seed-vc`；`tools/seed-vc-run.ps1` 執行 `offline-v1` profile：檢查第三方 repo、checkpoint、輸入檔與輸出資料夾，再呼叫官方 `inference.py`。每次成功執行會寫出 `seed-vc-run.json`，記錄來源／目標／checkpoint／設定／Torch runtime／輸出 SHA-256 與 inference log。它不會自動覆蓋輸入，也不會把輸出誤登記成 ready model。`realtime-tiny` 要用官方 `real-time-gui.py`，不能把 tiny checkpoint 硬塞進 offline config。

```powershell
& .\tools\seed-vc-run.ps1 `
  -Source .\dataset\reference-voices\voice-male-m1.wav `
  -Target .\dataset\reference-voices\voice-female-f1.wav `
  -OutputDir .\artifacts\seed-vc\male-to-female `
  -Fp16
```

## 本機驗證結果

截至 2026-09-20，`offline-v1` 已在 RTX 5060 Ti 上以 Torch `2.7.1+cu128` 完成兩個方向的實際推論：

- 男聲 → 女聲：RTF `0.3383`，結果與 manifest 位於 `artifacts/seed-vc/male-to-female/`。
- 女聲 → 男聲：RTF `0.3997`，結果與 manifest 位於 `artifacts/seed-vc/female-to-male/`。

這代表「可以執行並產生 WAV」已通過；聲音相似度、自然度與即時使用仍需人工聽測及獨立 latency 驗收。兩次推論都留下上游 warning：`sampling_rate` 建議明確傳入，以及部分 estimator keys 因 shape mismatch 被略過；目前不影響產檔，但列為後續清理項目。完整紀錄見 [`docs/seed-vc-verification-latest.md`](../../docs/seed-vc-verification-latest.md)。

官方 repo：<https://github.com/Plachtaa/seed-vc>

模型與 license 以官方 Hugging Face model card 為準；Seed-VC code/model page 目前標示 GPL-3.0，使用前仍需核對上游條款與輸入聲音授權。
