# RVC + FCPE + GPU 最新驗證

日期：2026-10-01（Asia/Taipei）

## Desktop 整合結論

RVC 已由僅有 planned manifest 改成正式 EngineManager 可啟停的 headless runner。UI 可選四個登錄角色、Mic／來源 WAV、FCPE／RMVPE、音高及 block 參數，並提供預設關閉的自己監聽。RVC 使用 `.pth/.index` 配對，不再要求 zero-shot Reference WAV。

本輪以真正 `desktop-probe.exe` → Rust EngineManager／Windows Job → Python bridge → RVC core 執行，四個角色的 FCPE CUDA 轉換及 CABLE 獨立擷取 `PASS`；Sage 的 RMVPE 備用與實體監聽 callback 亦 `PASS`。虛擬來源 duplex callback、physical Mic、接收端路由、人耳聽評與 LIVE 分開判定。沒有修改或卸載 Windows 裝置／驅動，也沒有修改 ignored upstream。

## 本輪 WAV／播放矩陣

來源是前一輪 Breeze 真實生成的 24 kHz、1.76 秒 WAV：`artifacts/sessions/breeze-switch-check-b6ff37a14e23477bb53e25bc2b0570ab/jobs/0c3ddca3-26c8-4b25-ad30-063d149fd68e/0c3ddca3-26c8-4b25-ad30-063d149fd68e.wav`，SHA-256 `2ed22842bf02ac7b2ecd7fe91b7af57cfa29cbcf3dab89e8b3102ed814722784`。所有 `.pth/.index` 都在 preflight 及 runtime 驗 hash，與 `models/model-register.csv` 對應；每個 report 保存完整模型／index hash。

共同參數：pitch `0`、index rate `0.75`、chunk `160 ms`、crossfade `40 ms`、extra context `1 s`。輸出全部為 48 kHz／1.76 秒、finite／nonzero，播放至 `CABLE Input (VB-Audio Virtual Cable)`／`Windows DirectSound`，擷取 CABLE Output；所有擷取 error 為 `0`。

| 角色／F0 | 狀態 | 載入秒 | 輸出 RMS | block p50／p95 ms | 輸出 WAV SHA-256 |
|---|---|---:|---:|---|---|
| Chinese_Narrator_Uncle／FCPE | PASS | 4.374 | 0.145504 | 25.12／31.69 | `f48a11100835ecc5ddbe01325fc6ae2f1391fe0e4ef4a4c45a1d4e4c8dda416c` |
| Kafka_CN_Yujie／FCPE | PASS | 5.820 | 0.213542 | 24.52／44.49 | `faeef417739c17312265a3cb1d2f9a6e10ca24d03d1fd94fcf1a0e9fdcbce473` |
| Sage_CN_HeroicFemale／FCPE＋監聽 | PASS | 5.003 | 0.124760 | 27.33／27.91 | `f87baf2a6fa6c5da4ad3376df3896bd3874e630aa037f0fabf4426c83b8f0832` |
| Wukong_HeroicMale／FCPE | PASS | 4.670 | 0.226828 | 23.69／27.52 | `65c80e3b8803ad5016848bc633bb54530b54aee2264ba9c3938f83462536e07b` |
| Sage_CN_HeroicFemale／RMVPE | PASS | 19.625 | 0.123176 | 39.19／52.89 | `84b51a073438aac45a9e08507968a84f0095b7a6a826fea57bc77051b95470e5` |

以上時間是本輪 block 處理／載入時間，不是 Mic → Discord 延遲保證。各自 artifact 為 `artifacts/desktop/rvc-narrator-fcpe-20261001/`、`rvc-kafka-fcpe-20261001/`、`rvc-sage-fcpe-monitor-20261001/`、`rvc-wukong-fcpe-20261001/`、`rvc-sage-rmvpe-20261001/`。每個 `report.json` 內含 runtime evidence、來源／輸出／capture SHA-256；`probe.jsonl` 留 lifecycle 與程序 PID。

Runtime：Python `3.10.11`、Torch `2.7.1+cu128`、`cuda:0`、RTX 5060 Ti；warmup 後另檢查 F0 model 真正位於 `cuda:0`。FCPE 權重 hash `b9aeaeb673436eeda50ceafd632aa681aa63417e52eae4207503d180c9b10015`；RMVPE `6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193`；HuBERT `cc8c20f4b90a520757260197a3ff2505705a7adbd20ad9eeaa4e1a9b38442ef5`。固定 source revision 與本機修改的 source hashes 一併記錄，來源邊界見 [source-audit.md](../../reference/source-audit.md)。

Sage WAV 同時送 CABLE／DirectSound 與 HyperX／MME 監聽，各 `84480 frames`、underrun `0`、首次 callback 相差約 `5 ms`；主路由擷取 RMS `0.0519692`。這是 stream／callback 證據，沒有代替實體耳機 loopback 或人耳聽評。

## 本輪虛擬來源 duplex／監聽

`artifacts/desktop/rvc-stream-monitor-final-20261001/report.json`：指定上述 WAV 注入 CABLE，RVC 使用真實 PortAudio duplex stream 執行 `12 秒／75 blocks／576000 frames`，input peak `0.369507`、output peak `0.770508`、finite，underrun／overrun／monitor drops 均 `0`。實體 HyperX／MME 監聽寫入 `576000 frames`、peak `0.770508`、underrun `0`，Stop 後 status=`stopped`。block p50／p95=`29.98／47.11 ms`；主 callback bytes SHA-256 `20006d855727910fcc90dc373e1a5d1d3b32c73182edc6659edcde43fda39e8e`。

這是虛擬來源與 callback `PASS`，B1 capture 仍 `WAITING`，不是 physical Mic／Discord／人耳聽評或 600 秒穩定性。`artifacts/desktop/rvc-process-cleanup-20261001.json` 確認本輪所有已記錄的 probe／service／runner PID 及 RVC 子程序均無殘留，cleanup=`PASS`。

## 可重跑 Desktop 命令

```powershell
Set-Location D:\AetherTune
$taskRvcSource = 'artifacts/sessions/breeze-switch-check-b6ff37a14e23477bb53e25bc2b0570ab/jobs/0c3ddca3-26c8-4b25-ad30-063d149fd68e/0c3ddca3-26c8-4b25-ad30-063d149fd68e.wav'
& .\tools\venvs\seed-vc\Scripts\python.exe app/tests/rvc-audio-smoke.py `
  --source $taskRvcSource --model-id Sage_CN_HeroicFemale `
  --output artifacts/desktop/rvc-sage-recheck --monitor
# 換 model-id 可測其他三個角色；加 --f0-method rmvpe 可測備用 F0。
& .\tools\venvs\seed-vc\Scripts\python.exe app/tests/rvc-audio-smoke.py `
  --source $taskRvcSource --stream-seconds 12 --monitor `
  --output artifacts/desktop/rvc-stream-recheck
```

Smoke harness 用 Seed runtime 擷取，正式 RVC bridge／runner 使用 `.venv`。串流 harness 只把指定 WAV 注入 CABLE，沒有讀實體麥克風；RVC 讀 CABLE Output，主輸出 Voicemeeter Input，獨立擷取 B1。當前 Voicemeeter Remote API `login_code=1`（未啟動），B1 擷取只有低量化噪聲，因此該外部路由保持 `WAITING`；harness 的 callback PASS 不升格 B1 capture PASS。正常使用可直接輸出 CABLE，接收程式選 CABLE Output，毋須啟動 Voicemeeter。

## 初輪失敗與回歸

初輪 native run 未出音：revision 的 Git subprocess，以及 DLL 載入前啟動的阻塞 stdin reader，先後卡在載入。修正為只讀 Git metadata、warmup 後才啟動 control reader，並加 120 秒 DLL／模型載入 watchdog；保留失敗 artifact `rvc-file-smoke-20260930/`、`rvc-file-smoke-fixed-20260930/`、`rvc-file-smoke-importfix-20260930/`，沒有把它們改成 PASS。

回歸：Python runner `10` tests、TTS `35` tests、Rust native process／crash／grandchild cleanup `5` tests、AJV contracts、Playwright Edge preview 與 mock IPC UI、Tauri debug build 全 PASS。Codex Browser 在 `http://127.0.0.1:1420/` 的 1280×720 preview 另複核角色／F0／來源切換；WAV 模式隱藏 Mic 與 Reference WAV，preview START 停用。mock screenshot／console／network report 在 `artifacts/desktop/ui/manual-tts-report.json` 與 `output/playwright/rvc-controls-mock.png`。原生 WebView 的新 UI、人耳聽評、physical Mic、外部 Rack／Discord、600 秒與模型 provenance 仍 WAITING。

根目錄 exe 已更新至當次 build，SHA-256 `42E3496B9BE104B9F0754A554846359FB16B25B32EFE87FC653F8EB522D91E96`。舊視窗 PID `37876` 仍是先前載入版本；未中斷其 resident Breeze。使用新 UI 前從 Tray 的 Exit 完整退出，再開根目錄 `AetherTune.exe`。

## 歷史：2026-09-21 離線 pipeline

## 結論

目前四組本機 RVC 角色模型都已透過專案 RVC WebUI pipeline 完成真正的 `FCPE + cuda:0` 離線推論，產生非零 WAV。這是 RVC 角色模型與 FCPE GPU 的 `PASS`；尚不代表即時 Discord／OBS 音訊鏈路與長時間 latency 已驗收。

## 最新實測矩陣

測試輸入：`dataset/reference-voices/voice-male-m1.wav`；index rate `0.75`；pitch `0`。

| 角色模型 | 狀態 | sample rate | 輸出 bytes | RTF | 輸出 SHA-256 |
|---|---|---:|---:|---:|---|
| Chinese_Narrator_Uncle | PASS | 40,000 | 1,188,844 | 1.0561 | `6f57d0e2fcaf328115095315b9e6eb827d25e75f515f6cf397c09fd63d4e071f` |
| Kafka_CN_Yujie | PASS | 40,000 | 1,188,844 | 0.2965 | `bea7c386d79578e4dbae85505933b8502ec22ca2ee626a842d3da172123e94b7` |
| Sage_CN_HeroicFemale | PASS | 48,000 | 1,426,604 | 0.2846 | `130b9eabbc388f509c5a71da25a83b76554b9ac1427033f7841f7268110b12e7` |
| Wukong_HeroicMale | PASS | 40,000 | 1,188,844 | 0.2569 | `226ae043e49d9fd8dddabbf177ce9ba24ce9372e8ed3dac74640977fcc54b28d` |

共同 runtime 證據：

- `f0_method=fcpe`
- `device=cuda:0`
- GPU：`NVIDIA GeForce RTX 5060 Ti`
- Torch：`2.7.1+cu128`
- 四組 `.pth/.index` SHA-256 與 `models/model-register.csv` 一致

## 可重跑命令

單一角色：

```powershell
Set-Location D:\AetherTune
& .\.venv\Scripts\python.exe tools\rvc-fcpe-gpu-infer.py `
  --model .\models\weights\Sage_CN_HeroicFemale.pth `
  --index .\models\indexes\Sage_CN_HeroicFemale.index `
  --input .\dataset\reference-voices\voice-male-m1.wav `
  --output .\artifacts\rvc-fcpe-gpu\Sage_CN_HeroicFemale.wav
```

每次輸出旁會寫入同名 JSON，記錄模型／index／input／output hash、FCPE、CUDA device、RTF 與 sample rate。四組矩陣使用的入口是 `tools/rvc-fcpe-gpu-infer.py`，不依賴 VCClient packaged ONNX provider。

## 與 VCClient 的關係

- `tools/vcclient-rvc-probe.ps1` 仍可測試官方 ONNX sample slot，但該 sample 是 `RMVPE ONNX`，目前 settings 會使用 `CPUExecutionProvider`；它不是本次 `FCPE + GPU` 證據。
- 本次 FCPE GPU PASS 證明 RVC WebUI offline pipeline 與四組角色模型可用；VCClient 即時前端仍需另測相容性、buffer、VST、VB-CABLE／Voicemeeter、Discord／OBS。
- 四組模型的來源、授權、訓練 revision 與 dataset metadata 仍應由使用者補齊；runtime PASS 不會自動把 provenance 補成已知。

## 尚未完成

1. Light Host／Graillon 實際 chain 與 bypass／active loopback。
2. VCClient realtime path 使用 FCPE、p50/p95 latency、斷音與 10 分鐘穩定性。
3. Discord／OBS 實際收音與人工聽測。
