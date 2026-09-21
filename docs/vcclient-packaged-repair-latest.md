# VCClient packaged RVC 修復與實測

日期：2026-09-21（Asia/Taipei）

## 結論

目前 VCClient `2.1.4-alpha` 的官方 runtime 資產已恢復並通過 20/20 SHA-256 檢查；本機 Sage 與 Wukong `.pth/.index` 也能透過官方 uploader 建立 slot。可是 packaged REST conversion 仍無法通過真實角色模型驗收，因此這一項是 `BLOCKED/DEGRADED`，不能宣稱 VCClient 即時 RVC 已可用。

## 已完成

- `tools/vcclient-runtime-repair.ps1 -Download -IncludeSampleModels`：官方 modules/sample 共 20 個，SHA-256 驗證 `PASS`。
- `tools/vcclient-rvc-register.ps1`：以 16 MiB chunks 上傳 `.pth/.index`、concat、註冊獨立 slot；不覆寫已有 slot，也不呼叫會清空 filesystem 的 `/api/operation/initialize`。
- Sage slot 7：`.pth + .index`、`pyTorchRVCv2`、`sample_rate=48000`、`chunk_sec=0.5`，註冊成功。
- Wukong slot 8：`.pth + .index`、`pyTorchRVCv2`、`chunk_sec=0.5`，註冊器實測 `PASS`。
- `tools/vcclient-rvc-probe.ps1` 現在記錄每 chunk latency、p50/p95、輸出 RMS、peak、有限值與非零 sample；整體 WAV 即使非零，只要任一 chunk 是 4-byte 全零就標成 `DEGRADED`。

## 目前阻塞證據

### 最新 post-gate slot 契約證據

最新 bounded probe：`artifacts/vcclient-rvc-test-postgate/1dc5db0e-8827-432e-94ff-ec252f582d94/vcclient-rvc-probe.json`。

這次只驗證 slot contract 與短 probe，沒有宣稱 600 秒 realtime 通過：

| 檢查 | 結果 |
|---|---|
| requested／active／initial slot | `7 / 7 / 7` |
| slot model evidence | `Sage_CN_HeroicFemale.pth/.index`、`pyTorchRVCv2`、`sample_rate=48000`、`pitch_estimator=rmvpe_onnx` |
| REST bulk conversion | `DEGRADED`；30 chunks 中 28 個回傳 4-byte 全零，只有 2 個非零 chunk |
| 整體輸出 | 有 finite／non-zero sample，但逐 chunk gate 未通過 |

對應的 bounded latency matrix：`artifacts/vcclient-rvc-latency-matrix-postgate/d89946fe-9d02-4445-a70e-3fa6540a6708/vcclient-rvc-latency-matrix.json`。四組短測仍為 `DEGRADED`；stability row 是 `stability_seconds=0` 下因短測 gate 未通過而記錄的 `BLOCKED`，不是 600 秒測試的 PASS 或完成證據。

### Historical／full-gate 證據

以下 Wukong artifact 保留作為修改前的 historical/full-gate evidence，不再是最新 slot 證據：`artifacts/vcclient-rvc-test-final/5ee7d4ac-11ee-4e4e-8c74-999c2efc65e5/vcclient-rvc-probe.json`。

| 檢查 | 結果 |
|---|---|
| slot/model/index metadata | PASS；`Wukong_HeroicMale.pth/.index`、`chunk_sec=0.5` |
| REST bulk conversion | DEGRADED；30 chunks 中 27 個回傳 4-byte 全零，只有 3 個有效 chunk |
| REST non-bulk conversion | BLOCKED；另有同一 packaged pipeline 的 `SlotInfo.chunk_sec` HTTP 500 證據 |
| valid WAV / non-zero output | 整體 WAV 有 finite/non-zero sample，但逐 chunk gate 未通過，不能當成穩定輸出 |
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
  -SlotIndex 9 `
  -Name 'AetherTune Wukong Heroic Male'
```

再透過 VCClient UI/API 選擇該 slot，執行 probe。FFmpeg 必須傳絕對路徑：

```powershell
& .\tools\vcclient-rvc-probe.ps1 `
  -SlotIndex 9 `
  -ConfigureSlot `
  -FfmpegPath 'C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe'
```

Probe 會先核對 `requested_slot_index` 與 VCClient configuration 的 active/current slot，並把 `slot_model_evidence` 寫入 JSON；不一致時直接 `BLOCKED`。只有在輸出 bytes 足夠、float32 sample 有限、至少一個非零 sample 且每個 chunk 都不是全零時才會 `PASS`。目前若再出現 `SlotInfo.chunk_sec` 或全零 chunk，請保留 JSON/log，等待相容版 VCClient 或改用專案 RVC WebUI offline route。

## 與專案 RVC 的邊界

四組本機角色的 `RVC + FCPE + cuda:0` offline route 仍是 `PASS`，入口是 `tools/rvc-fcpe-gpu-infer.py`。它與 VCClient packaged runtime 是兩套不同環境；offline PASS 不能代替 realtime frontend PASS。
