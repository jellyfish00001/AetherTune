# 直播 TTS 加速矩陣（2026-11-20，PC1 RTX 5060 Ti 16GB）

分支 exp/live-tts-bench。量測方法同 `2026-11-20-live-tts-bench.md`：同一參考音、短/中/長三句、1 次暖機 + 3 次量測，取 p50。
加速套件只裝在實驗 venv（`D:\AetherTune-exp\tts-venvs\*`），不動系統、PATH、全域 Python；需要系統層級的標 BLOCKED。

- **CER**：faster-whisper small（CPU int8）轉寫後與原文比對，簡繁、「十二/12」、同音字都算錯，只能相對比較。
- **聽感欄**：只根據音長、ASR 轉寫、有沒有掉字推論，**不是真人評聽**（我沒有實際聽）。
- **證據等級**：A = 本機獨占 GPU 實測；B = 本機實測但有干擾或只跑部分；C = 文件/原始碼推論；D = 未驗證的推測。
- **磁碟**：17:00 後 PC1 有創作工坊 Bot 的 61 GiB 權重下載在跑（不用 GPU）。每組開始時取樣 `PhysicalDisk(_Total) % Disk Time`，全部在 0–0.5%（下載在別的磁碟或很慢），但**載入時間仍標「有下載佔用磁碟」**。首包/RTF 不含載入時間。
- 參考音：GSV/VoxCPM2 用 rvc-sage（9.26 s，同一人 RVC Sage）；Qwen3/CosyVoice2 用 qwen-zh（官方 clone_1），以便和第一輪不加速基準同參考比較。

## 矩陣

首包 p50 ms、RTF p50、CER 都是「短 / 中 / 長」。VRAM 是 torch 峰值配置量。

| 後端 | 組合 | 首包 p50 ms | RTF | VRAM | CER | 聽感（不是真人評聽） | 狀態 | 證據 | 時段 |
|---|---|---|---|---|---|---|---|---|---|
| GSV-TTS-Lite | 不加速（SDPA efficient，boost on，chunk 25） | 124 / 87 / 128 | 0.125 / 0.097 / 0.103 | 0.58 GiB | 0 / 0.08 / 0.23 | 長句尾「下次開台就不會錯過囉」整段消失 | 基準 | A | 16:22 |
| GSV-TTS-Lite | SDPA math | 111 / 101 / 112 | 0.136 / 0.113 / 0.106 | 0.58 GiB | 0 / 0.15 / 0.29 | 同上，尾句消失 | 可行，無增益 | A | 16:57 |
| GSV-TTS-Lite | **flash-attn 2.8.2**（use_flash_attn） | 78 / 70 / 85 | **0.106 / 0.081 / 0.075** | 0.58 GiB | 0 / 0.12 / 0.27 | 同上，尾句消失 | 可行，首包 −30%、RTF −25% | A | 16:58 |
| GSV-TTS-Lite | stream_chunk 12 / overlap 4 | **69 / 65 / 75** | 0.154 / 0.129 / 0.116 | 0.58 GiB | 0 / 0.08 / 0.27 | 同上，尾句消失 | 可行，首包最低、RTF 略升 | A | 16:58 |
| GSV-TTS-Lite | **zh-fix**（純中文略過語言偵測） | 117 / 94 / 105 | 0.124 / 0.097 / 0.089 | 0.58 GiB | 0 / 0.19 / **0.08** | 長句 15.2 s，尾句完整唸出 | **修好尾句截斷** | A | 17:07 |
| GSV-TTS-Lite | **flash-attn + zh-fix** | 102 / 73 / 83 | 0.108 / 0.089 / 0.078 | 0.59 GiB | 0 / 0.12 / **0.10** | 尾句完整；中句 ASR 有同音字錯 | **建議組合** | A | 17:07 |
| GSV-TTS-Lite | cut_minlen 4 | 89 / 92 / — | 0.133 / 0.107 / — | — | 0 / 0.04 / — | 長句直接拋例外（見下方尾句截斷原因） | 不可行（套件例外） | A | 16:55 |
| GSV-TTS-Lite | use_bert / boost off（第二輪） | 見研究文件第二輪 | | 1.19 / 0.58 GiB | | 沒改善 | 無增益 | A | 16:16–16:28 |
| VoxCPM2 | 不加速 t10 | 240 / 199 / 157 | 1.59 / 1.06 / 1.41 | 5.5 GiB | 0 / 0.04 / 0.06 | 尾句完整 | 基準，RTF>1 | A | 16:23 |
| VoxCPM2 | 降步數 t6 | 118 / 115 / 123 | 0.77 / 0.78 / 0.94 | 5.5 GiB | 0 / 0.04 / 0.04 | 與 t10 轉寫幾乎一樣 | 可行，RTF<1 | A | 16:29 |
| VoxCPM2 | 降步數 t4（qwen-zh） | 151 / 117 / 145 | 0.87 / 0.86 / 0.84 | 5.5 GiB | 0 / 0.04 / 0.06 | 同上 | 可行，不比 t6 快 | A | 16:27 |
| VoxCPM2 | **t6 + torch.compile**（triton-windows 3.3.1，optimize=True） | **83 / 75 / 80** | 0.91 / 0.92 / 0.93 | 5.5 GiB（整卡 8.3 GiB） | 0 / 0.04 / 0.06 | 尾句完整 | 可行：首包 −30%；RTF 沒降；**編譯/載入 240 s（有下載佔用磁碟）** | A | 16:59–17:05 |
| Qwen3-TTS 0.6B | 不加速（bf16 sdpa，整句生成） | 6100–24200 | 1.69–1.82 | — | 0–0.08 | — | 基準，非串流 | A | 第一輪 |
| Qwen3-TTS 0.6B | **自製串流**（攔截 talker 每步 codec，首包 4 幀、之後 12 幀，左側上下文 25 幀解碼） | **672 / 657 / 663** | 1.86 / 1.85 / 1.85 | 2.2 GiB | 0 / 0.12 / 0.06 | 尾句完整；中句「遊戲喔」轉寫成「咬細窩」 | 可行：首包從秒級降到 0.66 s；但 RTF>1 會斷音 | A | 17:08 |
| Qwen3-TTS 0.6B | 自製串流 + flash-attn 2.8.2 | 692 / 693 / 698 | 2.04 / 1.94 / 1.94 | 2.2 GiB | 0 / 0.04 / 0.06 | 尾句完整 | 可行但較慢（小批次單句 decode，FA2 沒優勢） | A | 17:12 |

## 虛擬麥原型（GSV + rvc-sage → VB-CABLE）

`tools/live-tts-bench/live_tts_to_vmic.py --device "CABLE Input" --loopback "CABLE Output" --text-file ...`，同時錄 CABLE Output，量「送出文字 → 虛擬線上真的出現聲音（振幅 > 0.01）」。每句播完才送下一句。17:07 獨占 GPU，GSV 不加速 + zh-fix。

| 句子 | 首塊產生 ms | 寫進裝置 ms | **線上出聲 ms** | 整句生成 ms |
|---|---|---|---|---|
| 大家晚安，謝謝你們來看。 | 103 | 104 | **296** | 562 |
| 今天的直播先陪大家聊聊天，等一下再一起來玩新出的遊戲喔。 | 152 | 152 | **335** | 911 |
| 謝謝小明送的禮物，真的太感動了！ | 110 | 110 | **248** | 492 |
| 歡迎新來的朋友。 | 91 | 91 | **292** | 295 |
| 好，那我們開始吧。 | 119 | 119 | **306** | 309 |

打字送出到虛擬線出聲約 **250–335 ms**；其中約 90 ms 是 MME 輸出緩衝（`out_stream_latency_ms` 91），其餘約 100 ms 是 GSV 開頭的靜音被裁掉前後的音訊與 VB-CABLE 本身延遲。換 WASAPI 獨占或 flash-attn 可再省一點（未量）。紀錄：`D:\AetherTune-exp\artifacts\live-tts-bench\vmic\latency-log.jsonl`。

## GSV 長句尾句截斷原因（已找到並修好）

- gsv-tts-lite 0.4.7 的 `TextProcessor.get_phones_and_bert` 先用 `LangSegment.getTexts` 做語言偵測，即使指定 `text_language="zh"` 也一樣，再把偵測不到的段落丟掉。
- 實測：`LangSegment.getTexts("下次開台就不會錯過囉。")` 回傳 `[]`（「囉」讓整段無法判斷）；`"下次開台就不會錯過了。"` 正常回 zh。`"記得按下追蹤，下次開台就不會錯過囉。"` 只回 `[{'lang':'ja','text':'記得按下追蹤，'}]`，後半段被丟。
- 預設切句 cut_minlen=10 把「記得按下追蹤，」併進最後一段，所以只聽到「記得按下追蹤」就結束；cut_minlen=4 讓「下次開台…囉。」單獨成段，回傳空段落，套件直接拋 `ValueError`。
- 修法（`--zh-fix`，不改套件檔）：純中日韓文字時把 `LangSegment.getTexts` 換成整段回傳 zh；有英文字母時照原本偵測。修後長句音長 12.2 s → 15.2 s，CER 0.23 → 0.08。證據等級 A。
- 補充：中句 CER 在 0.04–0.19 間跳動，是 GSV 取樣（top_k=15）每次不同，不是設定差異。

## 不可行 / 未完成

| 項目 | 原因 | 證據 |
|---|---|---|
| GSV cut_minlen 4 | 觸發上面的空段落例外（長句整句失敗） | A |
| CosyVoice2 vLLM | vLLM 不支援 Windows；WSL 需另建 Linux venv 並下載 vllm 與對應 torch（數 GB），會和創作工坊 Bot 的 61 GiB 下載搶頻寬，本輪先不做 | C |
| CosyVoice2 Windows 原生 / JIT / TRT | 實驗 venv `cosyvoice2-win` 已裝好（torch 2.7.1+cu128、onnxruntime-gpu 1.22 含 TensorRT/CUDA provider）；JIT 匯出在 CPU 進行中；TRT plan 要在 GPU 時段建；待下一段 GPU | — |
| Qwen3-TTS 1.7B 串流 / fp16 | 腳本已就緒，待下一段 GPU | — |

## 安裝紀錄（只在實驗 venv）

- voxcpm2 venv：`triton-windows==3.3.1.post21`
- qwen3-tts venv、gsv-tts-lite venv：`flash-attn==2.8.2+cu128torch2.7`（mjun0812/flash-attention-prebuild-wheels v0.4.10 公開輪檔，cp312 win_amd64）
- 新 venv `cosyvoice2-win`（uv CPython 3.12.11）：torch/torchaudio 2.7.1+cu128、onnxruntime-gpu 1.22.0、transformers 4.51.3、wetext 0.0.4、kaldifst 1.9.0（1.9.1 無 Windows 輪檔）、其餘照 CosyVoice requirements（matplotlib、pyworld 不鎖版）、wget 3.2
- 權重：`D:\AetherTune-exp\tts-models\cosyvoice2` 是 `D:\AetherTune\models\speech-reconstruction\cosyvoice` 的本機複本（不含 .cache），JIT/TRT 產物只寫在複本。

## GPU 時段

| 段 | 開始 | GPU 結束 | 放鎖 | 內容 |
|---|---|---|---|---|
| 1 | 16:55:31（登記 16:55） | 17:16:20 | **17:16:29**（AetherTune Bot 行數 0） | GSV 參數/FA、虛擬麥、VoxCPM2 compile、Qwen3 串流 |

nvidia-smi 前後：`D:\AetherTune-exp\logs\live-tts\accel\nvsmi-*.txt`。
