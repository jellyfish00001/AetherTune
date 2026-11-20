# PC2 實機 E2E 延遲量測結果（2026-11-20）

- 日期：2026-11-20（Asia/Taipei），15:07–15:45
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
| seed-vc（realtime-tiny，block 0.3 s，diffusion 10）#1 | chirp | 5/8 | 655.9 | 669.9 | 689.7 | 689.8 | 129.0 | 540.9 | 450／466 | 154／300 | 0.46 | 0／in 0、out 0 | 是 | 36%／43%、1413 MiB | A | `20261120-151319-seed-vc` |
| seed-vc（同上）#2 | chirp | 6/8 | 651.9 | 667.1 | 676.2 | 678.4 | 126.0 | 541.1 | 446／461 | 154／300 | 0.47 | 0／in 0、out 0 | 是 | 0%／0%、266 MiB | A | `20261120-152338-seed-vc` |
| meanvc2（realtime 40ms，block 160 ms）#1 | chirp | 0/8 | — | — | — | — | 123.7 | — | 385／1076 | 174／160 | 0.77 | 0／in 0、out 21120 | 邊緣：處理 p95 174 ms > block；量測中延遲由 356 ms 升到 ~1080 ms 並丟 0.44 s 輸出 | 29%／35%、2161 MiB | —（脈衝 0/8） | `20261120-151553-meanvc2` |
| meanvc2（同上）#4 | chirp | 0/8 | — | — | — | — | 133.7 | — | 370／393 | 128／160 | 0.71 | 0／in 0、out 0 | 是（本次無 drop） | 30%／42%、2163 MiB | C（僅 trace） | `20261120-153530-meanvc2` |

## 備註

- baseline 每次引擎 run 前重量；各 run 的 baseline p50（兩跳和）介於 125–134 ms，表中 engine−baseline 用該 run 自己的 baseline。
- seed-vc 兩次可重現：E2E p50 667–670 ms，engine−baseline ≈ 541 ms；trace in→out p50 ≈ 446–450 ms，比聲學少約 90 ms（trace 忽略 0.3 s block 的 rolling context／extra_time）。#2 的 GPU 取樣器只記到閒置值，GPU 以 #1 為準。
- seed-vc 偵測 5–6/8：轉換後的 chirp 與模板相關性 0.36–0.44，部分脈衝落在 missing 門檻下；有偵測到的脈衝彼此差 < 35 ms。
- meanvc2 對 chirp／click 這類非語音訊號幾乎輸出靜音（錄到 peak 0.004），脈衝 bench 量不到（0/8）；trace in→out p50 350–385 ms（4 次）。手動 click 診斷（`diag-meanvc2-manual-click`）7/8 落在 714–762 ms 但 confidence 0.37–0.50，只列 B 級參考。
- 環境變數：pc2-virtual 會自動設定 `AETHERTUNE_WASAPI_AUTOCONVERT=1` 與 `AETHERTUNE_WASAPI_EXCLUSIVE_INPUT=Steam Streaming Microphone`（只影響該程序及子程序，不改系統設定）；`AETHERTUNE_LATENCY_TRACE=1` 需手動設定；Seed-VC 的 `HF_HOME／HF_HUB_CACHE` 由 `stream_runtime` 指到 `tools/external/seed-vc/checkpoints`；`TCLLIBPATH=D:/AetherTune-exp/tcl-shim` 只在跑 Seed-VC setup 腳本或 GUI 時需要，量測不需要。

## 學到什麼

- Steam Streaming Microphone 的 capture 在 WASAPI shared mode（Windows 預設格式 44.1 kHz mono）會把音訊時間拉長約 2 倍並丟片段（0.5 s 間隔的 8 個 burst 只收到 4 個、間隔 ~1.03 s）；同一 stream 改 exclusive 48 kHz 後 8/8、≈ 52–59 ms。已以 opt-in 環境變數修正（f41b022）。
- `e2e-latency-run.ps1` 原本在 RUNNING 後不再讀取引擎 stdout／stderr，Seed-VC 每個 block 都會印 tqdm，管線塞滿後引擎卡住、bench 0/8；已改為非同步排空（2d3714b）。
- bench 的 `recorded.wav` 是 32-bit float 資料但 WAV 標頭為 PCM，用 soundfile 讀會看成雜訊（曾誤判為裝置振鈴）；分析要以 float32 原始資料讀取。此為工具既有限制，本輪未改。
- 脈衝 chirp 適合 Seed-VC／RVC 類保留音色輪廓的引擎；MeanVC2 這種以 ASR 內容為主的引擎會吃掉非語音脈衝，需要語音型測試訊號（例如短語音片段＋包絡互相關）才能做聲學 E2E。
- trace（approximate internal）系統性低估：Seed-VC 低約 90 ms；不能拿 trace 取代聲學數字。

## BLOCKED／WAITING

- meanvc2 聲學 E2E：WAITING——脈衝訊號無法通過引擎；需在 bench 加語音型訊號（屬工具改版，下一輪）。
- rvc／xvc：進行中（見後續更新）。

## 一行指令

```powershell
$env:AETHERTUNE_LATENCY_TRACE='1'; $env:HF_HOME='D:\AetherTune-exp\cache\hf'; $env:MODELSCOPE_CACHE='D:\AetherTune-exp\cache\modelscope'; $env:MPLCONFIGDIR='D:\AetherTune-exp\cache\mpl'; Set-Location D:\AetherTune-exp\wt-main-ref; pwsh -NoProfile -File tools\e2e-latency-run.ps1 -Profile pc2-virtual -Root D:\AetherTune-exp\wt-main-ref -Python D:\AetherTune-exp\wt-main-ref\.venv\Scripts\python.exe -Engine seed-vc -WarmupSec 20 -ResultsDir D:\AetherTune-exp\artifacts\e2e-latency
```
