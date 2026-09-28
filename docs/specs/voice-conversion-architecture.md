# AetherTune 多後端 Adapter 契約

**文件邊界：**本頁只定義 **Streaming VC／Speech Reconstruction 的 adapter 分工與跨 backend handoff**。整體研究目標及五層系統圖在[architecture.md](architecture.md)；Desktop 使用者功能在[app-requirements.md](app-requirements.md)；Rack、benchmark、LIVE 分類及 Windows 實際接線各由其 README、[live-gate.md](live-gate.md)、[operation-guide.md](../guides/operation-guide.md)負責。本頁不保存當次測試結果。

## 兩組輸入／輸出語意

| 組別 | 來源與目標 | 輸出能表達什麼 | 不可宣稱 |
|---|---|---|---|
| Streaming VC | source/mic 與目標 reference，或 RVC 已訓練角色模型 | 轉換聲線並盡量保留 source 的內容、節奏和表演 | 有 WAV 就等於 mic realtime／LIVE |
| Speech Reconstruction | 明確文字／STT draft 與 reference／voice-design prompt | 重新生成內容和聲學表演 | 原始呼吸、笑聲、停頓和情緒完整保留 |

RVC 的角色模型採 `.pth/.index` 配對與 f0；Seed-VC、MeanVC2、X-VC 使用各自 zero-shot reference/checkpoint；CosyVoice2／Breeze 使用文字與 TTS prompt/reference。模型格式與 runtime 不互換。CosyVoice3、Seed-VC realtime fork 等未接入候選不得因出現在研究表中就加入可執行清單；現況由對應 backend 文件、manifest 與驗證決定。

## 每個 Adapter 的最小交接

| 契約面 | 必須保存或驗證 |
|---|---|
| 身分 | `backend_id`、profile、固定 upstream revision、license classification、隔離 runtime |
| 來源 | source path/hash、sample rate/channels、provenance；真實 mic 要有 physical capture identity |
| 目標 | reference WAV／voice-design prompt、hash、使用範圍；TTS prompt transcript 的 exact／draft／manual-verified 狀態 |
| 執行 | 實際 device/provider、chunk/block/buffer、model fingerprint、參數與 run id |
| 輸出 | WAV／stream、finite/non-zero、hash、完整 runner manifest；失敗不可沿用舊 PASS |
| 時間 | generation、first audio／first playback、backend timing；只有有完整鏈路 artifact 才報 end-to-end timing |
| 下游 | output route 身分、Rack bypass/full-chain、loopback 與 benchmark 對應 artifact |

結構化欄位以 `contracts/` schema／manifest、register 與對應 verifier 為準；本表只規定必須跨界傳遞的語意，不創造第二套 JSON schema。STT 產生的是 **draft**，不能自行升為人工核對；Manual TTS 不經 STT，completed playback 後才可加入 `manual_text` Transcript。

## Backend 介面責任

| Adapter | 自己負責 | 下游仍需另驗 |
|---|---|---|
| RVC + FCPE／RMVPE | `.pth/.index` 配對、f0、已固定角色模型輸出；訓練流程由[訓練手冊](../guides/model-training-guide.md)擁有 | VCClient slot、即時 chunk、Mic、Rack |
| Seed-VC upstream | source/reference 的離線或官方 GUI profile；資產由[seed-vc-assets.md](../reference/seed-vc-assets.md)登記 | GUI 有效 callback、physical mic、Rack |
| MeanVC2／X-VC | 各自 source/reference、固定模型、file-driven streaming runner 輸出 | mic/virtual route／600 秒 |
| CosyVoice2／Breeze | 文字、prompt/reference、完整 TTS WAV 與 generation evidence | 實際 playback、外部 Post-FX、STT provenance |

每個 backend 的實際參數、安裝與限制只由 `backends/<name>/README.md` 擁有；桌面編排的 IPC／程序所有權由[app-architecture.md](app-architecture.md)與[Agent 維護手冊](../../.agent/reference/agent-maintenance-guide.md)擁有。Adapter 的 `PASS` 不會自動傳遞成下游的 `PASS`。

## 共用設施的 handoff

Adapter 輸出與其 metadata 交給共用 `audio-rack/`；需要播放或直播時，先保留 bypass，再保留 full-chain 配對，將明確 route 的最終聲音交給 `benchmarks/`。Rack 的 preset、plugin、routing、paired evidence 格式見[audio-rack/README.md](../../audio-rack/README.md)；三層比較的 corpus／Live Technical／Acoustic Objective／Human Listening 見[benchmarks/README.md](../../benchmarks/README.md)。音訊端點的 Windows 操作只在[operation-guide.md](../guides/operation-guide.md)，`LIVE` 分類只在[live-gate.md](live-gate.md)。
