# VCClient RVC 短音檔 Probe

日期：2026-09-20（Asia/Taipei）

## 結論

目前狀態：`BLOCKED`（VCClient REST conversion package error）。

這一輪已證明服務可以啟動、slot 可以列出、四組本機 `.pth/.index` 可以被 VCClient 的 slot manager 讀到，並且 `Sage_CN_HeroicFemale` 回報 `pyTorchRVCv2`、48 kHz、FCPE；但短音檔送入 `/api/voice-changer/convert_chunk_bulk` 時回傳 HTTP 500，因此沒有取得可驗證的輸出 WAV。RVC role model 仍維持 `candidate`，不能標成 `ready`。

## 可重跑命令

先啟動 VCClient，然後在另一個 PowerShell 執行：

```powershell
Set-Location D:\AetherTune
& .\tools\vcclient-rvc-probe.ps1 `
  -FfmpegPath 'C:\Users\User\AppData\Local\CapCut\Apps\8.5.0.3590\ffmpeg.exe'
```

每次執行會在 `artifacts/vcclient-rvc-test/<run_id>/` 寫入 `vcclient-rvc-probe.json`。這些 artifact 被 `.gitignore` 排除，不會把音檔或第三方模型推送到 Git。

## 本次證據

| Gate | 結果 | 證據 |
|---|---|---|
| VCClient Web UI | PASS | `GET http://127.0.0.1:18000/` 回傳 HTTP 200 |
| RVC slots | PASS | `GET /api/slot-manager/slots` 列出 `Chinese_Narrator_Uncle`、`Kafka_CN_Yujie`、`Sage_CN_HeroicFemale`、`Wukong_HeroicMale` |
| Sage runtime config | PASS | `slot_index=7`、`inferencer_type=pyTorchRVCv2`、`sample_rate=48000`、`pitch_estimator=fcpe` |
| GPU selection | PASS（選擇層） | VCClient API 回報 RTX 5060 Ti device 0；log 回報 `get_pytorch_device: cuda:0` |
| REST audio conversion | BLOCKED | HTTP 500：`'VoiceChanger' object has no attribute 'vc_chunk_sec'`；bulk 路徑另報 `'SlotInfo' object has no attribute 'chunk_sec'` |
| Output WAV | WAITING | 本次沒有有效 conversion response；不能用歷史 log 或模型檔案代替輸出 artifact |
| Restart persistence | BLOCKED | 重啟後 VCClient 將內部 module/sample 狀態判為缺失並進入下載；log 隨後顯示 sample model file 不存在，process 沒有維持服務 |

## 解讀與下一步

- 這是目前 VCClient `2.1.4-alpha` packaged REST path 的可重現錯誤，不是 AetherTune `.venv` 的 Torch CUDA probe。
- 目前不能只靠 API 回報的 `chunk_sec` 欄位繞過內部 `SlotInfo` 例外，也不應直接修改第三方打包檔案。
- 本次曾以已核對 hash 的 `Sage_CN_HeroicFemale` 建立 `model_dir\7`（包含 `.pth`、`.index`、`params.json`），但重啟後 packaged runtime 又回報 module/sample 缺失；因此目前不能宣稱 role slot 已持久化可直接使用。
- 下一步應優先比對 VCClient 上游修正版／相容 package，或改用其前端 Socket.IO／實體 client path 做測試；修正後必須重新產生 output WAV、input/output hash、GPU/provider 與 latency evidence。
- 在取得輸出 WAV 前，`docs/vcclient-runtime-gate.md` 與 `docs/wiring-verification-latest.md` 維持 WAITING/BLOCKED，不得宣稱 RVC 即時端到端完成。
