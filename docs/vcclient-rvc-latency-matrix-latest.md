# VCClient RVC latency／buffer／斷音矩陣

日期：2026-09-21（Asia/Taipei）

## 使用方式

```powershell
& .\tools\vcclient-rvc-latency-matrix.ps1 `
  -SlotIndex 7 `
  -FfmpegPath 'C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe'
```

矩陣先測 `0.25 / 0.50 / 0.75 / 1.00 s`，每個 chunk 記錄 HTTP round-trip latency、response bytes、全零輸出與 RMS。短測全部 `PASS` 且零 dropout 才會建立 600 秒 input 並執行長測；短測失敗時長測記錄 `BLOCKED`，不會產生假穩定性數據。probe 雖可能產生整體非零 WAV，但只要某些 chunk 只有 4-byte 全零 response，矩陣就標 `DEGRADED`。
矩陣預設使用專案目前 active slot `7`；每列另記錄 `requested_slot_index`、`active_slot_index` 與 `slot_model_evidence`。600 秒分支會把實際建立的 `stability-input.wav` 傳給 probe；短測未全部 `PASS` 時不建立或執行長測。

## 最新結果

最新 artifact：`artifacts/vcclient-rvc-latency-matrix-final/4903f51e-a371-49c4-92a3-4b6b0a9953e5/vcclient-rvc-latency-matrix.json`。

修正 probe 的逐 chunk gate 後，Wukong role 最新結果如下：

| chunk | 狀態 | chunks | dropout | p50／p95 |
|---:|---|---:|---:|---:|
| 0.25 s | `DEGRADED` | 60 | 58 | 1.547／16.024 ms |
| 0.50 s | `DEGRADED` | 30 | 22 | 1.720／21.891 ms |
| 0.75 s | `DEGRADED` | 20 | 15 | 2.331／24.906 ms |
| 1.00 s | `DEGRADED` | 15 | 11 | 2.421／21.755 ms |
| 600 s | `BLOCKED` | — | — | 短測未全部 PASS，依 gate 不執行 |

所有短測仍能形成整體 finite/non-zero WAV，但逐 chunk 有 4-byte 全零 response；因此不能當成穩定 PASS。另有 slot lifecycle／`SlotInfo.chunk_sec` HTTP 500 證據。

這個矩陣是驗收工具與證據格式，不是把離線 FCPE GPU RTF 當成 realtime latency。需等 packaged frontend 修復或改用相容的 realtime host 後重新跑。
