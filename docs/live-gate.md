# LIVE_GATE 與研究分類

更新日期：2026-09-26（Asia/Taipei）

## 目的

AetherTune 的硬條件是：在 RTX 5060 Ti 16GB、本地運算與完整音訊鏈路下，端到端延遲 `<= 5,000 ms` 才能分類為 `LIVE`。這個門檻不是模型宣稱、單段離線 WAV、RTF、Web UI HTTP 200 或輸出檔存在就能通過。

端到端測量必須從實際 capture input 開始，直到經過 backend、共用 Post-FX、virtual routing 後的可錄製 output 收到第一個有效音訊封包；若只量 backend inference，必須標成 partial，不能升格為 LIVE PASS。

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

`tools/live-gate-validate.py` 讀取本次實際 input/output WAV 與 metrics JSON，並要求 metrics SHA 綁定完整 `timing_ms`、`continuity`、capture source type、capture sample rate/channels、input/output WAV 的 sample rate/channels/frames/duration，以及整個 `human_review` object。capture 宣告必須與 input WAV header 相符；output metadata 也必須同時符合 manifest、hash-bound metrics 和 output WAV header。只重算 WAV file hash、卻沿用舊 metadata 的修改會 `BLOCKED`；若檔案本身改變，證據、metrics 和實際 header 必須重新一致。若 `human_review.status=PASS`，還需 reviewer/review identity、timezone-aware `reviewed_at_utc`、精確 input/output WAV hashes，以及自然度、音色相似、表演保留、內容正確、噪音／破音與接受度 1–5 ratings；不完整的 PASS review 會 `BLOCKED`。尚未完成的 `status=WAITING` 維持 `LIVE_CANDIDATE`，不會成為 LIVE。它不會替代真實 capture、PortAudio、VST、virtual device 或人工聽測，也不會由 synthetic audio 建立 physical-microphone evidence。paired rack 欄位另見 [`audio-rack/benchmarks/README.md`](../audio-rack/benchmarks/README.md)。

## 研究優先級

### Streaming VC：保留原始表演

1. RVC + FCPE/RMVPE：`historical-baseline`。保留作既有系統與延遲／失真對照；不再預設為主線。
2. Seed-VC upstream：`established-baseline`。本機 headless evidence 已有，但 upstream 已 archived。
3. MeanVC2：`priority candidate`。下一個優先 intake；[上游 repo](https://github.com/ASLP-lab/MeanVC2) 報告 40 ms chunk 與 110 ms first-packet latency，本專案尚未安裝、下載 checkpoint 或驗證 Windows／RTX 5060 Ti／完整鏈路。
4. X-VC：`research-candidate`。官方[程式碼庫](https://github.com/Jerrister/X-VC) 已公開 streaming inference；在 MeanVC2 baseline 矩陣完成後再 intake，先查固定 revision、weights、license 與環境。
5. Seed-VC realtime fork：`candidate`。作為獨立 worker/device/VAD 執行路徑比較；先做 source/revision/license/runtime inventory，不取代模型比較。
6. RT-VC 與後續新方法：`research-candidate`。保留觀察；只有來源、程式碼／權重、license 和可重現 streaming profile 齊備後才進可執行矩陣。

### Speech Reconstruction：重新生成內容

1. CosyVoice2：`offline-baseline`。目前本機 runtime evidence 保留。
2. Fun-CosyVoice3：`candidate`。先做上游來源、模型條款、環境隔離與本機 benchmark，再決定是否安裝。
3. Breeze TTS 2：`offline-candidate`。本機 runtime PASS 不等於 LIVE；目前 RTX 5060 Ti 的 RTF／完整鏈路仍不符合 LIVE 分類。

Speech Reconstruction 重新產生內容、韻律與呼吸，不可宣稱完整保留來源表演；它與 Streaming VC 應分組報告。

## 重新分類時機

- 只有保存完整 evidence 後，才可從 `candidate` 變成 `LIVE`、`OFFLINE` 或 `BLOCKED`。
- upstream README 的 benchmark 只作來源資訊；本機測量必須用固定硬體、固定 corpus 與同一 Post-FX policy 重跑。
- 變更 backend、reference、chunk、VST、buffer、driver 或 virtual route 後，舊 gate 不自動沿用。
- UI settings flow 也要保留 requested value、widget update result、PortAudio stream 結果與 output/loopback artifact；widget update error 不可被後續 event value 覆蓋。Seed-VC GUI 最新 preflight 及設定流程狀態見 [`seed-vc-verification-latest.md`](seed-vc-verification-latest.md)。
