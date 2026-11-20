# LIVE_GATE 與研究分類

**文件邊界：**本頁是 `LIVE`／`LIVE_CANDIDATE`／`OFFLINE`／`WAITING`／`BLOCKED` 的唯一分類規則；實際某輪是否符合，須由該輪 artifact／validator 與對應驗證報告證明。本頁不記錄 backend 當前成績、安裝步驟或人類操作流程。

更新日期：2026-11-20（Asia/Taipei）；2026-11-20 17:34 併入 R1–R10，2026-11-20 19:38 併入直播 TTS 五條與 R10 逐句判定，分類常數 5000 ms 未改。

## 目的

AetherTune 的硬條件是：在 RTX 5060 Ti 16GB、本地運算與完整音訊鏈路下，端到端延遲 `<= 5,000 ms` 才能分類為 `LIVE`。這個門檻不是模型宣稱、單段離線 WAV、RTF、Web UI HTTP 200 或輸出檔存在就能通過。

端到端測量必須從實際 capture input 開始，直到經過 backend、共用 Post-FX、virtual routing 後的可錄製 output 收到第一個有效音訊封包；若只量 backend inference，必須標成 partial，不能升格為 LIVE PASS。

### 兩種延遲門檻與直播 TTS 門檻不可混用

`<= 5,000 ms` 只是 `LIVE`／`LIVE_CANDIDATE` 的**分類可用下限**，不是產品的直播延遲目標；非即時功能仍用此門檻分類。`tools/live-gate-validate.py` 維持 5000 ms，不得因產品目標更嚴而改分類常數。

| 門檻 | 適用 | 數字 | 與分類的關係 |
|---|---|---|---|
| `LIVE` 分類門檻 | 完整鏈路首包，判定 `LIVE`／`LIVE_CANDIDATE`／`OFFLINE` | `e2e_first_packet_ms <= 5,000` | 分類規則；通過也不等於達到直播目標 |
| 直播目標（即時變聲，R3） | 完整鏈路的**聲學量測** p50 | `e2e_p50_ms <= 300`（產品目標 100–300 ms） | 另訂等級，不改 `LIVE`／`OFFLINE` 分類 |
| 直播 TTS 門檻（R10） | 打完字到第一段可播放聲音（首包／TTFA），且生成須快於播放 | 達標：首包 ≤ 3,000 ms 且每一句 RTF < 1；可接受：首包 ≤ 5,000 ms 且每一句 RTF < 1；否則不達標。RTF < 1 以單次最大值或 p95 判定，不得只看中位數。引擎短句超過時，短句交給 GSV | 與即時變聲的 300 ms 直播目標、以及 `LIVE` 分類門檻分開記錄。依據 Johnny 2026-11-20 17:31「可以接受 3–5 秒延遲」、17:34 定案，以及 19:38 定案（Q11 A／Q12 A） |

達到 `LIVE` 不代表達到直播目標；達到直播目標也仍須滿足 600 秒穩定與人工聽評，才能分類為 `LIVE`。

## 分類規則

| 分類 | 必要證據 | 意義 |
|---|---|---|
| `LIVE` | 本次 run 的 physical-microphone input 與 final-output WAV/metrics 均存在且 hash、run/model/route identity 相符；完整鏈路 `e2e_first_packet_ms <= 5000`；至少 600 秒連續、零 dropout／underrun，且有人類聽評記錄 | 技術與人評 gate 都完成的本機即時證據；不代表其他硬體或聲線也合格 |
| `LIVE_CANDIDATE` | 完整 artifact identity 通過且首包 `<= 5000 ms`，但 600 秒穩定性或人工聽評尚未完成 | 延遲符合門檻；仍不可當正式 LIVE 通過 |
| `OFFLINE` | 輸出可驗證，但完整鏈路超過 5 秒，或只有離線輸入輸出證據 | 可作內容重建／影片後製比較，不與 LIVE 排名混用 |
| `WAITING` | 缺少完整鏈路 timing、loopback、輸出驗證或人工聽測必要資料 | 尚不能分類 |
| `BLOCKED` | JSON schema 錯誤、artifact 身分不符、輸出無效或測量明確失敗 | 不可當作候選結果 |

`LIVE` 必須同時有真實麥克風 evidence、完整 artifact identity、延遲、穩定性與人工聽評。缺少 physical-microphone capture 時會是 `WAITING`；synthetic callback／file injection 不可填作 microphone source。`LIVE_CANDIDATE` 只表示必要的延遲與 artifact gate 已通過，尚缺 600 秒連續零 underrun/dropout 或人工聽評。

## 測量欄位

每次 run 至少保存：

- `run_id`、run start time、`backend_id`、`backend_profile`、model id、upstream revision、checkpoint SHA-256 與 license classification。
- source/reference audio hash、capture device、output device、buffer/block 設定。`capture.sample_rate_hz` 與 `capture.channels` 必須等於實際 input WAV header；`output_validation` 保存 output WAV 的 sample rate、channels、frames 與 duration。
- `capture_to_backend_first_packet_ms`、`backend_first_packet_ms`、`postfx_first_packet_ms`、`routing_first_packet_ms`、`e2e_first_packet_ms`。
- `e2e_p50_ms`、`e2e_p95_ms`（若有連續事件）、`continuous_seconds`、`dropouts`、`underruns`。
- output WAV／loopback artifact path、SHA-256、signal validation 結果與人工聽測記錄。

用來下結論或與直播目標比較的延遲，只認**聲學量測**（R1）：以錄音比對「實際輸入何時開始」與「可錄製輸出何時出現第一個有效音訊」。引擎內部 latency trace、GUI 顯示的 `res`／`buf` 或自我回報延遲，一律標 `partial`，不得當作完整鏈路延遲或直播目標的通過證據。

延遲報告必須固定拆成兩欄（R2），並記錄每一跳的緩衝設定（裝置、Host API、buffer／block、sample rate）：

| 欄位 | 含義 |
|---|---|
| 引擎淨延遲 | backend 處理本身，不含虛擬線路與後段路由 |
| 路由延遲 | 引擎輸出之後，經過虛擬線路／Post-FX／終端，到可錄製輸出的延遲 |

現有 `timing_ms` 的 `backend_first_packet_ms`、`postfx_first_packet_ms`、`routing_first_packet_ms`、`e2e_*` 應對應到上述兩欄與總和；若某段不是聲學量測，該段標 `partial`。不得只報一個未經拆欄的總和，就宣稱達到直播目標。

`tools/live-gate-validate.py` 讀取本次實際 input/output WAV 與 metrics JSON，並要求 metrics SHA 綁定完整 `timing_ms`、`continuity`、capture source type、capture sample rate/channels、input/output WAV 的 sample rate/channels/frames/duration，以及整個 `human_review` object。capture 宣告必須與 input WAV header 相符；output metadata 也必須同時符合 manifest、hash-bound metrics 和 output WAV header。只重算 WAV file hash、卻沿用舊 metadata 的修改會 `BLOCKED`；若檔案本身改變，證據、metrics 和實際 header 必須重新一致。若 `human_review.status=PASS`，還需 reviewer/review identity、timezone-aware `reviewed_at_utc`、精確 input/output WAV hashes，以及自然度、音色相似、表演保留、內容正確、噪音／破音與接受度 1–5 ratings；不完整的 PASS review 會 `BLOCKED`。尚未完成的 `status=WAITING` 維持 `LIVE_CANDIDATE`，不會成為 LIVE。它不會替代真實 capture、PortAudio、VST、virtual device 或人工聽測，也不會由 synthetic audio 建立 physical-microphone evidence。

人工聽評必須同時保存兩種樣本（R5）：一是**尚未經過 Discord** 的輸出；二是**經過 Discord（該次實際頻道位元率；預設語音頻道常為 64 kbps Opus）之後**錄下的版本。聽評結論以過 Discord 後的版本為準，過 Discord 前只作對照。若當次無法經由真實 Discord 錄製，須改用可說明的 Discord／Opus 壓縮模擬，並在 `human_review` 標明「模擬 Discord」，不得寫成真實 Discord 聽評。paired rack 欄位另見 [`audio-rack/benchmarks/README.md`](../../audio-rack/benchmarks/README.md)。

[`tools/seed-vc-live-capture.py`](../../tools/seed-vc-live-capture.py) 可在官方 Seed-VC GUI 已待命時，以明確指定的實體麥克風、backend loopback 與終端 loopback 同步錄音，保存 callback 數量、frame continuity、ADC timestamps、WAV hash 與訊號檢查。它產生的 onset delta 是跨 stream threshold estimate，不是精確 first-packet timing；capture 報告維持 `WAITING`，需另行核實完整時間線、填入符合 LIVE_GATE schema 的 evidence 並完成聽評，不能直接分類為 LIVE。

## 研究優先級

### Streaming VC：保留原始表演

1. RVC + FCPE/RMVPE：`priority candidate`（主線候選）。2026-11-20 17:34 依 PC2 聲學量測（`exp/bench-e2e-latency`）從 `historical-baseline` 改回主線候選。仍須按本頁完成 physical mic、600 秒穩定與「過 Discord 後」人工聽評，才能分類為 `LIVE`。這不是把 RVC 訂為唯一主線；其他引擎仍獨立比較。
2. Seed-VC upstream：`established-baseline`。本機 headless evidence 已有，但 upstream 已 archived。
3. MeanVC2：`priority candidate / installed`。Windows／RTX 5060 Ti 隔離 runtime 與雙向 CUDA file-driven streaming WAV `PASS`；mic、paired rack、600 秒連續穩定與人工聽評仍 `WAITING`。上游報告的 40 ms chunk／110 ms first-packet latency 不是本機完整鏈路結果。
4. X-VC：`research-candidate / installed`。固定 code/model 資產與雙向 CUDA streaming WAV `PASS`；完整 physical capture、paired rack、600 秒穩定及人工聽評仍 `WAITING`。GLM tokenizer 的授權範圍需與 repo 及各模型權重分開核對。
5. Seed-VC realtime fork：`candidate`。作為獨立 worker/device/VAD 執行路徑比較；先做 source/revision/license/runtime inventory，不取代模型比較。
6. RT-VC 與後續新方法：`research-candidate`。保留觀察；只有來源、程式碼／權重、license 和可重現 streaming profile 齊備後才進可執行矩陣。

### Speech Reconstruction：重新生成內容

1. CosyVoice2：`offline-baseline`。目前本機 runtime evidence 保留。
2. Fun-CosyVoice3：`candidate`。先做上游來源、模型條款、環境隔離與本機 benchmark，再決定是否安裝。
3. Breeze TTS 2：`offline-candidate`。本機 runtime PASS 不等於 LIVE；目前 RTX 5060 Ti 的 RTF／完整鏈路仍不符合 LIVE 分類。

Speech Reconstruction 重新產生內容、韻律與呼吸，不可宣稱完整保留來源表演；它與 Streaming VC 應分組報告。

直播 TTS（手動打字發聲，目標與變聲同一聲線）另適用下列規則，不與 Streaming VC 的 300 ms 直播目標混用：

- **加速分欄（R8）：**研究與驗證報告必須把「Windows 原生可跑」與「需 Linux／WSL／Docker」分成兩欄；後者屬系統層，不與 Windows 原生數字混成單一結論。
- **參考音（R9）：**同人參考音至少 9 秒、附逐字稿、由目標 RVC 女聲轉出，並記錄音檔與逐字稿 hash。短於 9 秒的參考音不得作為達標或可接受的依據。
- **量測方法：**直播 TTS 延遲以「每句只合成一次（不重複同句、不挑最佳）」的端到端量測為準，從打字到線上出聲。重複同句或先暖機再重測同一句的結果，不得當作達標或可接受的依據。
- **啟動暖機：**常駐 TTS 啟動時，用中文、英文、數字都有的句子暖機；暖機時間算在啟動，不算在第一句延遲。
- **送字前正規化：**送字前先把數字轉成中文字；CosyVoice2 另外要繁轉簡（例如 OpenCC t2s），字幕仍顯示繁體。
- **門檻與實測套用（R10）：**打完字到出聲（首包）≤ 3 秒且 RTF < 1 為達標；≤ 5 秒且 RTF < 1 為可接受；首包超過 5 秒或 RTF ≥ 1 為不達標。RTF < 1 須每一句都符合，以單次最大值或 p95 判定，不得只看中位數。引擎短句超過時，短句交給 GSV。套用 `exp/live-tts-bench` `056955ee013e8385768827a74a252a4562dc3a47` 的 `docs/reference/research/2026-11-20-live-tts-acceleration.md`：

| 後端 | 對 R10 的判定 |
|---|---|
| GSV-TTS-Lite | 達標（不加速＋zh-fix＋英文暖機；首包約 92–156 ms，RTF 0.11–0.16，虛擬麥從打字到出聲 218–335 ms） |
| VoxCPM2 | 10 步不達標；6 步達標，但接近上限（單次最高 1.05）。依單次最大值判定，標「不穩定達標，有單次超過 1」 |
| CosyVoice2 | 簡體輸入＋hop-fix＋TRT＋fp16：中句和長句達標（首包 1.1–1.6 秒，RTF 0.56–0.83）；短句 RTF 1.6–1.67 不達標，短句交給 GSV |
| Qwen3-TTS | 不達標（串流 RTF 約 1.8–2.0，fp16 不可行） |

## 重新分類時機

- 只有保存完整 evidence 後，才可從 `candidate` 變成 `LIVE`、`OFFLINE` 或 `BLOCKED`。
- upstream README 的 benchmark 只作來源資訊；本機測量必須用固定硬體、固定 corpus 與同一 Post-FX policy 重跑。
- 變更 backend、reference、chunk、VST、buffer、driver 或 virtual route 後，舊 gate 不自動沿用。
- UI settings flow 也要保留 requested value、widget update result、PortAudio stream 結果與 output/loopback artifact；widget update error 不可被後續 event value 覆蓋。Seed-VC GUI 最新 preflight 及設定流程狀態見 [`seed-vc-verification-latest.md`](../verification/backends/seed-vc-verification-latest.md)。
