# 直播即時 TTS 後端實測（2026-11-20）

分支：`exp/live-tts-bench`（從 `origin/main` 05b1ec4 開出）。只做實驗，不進 main。
狀態：WAITING（完成條件已定，量測進行中）

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
- 實際送進模型的參考音：從上面裁出 0.0–9.6 秒（前兩句），因為 GPT-SoVITS 參考音限 3–10 秒。四個後端都用同一段裁切檔，裁切檔 SHA-256 記在結果 JSON。
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

（量測完成後填入）
