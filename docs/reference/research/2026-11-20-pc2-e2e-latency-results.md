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
