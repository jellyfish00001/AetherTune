# Seed-VC 最新驗證

更新日期：2026-09-22

## 結論

`offline-v1` 已在本機 RTX 5060 Ti 上完成男聲／女聲雙向實際推論，並完成 60 秒長音檔測試；`realtime-tiny` 已完成 3 block smoke 與 200 block／60 秒連續 headless GPU streaming。官方 GUI callback user-flow 與 VB-CABLE／Voicemeeter synthetic virtual route 也已在受控非沙箱環境實測通過，但這些仍不等同實體麥克風 E2E、Light Host full-chain、人工聽測或完整 `LIVE <= 5s`。

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
| GUI／PortAudio callback user-flow | PASS | 官方 `real-time-gui.py`；CUDA available；MME input `麥克風 (HyperX QuadCast S)`、output `CABLE Input (VB-Audio Virtual C)`；四個 case 均 finite／非零且與 deterministic input 不同 | `artifacts/seed-vc/gui-userflow/phase-20260922-final/gui-userflow-report.json` |
| VB-CABLE／Voicemeeter synthetic virtual route | PASS | `CABLE Input → CABLE Output` 與 `Voicemeeter Input → B1 → Voicemeeter Out B1` 均 144000/144000 frames、非零 RMS；Remote API route check 也保存 B1 設定與內部 level | [`wiring-verification-latest.md`](wiring-verification-latest.md)、`artifacts/voicemeeter-b1-route-check.json` |
| 完整 mic E2E／audio-rack／LIVE gate | WAITING | callback 輸入仍是 deterministic WAV；尚未保存實體麥克風 → backend → Light Host full-chain → virtual route 的 first-packet timing、dropout／underrun 與人工聽測 | `docs/live-gate.md` 契約；synthetic route PASS 不等於完整 evidence |

GUI callback 四個 case 的最新訊號摘要：

| reference | input seconds | output seconds | output RMS | difference RMS | zero-lag correlation |
|---|---:|---:|---:|---:|---:|
| `female-young-f004` | 10.5 | 10.5 | 0.01164 | 0.02083 | 0.00196 |
| `female-sister-f003` | 3.9 | 3.9 | 0.01351 | 0.02349 | -0.05135 |
| `female-warm-f005` | 3.9 | 3.9 | 0.01372 | 0.02290 | 0.01413 |
| `female-fresh-f006` | 3.9 | 3.9 | 0.02323 | 0.02892 | 0.05450 |

首個 case 額外保留 15 秒 startup grace，原因是首次 GUI callback 的 model／VAD warm-up；這是測試 harness 的輸出捕捉措施，不是把 warm-up 延遲隱藏或宣稱 `LIVE`。

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

官方 GUI callback user-flow（輸出只到 VB-CABLE，不送往 Discord／OBS）：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-gui-userflow-test.py --preflight
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-gui-userflow-test.py `
  --output .\artifacts\seed-vc\gui-userflow\<run-id>
```

Voicemeeter virtual route smoke（只播放合成音，不使用實體麥克風，也不修改
Voicemeeter 參數）：

```powershell
& .\.venv\Scripts\python.exe .\tools\virtual_cable_loopback.py `
  --output-fragment 'Voicemeeter Input' `
  --input-fragment 'Voicemeeter Out B1' `
  --out .\artifacts\voicemeeter-b1-loopback.wav `
  --report .\artifacts\voicemeeter-b1-loopback.json
& .\.venv\Scripts\python.exe .\tools\voicemeeter-route-check.py `
  --out .\artifacts\voicemeeter-b1-route-check.wav `
  --report .\artifacts\voicemeeter-b1-route-check.json
```

## 已知警告與未完成項目

- 上游推論流程提示應明確傳入 `sampling_rate`；目前仍能產生結果，但應在後續 wrapper 修補或向上游確認。
- checkpoint 載入時略過 `estimator.input_pos` 與 `estimator.f0_embedder.weight` 兩個 shape mismatch keys；本次沒有因此中止，但尚未完成品質回歸。
- `realtime-tiny` wrapper 現在 local-first 並預設離線；本機 cache 包含 CampPlus、HiFT 與 Whisper assets。若 cache 不完整，需明確加 `--allow-network-assets`。
- 官方 GUI／PortAudio callback 與 synthetic virtual route 已通過，但 deterministic callback／合成音不等於實體麥克風內容已經過完整輸入；仍需 Light Host full-chain、人工聽測、10 分鐘以上穩定性與 underrun/dropout 證據。
- 尚未做人工聽測、MOS／相似度比較、10 分鐘以上 realtime 穩定性與多說話者測試；60 秒 headless PASS 不能替代實體裝置 E2E。
- 這個 PASS 只涵蓋離線 WAV 產生；CosyVoice2 與 Breeze TTS 2 也已各自完成 CUDA TTS 輸出，但人工音質與即時 latency 仍需分開評估。
