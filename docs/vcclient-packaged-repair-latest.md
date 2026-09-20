# VCClient packaged RVC 修復與實測

日期：2026-09-21（Asia/Taipei）

## 結論

目前 VCClient `2.1.4-alpha` 的官方 runtime 資產已恢復並通過 20/20 SHA-256 檢查；本機 Sage 與 Wukong `.pth/.index` 也能透過官方 uploader 建立 slot。可是 packaged REST conversion 仍無法通過真實角色模型驗收，因此這一項是 `BLOCKED`，不能宣稱 VCClient 即時 RVC 已可用。

## 已完成

- `tools/vcclient-runtime-repair.ps1 -Download -IncludeSampleModels`：官方 modules/sample 共 20 個，SHA-256 驗證 `PASS`。
- `tools/vcclient-rvc-register.ps1`：以 16 MiB chunks 上傳 `.pth/.index`、concat、註冊獨立 slot；不覆寫已有 slot，也不呼叫會清空 filesystem 的 `/api/operation/initialize`。
- Sage slot 7：`.pth + .index`、`pyTorchRVCv2`、`sample_rate=48000`、`chunk_sec=0.5`，註冊成功。
- Wukong slot 8：`.pth + .index`、`pyTorchRVCv2`、`chunk_sec=0.5`，註冊器實測 `PASS`。
- `tools/vcclient-rvc-probe.ps1` 現在記錄每 chunk latency、p50/p95、輸出 RMS、peak、有限值與非零 sample，並拒絕全零或無效輸出。

## 目前阻塞證據

最新 Sage role probe：`artifacts/vcclient-rvc-test/d4833d9b-0f08-4151-b659-a433d0597a77/vcclient-rvc-probe.json`。

| 檢查 | 結果 |
|---|---|
| slot/model/index metadata | PASS；`Sage_CN_HeroicFemale.pth/.index`、`chunk_sec=0.5` |
| REST bulk conversion | BLOCKED；HTTP 500，`'SlotInfo' object has no attribute 'chunk_sec'` |
| REST non-bulk conversion | BLOCKED；同一 packaged pipeline error |
| valid WAV / non-zero output | 未達到；不可把 120-byte 全零 response 當成 PASS |
| embedded ONNX provider | `CPUExecutionProvider`；available provider 清單不是 GPU proof |

VCClient 的 `/api/operation/initialize` 在本版會移除/rebuild `model_dir` 與 modules 狀態，不能放進一般註冊或 probe 流程。`-InitializeAfterConfigure` 只有在明確要重現 lifecycle 問題時才使用。

## 重跑方式

先啟動 VCClient，並確認 runtime：

```powershell
& .\tools\vcclient-runtime-repair.ps1 -Download
```

建立新 slot（不要使用既有 slot index）：

```powershell
& .\tools\vcclient-rvc-register.ps1 `
  -ModelPath .\models\weights\Wukong_HeroicMale.pth `
  -IndexPath .\models\indexes\Wukong_HeroicMale.index `
  -SlotIndex 8 `
  -Name 'AetherTune Wukong Heroic Male'
```

再透過 VCClient UI/API 選擇該 slot，執行 probe。FFmpeg 必須傳絕對路徑：

```powershell
& .\tools\vcclient-rvc-probe.ps1 `
  -SlotIndex 8 `
  -FfmpegPath 'C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe'
```

Probe 只有在輸出 bytes 足夠、float32 sample 有限且至少一個非零 sample 時才會 `PASS`。目前若再出現 `SlotInfo.chunk_sec`，請保留 JSON/log，等待相容版 VCClient 或改用專案 RVC WebUI offline route。

## 與專案 RVC 的邊界

四組本機角色的 `RVC + FCPE + cuda:0` offline route 仍是 `PASS`，入口是 `tools/rvc-fcpe-gpu-infer.py`。它與 VCClient packaged runtime 是兩套不同環境；offline PASS 不能代替 realtime frontend PASS。
