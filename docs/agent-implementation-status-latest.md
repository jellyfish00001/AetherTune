# Agent 實作與測試總表

更新日期：2026-09-21（Asia/Taipei）

這份文件回答「目前哪些可以直接使用、哪些仍需要補條件」。`PASS` 只代表指定 gate 有可重跑證據；不代表音質一定符合個人偏好。`WAITING` 是尚未完成或需要人工／系統條件；`BLOCKED` 是目前有明確錯誤，不能當作可用。

## 八項工作狀態

| # | 工作 | 目前狀態 | 可以直接做什麼 | 尚未完成／限制 | 主要證據 |
|---:|---|---|---|---|---|
| 1 | 修復 VCClient packaged RVC 無效 WAV、實際角色模型 | `BLOCKED`／`DEGRADED` | 可用官方 repair 與 register 工具重現問題；RVC 專案離線路線可用 | VCClient packaged role conversion 仍出現 `SlotInfo.chunk_sec` HTTP 500，或回傳短的全零 chunk；不能用於穩定即時通話 | [`vcclient-packaged-repair-latest.md`](vcclient-packaged-repair-latest.md) |
| 2 | RVC latency、buffer、斷音、10 分鐘矩陣 | `DEGRADED`／`BLOCKED` | 可執行矩陣並取得 p50/p95、dropout、RMS | Wukong 0.25／0.50／0.75／1.00 秒短測都有 dropout；600 秒 gate 依規則阻擋 | [`vcclient-rvc-latency-matrix-latest.md`](vcclient-rvc-latency-matrix-latest.md) |
| 3 | Seed-VC realtime tiny、長音檔 | 60 秒 headless `PASS`；裝置 E2E `WAITING` | 離線男女互轉、60 秒長檔、200 block headless GPU stream 可用 | 尚未以官方 GUI、PortAudio 麥克風和實際輸出裝置完成 10 分鐘以上 realtime | [`seed-vc-verification-latest.md`](seed-vc-verification-latest.md) |
| 4 | 四方法批次音質／音量／取樣率比較 | signal-level `PASS` | 可比較 10 個 WAV 的取樣率、RMS、peak、clipping、silence、DC 與 hash | 這不是 MOS、音色相似度或人工聽測；不同方法本來就有 22.05／24／40／48 kHz 差異 | [`audio-quality-comparison-latest.md`](audio-quality-comparison-latest.md) |
| 5 | RVC 模型來源、授權、訓練版本與 metadata | hash／配對 `PASS`；provenance `WAITING` | 可用 audit 查看四組模型的檔案與 hash | 現有四組仍是 `candidate`；source、license、f0、sample rate、revision、dataset 等仍為 unknown；不得升成 `ready` | [`rvc-model-audit-latest.md`](rvc-model-audit-latest.md) |
| 6 | Breeze `sox`、`flash-attn`、`fast-all` | `fast-all PASS`；project-local SoX `PASS`；flash-attn `WAITING` | Breeze eager、`-FastAll` 與 local SoX runtime 可用 | system SoX 尚未安裝；`flash-attn==2.8.3` 尚未成功 import；人工聽測未完成 | [`breeze-tts2-verification-latest.md`](breeze-tts2-verification-latest.md) |
| 7 | CosyVoice frontend cuDNN 8 GPU | partial `PASS` | 主模型 CUDA；持久化專案 wrapper 可重跑隔離 cuDNN 8 probe，且最新 artifact 證明 speech tokenizer node 實際使用 CUDA | 預設主流程不載入隔離 cuDNN 8；CampPlus 上游明確固定 CPU，因此不是全 frontend GPU | [`cosyvoice-verification-latest.md`](cosyvoice-verification-latest.md) |
| 8 | RVC training data audit、訓練命令、模型註冊 | tooling `PASS`；資料 `BLOCKED` | 可依 guide audit、dry-run register、驗證 hash 與 provenance 欄位 | `dataset/raw` 目前沒有 WAV，audit 正確回傳 exit 2；必須放入有授權乾聲並補完整 metadata 才能訓練／ready | [`model-training-guide.md`](model-training-guide.md)、[`rvc-model-audit-latest.md`](rvc-model-audit-latest.md) |

## 目前可直接使用的路線

在目前證據範圍內，可以直接使用：

1. RVC 專案離線推論：`tools/rvc-fcpe-gpu-infer.py`，使用 `FCPE + cuda:0`，輸入自己的 WAV 與現有 `candidate` 模型。
2. Seed-VC 離線轉換：`tools/seed-vc-run.ps1`，用 male／female reference WAV 做雙向測試。
3. CosyVoice2 離線 TTS／reference clone：`tools/speech-reconstruction-run.ps1 -Backend cosyvoice`。
4. Breeze TTS 2 離線 Voice Design／reference clone：同一 wrapper 使用 `-Backend breeze-tts-2`；需要人工核對的 reference transcript。

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
