# 直播即時 TTS 後端實測（2026-11-20）

分支：`exp/live-tts-bench`（從 `origin/main` 05b1ec4 開出）。只做實驗，不進 main。
狀態：PASS（四個後端都在 PC1 獨占 GPU 下量完；是否達直播門檻見結論）

## 背景與範圍

- Johnny 11-20 13:23：直播用的即時串流 TTS 歸 AetherTune；13:47：直播 TTS 用手動打字，音色要和變聲同一人，先用 CosyVoice2 驗證。
- Johnny 14:05：批准在實驗 venv 試裝 GPT-SoVITS 加速後端、Qwen3-TTS、VoxCPM2，和 CosyVoice2 用同一段參考音比首包延遲與 RTF。
- Johnny 14:06：新後端的試裝與量測改到 PC1（DESKTOP-IVKG49U，RTX 5060 Ti 16GB），PC2 GPU 留給 VC 延遲量測。CosyVoice2 基準也在 PC1 量，四者同硬體可比。
- 授權不作為篩選條件（Johnny 13:47），本文件只照實標註。

## 硬體與隔離

- 機器：PC1 DESKTOP-IVKG49U，NVIDIA GeForce RTX 5060 Ti 16GB（Blackwell，需 CUDA 12.8 以上的 PyTorch wheel）。
- 每個新後端一個獨立 venv：`D:\AetherTune-exp\tts-venvs\<名稱>\`；權重：`D:\AetherTune-exp\tts-models\`。
- CosyVoice2 使用 PC1 既有 WSL 環境 `D:\AetherTune\tools\venvs\cosyvoice-wsl`（唯讀使用，不改套件）。
- 不動全域 Python、CUDA、PATH、驅動。需要系統層變更就停下回報。
- PC1 可能同時有 Discord、遊戲或其他 Bot 的 GPU 工作，每次量測都記下當下 `nvidia-smi` 佔用。

## 統一量測方法

- 參考音來源：`dataset/reference-voices/voice-female-f1.wav`（JVNV 日文女聲，48 kHz 單聲道 13.40 秒，SHA-256 `37976F69F73FB13D6FEFAF80268794D545D6E19BE5059437DB067455A795F406`）。
- 實際送進模型的參考音：從上面裁出 0.0–9.6 秒（前兩句，完整句），因為 GPT-SoVITS 參考音限 3–10 秒。四個後端都用同一段裁切檔，裁切檔 SHA-256 記在結果 JSON。
- 參考音規格依 VSF `exp/research-archive` 801c0b3 `research/2026-11-20/07-配音參考音來源.md`：跨模型安全長度約 5–15 秒、完整句；逐字稿和參考音同名存放（`.txt`）；CosyVoice2 預建聲線 ID。
- 第二組參考音（Johnny 14:24，和 VSF 第一輪聽測對照）：Qwen3-TTS 官方中文（大陸口音）女聲示範 `clone_1.wav`，<https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone_1.wav>，16 kHz 單聲道 4.20 秒，SHA-256 `46DBC998C9D1D48111267C40741DD3200F2E5BCF4075F8C4C97F4451160DCE50`，逐字稿「甚至出现交易几乎停滞的情况。」取自 <https://github.com/QwenLM/Qwen3-TTS/blob/main/examples/test_model_12hz_base.py>（`ref_text_batch[1]`）。估計基頻中位數約 239 Hz（女聲）。不裁切。PC1 連不到阿里雲 OSS，所以由 Grok Bot 的雲端機下載後複製到 PC1。
- 兩組參考音都存在 `D:\AetherTune-exp\artifacts\live-tts-bench\ref\`（wav＋同名 txt）。
- 參考文本：`最近、自分の人生に充実感を感じているんだ。友達、家族、そして仕事もうまくいっている。`。來源是 faster-whisper small 的 ASR（`artifacts/stt/voice-female-f1.json`），加上 `tools/fixtures/cosyvoice/reference-female-text.txt` 的人工修正（言って→いって）。不需要參考文本的模型就不傳。
- 測試句（繁體中文，直播口語）：
  - 短（10 字）：大家晚安，謝謝你們來看。
  - 中（26 字）：今天的直播先陪大家聊聊天，等一下再一起來玩新出的遊戲喔。
  - 長（51 字）：謝謝小明送的禮物，真的太感動了！今天我們會一路玩到十二點，如果你也喜歡這個遊戲，記得按下追蹤，下次開台就不會錯過囉。
- 每句先暖機 1 次，再量 3 次。模型載入與參考音特徵快取不算在首包內（直播時模型常駐）。
- 指標：
  - 首包延遲：呼叫合成函式（文字送入）到拿到第一個非空音訊 chunk 的時間，報 p50 與 max。
  - RTF：總合成時間 ÷ 輸出音訊長度。
  - VRAM 峰值：`torch.cuda.max_memory_allocated` 加量測期間 `nvidia-smi` 取樣的行程用量。
  - 是否真串流：模型在整句生成完之前就吐出音訊 chunk，且首包時間明顯小於整句時間。
- 量測腳本：`tools/live-tts-bench/`。結果 JSON 和樣本 wav：`D:\AetherTune-exp\artifacts\live-tts-bench\<後端>\`（wav 不進 git）。

## 各後端完成條件

PASS 必須全部達成；任何一項做不到就標 BLOCKED 或 WAITING 並寫原因。安裝卡超過 40 分鐘記 BLOCKED，換下一個。

### 1. CosyVoice2-0.5B（基準）

- 用 PC1 既有 WSL venv 與 `models/speech-reconstruction/cosyvoice` 權重，能在 5060 Ti 跑。
- `inference_zero_shot(..., stream=True)` 用同一段參考音和參考文本，零樣本複製出三句中文，輸出可解碼 wav。
- 首包延遲、RTF、VRAM 都量得到，並判定是否真串流。

### 2. GPT-SoVITS 加速後端：GSV-TTS-Lite

- 選擇理由：GSV-TTS-Lite（chinokikiss，MIT，PyPI `gsv-tts-lite`）和 Aqua-TTS（Lucas1479，MIT，PyPI `aqua-tts`）二選一。GSV-TTS-Lite 社群較活躍（GitHub 183 星／16 fork，對 Aqua-TTS 49 星／2 fork，2026-11-20 查），而且純 pip 安裝、內建 V2ProPlus 預訓練模型自動下載，不需要另外架整個 GPT-SoVITS 原始碼；Aqua-TTS 要先裝完整 GPT-SoVITS v3 再疊上去，Windows 步驟較多。
- 安裝在獨立 venv，PyTorch cu128，能在 5060 Ti 跑。
- 用預設（底模）GPT/SoVITS 權重，以同一段參考音零樣本複製出三句中文（`spk_audio_path` 與 `prompt_audio_path` 都用裁切參考音），輸出 wav。
- `infer_stream` 的首包延遲、RTF、VRAM 量得到。

### 3. Qwen3-TTS（qwen-tts）

- 安裝在獨立 venv，能在 5060 Ti 跑 Base（語音複製）模型；先用 0.6B，VRAM 足夠再補 1.7B。
- 用同一段參考音和參考文本做 voice clone，輸出三句中文 wav。
- 量得到首包延遲、RTF、VRAM；如果開源套件沒有串流介面，就照實標「非串流」，首包延遲等於整句時間。

### 4. VoxCPM2（voxcpm）

- 安裝在獨立 venv，能在 5060 Ti 跑。
- 用同一段參考音（必要時加參考文本）零樣本複製出三句中文，輸出 wav。
- 用 `generate_streaming` 量首包延遲；量 RTF 與 VRAM。

## 證據等級

- A：本機實測（附 JSON 路徑與 wav 路徑）。
- B：官方文件或 README 宣稱。
- C：社群貼文或第三方說法。

## 結果

### 第一輪（同時負載，不拿來做結論）

2026-11-20 14:23–15:35（台北）在 PC1 量的第一輪，和創作工坊 Bot 在 PC1 GPU 上安裝與聽測 VSF 四個 TTS（locks.md 登記 14:26–15:38）重疊，所以整輪標「同時負載」。JSON 已移到 `D:\AetherTune-exp\artifacts\live-tts-bench\_concurrent-load\`，每個檔加了 `concurrent_load: true`。下表只保留當作過程紀錄；結論只看下面的獨占重量。

另外：VoxCPM2 第一次跑（15:21–15:25）直接呼叫 `_generate_with_prompt_cache` 時帶了 `min_len/max_len=4096/retry_*` 參數，結果每句 0 個音訊 chunk（`*-EMPTY.json`）。拿掉這些參數、只傳 `inference_timesteps/cfg_value/streaming` 後正常出聲（15:31–15:35 那一輪）。

| 後端@參考音 | 句 | 首包 p50 ms | 首包 max ms | RTF p50 | 音長 s | torch VRAM 峰值 MiB | 整卡已用 max MiB | 真串流 | 量測時間 |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| cosyvoice2-nospkid@f1 | short | 6818.7 | 7009.4 | 0.986 | 9.6 | 2727.0 | 9141.0 | 是 | 14:56 |
| cosyvoice2-nospkid@f1 | medium | 8149.1 | 8409.7 | 1.2 | 6.92 | 2725.2 | 10055.0 | 否 | 14:56 |
| cosyvoice2-nospkid@f1 | long | 7429.4 | 7454.4 | 1.054 | 15.0 | 2914.1 | 4921.0 | 是 | 14:56 |
| cosyvoice2-nospkid@qwen-zh | short | 5334.1 | 6599.0 | 0.983 | 5.24 | 2591.5 | 3960.0 | 否 | 14:54 |
| cosyvoice2-nospkid@qwen-zh | medium | 7992.1 | 8418.4 | 1.061 | 8.28 | 2651.7 | 4118.0 | 否 | 14:54 |
| cosyvoice2-nospkid@qwen-zh | long | 8968.4 | 9189.7 | 1.11 | 17.28 | 2817.1 | 8283.0 | 是 | 14:54 |
| cosyvoice2@f1 | short | 3015.8 | 4813.1 | 1.066 | 3.2 | 2726.4 | 4449.0 | 否 | 14:32 |
| cosyvoice2@f1 | medium | 6693.5 | 7195.7 | 1.092 | 7.32 | 2707.0 | 4325.0 | 否 | 14:32 |
| cosyvoice2@f1 | long | 5891.0 | 6444.4 | 0.992 | 14.8 | 2901.2 | 4831.0 | 是 | 14:32 |
| cosyvoice2@qwen-zh | short | 4790.4 | 7323.6 | 1.051 | 4.56 | 2620.2 | 8307.0 | 否 | 14:51 |
| cosyvoice2@qwen-zh | medium | 7221.4 | 7227.3 | 0.976 | 8.24 | 2620.2 | 4117.0 | 否 | 14:51 |
| cosyvoice2@qwen-zh | long | 7987.3 | 8758.8 | 1.025 | 17.52 | 2877.8 | 4722.0 | 是 | 14:51 |
| gsv-tts-lite@f1 | short | 90.5 | 117.0 | 0.122 | 3.0 | 594.0 | 1869.0 | 是 | 15:05 |
| gsv-tts-lite@f1 | medium | 238.3 | 258.5 | 0.118 | 4.85 | 594.4 | 1891.0 | 是 | 15:05 |
| gsv-tts-lite@f1 | long | 91.6 | 92.4 | 0.107 | 9.49 | 595.2 | 1889.0 | 是 | 15:05 |
| gsv-tts-lite@qwen-zh | short | 273.1 | 274.6 | 0.161 | 3.14 | 590.0 | 1866.0 | 否 | 15:05 |
| gsv-tts-lite@qwen-zh | medium | 257.4 | 269.3 | 0.125 | 7.02 | 592.4 | 1886.0 | 是 | 15:05 |
| gsv-tts-lite@qwen-zh | long | 221.0 | 271.3 | 0.122 | 10.49 | 592.4 | 1866.0 | 是 | 15:05 |
| qwen3-tts-0.6b-base@f1 | short | 6311.8 | 6715.3 | 2.023 | 3.28 | 2494.1 | 4232.0 | 否 | 15:18 |
| qwen3-tts-0.6b-base@f1 | medium | 11764.7 | 11894.4 | 1.861 | 6.32 | 2583.5 | 4654.0 | 否 | 15:18 |
| qwen3-tts-0.6b-base@f1 | long | 24320.7 | 24783.3 | 1.828 | 13.12 | 2804.8 | 5256.0 | 否 | 15:18 |
| qwen3-tts-0.6b-base@qwen-zh | short | 7025.8 | 7179.7 | 2.189 | 3.28 | 2338.8 | 8444.0 | 否 | 15:14 |
| qwen3-tts-0.6b-base@qwen-zh | medium | 13635.0 | 16731.4 | 1.775 | 7.6 | 2471.4 | 3743.0 | 否 | 15:14 |
| qwen3-tts-0.6b-base@qwen-zh | long | 28380.4 | 33409.1 | 1.988 | 14.24 | 2689.7 | 10466.0 | 否 | 15:14 |
| voxcpm2-ultimate-t10@f1 | short | 155.4 | 214.8 | 1.157 | 3.52 | 5667.4 | 7068.0 | 是 | 15:33 |
| voxcpm2-ultimate-t10@f1 | medium | 204.4 | 250.0 | 1.114 | 6.56 | 5668.3 | 7070.0 | 是 | 15:33 |
| voxcpm2-ultimate-t10@f1 | long | 176.4 | 236.7 | 1.171 | 13.76 | 5670.2 | 7072.0 | 是 | 15:33 |
| voxcpm2-ultimate-t10@qwen-zh | short | 240.2 | 270.6 | 1.222 | 2.56 | 5664.1 | 6874.0 | 是 | 15:31 |
| voxcpm2-ultimate-t10@qwen-zh | medium | 132.1 | 145.1 | 1.097 | 6.72 | 5665.0 | 6876.0 | 是 | 15:31 |
| voxcpm2-ultimate-t10@qwen-zh | long | 262.5 | 263.1 | 1.113 | 14.4 | 5666.9 | 6878.0 | 是 | 15:31 |

### GPU 實際使用時段（台北）與重疊檢查

| 時段 | 內容 | 和別的 Bot 重疊？ |
|---|---|---|
| 14:23–14:59 | CosyVoice2 第一輪（WSL；14:37–14:47 那次 nospk 卡在 /mnt/d 載入，被我中止重跑） | 重疊：創作工坊 VSF 四個 TTS 安裝與聽測 14:26–15:38 |
| 14:59–15:06 | GSV-TTS-Lite 第一輪（第一次 CUDNN 注意力報錯，改 EFFICIENT 後重跑） | 重疊 |
| 15:11–15:21 | Qwen3-TTS 0.6B 第一輪 | 重疊（VSF 15:11–15:21 正好在跑 Qwen3-TTS 1.7B） |
| 15:21–15:35 | VoxCPM2 第一輪（空輸出）＋除錯＋重跑 | 重疊 |
| 15:36–16:08 | 獨占重量：GSV 15:36–15:37、VoxCPM2 15:37–15:41、Qwen3 15:41–15:49、CosyVoice2 fp32 15:49–16:01、CosyVoice2 fp16 16:01–16:07 | 不重疊。VSF 在 locks 標 15:38 完成；每個 JSON 的 `nvidia_smi_before/after` 都只有本 Bot 一個 compute 行程 |

PC1 locks.md 起初寫「GPU 排在創作工坊之後」，但 14:23 起我就和 VSF 同時用 GPU。第一輪全部標「同時負載」，只留作過程紀錄。之後的規則：PC1 GPU 一次只給一個 Bot 量測，先登記、跑完刪除，別人在鎖就等；量測前後用 nvidia-smi 記錄 GPU 程序。

### 獨占 GPU 重量（結論用這張）

量測檔：`D:\AetherTune-exp\artifacts\live-tts-bench\<後端>\<後端>@<參考音>-result.json`；樣本 wav 同資料夾 `<後端>@<參考音>-<short|medium|long>.wav`（第 1 次量測的輸出）。nvidia-smi 全文：`D:\AetherTune-exp\logs\live-tts\nvsmi-excl-*.txt`。「torch VRAM 峰值」是該行程 `torch.cuda.max_memory_allocated`；「整卡已用」含桌面與其他程式（量測時約 0.9–1.0 GiB 底）。短句只有一個 chunk 時「真串流」欄會顯示否，那是句子太短，不代表後端不支援串流。

| 後端@參考音 | 句 | 首包 p50 ms | 首包 max ms | RTF p50 | 音長 s | torch VRAM 峰值 MiB | 整卡已用 max MiB | 真串流 | 量測時間 |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| cosyvoice2-fp16@f1 | short | 5469.3 | 6690.3 | 1.05 | 4.68 | 3770.3 | 5410.0 | 否 | 16:05 |
| cosyvoice2-fp16@f1 | medium | 5674.0 | 7760.7 | 0.975 | 5.84 | 3784.2 | 5360.0 | 否 | 16:05 |
| cosyvoice2-fp16@f1 | long | 7417.0 | 8214.9 | 1.135 | 16.2 | 3865.2 | 5957.0 | 是 | 16:05 |
| cosyvoice2-fp16@qwen-zh | short | 5063.1 | 5435.0 | 0.969 | 4.32 | 3701.4 | 5142.0 | 否 | 16:03 |
| cosyvoice2-fp16@qwen-zh | medium | 7858.2 | 8548.0 | 1.093 | 7.92 | 3733.9 | 5198.0 | 否 | 16:03 |
| cosyvoice2-fp16@qwen-zh | long | 9201.8 | 9806.4 | 1.173 | 16.88 | 3812.5 | 5694.0 | 是 | 16:03 |
| cosyvoice2-nospkid@f1 | short | 6178.9 | 6330.6 | 1.0 | 9.6 | 2727.2 | 4364.0 | 否 | 15:58 |
| cosyvoice2-nospkid@f1 | medium | 7783.3 | 8072.0 | 1.217 | 6.4 | 2707.2 | 4374.0 | 否 | 15:58 |
| cosyvoice2-nospkid@f1 | long | 7128.1 | 7587.9 | 1.194 | 19.0 | 3225.1 | 5587.0 | 是 | 15:58 |
| cosyvoice2-nospkid@qwen-zh | short | 4931.2 | 7269.1 | 0.931 | 5.6 | 2620.4 | 4112.0 | 否 | 15:56 |
| cosyvoice2-nospkid@qwen-zh | medium | 6934.8 | 8214.2 | 0.904 | 9.04 | 2614.7 | 4122.0 | 否 | 15:56 |
| cosyvoice2-nospkid@qwen-zh | long | 7848.4 | 8319.7 | 1.029 | 17.76 | 2924.8 | 4884.0 | 是 | 15:56 |
| cosyvoice2@f1 | short | 4378.0 | 6638.8 | 0.945 | 4.52 | 2727.0 | 4364.0 | 否 | 15:54 |
| cosyvoice2@f1 | medium | 5804.8 | 6604.1 | 0.959 | 8.2 | 2788.1 | 4534.0 | 否 | 15:54 |
| cosyvoice2@f1 | long | 6455.3 | 7448.2 | 1.041 | 15.08 | 2884.6 | 4832.0 | 是 | 15:54 |
| cosyvoice2@qwen-zh | short | 4390.4 | 6888.4 | 0.963 | 4.56 | 2620.2 | 4112.0 | 否 | 15:52 |
| cosyvoice2@qwen-zh | medium | 6936.5 | 7716.6 | 0.907 | 9.64 | 2622.8 | 4130.0 | 否 | 15:52 |
| cosyvoice2@qwen-zh | long | 7071.0 | 7967.1 | 0.94 | 17.24 | 2803.8 | 4560.0 | 是 | 15:52 |
| gsv-tts-lite@f1 | short | 120.5 | 121.9 | 0.127 | 2.89 | 594.8 | 1886.0 | 是 | 15:37 |
| gsv-tts-lite@f1 | medium | 250.1 | 287.3 | 0.123 | 5.21 | 595.2 | 1864.0 | 是 | 15:37 |
| gsv-tts-lite@f1 | long | 122.5 | 124.8 | 0.104 | 10.32 | 595.1 | 1886.0 | 是 | 15:37 |
| gsv-tts-lite@qwen-zh | short | 244.7 | 266.3 | 0.129 | 2.69 | 593.3 | 1864.0 | 否 | 15:37 |
| gsv-tts-lite@qwen-zh | medium | 211.4 | 212.7 | 0.114 | 7.18 | 592.1 | 1886.0 | 是 | 15:37 |
| gsv-tts-lite@qwen-zh | long | 257.2 | 271.6 | 0.12 | 11.0 | 592.9 | 1886.0 | 是 | 15:37 |
| qwen3-tts-0.6b-base@f1 | short | 4749.9 | 15024.2 | 1.799 | 2.64 | 2635.3 | 4121.0 | 否 | 15:46 |
| qwen3-tts-0.6b-base@f1 | medium | 11229.3 | 13090.0 | 1.823 | 6.16 | 2607.1 | 4121.0 | 否 | 15:46 |
| qwen3-tts-0.6b-base@f1 | long | 24130.5 | 25213.8 | 1.876 | 12.88 | 2814.5 | 4523.0 | 否 | 15:46 |
| qwen3-tts-0.6b-base@qwen-zh | short | 6090.9 | 6117.4 | 1.815 | 3.36 | 2341.2 | 3525.0 | 否 | 15:43 |
| qwen3-tts-0.6b-base@qwen-zh | medium | 13110.6 | 13874.3 | 1.711 | 7.68 | 2463.7 | 3791.0 | 否 | 15:43 |
| qwen3-tts-0.6b-base@qwen-zh | long | 24228.0 | 26364.6 | 1.691 | 14.32 | 2696.8 | 4403.0 | 否 | 15:43 |
| voxcpm2-ultimate-t10@f1 | short | 164.8 | 166.5 | 1.121 | 3.04 | 5667.4 | 7068.0 | 是 | 15:39 |
| voxcpm2-ultimate-t10@f1 | medium | 209.9 | 246.9 | 1.169 | 6.72 | 5668.3 | 7099.0 | 是 | 15:39 |
| voxcpm2-ultimate-t10@f1 | long | 171.6 | 204.1 | 1.156 | 14.24 | 5670.2 | 7101.0 | 是 | 15:39 |
| voxcpm2-ultimate-t10@qwen-zh | short | 143.5 | 146.0 | 1.104 | 2.88 | 5664.1 | 6874.0 | 是 | 15:37 |
| voxcpm2-ultimate-t10@qwen-zh | medium | 138.1 | 183.0 | 1.136 | 6.88 | 5665.0 | 6876.0 | 是 | 15:37 |
| voxcpm2-ultimate-t10@qwen-zh | long | 155.1 | 240.8 | 1.151 | 13.6 | 5666.9 | 6878.0 | 是 | 15:37 |

### 摘要（Qwen 官方中文示範音那組，p50）

| 後端 | 首包 p50（短／中／長） | 首包 max | RTF | torch VRAM 峰值 | 支援真串流 | ASR 字錯率（短／中／長） | 狀態 |
|---|---|---|---|---|---|---|---|
| CosyVoice2-0.5B fp32＋聲線 ID | 4390／6937／7071 ms | 7968 ms | 0.91–0.96 | 2.6–2.8 GiB | 是（`stream=True`，長句多 chunk） | 0.50／0.35／0.35 | PASS（量得到），不達直播門檻 |
| CosyVoice2 fp16＋聲線 ID | 5063／7858／9202 ms | 9806 ms | 0.97–1.17 | 見 JSON | 是 | 0.40／0.19／0.35 | fp16 沒有變快 |
| GSV-TTS-Lite 0.4.7（V2ProPlus 底模） | 245／211／257 ms | 272 ms | 0.11–0.13 | 0.58 GiB | 是（token 級，25 token 一塊） | 0.00／0.27／0.31 | PASS，最快 |
| Qwen3-TTS 0.6B Base | 6091／13111／24228 ms | 26365 ms | 1.69–1.82 | 2.3–2.6 GiB | 否（`qwen-tts` 0.1.1 沒有串流生成，首包＝整句） | 0.00／0.08／0.06 | PASS（量得到），不達直播門檻 |
| VoxCPM2（ultimate：參考音＋逐字稿續寫＋reference） | 144／138／155 ms | 241 ms | 1.10–1.15 | 5.5 GiB | 是 | 0.00／0.04／0.06 | PASS，首包快但 RTF>1 |

JVNV f1（日文參考音）那組：首包與 RTF 和上表差不多（GSV 121–250 ms、VoxCPM2 165–210 ms），但四個後端的中文都被帶成日文腔或亂碼，ASR 字錯率多在 0.4–1.5，Qwen3-TTS 和 CosyVoice2 的長句幾乎不能聽。日文參考音不適合拿來做中文直播 TTS。

聲線 ID 對 CosyVoice2 首包的影響：用預建聲線 ID 和每次傳參考音＋逐字稿差不多（qwen-zh 短句 4390 對 4931 ms、長句 7071 對 7848 ms），省 0.5–0.8 秒，但瓶頸不在參考音特徵抽取。

ASR 粗檢：`tools/live-tts-bench/asr_check.py`（faster-whisper small，CPU int8，繁體提示詞），結果 `D:\AetherTune-exp\artifacts\live-tts-bench\asr-check.json`。只轉寫每組第 1 次輸出；字錯率會被同音字、簡繁差異拉高，只能當可懂度粗檢，不能代替聽測。GSV-TTS-Lite 中長句的 ASR 結果常漏掉開頭幾個字（例如中句少了「今天的」、長句少了「謝謝小明」），要聽測確認是否吃字。

### VSF 對照組（另一個 Bot 在同一台 PC1 量的）

創作工坊 Bot：Qwen3-TTS 1.7B Base＋同一個官方 `clone_1.wav`，zh2 句 RTF 1.94、VRAM 峰值約 4.29 GiB（VSF `exp/tts-install` d33c97e）。證據等級 A（VSF 本機實測，非本 Bot 量），而且量的時段和本 Bot 第一輪重疊。和本 Bot 的 0.6B 獨占結果（RTF 1.69–1.82）同一個量級，1.7B 只會更慢，所以本輪沒有再量 1.7B（權重已下載在 `D:\AetherTune-exp\tts-models\qwen3-tts-1.7b-base`）。

### 安裝內容（PC1）

- venv（uv 建立，Python 3.12.11；uv 自動在 `C:\Users\User\AppData\Roaming\uv\python\` 放了一份 uv 管理的 CPython 3.12，使用者層級、沒改 PATH 或系統 Python）：
  - `D:\AetherTune-exp\tts-venvs\gsv-tts-lite`：gsv-tts-lite 0.4.7、torch/torchaudio/torchvision 2.7.1+cu128／0.22.1、transformers 5.23.0、onnxruntime 1.32.0、numpy 2.5.5（共 73 個套件）。
  - `D:\AetherTune-exp\tts-venvs\qwen3-tts`：qwen-tts 0.1.1、transformers 4.57.3、accelerate 1.12.0、torch 2.7.1+cu128（共 89 個；沒裝 flash-attn，用 sdpa）。
  - `D:\AetherTune-exp\tts-venvs\voxcpm2`：voxcpm 2.0.3、torch 2.7.1+cu128、torchcodec 0.17.0、transformers 5.23.0、kaldifst 1.9.0（共 150 個）。kaldifst 1.9.1 在 Windows x64 沒有 wheel、要編譯會失敗，改釘 1.9.0。
  - 完整清單：`D:\AetherTune-exp\logs\live-tts\freeze-<名稱>.txt`。
- 權重（`D:\AetherTune-exp\tts-models\`，只用公開下載）：GSV-TTS-Lite 自動下載的底模（s1v3、s2Gv2ProPlus、chinese-hubert、chinese-roberta、sv）；`Qwen/Qwen3-TTS-12Hz-0.6B-Base`、`Qwen/Qwen3-TTS-12Hz-1.7B-Base`；`openbmb/VoxCPM2`。
- CosyVoice2：唯讀使用 PC1 `D:\AetherTune\tools\venvs\cosyvoice-wsl`（WSL Ubuntu，Python 3.10、torch 2.7.1+cu128）與 `models\speech-reconstruction\cosyvoice`，沒改任何套件。wetext 前端從 ModelScope 下載被 403，所以沒有文字正規化（原本就有的限制）。
- 系統層變更：無。不需要電腦管家處理。

### 學到什麼

1. 直播要的「打字後 300 ms 內出聲、而且跟得上播放」，四個裡只有 GSV-TTS-Lite 同時做到（首包 0.12–0.29 秒、RTF 約 0.12、VRAM 0.6 GiB）。（A）
2. VoxCPM2 首包也很快（0.14–0.25 秒），可懂度最好，但 RTF 1.10–1.17，生成比播放慢，直播邊生成邊播會卡頓，要先緩衝或加速。這次為了 Windows 相容關掉了 `torch.compile`（`optimize=False`）。（A）
3. CosyVoice2 在 PC1 的既有 WSL 環境下首包 4–9 秒、RTF 約 1，fp16 也沒變快，不適合直播。可能原因是沒開 JIT／TensorRT／vLLM、跑在 WSL 的 /mnt/d、wetext 前端缺失，這幾點都還沒驗證。（首包數字 A；原因 C）
4. Qwen3-TTS 開源套件沒有串流生成，0.6B 的 RTF 也有 1.7–1.8，首包等於整句（短句 6 秒、長句 24 秒），不適合直播；中文可懂度很好，適合離線配音（歸 VSF）。（A）
5. 日文 JVNV 參考音會讓四個模型的中文都帶日文腔或變亂碼。直播 TTS 要和變聲同一人，就需要一段乾淨的中文女聲參考音（5–15 秒、附逐字稿）。（A）
6. gsv-tts-lite 0.4.7 在 5060 Ti/Windows 上自動選的 CUDNN 注意力後端會在帶 mask 時報「No available kernel」，在量測腳本裡改成 EFFICIENT 就好，不用改套件。VoxCPM2 直接呼叫 `_generate_with_prompt_cache` 時帶 `max_len=4096` 等參數會輸出 0 個 chunk。（A）

### 下一輪

1. GSV-TTS-Lite：聽測樣本；試 `boost_first_chunk=False`、`use_bert=True`，看開頭吃字是否消失，以及首包增加多少。
2. VoxCPM2：試 `inference_timesteps` 降到 6 或 4，看 RTF 能否壓到 1 以下；`torch.compile` 需要 triton-windows，屬新依賴，要先問 Johnny。
3. 決定直播 TTS 用的中文女聲參考音（和變聲目標同一人），補一段 5–15 秒、附逐字稿的版本，再量一次 GSV-TTS-Lite 與 VoxCPM2。
4. CosyVoice2 若要保留，另開實驗試 JIT／TensorRT 或把權重放到 WSL ext4，找出首包慢的原因。
5. 把 GSV-TTS-Lite 接到 AetherTune 的手動打字 TTS 路徑做端到端試驗（打字 → 虛擬麥克風）。

### 證據等級

本節所有數字都是 A（PC1 本機實測，JSON 與 wav 路徑如上），只有「CosyVoice2 慢的原因」是 C（推測），VSF 對照組是 A 但非本 Bot 量測。
## 第二輪（2026-11-20 16:14–16:31 台北，PC1 獨占 GPU）

鎖檔：16:16 登記「獨占 GPU」，**16:31:24 刪行**（刪後 `AetherTune Bot` 行數 0；整卡 1014 MiB、0%，無我方 python 行程）。
實際 GPU 時段：16:14:38–16:31:16。注意 16:20–16:22 我方兩支腳本（r2 的 VoxCPM2 t6 與 r2b 的來源/RVC）重疊，該次 t6 結果已刪除，16:25 於獨占下重量；下表皆為非重疊量測。

### 同一人參考音（rvc-sage）

- 產生方式：VoxCPM2（qwen-zh 參考）合成中文來源 `artifacts\live-tts-bench\ref\zh-source-voxcpm2.wav`（9.28 s）→ PC1 RVC `Sage_CN_HeroicFemale`（rvc-fcpe-gpu-infer.py）→ `D:\AetherTune-exp\dataset\reference-voices\rvc-sage-zh.wav`（9.26 s，SHA256 9D8AA839…AB12F3）。PC2 未使用（不搭 PC2 GPU）。
- 逐字稿（同名 .txt）：「歡迎來到我的直播間，今天天氣有點冷，大家記得多穿一點衣服，我們先來看看留言吧。」faster-whisper small 轉寫結果與稿逐字一致（僅簡繁差異），人工校正為繁體。

### 結果（首包 p50 ms / RTF p50 / ASR CER，短·中·長）

| 組合 | 首包 p50 | RTF | torch VRAM 峰值 | CER |
|---|---|---|---|---|
| GSV 預設 @qwen-zh（第一輪獨占） | 211–257 | 0.11–0.13 | 0.58 GiB | 0–0.31 |
| GSV boost_first_chunk=False @qwen-zh | 253 / 217 / 228 | 0.153 / 0.112 / 0.122 | 0.58 GiB | 0.40 / 0.35 / 0.52 |
| GSV use_bert @qwen-zh | 247 / 247 / 246 | 0.158 / 0.126 / 0.143 | 1.19 GiB | 0.20 / 0.31 / 0.52 |
| GSV use_bert + noboost @qwen-zh | 237 / 226 / 293 | 0.152 / 0.114 / 0.154 | 1.19 GiB | 0.40 / 0.31 / 0.58 |
| **GSV 預設 @rvc-sage** | **124 / 87 / 128** | 0.125 / 0.097 / 0.103 | 0.58 GiB | **0 / 0.08 / 0.23** |
| GSV noboost @rvc-sage | 172 / 148 / 185 | 0.122 / 0.102 / 0.096 | 0.58 GiB | 0 / 0.08 / 0.25 |
| VoxCPM2 t10 @rvc-sage | 240 / 199 / 157 | 1.59 / 1.06 / 1.41 | 5.5 GiB | 0 / 0.04 / 0.06 |
| **VoxCPM2 t6 @qwen-zh** | 103 / 101 / 127 | **0.757 / 0.774 / 0.777** | 5.5 GiB | 0 / 0.04 / 0.06 |
| VoxCPM2 t4 @qwen-zh | 151 / 117 / 145 | 0.866 / 0.856 / 0.844 | 5.5 GiB | 0 / 0.04 / 0.06 |
| **VoxCPM2 t6 @rvc-sage** | 118 / 115 / 123 | **0.768 / 0.783 / 0.942** | 5.5 GiB | 0 / 0.04 / 0.04 |

CER 為 faster-whisper small（CPU int8）對合成音轉寫，含簡繁/數字（12 vs 十二）/同音字誤差，只作相對比較；**不是真人評聽**。

### 結論

1. **GSV 開頭吃字的主因是參考音，不是 boost_first_chunk**：qwen-zh 參考只有約 3 秒單句，任何參數組合都吃掉開頭（短句「大家晚安」常消失）；換成 9 秒 rvc-sage 後短句 CER 0、首包降到 87–128 ms。boost_first_chunk=False 與 use_bert 在 qwen-zh 上沒改善（CER 反而略高），use_bert 多佔約 0.6 GiB。建議：預設參數 + 9 秒左右完整句參考音。（證據等級：本機實測 3 次量測 + ASR，A）
2. **VoxCPM2 步數 10→6 時 RTF 壓到 1 以下（0.76–0.94），CER 不變**；t4 沒有比 t6 更快（0.84–0.87，屬量測波動或其他瓶頸），故 t6 為建議值。t10@rvc-sage 的 RTF（1.06–1.59）比第一輪 t10@qwen-zh（1.10–1.15）波動大，原因未查明。
3. GSV 長句 CER 0.23–0.25 主要是「小明送→小明宋/松」「十二→12」等 ASR 差異與句尾「下次開台就不會錯過囉」被截，句尾截斷待查。

### 樣本路徑（PC1，不進 git）

- `D:\AetherTune-exp\artifacts\live-tts-bench\gsv-tts-lite\gsv-tts-lite{,-noboost,-bert,-bert-noboost}@{qwen-zh,rvc-sage}-{short,medium,long}.wav`
- `D:\AetherTune-exp\artifacts\live-tts-bench\voxcpm2\voxcpm2-ultimate-t{4,6,10}@{qwen-zh,rvc-sage}-{short,medium,long}.wav`
- 參考音：`D:\AetherTune-exp\dataset\reference-voices\rvc-sage-zh.wav` + `.txt`
- nvidia-smi：`D:\AetherTune-exp\logs\live-tts\r2b-nvsmi-end.txt`、`r2c-nvsmi-start/end.txt`、`r2d-nvsmi-end.txt`；ASR：`artifacts\live-tts-bench\asr-check.json`

### 虛擬麥原型

`tools/live-tts-bench/live_tts_to_vmic.py`（GSV → sounddevice → `CABLE Input (VB-Audio Virtual Cable)`）已寫好並推送，**尚未上 GPU 實測**（本輪 GPU 時段用完），待下一個獨占時段。
