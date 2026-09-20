# VCClient RVC 短音檔 Probe

日期：2026-09-21（Asia/Taipei）

## 結論

官方 sample RVC 路線目前 `PASS`：VCClient slot 0（`黃琴海月(onnx)`）已完成最新一輪 30/30 chunks 的實際轉換，取得非零輸出 WAV，並通過 FFmpeg 解碼。這個 PASS 不等於目前四組自有 `.pth/.index` 角色模型已 ready，也不等於 GPU provider 或 Discord／OBS 即時鏈路已通過。

## 可重跑命令

先啟動 VCClient，確認 `http://127.0.0.1:18000/` 可開啟，再在另一個 PowerShell 執行：

```powershell
Set-Location D:\AetherTune
& .\tools\vcclient-rvc-probe.ps1 `
  -SlotIndex 0 `
  -ChunkSec 0.5 `
  -FfmpegPath 'C:\Users\User\AppData\Local\CapCut\Apps\8.5.0.3590\ffmpeg.exe'
```

每次執行會在 `artifacts/vcclient-rvc-test/<run_id>/` 寫入 `vcclient-rvc-probe.json`、raw stream 與 output WAV。這些 artifact 被 `.gitignore` 排除，不會把音檔或第三方模型推送到 Git。

若 VCClient 重啟後缺少官方 runtime 或 sample model，先執行：

```powershell
& .\tools\vcclient-runtime-repair.ps1 -Download -IncludeSampleModels
```

這個 repair script 會依官方 VCClient log 的 SHA-256 驗證 10 個 runtime module，並恢復官方 sample slot 所需檔案。

## 最新證據

| Gate | 結果 | 證據 |
|---|---|---|
| VCClient Web UI | PASS | `GET http://127.0.0.1:18000/` 回傳 HTTP 200 |
| Official RVC sample slot | PASS | slot 0：`黃琴海月(onnx)`／`kikoto_kurage`、`onnxRVC` |
| Pitch estimator | PASS（選擇層） | slot 回報 `rmvpe_onnx`；FCPE 仍需獨立 runtime artifact，不以 slot label 代替 |
| Chunk conversion | PASS | run `a9449fed-a9ba-4dd1-b8d0-800c24446936`；`total_chunks=30`、`successful_chunks=30`、`converted_bytes=2,880,116` |
| Output WAV | PASS | `output.wav` 1,433,678 bytes；波形 min `-0.099915`、max `0.126221`、avg_abs `0.004667`，不是零輸出 |
| FFmpeg decode | PASS | 14.93 秒、48 kHz、mono、PCM s16le，無 error；SHA-256 `528d98f4ab74b4bdf7c4032eb00704b8a0cdf7e35419c867d6f3cae3e2d3c245` |
| Actual ONNX provider | WAITING | 本次 settings 使用 `gpu_device_id=-1`，log 的 ONNX execution provider 是 `CPUExecutionProvider`；不是 GPU inference PASS |
| 四組自有角色模型 | WAITING | `Chinese_Narrator_Uncle`、`Kafka_CN_Yujie`、`Sage_CN_HeroicFemale`、`Wukong_HeroicMale` 仍是 `candidate`，尚未各自完成輸出驗收 |
| 即時音訊鏈路 | WAITING | Light Host／Graillon／VB-CABLE／Voicemeeter／Discord／OBS 尚未完成實際 loopback 與長時間測試 |

## 探針行為與安全邊界

- `tools/vcclient-rvc-probe.ps1` 預設只使用目前 slot，不修改 VCClient configuration。
- `-ConfigureSlot` 是明確 opt-in；VCClient `2.1.4-alpha` 的 configuration PUT 在部分 packaged 狀態可能清空 slot，不能當作預設流程。
- `-ChunkSec 0.5` 對應目前官方 sample slot 的 standard chunk；探針也會拒絕小於 4096 bytes 的假成功輸出。
- `tools/vcclient-runtime-repair.ps1` 只修復本機 ignored runtime/model assets，不把第三方 binary 或模型加入 Git。

## 下一步

1. 補齊四組自有模型的來源、授權、sample rate、f0、revision、dataset metadata。
2. 逐一把角色模型註冊到 VCClient slot，使用相同 probe 取得非零 output WAV 與 hash。
3. 若需要 GPU，將 VCClient configuration 的 `gpu_device_id` 設為實際 device 0，再重新驗證 log 的實際 provider；`available_providers` 不能代替執行證據。
4. 完成 FCPE runtime probe、Light Host／VB-CABLE loopback、Discord／OBS 收音與人工聽測。
