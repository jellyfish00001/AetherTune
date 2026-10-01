# Desktop 即時 VC 修復驗證

日期：2026-10-01（Asia/Taipei）。本頁擁有本輪四個 Desktop VC 的無聲修復、內建 Post-FX、音訊／線路證據與剩餘驗收。操作見 [Desktop 手冊](../../guides/desktop-user-guide.md)，上游比較見 [VoiceStudio 研究](../../reference/voicestudio-comparison.md)。歷史官方 GUI、獨立 CLI、VCClient 與 LIVE gate 不由本頁改判。

## 已確認原因與修改

- Seed-VC 的 Desktop START 原先只啟動官方 GUI，沒有替使用者按下 GUI 的 Start；MeanVC2／X-VC 原先跑 Source WAV，沒有麥克風 capture/output。這是實際控制鏈路缺口，不能由模型已下載或 CUDA log 推論為可即時使用。
- Seed／Mean／X 現在透過 `stream_runtime.py` 開啟明確 PortAudio 裝置，模型與 reference conditioning 常駐，worker 做推論，callback 只搬 PCM。X 使用真正 future 音訊，Seed 預熱後保留 prompt conditioning；bounded FIFO 將 backlog／drops 明確回報。
- 三個 zero-shot 引擎不再要求 Source WAV；RVC 仍區分 Mic／File。四引擎共用裝置、監聽、EQ／壓縮／殘響／乾濕混合。wet 的乾聲是變聲後、未加音效的聲音，沒有混入原始麥克風。音效預設 bypass。
- 初次使用自動選實體輸入與播放端，合法的保存路由會保留；選 CABLE／Voicemeeter 時給出監聽提示。畫面顯示 input/output peak（共用 worker 為近期，既有 RVC 為 session 累計）、模型 p95、RTF 與 drops，不宣稱為端到端延遲。
- X-VC 隔離環境補上 `sounddevice==0.5.6`，setup／VerifyOnly 同步。Seed／X 的 Torch CPU threads 限制為 4，避免模型載入時 oversubscription；本輪 X 首次未限制 threads 的 180 秒試驗逾時，保留 `xvc/` 的 BLOCKED artifact，修正後 `xvc-threads4/` 重跑 PASS。

## 短時間音訊與路由

機器：Windows、NVIDIA GeForce RTX 5060 Ti、Torch `2.7.1+cu128`、CUDA `12.8`。輸入 fixture：`dataset/reference-voices/voice-male-m1.wav`，SHA-256 `3a4a5a048154cff60d717fc1fce929ebebc887f7c9222c56222dad48adb60662`；reference：`voice-female-f1.wav`，SHA-256 `37976f69f73fb13d6fefaf80268794d545d6e19be5059437db067455a795f406`。

Seed／Mean／X 的 20 秒試驗開啟 HyperX／DirectSound input callback，但以 fixture 替換 callback 輸入；輸出到 CABLE Input／DirectSound，以 CABLE Output／WASAPI 同期回錄。啟用音效，wet=0.5、low=+3 dB、high=-2 dB、reverb=0.15。**這證明 streaming worker、音效與 PortAudio/CABLE 路徑；不證明實體說話、聲線品質或人耳可接受。**

| 引擎／範圍 | 判定 | 模型 p95 | RTF | RUNNING 後首個非零輸出 | 回錄 RMS |
|---|---|---:|---:|---:|---:|
| MeanVC2 40ms、20 秒串流＋FX＋CABLE | PASS | 94.73 ms | 0.510 | 0.385 s | 0.056764 |
| X-VC current=160/future=80、20 秒串流＋FX＋CABLE | PASS | 79.63 ms | 0.406 | 0.436 s | 0.021650 |
| Seed realtime-tiny FP32、20 秒串流＋FX＋CABLE | PASS | 175.71 ms | 0.455 | 0.607 s | 0.027650 |
| RVC Sage/FCPE File＋FX＋native EngineManager＋CABLE | PASS | 32.08 ms | 不適用 | 檔案播放 | 0.032571 |
| RVC Sage/FCPE、20 秒虛擬輸入 duplex＋FX 核心 | PASS | 61.22 ms | 另見 runtime metrics | 未量測 | B1 擷取 WAITING |

三個共用 worker 的 input/output drops、PortAudio underruns/overruns 均為 0；startup 時填零的 callback 次數分別為 20／25／30，不應當成已排除所有斷音。RTF<1 只對本次配置有效。模型載入＋預熱為 Mean 13.39 秒、X 34.32 秒、Seed 49.53 秒；首個非零輸出欄位從 RUNNING 算起，不包含載入，也不是 mic→耳機延遲。

RVC duplex 的 independent Voicemeeter B1 capture peak=`3.0518e-05`，近零，`virtual_capture_status=WAITING`；核心 callback peak=`0.6009385`、blocks=125、underruns/overruns=0。該試驗不宣稱 Voicemeeter 全鏈通過。RVC File 的獨立 CABLE capture 已通過。

RVC log 另有「索引無效」警告：`rvc-index-audit.json` 確認四個登錄 index 都有已加入向量（ntotal=8598／37529／5896／1887），不是空的 trained-only index；目前 nprobe=1。上游在 k=8 搜尋出現負 id 時會整個 block 跳過 index blend，因此該警告不能直接診斷為 checkpoint 錯誤。此次保留既有檢索行為，index 搜尋覆蓋與對聽感的影響仍待調整驗收；非零輸出不等於檢索 blend 每個 block 都生效。

當輪 artifact 根目錄：`artifacts/desktop/vc-repair-20261001/`。每個三引擎子目錄保存 `request.json`、`runtime.log`、`stream-evidence.json`、`callback-output.wav`、`cable-loopback.wav`、`smoke-report.json`；source revision／實際 source hash／權重 hash／GPU／路由與完整 metrics 以 JSON 為準。

| 子目錄 | callback/output WAV SHA-256 |
|---|---|
| `meanvc2/` | `8e092999a93aa22871fe53a98116f7bfebe4a4c506e7423b97cb41032afa5573` |
| `xvc-threads4/` | `7bb574cf7ac10a27b80fed90f22f4d52998596dc86e8334f4b9865cd4a5466f1` |
| `seed-vc/` | `240fa98f8c14bb2fc086d86651217c341b287384f63791ee90e30534a4c09a66` |
| `rvc-postfx/` CABLE capture | `26dea58129e77b2de91d48ab85bcb8cd9fad46a165be0b4f3460844339f21a1b` |

## 可重跑命令與程式檢核

output-dir 每次必須使用新的目錄；三個引擎循序執行，避免 GPU 競爭。

```powershell
.\.venv\Scripts\python.exe tools\desktop-vc-smoke.py --engine meanvc2 --output-dir artifacts\desktop\vc-repair-20261001\meanvc2 --seconds 20 --postfx
.\.venv\Scripts\python.exe tools\desktop-vc-smoke.py --engine xvc --output-dir artifacts\desktop\vc-repair-20261001\xvc-threads4 --seconds 20 --postfx
.\.venv\Scripts\python.exe tools\desktop-vc-smoke.py --engine seed-vc --output-dir artifacts\desktop\vc-repair-20261001\seed-vc --seconds 20 --postfx
.\.venv\Scripts\python.exe app\tests\rvc-audio-smoke.py --output artifacts\desktop\vc-repair-20261001\rvc-postfx --postfx
.\.venv\Scripts\python.exe app\tests\rvc-audio-smoke.py --output artifacts\desktop\vc-repair-20261001\rvc-duplex-postfx --stream-seconds 20 --postfx
.\.venv\Scripts\python.exe services\engines\test_runner_service.py
.\.venv\Scripts\python.exe -m unittest services.engines.test_streaming_adapters services.engines.test_postfx services.engines.test_stream_runtime
```

- runner 邊界 12 tests、adapter 6 tests、Post-FX 4 tests、FIFO 3 tests PASS。
- 6 manifests／Manual contracts PASS；`npm run build`、Edge Playwright preview PASS；Codex 內建 Browser 的 preview 可見控制已複核。
- `cargo test --lib` 的 5 個程序與取消測試 PASS；內含前端建置用 `cargo build --bins --features tauri/custom-protocol` PASS。一般 `cargo build` 指向 devUrl，不能直接當成根目錄獨立 exe。
- 根目錄 `AetherTune.exe` 後續隨[操作畫面審查](usability-audit-latest.md)、[六引擎音效設定](audio-effects-verification-latest.md)及[介面語言](ui-language-verification-latest.md)更新，當前 SHA-256 `924b8db161a4c0f3fab54c18e022e8c57068a3474fbf8332a5fe2626bd41b815`；URL=`http://tauri.localhost/`，不依賴 localhost Vite server。先前本頁音訊與 START／STOP 試驗使用 `a3adb1086f6526e81c12ee0d9c3934ebdc389d6d7f415005d73a63fd1d494a48`；後續修改音效保存、TTS 處理與語言，未重跑本頁四 VC 音訊。
- 本輪完整 `test:ui` 原生檢核在既有拖曳位移斷言失敗；四引擎的控制／Full/Compact/Mini 截圖已執行，不能把整份測試記為 PASS。與本次 VC 對應的原生 START／STOP／metrics／LOADING cancel 由 `app/tests/vc-native.mjs` 另驗；結果以 `native/report.json` 為準。
- 原生 VC 專項 **PASS**：四引擎從實際 UI 按 START 進入 RUNNING，至少 10 個 blocks、有 GPU 與有限 p95、執行期間鎖定 Engine；按 STOP 後均 OFFLINE／`service_alive=false`。Seed LOADING cancel PASS。URL=`http://tauri.localhost/`、viewport=`1040×740`、DPR=`1.25`，console／network errors 均為空；畫面與狀態存於 `native/<engine>-running.png`、`native/ready.png`、`native/report.json`。結束後程序盤點無 VC child，僅 App 的閒置 TTS service；測試設定已恢復實體 HyperX input/output、RVC Mic、音效 bypass。
- 原生 session 的模型載入＋預熱實測 Mean=43.43 秒、X=95.76 秒、Seed=43.27 秒、RVC=11.67 秒，明顯會波動；尚未優化每次 START／切換引擎的 cold-load。上方 standalone 載入時間不能當成 Desktop 等待上限。`native/report.json` 的 `start_metrics_stop_seconds` 包含 START、等待 metrics、截圖與 STOP，不是純載入或端到端延遲。
- 78 份 Markdown、706 個本機連結存在性檢核 PASS；`git diff --check` PASS。程式、UI、音訊、文件各項證據仍各有範圍，不互相升級。

原生專項重跑：以暫時的 `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222` 啟動根目錄 exe，再於 `app/` 執行 `$env:AETHERTUNE_CDP='http://127.0.0.1:9222'; node tests/vc-native.mjs`。測試只把真實麥克風送往 CABLE，未保存原始說話音訊；程序開啟與環境音數值不當作說話驗收。日常啟動不需要 debug port。

## 尚未通過的驗收

實體 HyperX 說話→四引擎→實體耳機的人耳聽評、聲線相似度與音質、600 秒穩定性、端到端延遲、Discord／外部 VST Rack 全鏈仍 WAITING。內建 Post-FX 的短測不替代 Light Host／第三方 VST 驗收；模型與聲音授權也沒有因音訊 PASS 升級。保留 manifest `classification=WAITING`，不以本輪短測標成 LIVE-ready。
