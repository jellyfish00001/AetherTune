# PC2 實機 E2E 延遲量測結果（2026-11-20）

- 日期：2026-11-20（Asia/Taipei），15:07–16:09
- 證據等級：**A**（PC2 實機聲學脈衝量測；各列另標 A／B／C）
- 機器：PC2 DESKTOP-V5KNU03，RTX 2060 12 GB，driver 610.88，torch 2.7.1+cu128
- 工具：`tools/e2e-latency-run.ps1 -Profile pc2-virtual`（分支 `exp/bench-e2e-latency`），runtime 於 `D:\AetherTune-exp\wt-main-ref`（detached 於同分支）
- 原始證據：`D:\AetherTune-exp\artifacts\e2e-latency\<run>\`（`e2e-latency-report.json`、`stream-evidence.json`／`rvc-evidence.json`、`latency-trace.jsonl`、`results.json`、`gpu-*.csv`）；彙整 `results-2026-11-20.jsonl`

證據等級：**A** = PC2 實機聲學脈衝 bench 直接量到（偵測 ≥ 5/8、confidence ≥ 0.35）；**B** = 實機聲學但偵測少或 confidence 偏低（僅供參考）；**C** = 由 trace／baseline 推估，非聲學量測；**—** = 無法量到。trace `input_to_output_ms` 為 approximate internal（忽略 rolling context／lookahead），不是聲學 E2E。

## 路由

```text
bench --play--> 喇叭 (Steam Streaming Microphone) ==> 麥克風 (Steam Streaming Microphone)（WASAPI exclusive）--> 引擎輸入
引擎輸出 --> 喇叭 (Voice Changer Virtual Audio Device (WDM)) ==> 麥克風 (Voice Changer ...)（shared＋auto_convert）--> bench 錄音
```

## baseline

| 線路 | 路徑 | 偵測 | min | p50 | p95 | max | 證據 | run 目錄 |
|---|---|---|---:|---:|---:|---:|---|---|
| lineA | 喇叭→麥克風 (Steam Streaming Microphone)，capture exclusive | 8/8 | 55.7 | 59.0 | 59.0 | 59.0 | A | `20261120-150711-baseline/baseline-lineA` |
| lineB | 喇叭→麥克風 (Voice Changer Virtual Audio Device (WDM))，shared＋auto_convert | 8/8 | 74.3 | 74.3 | 79.5 | 82.3 | A | `20261120-150711-baseline/baseline-lineB` |

## through-engine

| 引擎（設定） | 訊號 | 偵測 | E2E min | p50 | p95 | max | baseline p50（兩跳） | engine−baseline p50 | trace in→out p50／p95 | 處理 p95／block | RTF | underrun／drop | 跟得上即時 | GPU util p50／max、VRAM | 證據 | run 目錄 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|---|---|---|---|
| **seed-vc**（realtime-tiny，block 0.3 s，diffusion 10） | speech | 8/8 | 645.0 | 652.5 | 658.2 | 660.0 | 120.0 | 532.5 | 443／459 | 138／300 | 0.43 | 0／in 0、out 0 | 是 | 37%／42%、1416 MiB | A | `20261120-160639-seed-vc` |
| seed-vc 對照 #1 | chirp | 5/8 | 655.9 | 669.9 | 689.7 | 689.8 | 129.0 | 540.9 | 450／466 | 154／300 | 0.46 | 0／in 0、out 0 | 是 | 36%／43%、1413 MiB | A | `20261120-151319-seed-vc` |
| seed-vc 對照 #2 | chirp | 6/8 | 651.9 | 667.1 | 676.2 | 678.4 | 126.0 | 541.1 | 446／461 | 154／300 | 0.47 | 0／in 0、out 0 | 是 | 取樣失敗（見上列） | A | `20261120-152338-seed-vc` |
| **meanvc2**（realtime 40ms，block 160 ms） | speech | 8/8 | 465.0 | 597.5 | 605.0 | 605.0 | 120.0 | 477.5 | 358／383 | 122／160 | 0.62 | 0／in 0、out 0 | 是（本次無 drop；見備註 #1 的一次落後） | 29%／37%、2187 MiB | A | `20261120-160112-meanvc2` |
| meanvc2 對照 #1 | chirp | 0/8 | — | — | — | — | 123.7 | — | 385／1076 | 174／160 | 0.77 | 0／in 0、out 21120 | 否（這次）：處理 p95 174 ms > 160 ms block；延遲由 356 ms 爬到約 1080 ms，丟 0.44 s 輸出 | 29%／35%、2161 MiB | —（脈衝 0/8） | `20261120-151553-meanvc2` |
| meanvc2 對照 #4 | chirp | 0/8 | — | — | — | — | 133.7 | — | 370／393 | 128／160 | 0.71 | 0／in 0、out 0 | 是 | 30%／42%、2163 MiB | C（只有 trace） | `20261120-153530-meanvc2` |
| **rvc**（Sage_CN_HeroicFemale，fcpe，chunk 160 ms，extra 1 s） | speech | 8/8 | 380.0 | 390.0 | 398.2 | 400.0 | 130.0 | 260.0 | 54／75 | 75／160 | 0.32 | 0／in 0、out 0 | 是 | 27%／40%、821 MiB | A | `20261120-160402-rvc` |
| rvc 對照 | chirp | 2/8 | 389.5 | 392.0 | 394.3 | 394.5 | 143.7 | 248.3 | 53／72 | —／160 | — | 0／in None、out None | 是 | 0%／0%、565 MiB | B（2/8） | `20261120-155441-rvc` |
| rvc 對照 | click | 2/12 | 682.4 | 700.7 | 717.2 | 719.0 | 123.7 | 577.0 | 55／88 | —／160 | — | 0／in None、out None | 是 | 28%／38%、777 MiB | 不採用（2/12，confidence 0.36–0.37，與 speech 不一致） | `20261120-155631-rvc` |

## 備註

- **主數字以 speech 列為準**（粗體列）：bench 新增 speech 訊號（參考語音能量最高的 400 ms 片段，間隔 1.6 s、max_delay 1.1 s，對數 RMS 包絡互相關，解析度 5 ms）；PC2 loopback 驗證 speech 與 chirp 相差 ≤ 5 ms。
- baseline 每個引擎 run 前重量一次；speech 三次 run 的兩跳 baseline p50 為 120–130 ms，chirp run 為 124–144 ms；engine−baseline 用該 run 自己的 baseline。
- Seed-VC：speech 645–660 ms 與 chirp 652–690 ms 一致；engine−baseline ≈ 533–541 ms；trace in→out ≈ 443–450 ms，比聲學少約 90 ms（trace 不含 0.3 s block 的 rolling context／extra_time）。
- MeanVC2：speech 8/8，p50 597.5 ms，其中 2 個脈衝落在 465／490 ms（包絡對位歧義，confidence 仍 0.66–0.69），p95 605 ms；chirp／click 會被轉成近乎靜音（錄到 peak 0.004），脈衝法量不到。trace in→out 350–385 ms，同樣低估約 240 ms。#1 那次（chirp）量測中延遲爬升並丟輸出，其餘 4 次沒有，屬偶發；ASR 在 CPU 上跑，推測與 CPU 爭用有關（推測，未證實）。
- RVC：speech 8/8，380–400 ms，engine−baseline 260 ms；chirp 2/8 的 389／395 ms 與之一致；click 的 682／719 ms 是門檻邊緣的誤配，不採用。RVC 的 trace 只記到 duplex callback 內（約 54／75 ms），不含 extra_time 1 s 的 rolling context 與 SOLA，不能代表 E2E。
- X-VC：本輪未量。Round 1 smoke 檔案模式 12.5 s 音訊花 222 s（RTF ≈ 18），在 RTX 2060 上不可能即時，量串流只會無限落後（證據 C，來自 smoke 紀錄）。
- GPU：nvidia-smi 每 0.5 s 取樣；表中 util 為模型載入後的取樣中位數／最大值，VRAM 為 run 期間最大值（含桌面約 266 MiB）。
- 環境變數：pc2-virtual 會自動設 `AETHERTUNE_WASAPI_AUTOCONVERT=1` 與 `AETHERTUNE_WASAPI_EXCLUSIVE_INPUT=Steam Streaming Microphone`（只影響該程序及子程序，不改系統設定）；`AETHERTUNE_LATENCY_TRACE=1` 要自己設；Seed-VC 的 `HF_HOME`／`HF_HUB_CACHE` 由 `stream_runtime` 指到 `tools/external/seed-vc/checkpoints`；`TCLLIBPATH=D:/AetherTune-exp/tcl-shim` 只有跑 Seed-VC setup 腳本或 GUI 時需要，量測不需要。不要在同一個 shell 設 `PYTHONIOENCODING=utf-8`：工具用 cp950 讀裝置名稱，會讓 runner 找不到裝置（DEVICE_NOT_FOUND）。

## 學到什麼

- 三個能即時的引擎在 PC2 虛擬線上的聲學 E2E（含約 120–130 ms 兩跳虛擬線）：RVC ≈ 390 ms、MeanVC2 ≈ 600 ms、Seed-VC ≈ 650 ms；扣掉虛擬線後引擎本身約 260／478／533 ms。三者都沒達到 100–300 ms 研究目標；最接近的是 RVC（扣線後 260 ms）。
- Steam Streaming Microphone 的 capture 在 WASAPI shared mode（Windows 預設格式 44.1 kHz mono）會把音訊拉長約 2 倍並丟片段（0.5 s 間隔的 8 個 burst 只收到 4 個、間隔約 1.03 s）；改 exclusive 48 kHz 後 8/8、約 52–59 ms。已用 opt-in 環境變數修正（f41b022）。
- `e2e-latency-run.ps1` 原本在 RUNNING 後不再讀引擎 stdout／stderr，Seed-VC 每個 block 都印 tqdm，管線塞滿後引擎卡住、bench 0/8；已改成非同步排空（2d3714b）。
- RVC upstream 每個 block 印簡體「耗时」，runner_service 的 stdout（cp950）編碼失敗會讓轉送執行緒中止，引擎卡在 LOADING 直到 300 s 逾時；已改為 errors=replace（39db29f）。
- chirp／click 脈衝只適合保留波形輪廓的引擎；MeanVC2（ASR 內容為主）和 RVC（F0 追蹤）會把非語音脈衝吃掉或變得很小，需要 speech 訊號（33e4de0）。同一個 commit 也修了舊 bug：錄音長度等於播放長度，延遲 > 200 ms 時最後一個脈衝必定被截掉。
- bench 的 `recorded.wav` 是 32-bit float 資料，WAV 標頭卻是 PCM，用 soundfile 讀會像雜訊（曾誤判成裝置振鈴）；要用 float32 原始資料讀。本輪沒改這個工具限制。
- trace（approximate internal）會系統性低估（Seed-VC 約 90 ms、MeanVC2 約 240 ms、RVC 更多），不能拿 trace 取代聲學數字。

## BLOCKED／WAITING

- X-VC 即時量測：不做（RTF ≈ 18，硬體上不可能即時；不是環境問題）。
- 實體麥克風／耳機 E2E 與 600 s LIVE：不在本輪範圍（WAITING）。
- 本輪沒有需要系統層級變更的阻塞（沒裝驅動，也沒改全域設定）。

## 一行指令

```powershell
$env:AETHERTUNE_LATENCY_TRACE='1'; $env:HF_HOME='D:\AetherTune-exp\cache\hf'; $env:MODELSCOPE_CACHE='D:\AetherTune-exp\cache\modelscope'; $env:MPLCONFIGDIR='D:\AetherTune-exp\cache\mpl'; Set-Location D:\AetherTune-exp\wt-main-ref; pwsh -NoProfile -File tools\e2e-latency-run.ps1 -Profile pc2-virtual -Root D:\AetherTune-exp\wt-main-ref -Python D:\AetherTune-exp\wt-main-ref\.venv\Scripts\python.exe -Engine rvc -WarmupSec 20 -Signal speech -IntervalMs 1600 -MaxDelayMs 1100 -ResultsDir D:\AetherTune-exp\artifacts\e2e-latency
```

<!-- rvc-tune:start -->

## RVC 延遲調校（PC2，2026-11-20 下午）

- 訊號：speech（voice-female-f1 能量最高 400 ms 片段，間隔 1600 ms，8 段），估計器 = 起音（包絡首次達峰值 25%，5 ms 解析度），證據等級 A（聲學、經實體虛擬線）。
- 每組都先量兩條虛擬線基線（同一次執行內），「引擎淨延遲」= 經引擎 p50 − 兩條線 p50 之和。
- 模型：Sage_CN_HeroicFemale（index_rate 0.75、pitch 0）；RTF／處理 p95 來自引擎 metrics；underrun／drops 來自引擎計數。
- 達標條件：淨 p50 ≤ 200 ms、RTF < 0.7、underrun = 0、8/8 偵測。

| 設定 (chunk/crossfade/extra/f0) | 經引擎 p50 / p95 | 基線 p50 | 淨 p50 / p95 | 首包淨值 | RTF | 處理 p95 (ms) | underrun / drops | GPU util p50 / VRAM | 達標 | run |
|---|---|---|---|---|---|---|---|---|---|---|
| c160-x40-e1.0-fcpe | 382.5 / 403.2 | 135.0 | 247.5 / 265.0 | 260.0 | 0.346 | 89.6 | 0 / 0+0+0 | 29.0% / 780.0 MiB | ❌ | `20261120-162025-rvc` |
| c120-x40-e1.0-fcpe | 330.0 / 340.0 | 130.0 | 200.0 / 203.5 | 190.0 | 0.376 | 55.2 | 0 / 0+0+0 | 28.0% / 780.0 MiB | ✅ | `20261120-162306-rvc` |
| c100-x30-e1.0-fcpe | 290.0 / 318.0 | 140.0 | 150.0 / 178.0 | 190.0 | 0.476 | 51.7 | 0 / 0+0+0 | 36.0% / 780.0 MiB | ✅ | `20261120-162548-rvc` |
| c80-x40-e1.0-fcpe | 292.5 / 336.5 | 135.0 | 157.5 / 201.5 | 140.0 | 0.538 | 51.0 | 0 / 0+0+0 | 35.0% / 780.0 MiB | ✅ | `20261120-162832-rvc` |
| c80-x20-e1.0-fcpe | 257.5 / 260.0 | 140.0 | 117.5 / 111.8 | 110.0 | 0.474 | 49.4 | 0 / 0+0+0 | 29.0% / 780.0 MiB | ✅ | `20261120-163119-rvc` |
| c80-x20-e0.5-fcpe | 237.5 / 249.8 | 135.0 | 102.5 / 114.8 | 110.0 | 0.471 | 47.5 | 0 / 0+0+0 | 29.5% / 780.0 MiB | ✅ | `20261120-163406-rvc` |
| c80-x10-e0.5-fcpe | 237.5 / 246.5 | 130.0 | 107.5 / 116.5 | 75.0 | 0.477 | 47.5 | 0 / 0+0+0 | 29.0% / 780.0 MiB | ✅ | `20261120-163651-rvc` |
| c100-x20-e0.5-fcpe | 277.5 / 311.2 | 140.0 | 137.5 / 171.2 | 135.0 | 0.468 | 50.3 | 0 / 0+0+0 | 36.0% / 780.0 MiB | ✅ | `20261120-163938-rvc` |
| c80-x20-e0.5-rmvpe | 285.0 / 306.5 | 130.0 | 155.0 / 170.0 | 180.0 | 0.641 | 69.7 | 0 / 0+0+0 | 28.0% / 882.0 MiB | ✅ | `20261120-164221-rvc` |
| c100-x30-e1.0-rmvpe | 292.5 / 295.0 | 140.0 | 152.5 / 155.0 | 150.0 | 0.531 | 74.0 | 0 / 0+0+0 | 29.0% / 884.0 MiB | ✅ | `20261120-164529-rvc` |

各脈衝延遲（ms，經引擎）：

- c160-x40-e1.0-fcpe：385, 395, 400, 405, 380, 370, 365, 375
- c120-x40-e1.0-fcpe：330, 330, 330, 330, 340, 340, 335, 330
- c100-x30-e1.0-fcpe：325, 305, 290, 285, 285, 290, 295, 280
- c80-x40-e1.0-fcpe：275, 330, 295, 290, 270, 340, 280, 315
- c80-x20-e1.0-fcpe：260, 250, 255, 260, 260, 260, 240, 250
- c80-x20-e0.5-fcpe：235, 235, 240, 255, 240, 210, 240, 235
- c80-x10-e0.5-fcpe：205, 235, 240, 230, 235, 250, 240, 240
- c100-x20-e0.5-fcpe：275, 275, 320, 280, 280, 295, 275, 275
- c80-x20-e0.5-rmvpe：310, 260, 265, 270, 300, 255, 300, 300
- c100-x30-e1.0-rmvpe：290, 295, 275, 275, 295, 295, 295, 290

### 音質輸出（供日後比較）

- 即時：bench 收到的 `recorded.wav`（經虛擬線、48 kHz float32），複製到 `D:\AetherTune-exp\artifacts\rvc-tune\realtime\<設定>.wav`。
- 離線：同一 RvcProcessor（同 block／SOLA／上下文）把整段 `wt-main-ref\dataset\reference-voices\voice-female-f1.wav` 轉成 `D:\AetherTune-exp\artifacts\rvc-tune\offline\<設定>.wav`（48 kHz PCM16），沒有裝置路徑干擾。

| 設定 | 即時 wav SHA256 | 離線 wav SHA256 | 離線 RTF | 離線處理 p95 (ms) |
|---|---|---|---|---|
| c160-x40-e1.0-fcpe | `8C1CB0C57D564121E88EB3809BA47A779BF62826312D3B7A8B51AF122C150864` | `081191D5C88D24107E6E0EE592237209E63E35DA8915212A82A3B7DC85E9F459` | 0.202 | 36.0 |
| c120-x40-e1.0-fcpe | `763C8040DB0C1CFA38C5EC357F704C85839E651A89B7813AFDEE08071C956A92` | `2F0CBCC6ABC045AF65D489350A6958DD7E0963232BDBA85058DC164F7C0A5BBE` | 0.259 | 32.3 |
| c100-x30-e1.0-fcpe | `2DE21C3747E58CE2CE2983F86A08E72D0407CE3890ADFCBEF528C46AB01B2AA3` | `9B5D096545096578A74B0EFC3F3056A9F1F7C4AF87AF0C8531159A9BD7F27DEF` | 0.342 | 39.3 |
| c80-x40-e1.0-fcpe | `92A665809D3C2B54F26B42A316C9D996B5B3FCE6F7D78B48D1FAD61D08EFE406` | `6CFC5E9493BB090A54FC4D51E82623C3A9EA2F5D7AD39C3D1DCA51E478E71C92` | 0.385 | 32.1 |
| c80-x20-e1.0-fcpe | `BBA0AC9C81804C3C1111DC636A7CC2CEFDAEB5D77F3328B25DBBD44404558877` | `9BAF7D39FD2E72507F6E40332AEBCBD9CF2842F3D2AD74D721CA46E812AF4EFA` | 0.401 | 37.0 |
| c80-x20-e0.5-fcpe | `49434A4E992A08677AAF8B8A29317C6B86593E9654BB9B2A9B6798F7E8D21881` | `F8A1CD5B482BF76B1506FD18D4E758DC4545CEC9FF1E1FCB8ACE85BEBAF616D0` | 0.382 | 32.0 |
| c80-x10-e0.5-fcpe | `8EA3E71FCE5CA38244859F3F6093111B81293AF664CD299559559F660C4223A2` | `C2CAC73E8D71A10202C47FE80A8A29044A28D014DE4051BDB71864E3B3DB34FC` | 0.392 | 34.5 |
| c100-x20-e0.5-fcpe | `B20CAD429B7E06E711DEA284D42C677075BDE54328CF043B1B5E1236C600504E` | `FB42963899600E71E5BC107F8873DE35FFCF5DD3E0168A17EDE2FD74E641BF15` | 0.317 | 35.1 |
| c80-x20-e0.5-rmvpe | `3D59275BDAD8ED01CC2E7C46808DC130E56FD4DD174BBDB9C51D2205586E43FD` | `6089C50C427F487A4DE805BBEEB1766161F55348B4BC33A30FFD7FE00476538B` | 0.581 | 49.8 |
| c100-x30-e1.0-rmvpe | `6FAB78B0D1854CCCDFC131E1C905BD5620E880BAA297B2B8C2A821AA6817D5BC` | `E46D5B55145D644626648C4ABD77FE4C6A350933DC34BE8E78E052632136A36F` | 0.449 | 46.6 |

### 結論與備註

- **最佳設定：chunk 80 ms／crossfade 20 ms／extra_time 0.5 s／f0 fcpe**：淨 p50 102.5 ms，RTF 0.47，underrun 0。c80-x10-e0.5-fcpe 幾乎一樣（107.5 ms），但 crossfade 10 ms 的接縫比較容易聽出來，所以選 20 ms。
- chunk 80 是 manifest 允許的下限（80–1000），要更低就得改 manifest 範圍，本輪沒有改。
- 延遲主要由 chunk 加 crossfade 決定：c80-x40（157.5 ms）比 c80-x20（117.5 ms）多約 40 ms。extra_time 從 1.0 降到 0.5，淨 p50 少約 15 ms；處理時間差不多。
- rmvpe 的 RTF 比 fcpe 高（0.64 vs 0.47，同為 c80-x20-e0.5），延遲也比較高，因為 rmvpe 每個 block 要多處理約 20 ms。
- 估計器在 96ec077 改用「起音」法。舊的互相關法遇到短 chunk 時會對錯音節，實測誤差約 150 ms。拿既有 run 重算，結果和先前一致。
- **重複確認（PC2 重開機後，17:33 台北）**：同一設定 c80-x20-e0.5-fcpe 再量一次，8/8 偵測，經引擎 p50 242.5／p95 248.25 ms，基線 135 ms，淨 p50 107.5 ms（第一次 102.5 ms，差 5 ms＝1 個估計器解析度格），RTF 0.46，處理 p95 47.5 ms，underrun 0、drops 0，GPU util p50 27%、VRAM 792 MiB。run `20261120-173312-rvc`，即時 wav `D:\AetherTune-exp\artifacts\rvc-tune\realtime\c80-x20-e0.5-fcpe-repeat.wav`（SHA256 `88C63C9C9E2EAD02EE724AAF14B2AA226E5749249E7ADFE077F6B5EDDFA43090`）。重開機前中斷的 `20261120-164838-rvc` 不完整，不採用。

### RVC 女聲試聽樣本（PC2，2026-11-20）

- 輸入（三個模型共用同一段）：`D:\AetherTune-exp\wt-main-ref\dataset\reference-voices\voice-female-f1.wav`（SHA256 `37976F69F73FB13D6FEFAF80268794D545D6E19BE5059437DB067455A795F406`；女聲參考語音 voice-female-f1，JVNV 日語短句、CC BY-SA 4.0，轉 48 kHz 單聲道）
- 轉換方式：`D:\AetherTune-exp\scripts\rvc_render.py`，以 wt-main-ref（exp/bench-e2e-latency）的 `services.engines.rvc_runtime.RvcProcessor` 逐 block 處理（與即時同樣的 rolling context／SOLA），離線、不經音訊裝置。
- 參數（本輪最佳即時設定 c80-x20-e0.5-fcpe）：`{"chunk":80,"crossfade":20,"extra_time":0.5,"f0_method":"fcpe"}`；另有 pitch 0、index_rate 0.75。GPU：RTX 2060。
- 輸出：48 kHz、PCM16、單聲道。

| 檔案 | 模型 | 權重 SHA256 | index SHA256 | 長度 (s) | 離線 RTF | 峰值 | RMS | 輸出 SHA256 |
|---|---|---|---|---|---|---|---|---|
| `Sage_CN_HeroicFemale.wav` | Sage_CN_HeroicFemale（`D:\AetherTune-exp\wt-main-ref\models\weights\Sage_CN_HeroicFemale.pth`） | `57C2A770211A7F08C7AE973E6343006547CA4400752CE4DA17842117E1E556AD` | `4D9DDA9D71D9BB6A65283718F0390AA45951A818E69F57B8686583AC31BB9AF9` | 13.4 | 0.36 | 0.796 | 0.1019 | `214131858281A93CD2AFAD5621A31ECB79569163587100E396964EF666D4251E` |
| `ChineseBluetooth_F.wav` | ChineseBluetooth_F（`D:\AetherTune-exp\wt-rvc-models\models\weights\ChineseBluetooth_F.pth`） | `A0C67C194B83A81D00339AEA3BAACF8CB69C41D4904DDAAA6862361303CF7B33` | `627C3FE5D48F513D3C518FB9900865891B557476E78B7CC35B2E042920ACDD23` | 13.4 | 0.356 | 0.943 | 0.1921 | `613B80AEBD52FE814AA1D2DB335ADCCE15267F028C5825721066950D0385A229` |
| `EGirl_F.wav` | EGirl_F（`D:\AetherTune-exp\wt-rvc-models\models\weights\EGirl_F.pth`） | `FA099355523B09DCDE45489A567F7B5E1F843DF64BB6F532D2CB6C93606880A1` | `29F2731238F14B6C509B9B7BCCC75A21AE7414737C6C101C739FD95CC8F37839` | 13.4 | 0.385 | 0.858 | 0.1041 | `8B0763D033D20728BF3E03EEE7011A466EF7C7B26DBD46FA33772926A2961739` |

驗證：在 `D:\AetherTune-exp\artifacts\listening\rvc-female-20261120\` 執行 `Get-FileHash *.wav -Algorithm SHA256` 對照 SHA256SUMS.txt。

<!-- rvc-tune:end -->

<!-- rvc-naturalness:start -->

## RVC 自然度掃描（PC2，2026-11-20 晚上，exp/rvc-naturalness）

- 基準：最佳即時設定 c80／x20／e0.5，Sage_CN_HeroicFemale，pitch 0；每組只改一個變數（formant、index_rate、f0）。formant 由 ae3d617 起可設定（原本寫死 0）。
- 輸入：`wt-main-ref\dataset\reference-voices\voice-female-f1.wav`（JVNV F1 日語短句、女聲，CC BY-SA 4.0）。本機只有這一段輸入語音；`voice-male-m1.wav` 在 wt-main-ref、D:\AetherTune、D:\AetherTune-exp\dataset 都不存在，**男轉女 +10～+12 半音未做**。
- 音檔：離線轉換（同 RvcProcessor、同 block／SOLA）`D:\AetherTune-exp\artifacts\listening\rvc-naturalness-20261120\render\<組>.wav`；即時錄音（經虛擬線）`...\realtime\<組>.wav`。
- CER：SenseVoiceSmall（funasr 1.1.5，seed-vc venv 既有套件；模型下載到 `D:\AetherTune-exp\cache\modelscope`），language=ja、不做 ITN；以「來源音檔的辨識結果」為參考算**相對 CER**（去標點／空白、NFKC）。來源沒有人工逐字稿，ASR 也會錯，所以只適合組間比較，不是絕對可懂度。
- 延遲：speech 訊號、起音估計器（等級 A），淨值 = 經引擎 p50 − 兩條虛擬線 p50。base 沿用重開機後的重複確認 run，rmvpe 沿用延遲調校的 c80-x20-e0.5-rmvpe run（設定相同）。

參考文字（來源 ASR）：「最近自分の人生に充実感を感じているんだ友達家族そして仕事もうまくいっている本当に幸せだ」

| 組 | formant | index_rate | f0 | 相對 CER | ASR 結果 | 淨 p50 / p95 (ms) | RTF | underrun | 離線 RTF | 離線 wav SHA256 | run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base-fm0-ix075-fcpe | 0 | 0.75 | fcpe | 0.070 | 最近自分の人生に充実感を感じているんだ友達家族そして仕事もうまくいってゃいるだ本当に幸せな | 107.5 / 113.2 | 0.460 | 0 | 0.474 | `3D1A27F1AB6823C9BB121992A01DB164A83995D1602669BF555C725960C160DA` | `20261120-173312-rvc` |
| fm-1.0 | -1 | 0.75 | fcpe | 0.093 | 最近自分の人生に忠実感を感じているんだ友達家族そして仕事もうまくいっちゃいる本当に幸せな | 122.5 / 143.2 | 0.548 | 0 | 0.535 | `85037E588D5ABD8DF3CA1919A0D03385FB788C3895BA1DDD84CCBF038BFA1136` | `20261120-174203-rvc` |
| fm-0.5 | -0.5 | 0.75 | fcpe | 0.093 | 最近自分の人生に忠実感を感じているんだ友達家族そして仕事もうまくいっちゃいる本当に幸せな | 95.0 / 119.8 | 0.541 | 0 | 0.458 | `44125B5BB1EB35663CAE147B186CD781752DA11B3E3204BBA4CB096584EAD9D3` | `20261120-174503-rvc` |
| fm+0.5 | 0.5 | 0.75 | fcpe | 0.047 | 最近自分の人生に充実感を感じているんだ友達家族そして仕事もうまくいってゃいる本当に幸せな | 120.0 / 146.5 | 0.474 | 0 | 0.399 | `16ACC3E6A67DD1593CD71807993A17AB5BB70F912F401C0328370B3F8CEC88FF` | `20261120-174800-rvc` |
| fm+1.0 | 1 | 0.75 | fcpe | 0.093 | 最近自分の人生に充実感を感じているんだ友達家族そして仕事もうまくいっちゃいるぶ本当に幸せな | 110.0 / 154.0 | 0.474 | 0 | 0.388 | `39BC9D07D1CE8DAD75F1869D818B75670B20F2EA0F0FB559AB93167FC130D560` | `20261120-175048-rvc` |
| ix0.30 | 0 | 0.3 | fcpe | 0.023 | 最近自分の人生に充実感を感じているんだ友達家族そして仕事もうまくいっている本当に幸せな | 112.5 / 131.5 | 0.478 | 0 | 0.465 | `362B5C0F03B3BE1F21949B27D824A050FF0516EFCD8DB1D0A3011F2FEAED4402` | `20261120-175335-rvc` |
| ix0.50 | 0 | 0.5 | fcpe | 0.023 | 最近自分の人生に充実感を感じているんだ友達家族そして仕事もうまくいっている本当に幸せな | 120.0 / 128.2 | 0.485 | 0 | 0.398 | `8F7E22D87C32D49598EE025B1BCCBF4B434F85E9F7E441E6ABCDBF8124FA3EE7` | `20261120-175622-rvc` |
| ix1.00 | 0 | 1.0 | fcpe | 0.070 | 最近自分の人生に忠実感を感じているんだ友達家族家そして仕事もうまくいっている本当に幸せな | 100.0 / 119.8 | 0.476 | 0 | 0.386 | `B25D4FDD0EE2EA77CD680691ACBC8A733AC7D6064BCEC7696D9D27FE0DDE3B39` | `20261120-175910-rvc` |
| f0-rmvpe | 0 | 0.75 | rmvpe | 0.023 | 最近自分の人生に充実感を感じているんだ友達家族そして仕事もうまくいっている本当に幸せな | 155.0 / 170.0 | 0.641 | 0 | 0.611 | `9EFBDE2EB3D1D8C50ED23236F3A0E0A3F37C4F4AECC0F309563A545F6B56B4F5` | `20261120-164221-rvc` |

### 經過「Discord」之後（Opus 64 kbps 模擬）與盲聽樣本

- **不是真的經過 Discord**：本輪沒有登入 Discord、也沒有建立語音頻道，所以用 ffmpeg 9.0.2（libopus）模擬 Discord 語音的編碼：Opus、48 kHz、單聲道、64 kbps VBR、`-application voip`、20 ms frame，編碼後再解回 48 kHz PCM16。Discord 自己的噪音抑制、回音消除、自動增益、網路掉包沒有模擬。
- 盲聽樣本：`D:\AetherTune-exp\artifacts\listening\rvc-naturalness-20261120\blind-opus64\S01.wav`～`S12.wav`，附 `SHA256SUMS.txt`。檔名由固定 seed 20261120 打亂。
- 對照表另存在 `D:\AetherTune-exp\artifacts\listening\rvc-naturalness-20261120\blind-key-DO-NOT-OPEN.csv`（code、label、來源路徑、SHA256）。內容包括 Sage 的 9 組設定、ChineseBluetooth_F、EGirl_F 與原始輸入（作為參考錨點）。
- 18:07 定案：日語這批 S01–S12 **不提交聽測**，等中文輸入重做後再聽。盲聽代號和組別的對應只放在另存的 key，文件裡不寫。

| 組別 | 相對 CER（離線） | 相對 CER（Opus 64k 後） |
|---|---|---|
| ChineseBluetooth_F-c80x20e0.5 | — | 0.047 |
| EGirl_F-c80x20e0.5 | — | 0.070 |
| Sage-base-fm0-ix075-fcpe | 0.070 | 0.093 |
| Sage-f0-rmvpe | 0.023 | 0.023 |
| Sage-fm+0.5 | 0.047 | 0.047 |
| Sage-fm+1.0 | 0.093 | 0.093 |
| Sage-fm-0.5 | 0.093 | 0.116 |
| Sage-fm-1.0 | 0.093 | 0.070 |
| Sage-ix0.30 | 0.023 | 0.023 |
| Sage-ix0.50 | 0.023 | 0.023 |
| Sage-ix1.00 | 0.070 | 0.093 |
| source-voice-female-f1 | 0.000 | 0.000 |

### 自然度掃描的觀察（CER 只反映可懂度，自然度仍要靠人耳聽）

- 參考句約 43 個字，1 個字的差別約等於 CER 0.023。所有組的 CER 都在 0～0.116 之間（0～5 個字），**差距很小**。
- 同一組參數重跑結果不完全一樣：Sage base 和女聲樣本的 Sage 參數相同，輸出 SHA256 卻不同（GPU／faiss 有非決定性）。所以 ±1 個字的差距應該視為雜訊。
- 相對好的組：index 0.3、index 0.5、f0 rmvpe。離線和 Opus 後都是 0.023，比 base（index 0.75）的 0.070／0.093 少錯 2～3 個字。
- 相對差的組：formant −0.5 經過 Opus 後最差（0.116）；formant ±1.0 離線都是 0.093。
- 延遲：formant、index 對延遲沒有可測的影響，淨 p50 都在 95～122.5 ms（重複量測本身就有 ±5～10 ms 的波動）。
- formant 為負時要先重取樣更長的輸入，RTF 會從 0.47 升到 0.54～0.55，仍低於 0.7。
- rmvpe 的淨 p50 是 155 ms（RTF 0.64），仍在 200 ms 目標內，但比 fcpe 多約 50 ms。
- 建議人耳盲聽時優先比較：base、index 0.5、index 0.3、rmvpe、formant +0.5。如果聽感也是 index 0.5 較好，下一步可以把 index_rate 預設改成 0.5 再量一次（本輪不改預設）。

<!-- rvc-naturalness:end -->

<!-- rvc-naturalness-zh:start -->

## RVC 中文自然度（PC2，2026-11-20 晚上，AISHELL-3 公開輸入）

### 輸入清單（公開資料集，音檔不進 repo）

- 來源：AISHELL-3（OpenSLR SLR93），取自 Hugging Face 鏡像 <https://huggingface.co/datasets/AISHELL/AISHELL-3>，revision `f20d5db4a31fe779ef07bb1af4ea92da5c786622`，只下載用到的單檔（train/wav）。授權（僅標註、未評估）：Apache-2.0（HF 資料卡標示；僅標註、未評估）；OpenSLR 原頁 <https://www.openslr.org/93/>。
- 每位說話者取 12～22 字的句子（排除含「亿／万／零」的數字串），依檔名順序接到約 11～14 秒，句間 0.3 秒靜音；44.1 kHz PCM16 單聲道。存放：`D:\AetherTune-exp\dataset\public-zh\`（含 `manifest.json`、`SHA256SUMS.txt`）。逐字稿來自資料集 `train/content.txt`（簡體）。

| 標籤 | 說話者 ID | 性別 | 年齡組／口音（spk-info） | 長度 (s) | SHA256 | 組成檔 | 逐字稿 |
|---|---|---|---|---|---|---|---|
| zh-m1 | SSB0535 | male | B／north | 11.32 | `595F79DE669308B12DC4A42454FD84640D6807057543087DEFB69F3B25B05101` | SSB05350001.wav、SSB05350005.wav | 结合智慧单元式温湿度系统的硬件儿部署往往只关注研报中给出的股票目标价位 |
| zh-m2 | SSB0407 | male | C／north | 13.86 | `C319804022617AE8D0EE880A495BF629719F01BFF58B0B425CDF77E6676BFA2C` | SSB04070006.wav、SSB04070007.wav、SSB04070010.wav、SSB04070011.wav | 稻垣吾郎出演的电视剧有什么我会信守承诺带你去阿卡普尔科还有一批出身低级别联赛的被告人京本政树出演的电视剧有什么 |
| zh-f1 | SSB0043 | female | B／north | 11.07 | `DD678ADFD010259FC4AC4EA81E2DE37B807E8734BB6FA9150D83DF472C65FBA6` | SSB00430005.wav、SSB00430009.wav、SSB00430014.wav | 你觉得你可以跟我玩儿一场我就跟你说那个儿科医生说话不负责任的但是连尤尼丝都不愿用那玩意 |
| zh-f2 | SSB0534 | female | C／north | 11.13 | `BF44538393DE722A74936746A6EDEAE3FFEAA7A723CA58A945EFE75267FFB43B` | SSB05340001.wav、SSB05340002.wav | 登顶最佳影片最佳导演最佳女配角三项大奖北京四块高溢价土地均来自北京大兴区 |

### 結果

- 基準：c80／x20／e0.5，Sage_CN_HeroicFemale；A 段＝女聲輸入（zh-f1、zh-f2，pitch 0），B 段＝男轉女（zh-m1、zh-m2，index 0.75、fcpe）。
- 延遲：每組一次 speech 訊號聲學量測（等級 A，起音估計器），淨值＝經引擎 p50 − 兩條虛擬線 p50；RTF／underrun 來自引擎計數。延遲與輸入語音無關（量測用固定 bench 訊號），所以每組一個值。
- CER：SenseVoiceSmall（language=zh、不做 ITN），去標點／空白、NFKC。**絕對 CER** 對資料集逐字稿；**相對 CER** 對「輸入原音的辨識結果」。表中是兩位說話者的平均（括號內為各自的值）。

原始輸入本身的絕對 CER（辨識器底線）：zh-m1-SSB0535 0.029、zh-m2-SSB0407 0.109、zh-f1-SSB0043 0.070、zh-f2-SSB0534 0.000

| 組 | 段 | pitch | formant | index | f0 | 淨 p50 / p95 (ms) | RTF | underrun | 絕對 CER | 相對 CER | 絕對 CER（Opus 64k 後） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| f-base | A | 0 | 0 | 0.75 | fcpe | 112.5 / 139.8 | 0.570 | 0 | 0.116（0.233／0.000） | 0.128（0.256／0.000） | 0.116（0.233／0.000） |
| f-ix0.5 | A | 0 | 0 | 0.5 | fcpe | 120.0 / 125.0 | 0.474 | 0 | 0.093（0.186／0.000） | 0.081（0.163／0.000） | 0.081（0.163／0.000） |
| f-ix0.3 | A | 0 | 0 | 0.3 | fcpe | 115.0 / 141.2 | 0.485 | 0 | 0.035（0.070／0.000） | 0.023（0.047／0.000） | 0.047（0.093／0.000） |
| f-rmvpe | A | 0 | 0 | 0.75 | rmvpe | 120.0 / 168.2 | 0.642 | 0 | 0.116（0.233／0.000） | 0.128（0.256／0.000） | 0.105（0.209／0.000） |
| f-fm+0.5 | A | 0 | 0.5 | 0.75 | fcpe | 195.0 / 259.0 | 0.538 | 0 | 0.081（0.163／0.000） | 0.093（0.186／0.000） | 0.070（0.140／0.000） |
| f-ix0.5-rmvpe | A | 0 | 0 | 0.5 | rmvpe | 105.0 / 118.2 | 0.633 | 0 | 0.081（0.163／0.000） | 0.070（0.140／0.000） | 0.093（0.186／0.000） |

### 進度註記（2026-11-20 20:30 台北）

- **A 段（女聲 6 組）已完成**：離線轉換、聲學延遲、中文 CER。鎖的使用時段是 18:13–18:31（台北）。
- **中文 CER 在 CPU 上計算**：A 段的 CER（含 Opus 64k 解碼版）是在等鎖期間用 CPU 跑 SenseVoiceSmall 算的，沒有用 GPU。結果和 GPU 版應一致，但沒有逐一比對。
- **zh-f2 太容易**：zh-f2（SSB0534）每一組的 CER 都是 0，鑑別力主要來自 zh-f1（SSB0043；句子較口語，原音的辨識也有 0.070）。
- **A 段女聲結論（zh-f1）**：index 0.3 最好，絕對 CER 0.070、Opus 後 0.093，和原音相同或只多 1 個字。formant +0.5、index 0.5、index 0.5＋rmvpe 在 0.14～0.19。base 和 rmvpe 最差（0.21～0.23）。和日語那一輪「index 調低比較好」的方向一致。
- **f-fm+0.5 延遲疑受干擾**：淨 p50 195 ms、淨 p95 259 ms（經引擎 p95 389 ms），明顯偏高。量測時間 18:27–18:30，和 Hub 在 18:22 與 18:29 起跑的測試重疊，懷疑受 CPU 負載干擾，待 B 段時重量一次。
- **尚未完成**：B 段（男轉女 pitch +10／+11／+12 × formant 0／+0.5）、f-fm+0.5 重量、中文盲聽樣本。原因是 Hub 從 18:34 起有「進行中」列，20:20 又開了一輪完整測試，預計 100 分鐘，依規則不重疊使用 GPU。
- f-base 的 RTF 0.57 也比上一輪同設定（0.46）高，但量測時間 18:13–18:17 早於 Hub 測試，原因不明，會一併重量。

<!-- rvc-naturalness-zh:end -->
