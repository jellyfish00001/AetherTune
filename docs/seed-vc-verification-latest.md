# Seed-VC 最新驗證

更新日期：2026-09-27

## 結論

`offline-v1` 已在本機 RTX 5060 Ti 上完成男聲／女聲雙向實際推論與 60 秒長音檔測試；`realtime-tiny` 已完成 3 block smoke 與 200 block／60 秒連續 headless GPU streaming。2026-09-26 的四案 GUI callback／VB-CABLE `PASS` 是 `offline-v1` 歷史證據。2026-09-27 `realtime-tiny` GUI 的 Start/Stop/Start/Stop 與 saved reference 跨程序載入 `PASS`；但 deterministic callback user-flow 雖套用 17/17 欄位並執行 CUDA inference，backend WAV／該次 CABLE loopback 仍為 `WAITING`。獨立 synthetic VB-CABLE smoke `PASS`，所以不能把它替代成 GUI backend 輸出通過。以上都不等同實體麥克風 E2E、Light Host full-chain、人工聽測或完整 `LIVE <= 5s`。

### 2026-09-26 GUI 設定重驗

先前 Python 3.10 preflight 因 Tcl/Tk 初始化失敗而 `WAITING`。2026-09-26 以 Windows Installer 修復官方 Python 3.10.11 Tcl/Tk Support 元件，MSI exit code `0`；其後 `tkinter.Tcl()` 回報 Tcl `8.6.12`，Seed-VC venv 的唯讀 preflight（資源、MME 裝置、`FreeSimpleGUI`）為 `PASS`。Codex 受限 sandbox 內 Tcl 原生檔案 API 無法辨識使用者 Python 安裝路徑；同一 Seed-VC venv 命令在本機非受限執行環境通過，故正式 GUI 驗證在該環境執行。

實際執行官方 `real-time-gui.py` user-flow 並同步擷取 WASAPI `CABLE Output`：四組 reference 全數 `PASS`；各案 17/17 GUI widget 更新成功、官方 event values 無錯誤／不符，CUDA backend 輸出 finite、非零且與注入 WAV 不同，四案 loopback 也都是 finite／非零。完整逐案欄位、音訊指標及 hash 見 `artifacts/seed-vc/gui-userflow/20260926-after-tcl-repair/gui-userflow-report.json`（SHA-256 `1EB604F1A778FCEEFE73AB2D341A82DA274F08D31FF8342280DCA80FD963262E`）；Tcl/Tk repair log 在 `artifacts/seed-vc/python310-tcltk-repair-20260926.log`（SHA-256 `364414613B6E315AFEF0349FC3E1A56B6C421F6CD31B74EE58E53F50D6F2A3BE`）。

GUI harness 已調整為逐案保存 widget 更新、官方 event values、設定錯誤與輸出狀態；widget 設定失敗會使該 case 為 `WAITING`，不再被手動注入 event value 掩蓋。`tools/seed-vc-gui-settings-regression.py` 只用 fake widget 驗證這項回報契約，不代表 GUI runtime 通過。

### 2026-09-27 realtime-tiny GUI lifecycle 與 callback

一般 Windows session 使用 Seed-VC CPython 3.10.11、CUDA RTX 5060 Ti、固定 realtime-tiny checkpoint（SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`）、DirectSound `CABLE Output` → `CABLE Input` 與 worktree 內隔離 SessionRoot。GUI 手動完成 Start → Stop → Start → Stop；兩輪均有 CUDA `target_lengths`／VC 時間輸出，Stop 後 log 停止增長，關閉視窗後 runner 結束。以同一 SessionRoot 不帶 `-ReferenceWav` 重啟 preflight，`status=PASS`、`missing=[]`、`reference_source=saved`，effective reference 為 `voice-male-m1.wav`。launcher stdout SHA-256：首輪 `B770F4EF2AC1B3E661131099F66BDB5B43BF4CAE774BFE803FCA695A182F23A6`；重啟 `4EC50FB849DFE649E46C2AE44EC81B499F50E12971D01593481FD5E6910D4917`。artifact 位於 `artifacts/seed-vc/gui-userflow/20260927-phase2-0ad07c8e/`，GUI cache/config 僅在對應 `gui-session/` overlay。

同日以官方 GUI event path 跑 deterministic callback harness：GUI 設定套用 `17/17`、Python `3.10.11`、CUDA `true`、GPU `NVIDIA GeForce RTX 5060 Ti`，但第一次來源輸入 21.3 秒／RMS `0.01594` 時，backend output RMS 僅 `0.00002162`、peak `0.00085449`，該次 loopback RMS 為 `0`；把來源增益到 peak `0.65` 後，backend output 與 loopback RMS 仍為 `0`。兩案都應維持 `WAITING`，不能由 CUDA inference log 推論音訊輸出成功。報告 SHA-256 分別為 `0E8B6CD51C304C5D26F8D2D7DD4414DB3E41B37CDCDCD9220D1F0568E198A964` 與 `628FB08C0C9391CF34DA0DE487EFAEBDE21CFEDD9E94BFBC88C02189041EBD04`。獨立 WASAPI `CABLE Input` → `CABLE Output` 3 秒 smoke 則為 `PASS`：144000/144000 frames、RMS `0.082621`、peak `0.16`，report SHA-256 `5E875CE172ABDA11EFCB7E93B47D6F2681AE71347EABE8C1C31557073B73E1A9`。這只證明 cable 路徑本身可傳音，GUI backend→cable 的新測試仍未通過。

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
| GUI settings／PortAudio callback／CABLE Output 重驗（2026-09-26 offline-v1） | PASS | 4/4 reference；各案 17/17 GUI 欄位已更新且無 widget/event mismatch；四案 backend WAV 與 WASAPI loopback 均 finite／非零；只代表 offline-v1 | `artifacts/seed-vc/gui-userflow/20260926-after-tcl-repair/gui-userflow-report.json` |
| realtime-tiny GUI Start/Stop/Start/Stop 與 saved reference restart（2026-09-27） | PASS | 兩輪 CUDA stream lifecycle；Stop 後 log 穩定，關窗後 runner 結束；不帶 reference override 的重啟 preflight 載入 saved reference，`missing=[]` | `artifacts/seed-vc/gui-userflow/20260927-phase2-0ad07c8e/launcher-host.stdout.log`、`launcher-restart.stdout.log` |
| realtime-tiny GUI callback backend WAV／同步 CABLE Output（2026-09-27） | WAITING | settings `17/17`、CUDA RTX 5060 Ti；原輸入／增益輸入兩次 GUI callback output 都未達 finite non-zero gate，loopback 亦全零。原因尚未定位；不得視為 GUI audio path PASS | `artifacts/seed-vc/gui-userflow/20260927-phase2-0ad07c8e/realtime-tiny-callback/gui-userflow-report.json`、`artifacts/seed-vc/gui-userflow/20260927-phase2-0ad07c8e/realtime-tiny-callback-normalized/gui-userflow-report.json` |
| 獨立 WASAPI VB-CABLE synthetic smoke（2026-09-27） | PASS | 3 秒、144000/144000 frames、RMS `0.082621`；僅驗證 cable endpoint 路徑，不證明 GUI backend 有送出音訊 | `artifacts/seed-vc/gui-userflow/20260927-phase2-0ad07c8e/realtime-tiny-callback/direct-vbcable-loopback.json` |
| GUI callback／backend／CABLE partial timing screening（2026-09-26） | PASS（partial） | stream 到 callback 首次輸入 `357.8–422.3 ms`；首案冷啟首次 backend output 實測 `14962.0 ms`（15 秒 startup grace 僅延長捕捉時間，沒有從量測扣除）；暖機後其他 case 為 `1953.5–2393.0 ms`；backend output 後首次 `CABLE Output` 非零為 `147.2–171.7 ms`。這不是完整 `e2e_first_packet_ms`，首案冷啟也超過 5 秒 | 同上 |
| GUI／PortAudio callback user-flow + CABLE Output capture（2026-09-22 historical） | PASS | 當時官方 `real-time-gui.py` 四案產生 backend output 並穿過 VB-CABLE；由 2026-09-26 重驗更新目前設定狀態 | `artifacts/seed-vc/gui-userflow/phase-20260922-cable-loopback/gui-userflow-report.json` |
| GUI callback／backend／CABLE partial timing screening（2026-09-22 historical） | PASS（partial） | 舊 run timing 僅作歷史參照，最新部分量測以上一列 2026-09-26 report 為準 | `artifacts/seed-vc/gui-userflow/phase-20260922-cable-loopback-timing-v2/gui-userflow-report.json` |
| VB-CABLE／Voicemeeter synthetic virtual route | PASS | `CABLE Input → CABLE Output` 與 `Voicemeeter Input → B1 → Voicemeeter Out B1` 均 144000/144000 frames、非零 RMS；Remote API route check 也保存 B1 設定與內部 level | [`wiring-verification-latest.md`](wiring-verification-latest.md)、`artifacts/voicemeeter-b1-route-check.json` |
| 完整 mic E2E／audio-rack／LIVE gate | WAITING | callback 輸入仍是 deterministic WAV；尚未保存實體麥克風 → backend → Light Host full-chain → virtual route 的 first-packet timing、dropout／underrun 與人工聽測 | `docs/live-gate.md` 契約；synthetic route PASS 不等於完整 evidence |

2026-09-26 GUI callback 四個 case 的最新訊號摘要：

| reference | input seconds | output seconds | output RMS | difference RMS | zero-lag correlation |
|---|---:|---:|---:|---:|---:|
| `female-young-f004` | 3.9 | 3.9 | 0.01074 | 0.02140 | 0.00257 |
| `female-sister-f003` | 4.5 | 4.5 | 0.01599 | 0.02437 | 0.00132 |
| `female-warm-f005` | 3.6 | 3.6 | 0.01379 | 0.02371 | -0.04252 |
| `female-fresh-f006` | 4.2 | 4.2 | 0.02448 | 0.03048 | 0.02527 |

2026-09-26 的 `offline-v1` harness 首個 case 額外保留 15 秒 startup grace，原因是首次 GUI callback 的 model／VAD warm-up；這是輸出捕捉措施，不是把 warm-up 延遲隱藏或宣稱 `LIVE`。2026-09-27 `realtime-tiny` harness 也沿用該等待時間，但沒有得到非零 GUI output。

Timing 欄位定義：`callback_first_input_ms` 是 duplex stream 建立後首次 callback 輸入；`callback_first_nonzero_output_ms` 是同一 stream 首次收到非零 backend output；`cable_output_first_nonzero_after_backend_ms` 是 backend 首次非零 output 後，WASAPI `CABLE Output` 首次觀察到的後續非零訊號。前一次量測曾觀察到 route buffer 殘留，因此不採用單獨的 `cable_output_first_nonzero_ms` 作為延遲結論；v2 report 改以 backend 時間點作關聯。這些結果仍排除實體麥克風、Light Host／Graillon、Voicemeeter B1、人工聽測與 600 秒穩定性。

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

官方 GUI callback user-flow（請在一般 Windows user session 執行；輸出只到 VB-CABLE，不送往 Discord／OBS）：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-gui-userflow-test.py --preflight
& .\.venv\Scripts\python.exe .\tools\seed-vc-gui-userflow-test.py --preflight
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-gui-userflow-test.py `
  --capture-loopback `
  --output .\artifacts\seed-vc\gui-userflow\<run-id>
```

GUI settings apply contract regression（不啟動 GUI 或 audio stream）：

```powershell
& .\.venv\Scripts\python.exe .\tools\seed-vc-gui-settings-regression.py
```

若要驗證 backend output 確實穿過 VB-CABLE，再加上同步 loopback capture：

```powershell
& .\tools\venvs\seed-vc\Scripts\python.exe .\tools\seed-vc-gui-userflow-test.py `
  --capture-loopback `
  --output .\artifacts\seed-vc\gui-userflow\<run-id>
```

測試 `realtime-tiny` 時，先透過 GUI launcher 建立隔離 SessionRoot 並關閉 GUI，再明確指定該 overlay、固定 upstream、checkpoint/config 與 endpoint；不要把 session 路徑改成第三方 source 目錄：

```powershell
& 'D:\AetherTune\tools\venvs\seed-vc\Scripts\python.exe' .\tools\seed-vc-gui-userflow-test.py `
  --profile realtime-tiny `
  --repo 'D:\AetherTune\tools\external\seed-vc' `
  --checkpoint 'D:\AetherTune\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth' `
  --config 'D:\AetherTune\tools\external\seed-vc\configs\presets\config_dit_mel_seed_uvit_xlsr_tiny.yml' `
  --session-root .\artifacts\seed-vc\gui-session\<run-id> `
  --source 'D:\AetherTune\dataset\reference-voices\voice-male-m1.wav' `
  --reference-case 'female=D:\AetherTune\dataset\reference-voices\voice-female-f1.wav' `
  --host-api 'Windows DirectSound' `
  --input-device-name 'CABLE Output (VB-Audio Virtual Cable)' `
  --output-device-name 'CABLE Input (VB-Audio Virtual Cable)' `
  --capture-loopback `
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
- 2026-09-26 四案 offline-v1 GUI 設定套用、PortAudio callback、backend → VB-CABLE capture 與部分 timing screening 為歷史 `PASS`；2026-09-27 realtime-tiny GUI lifecycle／saved reference restart 為 `PASS`，但其 deterministic callback backend WAV 與同步 loopback 為 `WAITING`。獨立 cable smoke `PASS` 不能取代 GUI output evidence。實體麥克風內容、Light Host full-chain、人工聽測、10 分鐘以上穩定性與 underrun/dropout 證據仍缺。
- 尚未做人工聽測、MOS／相似度比較、10 分鐘以上 realtime 穩定性與多說話者測試；60 秒 headless PASS 不能替代實體裝置 E2E。
- 這個 PASS 只涵蓋離線 WAV 產生；CosyVoice2 與 Breeze TTS 2 也已各自完成 CUDA TTS 輸出，但人工音質與即時 latency 仍需分開評估。
