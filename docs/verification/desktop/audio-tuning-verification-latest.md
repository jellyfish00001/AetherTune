# Desktop 載入提示、引擎參數與輸入降噪驗證

日期：2026-10-03（Asia/Taipei）。本頁擁有本輪新增載入進度、四 VC 參數保存、輸入降噪、資訊提示與視覺修正的命令／證據；操作由 [Desktop 手冊](../../guides/desktop-user-guide.md)擁有，預期行為由 [F02／06／08](../../specs/app-requirements.md)及 [App 架構](../../specs/app-architecture.md)擁有。既有音效、原生視窗與路由報告保留原日期，不由本輪覆蓋。

## 身分與判定

- 驗證基準 Git HEAD：`9357b6c2e3840a143f41b887e614a36bdaa866d2`，驗證時 source 尚未 commit／push；保留開始時四份文件的既有變更，提交版本以 Git 歷史為準。
- 根目錄 `D:\AetherTune\AetherTune.exe` 使用嵌入前端的 `tauri/custom-protocol` 開發建置；與 `app/src-tauri/target/debug/aethertune-desktop.exe` SHA-256 相同。最終 exe／source／artifact hash 由 `artifacts/desktop/audio-tuning-20261003/verification-summary.json` 記錄；這不是 installer／新機驗證。
  最終 exe SHA-256：`6a73965fd9f53358dbfc0b953870a91152f05c9c0b142c55f3c7acbecee46ad3`。
  真實 TTS cold／warm 測試在 heartbeat 修正版執行；後續只更新載入樣本與 UI 的生成／播放計時。最終 exe 重新通過原生設定／雙語測試，backend／Rust 進度程式保持相同；未重做所有模型生成。
- 契約、前端建置、相關 Python／Rust 回歸、DSP、實際模型 WAV／CABLE、Playwright preview／原生 WebView2 與 Codex Browser 的限定範圍 PASS。
- physical Mic、人工音質聽評、RVC duplex B1 問題、接收端及 600 秒 LIVE 保持 WAITING；`audio_verified=false` 保持原契約，不以 callback 或 WAV 升級。

## 載入與參數

載入範圍的唯一資料是 [model-load-estimates.json](../../../contracts/model-load-estimates.json)：每個項目帶樣本數與原始來源；RVC 分角色／FCPE／RMVPE，MeanVC2 分 40ms／120ms。未找到組合時顯示尚未量測。以下是本輪新增樣本，並非端到端等待保證。

| 配置 | 模型載入／預熱秒數 | 原始 evidence |
|---|---:|---|
| RVC Sage／FCPE | 115.36 | `artifacts/desktop/runs/64146d1964fa4e8d9c29595047d3d72d/rvc-evidence.json` |
| RVC Narrator／RMVPE | 12.63 | `artifacts/desktop/runs/29efbfb85cea4330b772a4f5a8f88bde/rvc-evidence.json` |
| RVC Kafka／RMVPE | 7.08 | `artifacts/desktop/runs/9d47d1aee06a45f7bbbdc0876c38dcb4/rvc-evidence.json` |
| RVC Wukong／RMVPE | 8.20 | `artifacts/desktop/runs/df2e4deed1864a81ac6c6c0550df3575/rvc-evidence.json` |
| MeanVC2／120ms | 49.31 | `artifacts/desktop/audio-tuning-20261003/meanvc2-120ms/stream-evidence.json` |
| Seed-VC | 48.61 | 同目錄 `seed-vc/stream-evidence.json` |
| X-VC | 132.17 | 同目錄 `xvc/stream-evidence.json` |
| CosyVoice2 cold | 54.94 | 同目錄 `native-progress/report.json` |
| Breeze TTS 2 cold | 84.03 | 同上 |

模型載入計時排除部分環境準備；實際首句另含 WSL 啟動、import、生成與播放，可能遠長於表中的數字。Sage／FCPE 與 X-VC 本輪特別慢，保留量測上界，不刪除慢樣本。UI 超出估計只提示載入較久，停止／診斷仍可用；沒有假的百分比或超時故障判定。

原生測試經正式 Rust command／Python service：Seed LOADING 的 child 存活與 phase 可見，STOP 後 OFFLINE、程序回收；非法降噪 25dB 拒絕為 `PARAMETER_INVALID`／ERROR。兩 TTS 各有新的 cold／warm request，snapshot 出現 environment、model_load、generating、playing；首句生成期間切換 Full／Mini／Compact，Mini 未開 Quick Input 仍顯示階段。次句 `runtime_reused=true`、load=0，顯示模型已就緒，生成時間獨立計算。

| 引擎 | cold request／生成秒數 | warm request／生成秒數 |
|---|---|---|
| CosyVoice2 | `3d5ab71b-fd08-43b4-8e34-5d470895cf72`／22.74 | `9dacebec-5838-4daa-99c0-65e3f0364661`／3.92 |
| Breeze TTS 2 | `1acb86cf-d718-4054-ac1f-246d807aee45`／52.52 | `8142b1d6-d85b-42e6-a3f2-468e06b76ec5`／5.48 |

Session 為 `7614e911-e67c-4efd-ac5b-7652800d144e`。四句 manifest PASS／Queue completed、CABLE 主輸出、monitor 關閉、playback underrun=0；本項沒有獨立 TTS CABLE 回錄，不宣稱 physical 或人耳 PASS。

初次原生測試暴露階段只在狀態切換時傳到 Rust 的缺口：worker 已進生成，UI 仍停在載入。保留 `native-progress/report-before-heartbeat-fix.json`；修正為每秒精簡 `speech_progress`、相同 current request ID 才合併，重跑兩引擎通過。心跳只更新存活與觀測時間，不假裝新的階段進展。

參數表單依 manifest 範圍／步進，四 VC 獨立保存；STOP 後修改、下次 START 套用。Playwright 驗證舊 RVC 移轉、路由保留、負值／方向鍵／自訂按鈕、reload 保存，以及 Seed fade／block、X codec 80ms 對齊與視窗交叉限制拒絕。MeanVC2 的 120ms 已在實際 processor metadata 中確認；其餘手動參數補驗見本輪 summary 與 `seed-parameters-pass`、`xvc-parameters`、`rvc-pitch` evidence。

| 手動參數補驗 | 實際 runner 確認 | 判定 |
|---|---|---|
| Seed：steps=6、CFG=0.6、reference=2s、block=0.32s、fade=0.06s、CE=4s、DiT=0.6s、right=0.04s | 正式校驗後 route parameters、host block=15360；CABLE RMS 0.021719 | PASS；12 秒、丟棄／underrun=0 |
| X：Current=240、Chunk=960、Future=80、Smooth=40ms | processor window 換算成 3840／15360／1280／640 frames，host block=11520；CABLE RMS 0.011485 | PASS；12 秒、丟棄／underrun=0 |
| RVC Sage／FCPE：pitch=-2 | 正式 EngineManager → RVC core 的參數及 WAV evidence，CABLE RMS 0.024233 | PASS；finite、capture errors=0 |

補驗的 Seed fixture 最初使用低於 manifest 下限的 DiT=0.4s，正式 runner 在載入前拒絕；保留 `seed-parameters/runtime.log`。改為合法 0.6s 後重跑通過，沒有放寬範圍。

## 降噪與音訊證據

四 VC 共用 20ms sqrt-Hann 窗／10ms hop，NOLA 檢核、平滑增益及跨區塊狀態；預設關閉、保存強度 12dB，範圍 0～24。關閉／0dB exact bypass；源音訊先降噪，再 VC，再原有 Post-FX，wet=0 不旁路降噪。TTS 沒有輸入降噪控制。

`services/engines/test_noise_reduction.py` 使用既有 `voice-male-m1.wav` 轉成 48kHz，前後各一秒噪音、固定 seed `20261003`、Gaussian 振幅 0.008；語音有效樣本以乾淨聲音幅度 >0.02 計。輸入／輸出 SHA-256 在 summary；量測用 float PCM、WAV 另存 PCM16。

| 量測 | 結果 | 門檻 |
|---|---:|---:|
| 噪音區段抑制 | 9.726dB | ≥6dB |
| 語音有效段能量損失 | 0.965dB | <3dB |
| 算法延遲 | 20ms | 固定、整檔模式已補償 |
| 16.879 秒整檔 DSP 耗時 | 0.171 秒 | 記錄，不作硬體泛用保證 |
| 同音訊以 20ms callback 處理 | 總 0.232 秒，單次最慢 2.382ms | 記錄 |

5 項 DSP regression 涵蓋關閉／0 exact bypass、可變區塊與整檔延遲補償結果一致、有限樣本、靜音／非法值、尾端排出與固定底噪目標。`denoise-report.json`、`noisy-source.wav`、`denoised-source.wav` 保存原始數據。這是持續底噪驗收，不代表模型電子感消除。

主輸出使用 Windows DirectSound 的 `CABLE Input (VB-Audio Virtual Cable)`；獨立擷取其 `CABLE Output`。三串流引擎開啟 callback 裝置，但來源以同一 noisy WAV 注入，非 physical 說話。GPU 是 RTX 5060 Ti／cuda:0；實際 provider、checkpoint、reference／source／輸出 hash 保存在各 `stream-evidence.json`。

| 引擎／配置 | CABLE RMS | NR 總耗時／單次最慢 | input drops／output drops／underruns |
|---|---:|---:|---|
| Seed-VC（15秒） | 0.027238 | 0.116s／15.298ms | 0／0／0 |
| MeanVC2 120ms（15秒） | 0.048395 | 0.115s／9.703ms | 0／0／0 |
| X-VC（15秒） | 0.012115 | 0.149s／18.582ms | 0／0／0 |
| RVC Sage／FCPE（WAV） | 0.022498 | 整檔前處理，見 rvc evidence | file scope，不套用串流丟棄判定 |

RVC 三個角色的 RMVPE 與 Sage／FCPE 均有 finite／nonzero 回錄、capture errors=0、正式 probe exit=0；其模型／index／F0／來源 hash 保存在 `rvc-*/report.json` 及對應 `artifacts/desktop/runs/*/rvc-evidence.json`。檔案降噪的自身延遲已補償。RVC Mic 接點沿用同一 DSP 並經回歸檢核，但本輪未把 duplex B1 或 physical 聽感標成 PASS。

## UI 交叉驗證

| 能力 | URL／viewport | 判定與證據 |
|---|---|---|
| Playwright／Edge preview，explicit IPC mock | `http://127.0.0.1:1420/`；1040×740／420×740 | `ui/preview-report.json`、雙語 tooltip 截圖；START payload、慢載入非故障、STOP、illegal params、移轉與保存 PASS |
| Codex 內建 Browser | 同 route；1280×720 | 實際設定頁深色 tooltip／spinner／scrollbar 目視複核；點擊與 Escape 關閉、console warn/error 空；這層沒有原生程序控制 |
| 原生根目錄 exe／WebView2，Playwright CDP | `http://tauri.localhost/`；Full 1040×740，Compact 420×490，Mini 420×74 | `ui/native-report.json`／`native-progress/report.json` 與截圖；雙語設定操作、保存、Compact 設定入口及真實 cold／warm／取消／失敗 PASS |

tooltip 使用 portal 避免 overflow 裁切，hover／focus／click 可讀、Escape 可關；窄 viewport 不越界。自訂深色數字按鈕保留直接輸入、負值、方向鍵、步進與上下限；進階參數及五項症狀排查預設收合。UI／原生報告的 console／network errors 均為空。測試後還原使用者既有設定與 shell，退出測試 app 並清除 CDP 啟動參數。

最終 preview 另模擬先等待 300／500 秒再進入生成／播放，確認 Mini 顯示該階段的 7／5 秒，而不是累計等待；模型重用提示保持可見。文件鏈結／新增檔案索引檢核：9 份文件、533 個本機連結、15 個新增檔案均 PASS，見 `doc-links.json`；`git diff --check` 以 Windows CRLF 相容規則通過。

![原生 WebView2 深色音效說明與數字控制](../../../artifacts/desktop/audio-tuning-20261003/ui/native-zh-TW-1040-tooltip.png)

## 可重跑命令與回歸

在 `D:\AetherTune\app`，開發 preview 先啟動 `npm run dev`：

```powershell
npm run build
npm run test:contracts
node tests/audio-tuning.mjs
npm run test:i18n-ui
npm run test:audio-effects-ui
npm run test:manual-tts-ui
npm run test:ui
```

原生測試只對本輪以 WebView2 debug port 啟動的 idle App 執行；不要中斷使用者正在使用的音訊。`AETHERTUNE_CDP=http://127.0.0.1:9222` 時執行 `node tests/audio-tuning.mjs`／`npm run test:i18n-ui`；`node tests/native-progress.mjs` 會產生兩引擎真實語音並送 CABLE。

在 repository root：

```powershell
.venv/Scripts/python.exe services/engines/test_runner_service.py
.venv/Scripts/python.exe -m unittest services.engines.test_noise_reduction services.engines.test_postfx services.engines.test_stream_runtime services.tts.test_service services.tts.test_snapshot services.tts.test_validation services.tts.test_postfx
.venv/Scripts/python.exe tools/desktop-vc-smoke.py --engine meanvc2 --model 120ms --noise-reduction --postfx --source artifacts/desktop/audio-tuning-20261003/noisy-source.wav --output-dir artifacts/desktop/audio-tuning-20261003/meanvc2-rerun --timeout 300
.venv/Scripts/python.exe app/tests/rvc-audio-smoke.py --model-id Sage_CN_HeroicFemale --f0-method fcpe --noise-reduction --pitch -2 --source artifacts/desktop/audio-tuning-20261003/noisy-source.wav --output artifacts/desktop/audio-tuning-20261003/rvc-rerun
```

實際完成：runner 13 tests、上述 Python suite 63 tests、Rust `cargo test --lib` 6 tests PASS。Rust 的既有 RVC torch／faiss import 測試曾在同時執行模型時超出 20 秒，待模型作業結束後全 6 項重跑通過；沒有修改 timeout 或忽略失敗。Rust toolchain 使用 `artifacts/desktop-toolchain/{cargo,rustup}`，建置為 `cargo build --bin aethertune-desktop --features tauri/custom-protocol`。

本輪沒有新增一鍵調音預設、無效半音控制或修改 Windows 音訊端點。仍需使用者實際比較顫抖、段落感、電子感與氣音／字尾；自動能量／CABLE 結果不能代替此項聽評。
