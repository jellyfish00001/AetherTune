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
| GSV-TTS-Lite | **flash-attn + zh-fix** | 102 / 73 / 83 | 0.108 / 0.089 / 0.078 | 0.59 GiB | 0 / 0.12 / **0.10** | 尾句完整；中句 ASR 有同音字錯 | bench 最佳，但**直播虛擬麥實測 FA 反而慢**（見虛擬麥節），直播用不加速 + zh-fix | A | 17:07 |
| GSV-TTS-Lite | cut_minlen 4 | 89 / 92 / — | 0.133 / 0.107 / — | — | 0 / 0.04 / — | 長句直接拋例外（見下方尾句截斷原因） | 不可行（套件例外） | A | 16:55 |
| GSV-TTS-Lite | use_bert / boost off（第二輪） | 見研究文件第二輪 | | 1.19 / 0.58 GiB | | 沒改善 | 無增益 | A | 16:16–16:28 |
| VoxCPM2 | 不加速 t10 | 240 / 199 / 157 | 1.59 / 1.06 / 1.41 | 5.5 GiB | 0 / 0.04 / 0.06 | 尾句完整 | 基準，RTF>1 | A | 16:23 |
| VoxCPM2 | 降步數 t6 | 118 / 115 / 123 | 0.77 / 0.78 / 0.94 | 5.5 GiB | 0 / 0.04 / 0.04 | 與 t10 轉寫幾乎一樣 | 可行，RTF<1 | A | 16:29 |
| VoxCPM2 | 降步數 t4（qwen-zh） | 151 / 117 / 145 | 0.87 / 0.86 / 0.84 | 5.5 GiB | 0 / 0.04 / 0.06 | 同上 | 可行，不比 t6 快 | A | 16:27 |
| VoxCPM2 | **t6 + torch.compile**（triton-windows 3.3.1，optimize=True） | **83 / 75 / 80** | 0.91 / 0.92 / 0.93 | 5.5 GiB（整卡 8.3 GiB） | 0 / 0.04 / 0.06 | 尾句完整 | 可行：首包 −30%；RTF 沒降；**編譯/載入 240 s（有下載佔用磁碟）** | A | 16:59–17:05 |
| Qwen3-TTS 0.6B | 不加速（bf16 sdpa，整句生成） | 6100–24200 | 1.69–1.82 | — | 0–0.08 | — | 基準，非串流 | A | 第一輪 |
| Qwen3-TTS 0.6B | **自製串流**（攔截 talker 每步 codec，首包 4 幀、之後 12 幀，左側上下文 25 幀解碼） | **672 / 657 / 663** | 1.86 / 1.85 / 1.85 | 2.2 GiB | 0 / 0.12 / 0.06 | 尾句完整；中句「遊戲喔」轉寫成「咬細窩」 | 可行：首包從秒級降到 0.66 s；但 RTF>1 會斷音 | A | 17:08 |
| Qwen3-TTS 0.6B | 自製串流 + flash-attn 2.8.2 | 692 / 693 / 698 | 2.04 / 1.94 / 1.94 | 2.2 GiB | 0 / 0.04 / 0.06 | 尾句完整 | 可行但較慢（小批次單句 decode，FA2 沒優勢） | A | 17:12 |
| Qwen3-TTS 1.7B | 自製串流（同上） | 682 / 692 / 703 | 1.86 / 2.06 / 1.82 | 4.2 GiB | 0 / 0.08 / 0.02 | 尾句完整，轉寫最準 | 可行；首包同 0.6B，RTF 沒更差但仍 >1 | A | 17:34 |
| Qwen3-TTS 0.6B | 自製串流 + **fp16**（`--dtype fp16`，sdpa） | — | — | — | — | 沒有產出 | **不可行**：第一句生成中 `code_predictor.generate` 取樣觸發 CUDA device-side assert（`TensorCompare.cu:112 input[0] != 0`），推測 fp16 數值溢位成 inf/NaN；bf16 同腳本正常 | B | 18:34–18:36 |
| CosyVoice2 | 不加速（WSL /mnt/d，fp32 + 預建聲線 ID，第一輪） | 4400–7100 | ≈0.93 | 2.6 GiB | 0.35–0.5 | 有亂詞 | 基準 | A | 第一輪 |
| CosyVoice2 | **Windows 原生**實驗 venv（fp32 + 聲線 ID） | 2993 / 4562 / 4729 | **0.66 / 0.62 / 0.69** | 2.6 GiB | 0.50 / 0.19 / 0.42 | 短句轉寫「大家晚安嚇傻你懵快」，有亂詞（與 WSL 同樣問題，非加速造成） | 可行：RTF −30%，首包略降但仍 3–5 s；**載入 158 s（有下載佔用磁碟，首次讀複本）** | A | 17:27–17:31 |
| CosyVoice2 | Windows 原生 + JIT（flow.encoder TorchScript，CPU 匯出） | 4147 / 5011 / 5156 | 0.75 / 0.68 / 0.72 | 2.6 GiB | 0.50 / 0.19 / 0.40 | 同上 | 可行但沒變快（反而略慢） | A | 17:31–17:33 |
| CosyVoice2 | Windows 原生 + JIT + TensorRT + fp16（第 2 段） | — | — | — | — | — | 失敗：venv 當時還沒裝 tensorrt（不跟下載搶頻寬），17:49 裝好後第 3 段重量 | B | 17:33 |
| CosyVoice2 | **Windows 原生 + hop-fix**（每次合成前把 token_hop_len 設回 25） | 1993 / 2038 / 2013 | 0.87 / 0.84 / 0.83 | 2.6 GiB | 0.40 / 0.19 / 0.40 | 每 1–2 s 一塊（真串流），繁體字仍唸錯 | 可行：首包 3–5 s → 2.0 s | A | 17:57 |
| CosyVoice2 | Windows 原生 + hop-fix @rvc-sage | 2251 / 2151 / 2076 | 1.14 / 0.87 / 1.01 | 2.7 GiB | 0.70 / 0.23 / 0.40 | 同上；9 秒參考音沒有改善錯字 | 可行 | A | 17:59 |
| CosyVoice2 | **Windows 原生 + hop-fix + JIT + TensorRT + fp16**（tensorrt-cu12 10.13.3.9，plan 首次建立在本機複本） | **1611 / 1611 / 1618** | **0.79 / 0.74 / 0.74** | 3.2 GiB | 0.50 / 0.27 / 0.52（不分簡繁 0.40 / 0.27 / 0.52） | 同上 | 可行：首包再 −20%；**載入 191 s（含建 TRT plan，開始時磁碟 12.7%／56 MB/s，有其他 I/O）** | A | 18:01–18:04 |
| CosyVoice2 | 同上 @rvc-sage | 1545 / 1431 / 1537 | 0.79 / 0.67 / 0.76 | 3.2 GiB | 0.40 / 0.31 / 0.39（不分簡繁相同：錯的是同音字，不是簡繁） | 同上 | 可行 | A | 18:06 |
| CosyVoice2 | **hop-fix + JIT + TensorRT + fp16 + 簡體輸入**（`--zhs`，同三句改簡體字） @qwen-zh | 1509 / 1505 / 1607 | 0.83 / 0.74 / 0.73 | 3.1 GiB | 原始 0.40 / 0.15 / 0.46；**不分簡繁 0 / 0.04 / 0.14** | 謝謝、禮物、遊戲、記得、錯過都唸對；長句「追蹤」轉寫成「之鐘」、句尾多一字 | **錯字主因確認：繁體輸入** | A | 18:31–18:33 |
| CosyVoice2 | 同上 @rvc-sage | 1546 / 1541 / 1537 | 0.80 / 0.72 / 0.73 | 3.2 GiB | 原始 0.40 / 0.04 / 0.10；**不分簡繁 0 / 0.04 / 0.10** | 長句只剩「小明送」→「小民宋」同音錯；短句 1 塊就結束（streamed_all=false） | 可行 | A | 18:33–18:34 |

## 虛擬麥原型（GSV + rvc-sage → VB-CABLE）

`tools/live-tts-bench/live_tts_to_vmic.py --device "CABLE Input" --loopback "CABLE Output" --text-file ...`，同時錄 CABLE Output，量「送出文字 → 虛擬線上真的出現聲音（振幅 > 0.01）」。每句播完才送下一句。17:07 獨占 GPU，GSV 不加速 + zh-fix。

| 句子 | 首塊產生 ms | 寫進裝置 ms | **線上出聲 ms** | 整句生成 ms |
|---|---|---|---|---|
| 大家晚安，謝謝你們來看。 | 103 | 104 | **296** | 562 |
| 今天的直播先陪大家聊聊天，等一下再一起來玩新出的遊戲喔。 | 152 | 152 | **335** | 911 |
| 謝謝小明送的禮物，真的太感動了！ | 110 | 110 | **248** | 492 |
| 歡迎新來的朋友。 | 91 | 91 | **292** | 295 |
| 好，那我們開始吧。 | 119 | 119 | **306** | 309 |

打字送出到虛擬線出聲約 **250–335 ms**；其中約 90 ms 是 MME 輸出緩衝（`out_stream_latency_ms` 91），其餘約 100 ms 是 GSV 開頭的靜音被裁掉前後的音訊與 VB-CABLE 本身延遲。換 WASAPI 獨占可再省一點（未量）。紀錄：`D:\AetherTune-exp\artifacts\live-tts-bench\vmic\latency-log.jsonl`。

### flash-attn + zh-fix 接虛擬麥（第 4、5 段）

同腳本加 `--flash-attn`。第 4 段（18:36）量到 FA 反而慢，第 5 段（18:57–19:00）把「不加速 / FA」交錯各跑兩輪（同一行程內 5 句、每句都是第一次合成、沒有暖機重複），確認可重現。GPU 時脈 2670 MHz P0、使用率 1%，沒有其他 GPU 工作。

| 組合 | 首塊產生 ms（5 句） | **線上出聲 ms** | 整句生成 ms | 紀錄檔 |
|---|---|---|---|---|
| 不加速 + zh-fix（17:07） | 91–152 | **248–335** | 295–911 | latency-log.jsonl |
| 不加速 + zh-fix r2（18:57） | 97–171 | **263–335** | 295–879 | latency-log-nofa-r2.jsonl |
| 不加速 + zh-fix r3（18:58） | 102–169 | **218–326** | 303–915 | latency-log-nofa-r3.jsonl |
| flash-attn + zh-fix（18:36） | 304–357 | **446–665** | 581–1292 | latency-log-fa.jsonl |
| flash-attn + zh-fix r2（18:58） | 271–404 | **414–582** | 565–1226 | latency-log-fa-r2.jsonl |
| flash-attn + zh-fix r3（18:59） | 272–404 | **384–579** | 527–1286 | latency-log-fa-r3.jsonl |

- **結論（證據 A）**：直播實際的用法（每句都是新文字、只合成一次）flash-attn 讓首塊慢約 170–230 ms，線上出聲從約 0.22–0.34 s 變成 0.38–0.67 s。**虛擬麥用不加速 + zh-fix**。
- 與矩陣 FA 列（首包 −30%）不一致：bench 同一句先暖機再重複量，FA 每遇到新的序列長度可能要額外配置/建立 kernel，重複同句時被暖機吃掉（推論，證據 C，沒有再拆）。所以 bench 的 FA 增益不能直接套到直播。
- 紀錄都在 `D:\AetherTune-exp\artifacts\live-tts-bench\vmic\`；腳本 `D:\AetherTune-exp\logs\live-tts\accel-gpu5.ps1`。

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
| CosyVoice2 vLLM | **BLOCKED（Johnny 17:50 決定先不做）**：vLLM 不支援 Windows，要在 WSL 另建 Linux venv、下載好幾 GB（vllm 與對應 torch）；而且 CosyVoice2 的首包與錯字問題不在 LLM 速度（見下方 CosyVoice2 調查），加速 LLM 解決不了 | C |
| CosyVoice2 首包 3–5 s、錯字 | 已查，見下方「CosyVoice2 首包與錯字調查」 | A/B |
| Qwen3-TTS fp16 | 第 4 段實測：CUDA device-side assert，沒有產出（見矩陣）；直播用 bf16 | B |

## 安裝紀錄（只在實驗 venv）

- voxcpm2 venv：`triton-windows==3.3.1.post21`
- qwen3-tts venv、gsv-tts-lite venv：`flash-attn==2.8.2+cu128torch2.7`（mjun0812/flash-attention-prebuild-wheels v0.4.10 公開輪檔，cp312 win_amd64）
- cosyvoice2-win venv 另補：wget 3.2、pyworld 0.3.5；tensorrt-cu12 10.13.3.9 安裝中（17:36 開始）
- 新 venv `cosyvoice2-win`（uv CPython 3.12.11）：torch/torchaudio 2.7.1+cu128、onnxruntime-gpu 1.22.0、transformers 4.51.3、wetext 0.0.4、kaldifst 1.9.0（1.9.1 無 Windows 輪檔）、其餘照 CosyVoice requirements（matplotlib、pyworld 不鎖版）、wget 3.2
- 權重：`D:\AetherTune-exp\tts-models\cosyvoice2` 是 `D:\AetherTune\models\speech-reconstruction\cosyvoice` 的本機複本（不含 .cache），JIT/TRT 產物只寫在複本。

## GPU 時段

| 段 | 開始 | GPU 結束 | 放鎖 | 內容 |
|---|---|---|---|---|
| 1 | 16:55:31（登記 16:55） | 17:16:20 | **17:16:29**（AetherTune Bot 行數 0） | GSV 參數/FA、虛擬麥、VoxCPM2 compile、Qwen3 串流 |
| 2 | 17:27:10（登記 17:27，距上次放鎖 10 分 40 秒） | 17:44:58 | **17:45:35**（AetherTune Bot 行數 0） | CosyVoice2 Windows 原生/JIT、Qwen3 1.7B 串流、VoxCPM2 與 VSF 對齊 |
| 3 | 17:55:48（登記 17:55，距上次放鎖 10 分 13 秒） | 18:08:07 | **18:08:07**（AetherTune Bot 行數 0） | CosyVoice2 hop-fix、hop-fix+JIT+TRT+fp16。VSF 要用 GPU，這組跑完就放鎖，Qwen3 fp16 與虛擬麥順延 |
| 4 | 18:30:43（登記 18:30，VSF 18:17 那行 18:25 標完成後；距上次放鎖 22 分） | 18:37:53 | **18:40:15**（AetherTune Bot 行數 0） | CosyVoice2 TRT+fp16+簡體、Qwen3 fp16（失敗）、GSV FA+zh-fix 虛擬麥 |
| 5 | 18:57:42（登記 18:57，距上次放鎖 17 分） | 19:00:00 | **19:00:18**（AetherTune Bot 行數 0） | 虛擬麥 不加速 / FA 交錯重量各 2 輪 |

nvidia-smi 前後：`D:\AetherTune-exp\logs\live-tts\accel\nvsmi-*.txt`。

## VoxCPM2 與 VSF 對齊

VSF 在 PC1 獨占、未加速量到的 VoxCPM2 RTF 是 1.03–1.53（VisualSoundForge `exp/tts-install` 309200a，`experiments/2026-11-20-tts-install/results.jsonl` 的 `listen_exclusive`）。我們用 `git show` 只讀 VSF 的 `scripts/vsf_run_voxcpm2.py` 和 `scripts/vsfmeasure.py`，在本 repo 寫了對齊版 `tools/live-tts-bench/bench_voxcpm2_vsf_align.py`。VSF repo 沒改；只在 D:\VisualSoundForge 做了一次 `git fetch origin exp/tts-install`，用來讀那個 commit。

### 我們每組 VoxCPM2 的完整設定

| 組 | API | inference_timesteps | cfg | 複製模式 | 參考音 | 句子 | 串流 | compile | retry_badcase | 次數 |
|---|---|---|---|---|---|---|---|---|---|---|
| 第一輪 t10 @qwen-zh | `build_prompt_cache` + `_generate_with_prompt_cache` | 10 | 2.0 | prompt_wav + prompt_text + reference_wav 三個同時給、同一檔 | qwen3-tts-clone_1.wav（與 VSF clone_1.wav SHA256 相同 46DBC998…CE50）「甚至出现交易几乎停滞的情况。」 | 本專案 short/medium/long（中文） | 是 | 否 | 否（不走這條） | 暖機 1 + 3 |
| t10/t6/t4 @qwen-zh、@rvc-sage | 同上 | 10 / 6 / 4 | 2.0 | 同上 | qwen-zh 或 rvc-sage-zh.wav（9.26 s） | 同上 | 是 | 否 | 否 | 暖機 1 + 3 |
| t6 compile @rvc-sage | 同上（`VoxCPM(optimize=True)`） | 6 | 2.0 | 同上 | rvc-sage | 同上 | 是 | **是**（triton-windows 3.3.1） | 否 | 暖機 1 + 3 |
| **VSF 對齊 t10 / t6** | `VoxCPM.from_pretrained(load_denoiser=False, optimize=False)` + `model.generate(...)`；另量 `generate_streaming`（同參數） | 10 / 6 | 2.0 | 三個同時給、同一檔 | VSF `D:\VSF\tts\refs\clone_1.wav`（中）/`clone_2.wav`（英），只讀 | VSF zh1/zh2/en1/en2 | 整句 + 串流各量 | 否 | 是（套件預設） | 暖機 zh1 一次 + 每句 3 次 |

之前每一組都是三個同時給，沒有「只給單一種」的組，所以沒有加量單一種的對照（腳本有 `--modes prompt,ref` 可以補）。

### 與 VSF 的差異

| 項目 | VSF 309200a | 我們的對齊版 | 我們的直播量測 |
|---|---|---|---|
| torch | 2.9.1+cu128 | 2.7.1+cu128 | 2.7.1+cu128 |
| voxcpm / transformers | 2.0.3.post46 / 5.23.0 | 2.0.3 / 5.23.0 | 同左 |
| 權重 | openbmb/VoxCPM2 `7936080b`（D:\VSF\tts\voxcpm2\weights） | D:\AetherTune-exp\tts-models\voxcpm2 | 同左 |
| 載入 | `from_pretrained(load_denoiser=False)`，optimize 預設 True；venv 沒有 triton，compile 自動停用 | `from_pretrained(load_denoiser=False, optimize=False)`（venv 有 triton，要明確關） | `VoxCPM(..., enable_denoiser=False, optimize=False)` |
| 生成 API | `generate`（整句），retry_badcase 預設 True、max_len 4096 | 同 VSF；另量 `generate_streaming` | `_generate_with_prompt_cache(streaming=True)`，不重試、max_len 預設 |
| 量測 | 每句 1 次，synchronize + reset peak，time.time | 每句 3 次，其他同 VSF | 每句 3 次，首包 + perf_counter |
| 下載 I/O | 有（同時有下載） | 下載已結束（鎖檔無下載列），開始時磁碟 3.1% | 第一輪無；17:00 後有 |
| RTF 定義 | 生成秒數 ÷ 音檔秒數，不含載入和暖機 | 同左 | 同左 |

### 結果（PC1 獨占，17:39:03–17:44:55；載入 82 s；nvidia-smi 量前 927 MiB / 1%）

RTF 為 3 次的 p50，括號內是第 1 次（對應 VSF 只量 1 次）。首包是 `generate_streaming` 3 次的 p50。VRAM 是 torch 峰值配置量。

| 步數 | 句 | 整句 RTF p50（第 1 次） | 串流 RTF p50 | 串流首包 p50 ms | VRAM GiB | VSF 獨占 RTF |
|---|---|---|---|---|---|---|
| 10 | zh1 | 1.207（1.632） | 1.091 | 202 | 5.51 | 1.477 |
| 10 | zh2 | 1.153（1.181） | 1.101 | 233 | 5.54 | 1.027 |
| 10 | en1 | 1.245（1.061） | 1.239 | 233 | 5.68 | 1.089 |
| 10 | en2 | 1.157（1.157） | 1.187 | 235 | 5.68 | 1.525 |
| 6 | zh1 | 0.918（0.843） | 0.818 | 154 | 5.52 | — |
| 6 | zh2 | 0.778（0.762） | 0.826 | 177 | 5.54 | — |
| 6 | en1 | 0.779（0.779） | 0.863 | 194 | 5.68 | — |
| 6 | en2 | 0.787（0.937） | 0.853 | 292 | 5.68 | — |

- **對齊後 10 步 RTF 1.01–1.63（單次值），p50 1.15–1.25，和 VSF 的 1.03–1.53 一致。** VoxCPM2 在 PC1 10 步本來就在 1 上下；單次波動大（同句 1.14–1.63），VSF 只量 1 次，所以範圍較寬。
- **6 步 RTF 0.75–1.05（單次），p50 0.78–0.92**，在 VSF 的句子和參考音上也低於 1，和我們之前 t6 的 0.76–0.94 一致。
- 我們先前 10 步量到 1.06–1.59，和 VSF 沒有矛盾；之前用 6 步得到 RTF < 1，差別在步數，不是設定錯。
- 串流與整句的 RTF 差不多；串流首包 10 步約 200–235 ms、6 步約 150–290 ms。
- 量後 nvidia-smi（7301 MiB / 70%）是在我們自己的行程還沒結束時取的，是自己的佔用，17:45 放鎖時整卡回到 927 MiB / 0%。

檔案：`D:\AetherTune-exp\artifacts\live-tts-bench\vsf-align\voxcpm2-vsfalign-hifi-result.json`（每次的原始列與摘要）、`voxcpm2-vsfalign-hifi-t{10,6}-{zh1,zh2,en1,en2}-r{1,2,3}.wav`；nvidia-smi 在 `D:\AetherTune-exp\logs\live-tts\accel\nvsmi-vsfalign-{start,end}.txt`；log 在 `accel\vsfalign.out`。

## CosyVoice2 首包與錯字調查

### 首包 3–5 s：呼叫方式 / 上游狀態沒有重設（已修，證據 A）

`cosyvoice/cli/model.py` 的 `CosyVoice2Model.tts(stream=True)` 每送出一塊就做 `self.token_hop_len = min(self.token_max_hop_len, self.token_hop_len * self.stream_scale_factor)`，是改**模型物件本身**的屬性，而且下一次呼叫不會設回 25。同一行程第一次合成第一塊是 25 個 token（約 1.6 s 音訊）；之後每次第一塊都要等 100 個 token 加 prompt 補齊（log 裡第一塊 7.64 s 音訊），所以首包變 3–5 s，短句只出 1 塊。
修法：量測腳本 `--hop-fix` 在每次合成前設 `cv.model.token_hop_len = 25`，不改套件檔。首包 3–5 s → 2.0 s，再加 JIT+TRT+fp16 → 1.4–1.6 s。直播常駐服務要在每句開始前重設，或改用每句新的 model 狀態。

### 錯字：主要是繁體字（第 4 段 GPU 驗證，證據 A）

- **文字前端確實缺**：log 顯示 `no frontend is avaliable`。ttsfrd 沒裝；wetext 0.0.4 用 `modelscope.snapshot_download("pengzhendong/wetext")` 下載資源，未登入時 ModelScope 回 403；Hugging Face 上沒有公開的同名 repo（API 回 401）。依規則不用 token，所以沒有文字正規化。但本測試句沒有阿拉伯數字或符號要正規化（「十二點」已經是中文數字），**缺前端不是錯字主因**。
- **錯字集中在繁體字**：不論 WSL 或 Windows、fp32 或 fp16+TRT、qwen-zh 或 9 秒 rvc-sage 參考音，ASR 都在同樣的字出錯：謝謝→沙沙/嚇傻、禮物→流霧、會→看、點→鼻/比、遊戲→冷食/永瘦、記得→踢得、追蹤→追欠、錯過→撒卡。簡繁同形的字（大家晚安、今天的直播先陪大家聊聊天、小明送的、真的太）幾乎都對。CosyVoice2 的 LLM 用 Qwen2 tokenizer，訓練語料以簡體為主，繁體字的發音學得差。
- **呼叫方式**：zero-shot 聲線 ID（`add_zero_shot_spk` 後 `inference_zero_shot(text, "", "", zero_shot_spk_id=...)`）和官方範例一致；prompt_text 與參考音逐字相符。沒有看到「合成句太短」的警告。
- **驗證（18:31–18:34，同一 TRT+fp16 設定，只把輸入換簡體）**：不分簡繁 CER（`common.T2S` 把參考與轉寫都轉簡體後再比）qwen-zh 從 0.40 / 0.27 / 0.52 降到 **0 / 0.04 / 0.14**，rvc-sage 從 0.40 / 0.31 / 0.39 降到 **0 / 0.04 / 0.10**。繁體時「沙沙、流霧、撒卡」這類錯字在簡體時全部消失，剩下的只有「小明→小民」「追蹤→之鐘」這種同音字。首包與 RTF 不變（1.5 s／0.72–0.83）。
- **結論**：錯字主因是繁體輸入，不是缺文字前端、也不是呼叫方式。直播端送 CosyVoice2 前先做繁→簡轉換（例如 OpenCC t2s），字幕照常顯示繁體。缺前端只影響數字、符號、英文縮寫的正規化，送字前自己把數字轉中文即可。ASR 紀錄：`D:\AetherTune-exp\logs\live-tts\asr_slot4.py` 的輸出整理在本節。
