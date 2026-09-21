# VCClient RVC latency／buffer／斷音矩陣

日期：2026-09-21（Asia/Taipei）

## 使用方式

```powershell
& .\tools\vcclient-rvc-latency-matrix.ps1 `
  -SlotIndex 7 `
  -FfmpegPath 'C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe'
```

矩陣先測 `0.25 / 0.50 / 0.75 / 1.00 s`，每個 chunk 記錄 HTTP round-trip latency、response bytes、4-byte 對齊、finite／non-zero 統計、invalid reason 與 RMS。短測全部 `PASS` 且零 invalid chunk 才會建立 600 秒 input 並執行長測；短測失敗時長測記錄 `BLOCKED`，不會產生假穩定性數據。probe 即使能形成整體非零 WAV，只要任何 chunk 是 empty、short、unaligned、全零或 NaN/Infinity，矩陣就標 `DEGRADED`。
矩陣預設使用專案目前 active slot `7`；每列另記錄 `requested_slot_index`、`active_slot_index` 與 `slot_model_evidence`。600 秒分支會把實際建立的 `stability-input.wav` 傳給 probe；短測未全部 `PASS` 時不建立或執行長測。

## 最新結果

最新 bounded post-gate artifact：`artifacts/vcclient-rvc-latency-matrix-postgate/d89946fe-9d02-4445-a70e-3fa6540a6708/vcclient-rvc-latency-matrix.json`。

這次以 Sage slot 7 驗證 requested／active slot 與 model evidence；四組短測結果如下：

| chunk | 狀態 | chunks | dropout | p50／p95 |
|---:|---|---:|---:|---:|
| 0.25 s | `DEGRADED` | 60 | 58/60 | 1.359／28.043 ms |
| 0.50 s | `DEGRADED` | 30 | 26/30 | 1.577／21.338 ms |
| 0.75 s | `DEGRADED` | 20 | 17/20 | 2.381／25.215 ms |
| 1.00 s | `DEGRADED` | 15 | 13/15 | 2.544／24.252 ms |
| stability（`stability_seconds=0`） | `BLOCKED` | — | — | 短測未全部 PASS，依 gate 不執行 |

所有短測都記錄 requested slot `7`、active slot `7` 與 `Sage_CN_HeroicFemale.pth` model evidence；整體輸出仍有 finite/non-zero WAV，但逐 chunk 有 4-byte 全零 response，因此不能當成穩定 PASS。這是 bounded post-gate／slot contract check，不是 600 秒 realtime 驗收。

修改前的 Wukong historical/full-gate evidence 仍保留於 `artifacts/vcclient-rvc-latency-matrix-final/4903f51e-a371-49c4-92a3-4b6b0a9953e5/vcclient-rvc-latency-matrix.json`；其短測 dropout 為 58/60、22/30、15/20、11/15，不能與本次 Sage slot 7 結果混用。

這個矩陣是驗收工具與證據格式，不是把離線 FCPE GPU RTF 當成 realtime latency。需等 packaged frontend 修復或改用相容的 realtime host 後重新跑。
