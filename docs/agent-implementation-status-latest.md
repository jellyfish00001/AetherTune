# Agent 實作與測試總表

更新日期：2026-09-21（Asia/Taipei）

這份文件回答「目前哪些可以直接使用、哪些仍需要補條件」。`PASS` 只代表指定 gate 有可重跑證據；不代表音質一定符合個人偏好。`WAITING` 是尚未完成或需要人工／系統條件；`BLOCKED` 是目前有明確錯誤，不能當作可用。

## 八項工作狀態

| # | 工作 | 目前狀態 | 可以直接做什麼 | 尚未完成／限制 | 主要證據 |
|---:|---|---|---|---|---|
| 1 | 修復 VCClient packaged RVC 無效 WAV、實際角色模型 | `BLOCKED`／`DEGRADED` | 可用官方 repair 與 register 工具重現問題；RVC 專案離線路線可用 | 最新 Sage slot 7 v2 post-gate probe 已核對 requested／active／initial=`7/7/7`，30 chunks 僅 2 個 valid、28 個 invalid（全零 28）；仍不能用於穩定即時通話 | [`vcclient-packaged-repair-latest.md`](vcclient-packaged-repair-latest.md) |
| 2 | RVC latency、buffer、斷音、10 分鐘矩陣 | `DEGRADED`／`BLOCKED` | 可執行 bounded 矩陣並取得 p50/p95、invalid/dropout、RMS，且報告 slot 核對證據 | Sage slot 7 v2 的 0.25／0.50／0.75／1.00 秒短測 invalid/dropout 為 58/60、28/30、19/20、15/15；1.00 秒為 `0/15` valid，stability=`stability_seconds=0` 為 `BLOCKED`，尚非 600 秒證據 | [`vcclient-rvc-latency-matrix-latest.md`](vcclient-rvc-latency-matrix-latest.md) |
| 3 | Seed-VC realtime tiny、長音檔 | 60 秒 headless `PASS`；裝置 E2E `WAITING` | 離線男女互轉、60 秒長檔、200 block headless GPU stream 可用 | 尚未以官方 GUI、PortAudio 麥克風和實際輸出裝置完成 10 分鐘以上 realtime | [`seed-vc-verification-latest.md`](seed-vc-verification-latest.md) |
| 4 | 四方法批次音質／音量／取樣率比較 | signal-level `PASS` | 可比較 11 個 WAV 的取樣率、RMS、peak、clipping、silence、DC 與 hash；BLOCKED row 不會被彙總成 PASS | 這不是 MOS、音色相似度或人工聽測；不同方法本來就有 22.05／24／40／48 kHz 差異 | [`audio-quality-comparison-latest.md`](audio-quality-comparison-latest.md) |
| 5 | RVC 模型來源、授權、訓練版本與 metadata | hash／配對 `PASS`；provenance `WAITING` | 可用 audit 查看四組模型的檔案與 hash；checkpoint sample rate/version 已核對為 40/48 kHz、v2 | 現有四組仍是 `candidate`；source、license、f0、revision、dataset、trained-at 與 verification evidence 仍為 unknown；不得升成 `ready` | [`rvc-model-audit-latest.md`](rvc-model-audit-latest.md) |
| 6 | Breeze `sox`、`flash-attn`、`fast-all` | `fast-all PASS`；project-local SoX `PASS`；flash-attn `WAITING` | Breeze eager、`-FastAll` 與 local SoX runtime 可用 | system SoX 尚未安裝；`flash-attn==2.8.3` 尚未成功 import；人工聽測未完成 | [`breeze-tts2-verification-latest.md`](breeze-tts2-verification-latest.md) |
| 7 | CosyVoice frontend cuDNN 8 GPU | partial `PASS` | 主模型 CUDA；持久化專案 wrapper 可重跑隔離 cuDNN 8 probe，且最新 artifact 證明 speech tokenizer node 實際使用 CUDA | 預設主流程不載入隔離 cuDNN 8；CampPlus 上游明確固定 CPU，因此不是全 frontend GPU | [`cosyvoice-verification-latest.md`](cosyvoice-verification-latest.md) |
| 8 | RVC training data audit、訓練命令、模型註冊 | tooling `PASS`；資料 `BLOCKED` | 可依 guide audit、dry-run register、驗證 hash、provenance 與 verification evidence | `dataset/raw` 目前沒有 WAV，audit 正確回傳 exit 2；ready gate 負向回歸會拒絕 unknown metadata、缺失或 FAIL artifact；必須放入有授權乾聲並補完整 metadata 才能訓練／ready | [`model-training-guide.md`](model-training-guide.md)、[`rvc-model-audit-latest.md`](rvc-model-audit-latest.md) |

## 本輪工具契約修正與可重跑檢查

- `tools/rvc-ready-gate-regression.ps1`：PASS；register 與 audit 都拒絕 ready 的 unknown metadata、缺失、malformed、FAIL／DEGRADED artifact、錯誤 model／index path／hash 與 input／output hash。
- `tools/vcclient-rvc-chunk-validation-regression.ps1`：PASS；逐 chunk 拒絕 empty、short、unaligned、全零、NaN 與 Infinity，只接受 finite non-zero float32 response。
- `tools/rvc-model-audit.py`：現有四列仍為 `WAITING`／`candidate`；ready 需要可解析且 `status=PASS` 的 verification JSON，並核對 model／index／input／output 路徑與 SHA-256。
- `tools/vcclient-rvc-probe.ps1` 與矩陣：最新 post-gate v2 artifact `artifacts/vcclient-rvc-test-postgate-v2/c0d00306-ce10-4746-9b81-9f0cff5d3ed5/vcclient-rvc-probe.json` 已保存 requested／active／initial slot 與 model evidence；Sage slot `7` runtime probe 為 `DEGRADED`（2/30 valid、28/30 invalid，且 28 個全零）。bounded 矩陣 `artifacts/vcclient-rvc-latency-matrix-postgate-v2/524e1a71-c00c-49c0-9127-82ae23aca119/vcclient-rvc-latency-matrix.json` 的短測 invalid/dropout 為 58/60、28/30、19/20、15/15，1.00 秒與 stability row 維持 `BLOCKED`。v1 Sage 與舊 Wukong／600 秒矩陣只作 historical/full-gate evidence。
- `tools/speech-reconstruction-run.ps1`：`TextFile` 與 `ReferenceTextFile` 分流；不同 source/reference 音檔未提供 reference transcript 時，另做 reference STT draft；caller text 預設是 `caller_provided_unverified`，只有明確 `-ReferenceTextVerified` 才標 verified，workflow 保存 `reference_text_verified` 與 manual review gate。
- `tools/audio-quality-batch-regression.py`：PASS；同一 backend 的 `PASS + BLOCKED` 彙總為 `BLOCKED`，`PASS + DEGRADED` 彙總為 `DEGRADED`。
- `tools/audio-output-validation-regression.py`：PASS；共用 helper 與檔案 gate 覆蓋空檔、零 frame、非 finite、錯誤取樣率、PCM16 與有效訊號；CosyVoice／Breeze runner 的原始 chunk gate 另在實際 runner 執行時生效。
- `tools/audio-runner-entry-regression.py`：PASS；實際啟動 Breeze／CosyVoice runner subprocess，覆蓋 `--help` 保留 stale PASS、四個明確 output 別名 (`--output`／`--out`／`--outp`／`--o`) 的分開與 `=` 形式（含 `--outp=path`、`--o path`）、重複 output 只清理最後目標、`--` 終止符、四個分開空值與既有 `--out=` 空值在 parser exit 2 時保留 stale output/manifest、非 0 parse failure 的 FAIL manifest 入口，以及 top-level dependency-safe import AST 契約。
- `tools/speech-reconstruction-failure-regression.ps1`：PASS；缺少輸入音檔時仍先移除精確的舊 workflow，且不啟動 WSL／模型。
- `tools/speech-reconstruction-run.ps1 -VoiceDesign`：Breeze wrapper smoke PASS；實際產生 24 kHz、10.48 秒非零 WAV，workflow 記錄 `voice_design=true` 與 `not_applicable_voice_design`。預設未加 switch 的 clone smoke 行為保留。
- 最新 runner smoke：Breeze `artifacts/speech-reconstruction/breeze-output-gate-v2.json` 為 24 kHz／11.52 秒、`run_id` 與 `output_validation` 通過；CosyVoice `artifacts/speech-reconstruction/cosyvoice-output-gate-v2.json` 為 24 kHz／10.28 秒、`run_id` 與 `output_validation` 通過。兩者仍不是人工音質或 realtime E2E 證據。

可重跑：

```powershell
Set-Location D:\AetherTune
& .\tools\rvc-ready-gate-regression.ps1
& .\tools\vcclient-rvc-chunk-validation-regression.ps1
& .\.venv\Scripts\python.exe .\tools\rvc-model-audit.py --fail-on-waiting
& .\.venv\Scripts\python.exe .\tools\audio-quality-batch-regression.py
& .\.venv\Scripts\python.exe .\tools\audio-output-validation-regression.py
```

## 目前可直接使用的路線

在目前證據範圍內，可以直接使用：

1. RVC 專案離線推論：`tools/rvc-fcpe-gpu-infer.py`，使用 `FCPE + cuda:0`，輸入自己的 WAV 與現有 `candidate` 模型。
2. Seed-VC 離線轉換：`tools/seed-vc-run.ps1`，用 male／female reference WAV 做雙向測試。
3. CosyVoice2 離線 TTS／reference clone：`tools/speech-reconstruction-run.ps1 -Backend cosyvoice`。
4. Breeze TTS 2 離線 Voice Design／reference clone：同一 wrapper 使用 `-Backend breeze-tts-2`；Voice Design 加 `-VoiceDesign -Instruction`，reference clone 需要人工核對 transcript。

其中第 1 項是「可測試」而不是「模型已獲授權的 ready preset」；第 2～4 項是離線輸出路線，不等於麥克風即時變聲。

## Agent 還能繼續做的工作

- VCClient：可繼續追查上游 packaged binary／版本相容性，或改用另一個已支援 RTX 5060 Ti 的 runtime；在沒有新 binary 或 source 修復前，不能由文件把 `BLOCKED` 改成 `PASS`。
- RVC realtime：可在 VCClient 修復後重跑矩陣；目前短測 dropout 已足以阻擋 10 分鐘測試，不應反覆把同一份失敗證據重命名成通過。
- Seed-VC：可補 PortAudio／官方 GUI、實體 loopback 與長時間穩定性；目前 headless 測試不涵蓋麥克風權限與裝置 buffer。
- 四方法比較：可加入人工聽測表或固定評分規則，但需要使用者實際聽音與確認評分，不應由 Agent 代填主觀音質結論。
- RVC provenance：可在使用者提供有授權的 raw WAV、來源、license、訓練設定後重新 audit、register 與 ready gate。
- Breeze／CosyVoice：system SoX、flash-attn、人工音質與預設 runtime 仍有可選優化；CosyVoice 隔離 cuDNN 8 probe 已有可重跑 GPU 證據，但不會覆蓋預設 PyTorch cuDNN 9 runtime。

## 建議下一步

若目標是「現在先用」，先讀根目錄 [`README.md`](../README.md) 的 Seed-VC 或 STT → TTS 命令；若目標是「完成 RVC 即時通話」，先處理 VCClient packaged conversion 的 HTTP 500／全零輸出，再重跑第 2 項矩陣。若目標是訓練自己的 RVC，先提供有授權的乾聲 WAV 與 provenance，不要直接把目前 `candidate` 模型升成 `ready`。
