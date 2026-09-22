# LIVE_GATE 與研究分類

更新日期：2026-09-22（Asia/Taipei）

## 目的

AetherTune 的硬條件是：在 RTX 5060 Ti 16GB、本地運算與完整音訊鏈路下，端到端延遲 `<= 5,000 ms` 才能分類為 `LIVE`。這個門檻不是模型宣稱、單段離線 WAV、RTF、Web UI HTTP 200 或輸出檔存在就能通過。

端到端測量必須從實際 capture input 開始，直到經過 backend、共用 Post-FX、virtual routing 後的可錄製 output 收到第一個有效音訊封包；若只量 backend inference，必須標成 partial，不能升格為 LIVE PASS。

## 分類規則

| 分類 | 必要證據 | 意義 |
|---|---|---|
| `LIVE` | 完整鏈路有 `e2e_first_packet_ms <= 5000`，並保存 capture/backend/Post-FX/routing timing | 可進入即時候選比較，但不代表長時間穩定 |
| `OFFLINE` | 輸出可驗證，但完整鏈路超過 5 秒，或只有離線輸入輸出證據 | 可作內容重建／影片後製比較，不與 LIVE 排名混用 |
| `WAITING` | 缺少完整鏈路 timing、loopback、輸出驗證或人工聽測必要資料 | 尚不能分類 |
| `BLOCKED` | JSON schema 錯誤、artifact 身分不符、輸出無效或測量明確失敗 | 不可當作候選結果 |

`LIVE` 是延遲分類，不是品質通過。正式的 `live_candidate` 還需要至少 600 秒連續執行、零 underrun／dropout，以及人工聽測；10 分鐘只是目前研究 gate，不是產品保證。

## 測量欄位

每次 run 至少保存：

- `backend_id`、`backend_profile`、model id、upstream revision、license classification。
- source/reference audio hash、capture device、output device、sample rate、channel、buffer/block 設定。
- `capture_to_backend_first_packet_ms`、`backend_first_packet_ms`、`postfx_first_packet_ms`、`routing_first_packet_ms`、`e2e_first_packet_ms`。
- `e2e_p50_ms`、`e2e_p95_ms`（若有連續事件）、`continuous_seconds`、`dropouts`、`underruns`。
- output WAV／loopback artifact path、SHA-256、signal validation 結果與人工聽測記錄。

`tools/live-gate-validate.py` 只驗證 evidence 是否足以分類；它不會替代真實 capture、PortAudio、VST、virtual device 或人工聽測。

## 研究優先級

### Streaming VC：保留原始表演

1. RVC + FCPE/RMVPE：`historical-baseline`。保留作既有系統與延遲／失真對照；不再預設為主線。
2. Seed-VC upstream：`established-baseline`。本機 headless evidence 已有，但 upstream 已 archived。
3. Seed-VC realtime fork：`candidate`。先做 source/revision/license/runtime inventory，再與 upstream profile 以同一 capture corpus 比較。
4. MeanVC2：`candidate`。上游研究與程式碼已存在，但本專案尚未安裝、下載 checkpoint 或驗證 Windows／RTX 5060 Ti／完整鏈路。
5. X-VC、RT-VC：`research-candidate`。只保留追蹤位置，未列入目前可執行矩陣。

### Speech Reconstruction：重新生成內容

1. CosyVoice2：`offline-baseline`。目前本機 runtime evidence 保留。
2. Fun-CosyVoice3：`candidate`。先做上游來源、模型條款、環境隔離與本機 benchmark，再決定是否安裝。
3. Breeze TTS 2：`offline-candidate`。本機 runtime PASS 不等於 LIVE；目前 RTX 5060 Ti 的 RTF／完整鏈路仍不符合 LIVE 分類。

Speech Reconstruction 重新產生內容、韻律與呼吸，不可宣稱完整保留來源表演；它與 Streaming VC 應分組報告。

## 重新分類時機

- 只有保存完整 evidence 後，才可從 `candidate` 變成 `LIVE`、`OFFLINE` 或 `BLOCKED`。
- upstream README 的 benchmark 只作來源資訊；本機測量必須用固定硬體、固定 corpus 與同一 Post-FX policy 重跑。
- 變更 backend、reference、chunk、VST、buffer、driver 或 virtual route 後，舊 gate 不自動沿用。
