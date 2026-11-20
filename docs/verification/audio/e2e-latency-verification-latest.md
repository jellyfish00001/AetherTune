# 端到端延遲量測驗證（mic→輸出）

日期：2026-11-20（Asia/Taipei）。本頁擁有 Round 1 脈衝列 E2E 延遲 harness、離線分析與合成 regression 邊界。**即時串流研究目標為 100–300 ms E2E**（僅研究目標）；**LIVE gate 仍為 `e2e_first_packet_ms <= 5000`**，見 [live-gate](../../specs/live-gate.md) 欄位 `e2e_first_packet_ms`、`e2e_p50_ms`、`e2e_p95_ms`。

## 目的與方法

- **loopback baseline**：`--mode loopback`，單跳虛擬迴授（例如 `--output-device "CABLE Input"`、`--input-device "CABLE Output"`），量測 OS／驅動 baseline。
- **through engine**：`--mode engine` 須**兩條路由**（不可在同一端點 play/rec，否則只量到直接線而非引擎）：bench 播 **CABLE Input** → 引擎（Desktop VC）擷 **CABLE Output** → 輸出 **Voicemeeter Input** → bench 錄 **Voicemeeter Out B1**（見 `audio-rack/routing/seed-vc-virtual-route.json`）。減 baseline 時應為**未掛引擎的相同兩跳迴授**，或兩段單跳 loopback 相加。此為注入虛擬線量測，**不含實體麥 ADC／耳機 DAC**，非實體麥 E2E，**不能**作 LIVE gate 麥克風來源。建議 `--signal chirp`。
- 每個脈衝以參考模板在錄音上窗內做正規化互相關，拋物線子樣本插值；彙總 `min`／`p50`／`p95`／`max` 與 `e2e_first_packet_ms`。
- **脈衝間隔必須大於 `max_delay_ms` + 單脈衝長度**，否則長 E2E 延遲會與前一脈衝混淆；預設 **interval 1000 ms**、`max_delay_ms` **900 ms**（`build_pulse_train`／bench）。
- 可選 `AETHERTUNE_LATENCY_TRACE=1` 或 request `latency_trace` 於 `stream_runtime` 寫入 `latency-trace.jsonl` 與 `report["latency_trace"]`。事件以 **48 kHz 累積 frame 位置** 記錄（輸入 callback 結束位置、worker 已消耗輸入 frame、非空輸出累積 frame）；`summary` 以 `bisect` 對齊輸入時間軸計算 `input_to_model_ms`／`input_to_output_ms`（輸出假設第 *k* 個輸出 frame 對應第 *k* 個輸入 frame，**忽略** rolling context／lookahead／啟動填補）。屬 **approximate_internal, not acoustic E2E**；脈衝 bench 仍為權威 E2E。

## PC2 裝置盤點（2026-11-20）

量測時間：2026-11-20 13:45（Asia/Taipei）。PC2 **無** VB-CABLE、**無** Voicemeeter；決策為沿用既有 Voicemod／Voxal 虛擬裝置，不安裝新驅動。

| 端點（名稱片段） | 方向 | 狀態 | winmm loopback（MME，粗探） |
|---|---|---|---|
| Voice Changer Virtual Audio Device (WDM) | render／capture | 使用中（**推測**為 NCH Voxal 側虛擬裝置，安裝於 `C:\Program Files (x86)\NCH Software\Voxal`，**推測，未證實**；driver MFDriver 1.0.0.1／Voice Changer soda） | lineB：PASS（peak 0.0751 vs 播放 0.183，約 −7.7 dB 衰減；粗 onset 約預期後 2.5 ms） |
| Steam Streaming Microphone | render／capture | 使用中（Valve） | lineA：PASS（peak 0.1849；粗 onset 約預期後 298 ms，MME buffering） |
| Voicemod Virtual Audio Device (WDM) | render「線路」／capture「麥克風」 | **未啟用／不可見**（MMDevices `DeviceState 0x10000001`；winmm／PnP AudioEndpoint 清單缺席） | 未測；啟用屬系統變更（電腦管家／Johnny），本輪不必做（兩條獨立線已足夠） |
| crosstalk（Voice Changer → Steam capture／Steam → Voice Changer capture） | — | 獨立線 | 兩向 peak 0.0000 |

13:51（Asia/Taipei）以 repo 內 `tools/virtual-line-probe.ps1` 重跑 lineA（Steam Streaming Microphone）＋crosstalk（Voice Changer capture）：PASS，peak 0.1849、粗 onset 4.0 ms、crosstalk peak 3.05e-05；同一條線 13:45 為約 298 ms，可見 MME 粗 onset 波動大，只能判斷「通／不通」，不能當延遲數字。

探測探測條件（與 `tools/virtual-line-probe.ps1` 一致）：16-bit mono 48 kHz；1 kHz、300 ms、約 −14.7 dBFS；錄製 2 s。表中 onset 為 **粗 MME 估計，不是 E2E 延遲**。

**路由（PC2）**

- **lineA**（tool → engine）：Steam Streaming Microphone 成對（bench 播 render／引擎擷 capture）。
- **lineB**（engine → tool）：Voice Changer Virtual Audio 成對。
- **baseline**：lineA、lineB **各自**單跳 loopback；`engine_minus_baseline` 減去 **lineA + lineB baseline 之和**（`baseline_sum`）。
- `tools/verify_wiring.ps1` 針對 CABLE／Voicemeeter；**pc2-virtual 不用**該腳本。未改 `audio-rack/routing/` profile。

```text
bench --(lineA play)--> Steam render ===> Steam capture --(engine in)--> engine
engine --(lineB play)--> Voice Changer render ===> Voice Changer capture --(bench rec)--> bench
```

預檢（可 `-SkipPrecheck` 略過）：`virtual-line-probe.ps1` 對兩線做 loopback + crosstalk；若 python 含 sounddevice／soundfile 可再加 `virtual_cable_loopback.py`。

**PC2 一行**（完整環境變數版見下文「PC2 實機結果 → 一行指令」）

```powershell
pwsh -NoProfile -File tools/e2e-latency-run.ps1 -Profile pc2-virtual -Root D:\AetherTune-exp\wt-main-ref -Python <runtime python> -Engine meanvc2
pwsh -NoProfile -File tools/virtual-line-probe.ps1 -List
pwsh -NoProfile -File tools/virtual-line-probe.ps1 -Out "Steam Streaming Microphone" -In "Steam Streaming Microphone" -Crosstalk -CrosstalkOut "Steam Streaming Microphone" -CrosstalkIn "Voice Changer Virtual Audio" -OutJson $env:TEMP\probe-lineA.json
```

系統 python 無 numpy／sounddevice；基準量測須由 `D:\AetherTune-exp` 另案 runtime 經 `-Python` 傳入。`-RequestOnly` 可僅產生 `engine-request.json`（reference 缺檔時 BLOCKED）。

## 一行指令

自 repo 根目錄，**單條命令**可重跑整套編排（無自動安裝、無 git 推送）；輸出目錄預設為 gitignored `artifacts/e2e-latency/`（每次 run 建立 `yyyyMMdd-HHmmss-<engine>/` 子目錄，結束時寫入同 timestamp 的 `-summary.json`／`-summary.md` 並列印彙總表）。`-SelfTest` 僅跑 bench 合成路徑，**不接音訊裝置與 GPU**。

```powershell
pwsh -NoProfile -File tools/e2e-latency-run.ps1 -Profile cable-voicemeeter -Engine none
pwsh -NoProfile -File tools/e2e-latency-run.ps1 -Profile pc2-virtual -Root D:\AetherTune-exp\wt-main-ref -Python <runtime python> -Engine meanvc2
pwsh -NoProfile -File tools/e2e-latency-run.ps1 -SelfTest
pwsh -NoProfile -File tools/e2e-latency-run-regression.ps1
```

| 子目錄內容（典型） | 說明 |
|---|---|
| `e2e-latency-report.json` | bench 權威 E2E 報告（`aethertune-e2e-latency/v1`） |
| `reference.wav`／`recorded.wav`／`pulses.json` | 脈衝參考與錄音證據 |
| `engine-stdout.jsonl`（引擎 run） | `runner_service` JSONL |
| `stream-evidence.json`（若可用） | `stream_runtime` 路由／metrics 快照 |

**CABLE／Voicemeeter profile** 實機仍 **WAITING**（PC2 無該驅動）；**pc2-virtual** 實機結果見下文「PC2 實機結果」。合成 `-SelfTest` 可本地 PASS。

仍須注意：經 CABLE／Voicemeeter **注入**的來源不是實體麥 E2E；engine 模式 baseline 須覆蓋**相同兩跳**（見上文 loopback 說明）。

## 可重跑命令（細項）

```powershell
Set-Location D:\AetherTune
python tools/e2e-latency-bench.py --help
python tools/e2e-latency-bench.py --dry-run --out-dir $env:TEMP\e2e-dry
python tools/e2e-latency-bench.py --self-test --out-dir $env:TEMP\e2e-self
python tools/e2e-latency-analysis-regression.py
python -m unittest services.engines.test_latency_trace -v
pwsh -NoProfile -File tools/e2e-latency-run.ps1 -SelfTest -ResultsDir $env:TEMP\e2e-results

# 實機（需已安裝 sounddevice／numpy；本輪未執行）
# 單跳 baseline（可各跑一段或合併兩跳無引擎迴授）
python tools/e2e-latency-bench.py --mode loopback --input-device "CABLE Output" --output-device "CABLE Input" --out-dir artifacts\e2e-latency\loopback-cable
python tools/e2e-latency-bench.py --mode loopback --input-device "Voicemeeter Out B1" --output-device "Voicemeeter Input" --out-dir artifacts\e2e-latency\loopback-vm-b1
# engine：播 CABLE Input，錄 Voicemeeter Out B1（引擎已接好 CABLE Out → VM Input）
python tools/e2e-latency-bench.py --mode engine --input-device "Voicemeeter Out B1" --output-device "CABLE Input" --baseline-report artifacts\e2e-latency\loopback-cable\e2e-latency-report.json --out-dir artifacts\e2e-latency\engine

# 離線重算
python tools/e2e_latency_analysis.py --reference ref.wav --recorded rec.wav --pulses-json pulses.json --out report.json
```

輸出預設在 gitignored `artifacts/`；不得提交 WAV／報告。

## PC2 實機結果（2026-11-20，exp/bench-e2e-latency）

量測時間：15:07–15:45（Asia/Taipei）；commit 見 run 目錄 `e2e-latency-report.json` 的 `git_commit`；結果目錄 `D:\AetherTune-exp\artifacts\e2e-latency\`（不進 git）。詳細研究紀錄：[2026-11-20-pc2-e2e-latency-results](../../reference/research/2026-11-20-pc2-e2e-latency-results.md)。

證據等級：**A** = PC2 實機聲學脈衝 bench 直接量到（偵測 ≥ 5/8、confidence ≥ 0.35）；**B** = 實機聲學但偵測少或 confidence 偏低（僅供參考）；**C** = 由 trace／baseline 推估，非聲學量測；**—** = 無法量到。trace `input_to_output_ms` 為 approximate internal（忽略 rolling context／lookahead），不是聲學 E2E。

### baseline（`-Engine none`，各線單跳）

| 線路 | 路徑 | 偵測 | min | p50 | p95 | max | 證據 | run 目錄 |
|---|---|---|---:|---:|---:|---:|---|---|
| lineA | 喇叭→麥克風 (Steam Streaming Microphone)，capture exclusive | 8/8 | 55.7 | 59.0 | 59.0 | 59.0 | A | `20261120-150711-baseline/baseline-lineA` |
| lineB | 喇叭→麥克風 (Voice Changer Virtual Audio Device (WDM))，shared＋auto_convert | 8/8 | 74.3 | 74.3 | 79.5 | 82.3 | A | `20261120-150711-baseline/baseline-lineB` |

### through-engine

| 引擎（設定） | 訊號 | 偵測 | E2E min | p50 | p95 | max | baseline p50（兩跳） | engine−baseline p50 | trace in→out p50／p95 | 處理 p95／block | RTF | underrun／drop | 跟得上即時 | GPU util p50／max、VRAM | 證據 | run 目錄 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|---|---|---|---|
| seed-vc（realtime-tiny，block 0.3 s，diffusion 10）#1 | chirp | 5/8 | 655.9 | 669.9 | 689.7 | 689.8 | 129.0 | 540.9 | 450／466 | 154／300 | 0.46 | 0／in 0、out 0 | 是 | 36%／43%、1413 MiB | A | `20261120-151319-seed-vc` |
| seed-vc（同上）#2 | chirp | 6/8 | 651.9 | 667.1 | 676.2 | 678.4 | 126.0 | 541.1 | 446／461 | 154／300 | 0.47 | 0／in 0、out 0 | 是 | 0%／0%、266 MiB | A | `20261120-152338-seed-vc` |
| meanvc2（realtime 40ms，block 160 ms）#1 | chirp | 0/8 | — | — | — | — | 123.7 | — | 385／1076 | 174／160 | 0.77 | 0／in 0、out 21120 | 邊緣：處理 p95 174 ms > block；量測中延遲由 356 ms 升到 ~1080 ms 並丟 0.44 s 輸出 | 29%／35%、2161 MiB | —（脈衝 0/8） | `20261120-151553-meanvc2` |
| meanvc2（同上）#4 | chirp | 0/8 | — | — | — | — | 133.7 | — | 370／393 | 128／160 | 0.71 | 0／in 0、out 0 | 是（本次無 drop） | 30%／42%、2163 MiB | C（僅 trace） | `20261120-153530-meanvc2` |

### 備註

- baseline 每次引擎 run 前重量；各 run 的 baseline p50（兩跳和）介於 125–134 ms，表中 engine−baseline 用該 run 自己的 baseline。
- seed-vc 兩次可重現：E2E p50 667–670 ms，engine−baseline ≈ 541 ms；trace in→out p50 ≈ 446–450 ms，比聲學少約 90 ms（trace 忽略 0.3 s block 的 rolling context／extra_time）。#2 的 GPU 取樣器只記到閒置值，GPU 以 #1 為準。
- seed-vc 偵測 5–6/8：轉換後的 chirp 與模板相關性 0.36–0.44，部分脈衝落在 missing 門檻下；有偵測到的脈衝彼此差 < 35 ms。
- meanvc2 對 chirp／click 這類非語音訊號幾乎輸出靜音（錄到 peak 0.004），脈衝 bench 量不到（0/8）；trace in→out p50 350–385 ms（4 次）。手動 click 診斷（`diag-meanvc2-manual-click`）7/8 落在 714–762 ms 但 confidence 0.37–0.50，只列 B 級參考。
- 環境變數：pc2-virtual 會自動設定 `AETHERTUNE_WASAPI_AUTOCONVERT=1` 與 `AETHERTUNE_WASAPI_EXCLUSIVE_INPUT=Steam Streaming Microphone`（只影響該程序及子程序，不改系統設定）；`AETHERTUNE_LATENCY_TRACE=1` 需手動設定；Seed-VC 的 `HF_HOME／HF_HUB_CACHE` 由 `stream_runtime` 指到 `tools/external/seed-vc/checkpoints`；`TCLLIBPATH=D:/AetherTune-exp/tcl-shim` 只在跑 Seed-VC setup 腳本或 GUI 時需要，量測不需要。

### 一行指令（PC2）

```powershell
$env:AETHERTUNE_LATENCY_TRACE='1'; $env:HF_HOME='D:\AetherTune-exp\cache\hf'; $env:MODELSCOPE_CACHE='D:\AetherTune-exp\cache\modelscope'; $env:MPLCONFIGDIR='D:\AetherTune-exp\cache\mpl'; Set-Location D:\AetherTune-exp\wt-main-ref; pwsh -NoProfile -File tools\e2e-latency-run.ps1 -Profile pc2-virtual -Root D:\AetherTune-exp\wt-main-ref -Python D:\AetherTune-exp\wt-main-ref\.venv\Scripts\python.exe -Engine seed-vc -WarmupSec 20 -ResultsDir D:\AetherTune-exp\artifacts\e2e-latency
```

### 本輪狀態

| 範圍 | 判定 | 備註 |
|---|---|---|
| baseline（Steam exclusive＋Voice Changer） | PASS | 8/8＋8/8，兩跳 p50 133 ms |
| seed-vc through-engine | PASS（量到；研究目標 100–300 ms 未達） | p50 ≈ 668 ms |
| meanvc2 through-engine | WAITING | trace 350–385 ms；聲學需語音訊號 |
| rvc through-engine | 進行中 |  |
| xvc through-engine | 進行中 | 有時間才做 |
