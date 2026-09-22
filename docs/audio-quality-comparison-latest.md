# 既有四種 profile WAV 批次比較

更新日期：2026-09-21

## 結論

本報告只涵蓋目前既有的四種 backend/profile 與 11 個樣本；它不是新研究矩陣的完整結果。所有樣本皆可解碼、finite、non-zero，signal-level 批次檢查 `PASS`。批次工具現在會保留任何 `BLOCKED` row，不會被同一 backend 的有效 row 掩蓋。本報告的「音量」是 RMS／peak dBFS proxy，「品質」只涵蓋檔案有效性、靜音比例與 clipping；不代表 MOS、自然度、聲線相似度或人工聽感通過。

可重跑命令：

```powershell
Set-Location D:\AetherTune
& .\.venv\Scripts\python.exe .\tools\audio-quality-batch.py
```

原始 JSON／CSV：`artifacts/audio-quality-comparison/audio-quality-comparison.json`、`audio-quality-comparison.csv`。

## 本次比較集合

| 後端 | 樣本 | sample rate | duration | RMS dBFS | peak dBFS | clipping |
|---|---:|---:|---:|---:|---:|---:|
| RVC + FCPE GPU | 5 個角色輸出 | 40/48 kHz | 13.38 ～ 14.86 s | -22.53 ～ -14.62 | -2.48 ～ -0.41 | 0 |
| Seed-VC | 男→女、女→男 | 22.05 kHz | 13.40 ～ 14.87 s | -33.20 ～ -30.23 | -11.70 ～ -9.33 | 0 |
| CosyVoice2 | male/female clone | 24 kHz | 12.64 ～ 14.72 s | -34.26 ～ -25.91 | -15.66 ～ -7.22 | 0 |
| Breeze TTS 2 | male/female clone | 24 kHz | 9.68 s | -31.94 ～ -31.76 | -16.04 ～ -12.25 | 0 |

## 如何解讀

- RVC 這批輸出有 40 kHz 與 48 kHz，不能直接和其他 22.05／24 kHz 的數值做音質排名；若要正式比較，先重取樣到同一 sample rate，再以同一段內容、同一音量基準與人工聽測比較。
- RMS／peak 不等於響度。這次沒有把不同後端輸出正規化後再比較，避免把原始輸出問題掩蓋掉；若要做播放體驗比較，另做一份明確標記 `normalized` 的副本。
- 全部樣本 clipping ratio 為 0、皆為 finite 且 non-zero；這只證明 WAV 訊號有效，不代表 Seed-VC、CosyVoice2 或 Breeze 的語音內容與聲線品質一致。
- 沒有把 VCClient packaged RVC 的全零／4-byte chunk 放進比較集合，因為那是已知 `DEGRADED` 的即時鏈路證據，不是有效完成輸出。

## 後續尚缺

1. 以同一段 source／transcript 建立四方法可比的 paired set。
2. 產生同 sample rate、同 loudness policy 的 normalized comparison set。
3. 人工聽測：內容正確性、聲線相似度、自然度、噪音、斷音與情緒保留。
4. 若要宣稱「品質」而非「訊號有效」，需另建盲測或 MOS 記錄，不能由本報告的 RMS／peak 推導。
