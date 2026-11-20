# AetherTune 研究：即時變聲與直播即時 TTS 的分維度選項（2026-11-20）

**文件邊界：**本頁是 2026-11-20 當日的研究快照，只供選型參考，不是決策、不是驗收。採用與否寫進[決策紀錄](../decision-log.md)；實測結果以 `docs/verification/` 分項報告為準。前一份研究見[第 0 輪](2026-11-20-round0-seedvc-engines-latency-tts-split.md)。

- 基準：`origin/main` 05b1ec4；本輪只做網路與文件研究，沒有安裝、沒有使用 GPU、沒有改程式。
- 範圍（Johnny 2026-11-20 13:08／13:23 定案）：AetherTune 負責即時變聲、混音、直播用即時串流 TTS；配音品質 TTS 歸 VisualSoundForge（VSF），品質模型可從 VSF 引用。
- 目標（[願景](https://github.com/jellyfish00001/AetherTune/blob/codex/docs-vision/docs/specs/vision.md)）：自然女聲、聽不出是變聲；麥克風 → 輸出端到端 100–300ms（PC1 RTX 5060 Ti 為準，PC2 RTX 2060 12GB 只作參考）；第一個輸出是 Discord；自用開發版。
- 寫法依 Johnny 的技術選型偏好：分維度、每維度 1–2 個最強選項與優缺點、**不給總排名**；每個說法標證據等級。

**證據等級：**A＝AetherTune repo 實測；B＝社群獨立量測（附連結）；C＝論文或作者宣稱；D＝論壇、個案或推論。

---

## 0. 先講最影響方向的一件事：100–300ms 預算裡，硬體與音訊 API 本身就吃掉約 100ms

- Beatrice 作者社群量測：同一顆 UR12 介面、WASAPI 下 beatrice-client 端到端約 138.7ms，扣掉約 36ms 演算法延遲後，**音訊介面＋WASAPI 本身約 100ms**；ASIO 128 frame 時 Beatrice VST 只有約 50.7ms。〔B，https://zenn.dev/gokrack/articles/621a2872fd9ccd 〕
- 同一篇量測：VCClient 實際延遲約是 chunk 設定的 2–3 倍（RVC chunk 0.25s → 約 817.5ms）。〔B，同上〕
- AetherTune 現行路由是 引擎 → CABLE Input → Light Host（VST）→ Voicemeeter → B1，48kHz、960 frame、WASAPI 共享，每一跳都有緩衝。〔A，`audio-rack/routing/seed-vc-virtual-route.json`〕
- **推論：**若裝置＋路由就約 100–150ms，留給模型的只剩約 100–150ms。這代表「模型 p95 < 100ms」的引擎（MeanVC2 94.7ms、X-VC 79.6ms〔A〕）才有機會進 300ms；而且路由跳數比換引擎更可能決定成敗。〔D〕
- 所以第一優先仍是 `exp/bench-e2e-latency` 的實機端到端量測；在那之前，下面所有延遲比較都只是「模型或作者數字」。

---

## 1. 即時變聲（VC）

### 1.1 端到端延遲（能不能進 100–300ms）

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **MeanVC2**（ASLP-lab，已整合） | 40ms chunk、論文宣稱端到端首包 109.88ms〔C，https://arxiv.org/html/2606.09050 〕；AetherTune 模型 p95 94.7ms〔A，`realtime-vc-verification-latest.md` 2026-10-01〕；18M 參數，單核 CPU RTF 0.633〔C〕 | 上游很新（2026-06 建立，207 星）；README 寫 Apache-2.0 但 repo 沒有 LICENSE 檔〔A，第 0 輪〕；AetherTune 尚無實機 E2E |
| **Beatrice 2**（未整合） | 社群實測 VST+ASIO 約 50.7ms、beatrice-client（WASAPI）約 138.7ms〔B，zenn〕；作者目標 RTF<0.2 單執行緒 CPU〔C，https://huggingface.co/fierce-cats/beatrice-trainer 〕 | 每個聲線都要先訓練；推論庫 `beatrice.lib` 是專有、不能再散布，只能當外部 VST／client 用，不能嵌進 AetherTune〔D，https://note.com/ainanashiko/n/nd1d66d674458 〕 |

對照：X-VC 模型 p95 79.6ms〔A〕但架構固有延遲約 240ms〔C，https://arxiv.org/abs/2604.12456 〕；Seed-VC tiny 模型 p95 175.7ms〔A〕、作者 GUI 建議設定總延遲 430ms〔C，https://github.com/plachtaa/seed-vc 〕；RVC＠VCClient 約 0.8–1.7s〔B，zenn〕。Applio 2026 年的即時化 PR 宣稱處理延遲 60–80ms，但那是 Colab 上的處理時間、不是麥克風到喇叭〔C，https://github.com/IAHispano/Applio/pull/1245 〕。

### 1.2 自然度與「聽不出是變聲」（女聲）

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **訓練型：RVC／Beatrice 2** | 社群直播、VTuber 實際在用的主流；有固定目標聲線時音色最穩；RVC 生態最大（WebUI 約 39.2k 星、w-okada 約 21.4k 星）〔A，第 0 輪〕 | 要有授權乾聲資料（Beatrice 案例：11 分鐘、100 檔、10,000 step、RTX 2070 上 1 小時 19 分）〔D，note.com 個案〕；男轉女的「濁聲」問題常見，需調音〔D，同上〕 |
| **zero-shot：Seed-VC／MeanVC2** | 不必訓練，換參考音檔就換聲線，適合「還沒決定目標聲線」的現在 | zero-shot 音色相似度普遍比訓練型弱，尤其短 chunk 時；MeanVC2 論文宣稱 40ms chunk 仍維持相似度，但沒有獨立聽評〔C〕；AetherTune 尚無本人聽評〔A：無資料〕 |

### 1.3 是否要訓練（直接決定 Johnny 要花多少時間）

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **zero-shot（MeanVC2、Seed-VC、X-VC）** | 零訓練、切換便宜，方向錯了損失小 | 品質天花板較低；仍需一段乾淨的參考音 |
| **少量訓練（Beatrice 2）** | 訓練器 MIT、有 Windows 本機與 Colab/Kaggle 免費方案；預設約 9GB VRAM，RTX 4090 約 40 分鐘〔C，beatrice-trainer README〕，12GB 的 2060 可跑〔D〕 | 需要合法語料；官方 v2 沒有現成聲線模型，一定要自己訓練〔D，note.com〕 |

### 1.4 授權與可長期依賴

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **X-VC（MIT）／MeanVC2（宣稱 Apache-2.0）** | 寬鬆授權，可改可嵌入 | MeanVC2 缺 LICENSE 檔需追問上游〔A〕 |
| **RVC（MIT 系生態）** | 社群最大、問題最好查 | 原版 WebUI 已不是活躍主線，即時化要靠 w-okada／Applio 等分支〔D〕 |

風險：Seed-VC 上游已封存、GPL-3.0、權重在個人 HF 帳號〔A，第 0 輪〕；Beatrice 推論庫專有、聲線使用規約限制發言內容〔D，note.com〕。

### 1.5 維護活躍度

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **MeanVC2** | 2026-09 仍有 push、4 個 open issue、同團隊從 MeanVC 一路迭代〔A，第 0 輪；C，GitHub 頁面〕 | 學術團隊，長期維護無承諾 |
| **w-okada VCClient** | 持續發版（v2.2.2-beta 支援 Beatrice v2.0.0-rc0）〔C，https://github.com/w-okada/voice-changer 〕 | 是整套 App，不是可嵌入的引擎 |

Seed-VC：封存，唯一活躍 fork `jiaheguo521/seed-vc-realtime` 依 Johnny 13:23 決定不評估、只備份原版。

### 1.6 GPU／VRAM 佔用（直播時 GPU 還要給遊戲、OBS）

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **MeanVC2** | 18M 參數，論文稱單核 CPU 即時、FRC 讓峰值 GPU 記憶體降約 60%〔C〕 | CPU 模式未在 AetherTune 量過 |
| **Beatrice 2** | 推論不需 GPU〔C，beatrice-trainer README〕 | 訓練仍需 GPU |

Seed-VC 作者提醒：同時跑其他吃 GPU 的工作時速度會掉〔C，seed-vc README〕。

### 1.7 混音與虛擬音訊線路（Discord 輸出）

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **App 內 Rust cpal／WASAPI 混音，直接輸出到一個虛擬麥克風** | 省掉 CABLE→Light Host→Voicemeeter 兩到三跳；不需新驅動（Johnny 13:23：先用既有 Voicemod／Voxal 虛擬麥克風）〔D，推論〕 | 要寫程式與驗證；WASAPI 共享模式仍有固定緩衝 |
| **Virtual-Audio-Driver（MIT，開源）** | 開源取代 VB-CABLE〔C，https://github.com/VirtualDrivers/Virtual-Audio-Driver 〕 | 要裝驅動＝系統層級，需交 PC2 管家，今天不做 |

已知社群缺陷：取樣率不一致會爆音（建議全鏈 48kHz）、只在 Discord 卡頓可換 VAC、Win11 power throttling 讓音訊斷續〔D，第 0 輪連結〕。

---

## 2. 直播用即時串流 TTS

情境假設：直播中打字或程式送文字 → 立刻念出 → 進同一條混音到 Discord。重點是首包延遲、中文女聲、串流、能在 12–16GB 消費級顯卡和 VC 同時跑。

### 2.1 首包延遲（TTFA）

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **CosyVoice2／Fun-CosyVoice3（Apache-2.0）** | 官方宣稱雙向串流首包 150ms〔C，https://github.com/QwenAudio/CosyVoice 〕；社群實測：RTX 4070 vLLM 加速後 150–250ms〔B，https://github.com/qi-hua/async_cosyvoice 〕；RTX 4090 TensorRT-LLM 單併發 p50 335ms〔B，https://github.com/FunAudioLLM/CosyVoice/issues/1835 〕 | 沒加速時首包約 0.4–0.6s（4090）〔B，issue #1521〕；**AetherTune 現行 CosyVoice2 離線 RTF 1.2059、warm 次句生成 4.096 秒**〔A，`cosyvoice-verification-latest.md`、`manual-tts-verification-latest.md`〕→ RTF>1 時串流會追不上播放，必須先加速；vLLM／TRT 加速多半只支援 Linux（async_cosyvoice 明寫僅 Linux）〔C〕→ Windows 要走 WSL |
| **GPT-SoVITS v2Pro＋加速後端** | GSV-TTS-Lite 在 RTX 3050 Laptop 首包 133–150ms、VRAM 0.8GB〔B，https://github.com/chinokikiss/GSV-TTS-Lite 〕；Aqua-TTS 在 Windows RTX 4070 Ti SUPER 短句首包 p50 約 86–100ms〔B，https://github.com/Lucas1479/Aqua-TTS 〕 | 需要約 1 分鐘目標聲線資料微調才好；原版 streaming_mode=3 長句韻律劣化、首包 0.8s 級〔B，https://blog.hodaru.com/posts/project/bettergi-questvoice/systems/gpt-sovits-streaming-pipeline/ 〕 |

### 2.2 中文（台灣口音）女聲品質

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **Breeze TTS 2（BreezeBlue，已整合為配音引擎）** | 官方宣稱 TTFA p50 127.2ms、有串流 API〔C，https://breezeblue.ai/breeze-tts-2 〕；上游有 `FastBreezeStreamingRuntime`〔A，`tools/breeze-tts2-infer.py`〕；台灣團隊、中文女聲 Voice Design／Clone 已在 repo PASS〔A，`breeze-tts2-verification-latest.md`〕 | **AetherTune 在 RTX 5060 Ti 實測 RTF 4.3–11.4**，離即時很遠〔A，同上〕；權重是 BreezeBlue Research and Non-Commercial License〔A，同上〕；約 7.7 GiB VRAM〔A，同上〕 |
| **BreezyVoice（MediaTek，CosyVoice 衍生）** | 專為台灣口音中文、注音輔助破音字〔C，https://huggingface.co/MediaTek-Research/BreezyVoice 〕 | 開源 API 一次產生整個 WAV、沒有串流〔C，https://github.com/mtkresearch/BreezyVoice/blob/main/api.py 〕；和 Breeze TTS 2 是不同模型 |
| **CosyVoice3** | 中文＋18 種方言、指令控制情緒語速〔C〕 | 台灣口音需參考音引導；同上加速平台限制 |

對照：Kokoro-82M 的 4 個中文女聲官方自評等級都是 D（訓練資料僅數十分鐘）〔C，https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md 〕，自然度不足以「聽不出」。

### 2.3 授權（直播若有營利會變成關鍵）

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **CosyVoice2/3（Apache-2.0）、GPT-SoVITS（MIT）、Kokoro（Apache-2.0）** | 權重可商用〔C，https://tts.mahimai.ca/open-source-and-open-weight-models/ 〕 | — |
| **IndexTTS2（bilibili Model Use License）** | 原文只要求月活 > 1 億或年營收 > 人民幣 10 億者另申請，個人直播實際上可用〔C，https://github.com/index-tts/index-tts/blob/main/LICENSE 〕；第三方彙整說「商用需另申請」是誤讀〔D〕 | 有撤銷條款、受中國法律管轄；串流首包慢（見 2.4） |
| 非商用、營利直播不能用的：Fish S2-Pro（Research License）〔C，https://huggingface.co/fishaudio/s2-pro 〕、F5-TTS（權重 CC-BY-NC）〔C，https://github.com/SWivid/F5-TTS 〕、Spark-TTS（CC-BY-NC-SA）〔C〕、**Breeze TTS 2（已在 repo，Research and Non-Commercial）**〔A〕 | 品質強 | 營利直播不符條款 |

### 2.4 顯卡需求（能否和 VC 同機同時跑）

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **Kokoro-82M** | 82M、CPU 即可、串流首包約 126ms（M3 Max）、內建中文女聲 `zf_*`〔B，https://huggingface.co/sonic-speech/kokoro-82m-bf16 〕 | 固定預設聲線、不能複製聲音；中文自然度社群評價低於 LLM 型 TTS〔D〕 |
| **GSV-TTS-Lite** | 0.8GB VRAM〔B〕 | 見 2.1 |

不適合目前硬體：Fish S2-Pro 至少 24GB VRAM〔C，https://speech.fish.audio/install/ 〕；IndexTTS2 串流首包約 0.4–0.6s 且需 TensorRT〔C，https://arxiv.org/html/2607.21042 〕；Spark-TTS 沒有串流〔C，faun.dev 比較〕；VoxCPM2 2B、RTF 0.3 是 4090 數字〔C，https://github.com/openbmb/VoxCPM 〕。

### 2.5 串流方式與 Windows 整合成本

| 選項 | 強在哪 | 弱在哪 |
|---|---|---|
| **CosyVoice2 `stream=True`（已安裝）** | AetherTune 已裝 CosyVoice2 做手動 TTS，只是走整檔模式（`supports_streaming_tts=false`）〔A，`contracts/engines/cosyvoice.json`〕；換成串流不一定要新依賴 | 現行 RTF 1.2059〔A〕，不加速就無法連續串流；冷啟動首句約 62.9 秒〔A，`manual-tts-verification-latest.md`〕 |
| **GPT-SoVITS api_v2（HTTP chunked）** | 社群用 Windows 本機服務最多，有遊戲實機 29 次串流 0 欠載的紀錄〔B，hodaru 部落格〕 | 是新依賴，需 Johnny 核准 |

### 2.6 TTS 聲音要不要和變聲同一個人（D，推論）

直播中 TTS 與變聲交替出現時，若兩個音色不同，聽眾會察覺。兩種做法：(a) TTS 用同一段女聲參考音做 zero-shot（CosyVoice2/3）；(b) TTS 輸出再過一次 VC。(b) 會疊加 VC 延遲。這件事會改變 TTS 選型，列入下方問題 3。

---

## 3. 哪些決定可以輕易退回，哪些很貴

| 決定 | 可退回程度 | 理由 |
|---|---|---|
| 今天先主測哪個 zero-shot 引擎（MeanVC2／X-VC／Seed） | **便宜** | 都已整合在同一份 backend 契約後面，換引擎只換 profile〔A，`.agent/rules/project.md`〕 |
| 直播 TTS 先用哪個模型 | **便宜**（若先做 adapter） | 只要先定「文字進、PCM 串流出」介面，模型可替換 |
| 自建 App 內混音（Rust cpal／WASAPI） | **中** | 是架構變更，但可和現有 CABLE 路由並存、用開關切換 |
| 投入「訓練型聲線」（收語料＋訓練 RVC／Beatrice） | **貴** | 要花 Johnny 的時間錄音或找授權語料；語料若不合法，模型整批作廢 |
| 安裝虛擬音訊驅動、改系統音訊設定 | **貴** | 系統層級、影響其他軟體；要交管家 |
| 選擇非商用授權的模型（Fish、IndexTTS2、F5） | **貴（之後才發現）** | 一旦直播開始營利就要整條換掉 |
| 刪除配音程式碼 | **貴** | Johnny 13:23 已決定先凍結、共用模組搬出後才拆 |

## 4. 每個方向最便宜、能早點看出對錯的實驗

| 方向 | 最小實驗 | 需要核准？ | 看出什麼 |
|---|---|---|---|
| 端到端能否進 300ms | 用 `exp/bench-e2e-latency` 量既有四引擎的麥克風 → 輸出；同時量「不經引擎的直通」得到裝置＋路由底噪 | 否（已在進行） | 預算是被路由還是被模型吃掉 |
| 路由跳數 | 同一引擎輸出直接進 Voicemod／Voxal 虛擬麥克風 vs 經 CABLE+Light Host+Voicemeeter，比延遲差 | 否（既有裝置） | 自建混音值不值得做 |
| MeanVC2 短 chunk 品質 | 同一段錄音跑 40ms 與 120ms 模型（上游 `run_rt.py --mode file`），讓 Johnny 盲聽 2 段 | 否（已整合），只需排 GPU 鎖 | zero-shot 路線天花板夠不夠 |
| 訓練型是否值得 | 先不訓練；找 1 個社群已公開、可用於 VC 的中文女聲訓練成品聽感比對 | 否（只聽） | 是否值得投入語料與訓練時間 |
| 直播 TTS 首包 | CosyVoice2 既有安裝改用 `stream=True`，量 warm 首包與串流期間 RTF | 否（不新增依賴） | 不加速能否串流；若 RTF 仍 > 1，就證明必須加速或換 GPT-SoVITS 路線 |
| GPT-SoVITS 路線 | 在 `D:\AetherTune-exp\` 獨立 venv 試 GSV-TTS-Lite 首包 | **是**（新依賴） | 是否有 < 200ms 的中文女聲 |

## 5. 社群明確抱怨過、會影響選型的缺陷（補第 0 輪）

- CosyVoice2 串流在併發 ≥4 時 p99 尾延遲約 1.47s（直播單人使用影響小）〔B，issue #1835〕。
- GPT-SoVITS streaming_mode=3 首包最快但長句韻律劣化、總時長可能超過音訊本身 → 播放欠載風險〔B，hodaru〕。
- VCClient 實際延遲是 chunk 設定的 2–3 倍〔B，zenn〕。
- Beatrice 2 男轉女常見「濁聲」，需調 pitch 與格式〔D，note.com〕。
- Seed-VC：推論時間越跑越長（issue #155）、resampler 雜音（PR #123），上游不再修〔D，第 0 輪〕。

## 6. 需要 Johnny 回答的問題（最多 3 題）

已先查：AetherTune `docs/specs/vision.md`（codex/docs-vision）、`docs/status.md`、`docs/reference/open-questions.md`，以及 MyBrainWiki（`.agent/plans/VISION.md`、`qianwen/20-guidelines-for-bots.md`、`qianwen/10-analysis-N001-N999.md`）。MyBrainWiki 沒有 AetherTune 專頁；技術選型偏好已採用於本頁寫法。

### Q1. 直播會不會營利（斗內、訂閱、業配）？
- **為什麼問：**Fish S2、IndexTTS2、F5-TTS、Spark-TTS 權重是非商用；Beatrice 聲線規約限制發言內容。營利與否決定哪些模型可以進候選。
- **影響的決定：**TTS 與 VC 候選清單、是否值得試 Fish／IndexTTS2。
- **選項：**
  1. 純自娛、不營利（非商用模型也可試）
  2. 現在不營利、之後可能營利（只用可商用授權）
  3. 已經或很快營利（只用可商用授權，並保留授權紀錄）
- **建議：**選 2。可商用的 CosyVoice、GPT-SoVITS、IndexTTS2、MeanVC2、X-VC 已足夠覆蓋需求，避免之後整條換掉；已整合的 Breeze TTS 2 屬非商用，選 2 或 3 時不應成為直播主力。

### Q2. 女聲聲線要「不訓練、換參考音就好」，還是願意投入一次訓練？
- **為什麼問：**zero-shot 換聲便宜但自然度天花板較低；訓練型（RVC／Beatrice）社群直播最常用、音色最穩，但要合法語料和約 1–2 小時訓練（＋Johnny 試聽調整的時間）。願景說「不模仿特定人物」、參考聲線待定，open-questions 第 1、7 題也還沒答。
- **影響的決定：**主力路線是 MeanVC2 類 zero-shot 還是訓練型；要不要開始找語料。
- **選項：**
  1. 只做 zero-shot，先挑一段參考音
  2. 先 zero-shot 拿到可用版，若聽評不過再投入訓練
  3. 直接投入訓練：用可商用、允許 VC 訓練的公開女聲語料
  4. 直接投入訓練：用 TTS 合成的女聲當訓練資料
- **建議：**選 2。先用已整合的 zero-shot 做出看得到的進度，聽評結果再決定是否花訓練時間，方向錯了損失最小。

### Q3. 直播 TTS 主要怎麼用，聲音要不要和變聲同一人？
- **為什麼問：**手動打字念出只需要「整句快速首包」；接 LLM 或聊天室自動念要「邊來文字邊念」（雙向串流）。若 TTS 必須和變聲同一個音色，選型會偏向能用同一段參考音的 zero-shot TTS（CosyVoice2/3），或把 TTS 再過一次 VC（加延遲）。
- **影響的決定：**TTS 引擎選型、要不要做文字串流輸入、TTS 是否要經 VC。
- **選項：**
  1. 手動打字念出，音色可以和變聲不同
  2. 手動打字念出，音色要和變聲同一人
  3. 接 LLM／聊天室自動念，音色要同一人
  4. 先不定，先做手動、首包最快的版本
- **建議：**選 2。手動情境最常見，先用已安裝的 CosyVoice2 串流＋同一段女聲參考音驗證（不需新依賴）；若 RTF 不夠，再請核准試 GPT-SoVITS 加速後端；之後要接 LLM 再補文字串流。

---

## 7. 來源清單

- MeanVC2：https://github.com/ASLP-lab/MeanVC2 、https://arxiv.org/html/2606.09050
- X-VC：https://github.com/Jerrister/X-VC 、https://arxiv.org/abs/2604.12456
- Seed-VC：https://github.com/plachtaa/seed-vc
- 延遲實測（Beatrice、Paravo、VCClient）：https://zenn.dev/gokrack/articles/621a2872fd9ccd
- Beatrice：https://huggingface.co/fierce-cats/beatrice-trainer 、https://github.com/Project-Beatrice-V2/Beatrice-colab 、https://note.com/ainanashiko/n/nd1d66d674458
- Applio 即時化：https://github.com/IAHispano/Applio/pull/1245
- VCClient：https://github.com/w-okada/voice-changer
- CosyVoice：https://github.com/QwenAudio/CosyVoice 、https://github.com/FunAudioLLM/CosyVoice/issues/1835 、https://github.com/FunAudioLLM/CosyVoice/issues/1521 、https://github.com/qi-hua/async_cosyvoice
- GPT-SoVITS：https://github.com/chinokikiss/GSV-TTS-Lite 、https://github.com/Lucas1479/Aqua-TTS 、https://blog.hodaru.com/posts/project/bettergi-questvoice/systems/gpt-sovits-streaming-pipeline/
- Fish：https://huggingface.co/fishaudio/s2-pro 、https://speech.fish.audio/install/
- IndexTTS2 串流：https://arxiv.org/html/2607.21042
- Breeze：https://huggingface.co/MediaTek-Research/BreezyVoice 、https://breezeblue.ai/breeze-tts-2 、https://huggingface.co/BreezeBlue/Breeze-TTS-2
- IndexTTS2 授權：https://github.com/index-tts/index-tts/blob/main/LICENSE
- F5-TTS：https://github.com/SWivid/F5-TTS
- Kokoro：https://huggingface.co/sonic-speech/kokoro-82m-bf16 、https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- 授權總表：https://tts.mahimai.ca/open-source-and-open-weight-models/
- 虛擬音訊：https://github.com/VirtualDrivers/Virtual-Audio-Driver
