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

**PC2 一行（真實 E2E 仍 WAITING；需另案提供含 sounddevice 的 `-Python`）**

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

**本輪實機**（`Engine none|all` 接 Voicemeeter／CABLE）判定 **WAITING**（未執行）。合成 `-SelfTest` 可本地 PASS。

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

## 本輪狀態

| 範圍 | 判定 | 備註 |
|---|---|---|
| `e2e_latency_analysis` 合成 regression | PASS | 120／450／600／850 ms、子樣本、anti-alias、missing、WAV、verdict |
| `LatencyTrace` 單元測試 | PASS | stdlib only |
| bench `--dry-run`／`--help`／`--self-test` | PASS | 無 sounddevice 依賴 |
| `e2e-latency-run.ps1 -SelfTest` | PASS | 合成編排與 summary |
| `e2e-latency-run-regression.ps1` | PASS | 解析／SelfTest／RequestOnly／probe `-List` |
| `virtual-line-probe.ps1` winmm 粗 loopback（PC2 2026-11-20） | PASS | 見上表；非 E2E |
| loopback 實機（pulse bench） | WAITING | PC2 缺 sounddevice runtime |
| through-engine 實機 E2E | WAITING | 需引擎運行與 `-Python` |
| 研究目標 100–300 ms p95 | WAITING | 無實測數字 |

## 實測結果（placeholder）

| 模式 | p50 ms | p95 ms | e2e_first_packet_ms | target_verdict |
|---|---:|---:|---:|---|
| loopback_baseline | WAITING | WAITING | WAITING | WAITING |
| through_engine | WAITING | WAITING | WAITING | WAITING |
| engine − baseline | WAITING | WAITING | — | WAITING |