# AetherTune 研究：13:47 定案與調整後候選（第 2 輪，2026-11-20）

**文件邊界：**本頁是 2026-11-20 當日的研究快照，只供選型參考，不是驗收。採用與否寫進[決策紀錄](../decision-log.md)；實測結果以 `docs/verification/` 分項報告為準。前一份分維度研究見[同日維度文](2026-11-20-realtime-vc-tts-dimensions.md)。

- 基準：研究 worktree `D:\AetherTune-exp\wt-research`，分支 `exp/research-realtime-vc-tts`，父提交 `40c4c29`；對照 `origin/main` `05b1ec4`。
- 本輪只做網路與文件研究：沒有安裝新依賴、沒有使用 GPU、沒有把模型權重下載到磁碟。Hugging Face 連結以 HTTP HEAD 確認為 200；ZIP 只讀中央目錄列出 `.pth`／`.index`，未解壓、未載入引擎。
- **候選篩選已依 2026-11-20 13:47 定案改版，授權只標示不篩選。**
- 證據等級：A＝AetherTune repo 實測（含本輪對公開 URL 的 HEAD／ZIP 目錄核對）；B＝社群獨立量測（附連結）；C＝論文或作者宣稱；D＝論壇、個案或推論。

---

## 1. 三項定案（2026-11-20 13:47）

由內容架構師轉達，Johnny 親口定案（對應維度文 Q1–Q3）。原文如下：

1. 開源專案一律不評估商用授權，全部可以用（含 Breeze TTS 2 等非商用）。研究文件裡可以照實標授權，但不要拿授權來篩候選。
2. 女聲不自己訓練，直接找網路上別人訓練好、穩定的聲音模型，網路找得到的都可以用。
3. 直播 TTS 用手動打字，音色要和變聲同一人，先用 CosyVoice2 驗證。

### 對路線的影響

| 定案 | 影響 |
|---|---|
| 1. 授權只標不篩 | 開源／開權重候選（含 Breeze TTS 2 的非商用權重）全部保留在比較表。授權欄照實寫，作為後續散布或上架時的資訊，不用來淘汰。本輪也不再用「可否商用」縮清單。 |
| 2. 不自己訓練，用現成預訓練模型 | 主力從「先 zero-shot、聽不過再訓練」改為「現成預訓練女聲模型、可直接即時用」。RVC v2 的 `.pth`＋`.index` 是最短路徑（`rvc_runtime.py` 已整合，且**同時要求** weights 與 index）。MeanVC2／X-VC／Seed-VC 仍可用，但屬零樣本，要另備網路現成女聲參考音，不是「載入現成聲線檔就能用」。Beatrice v2 社群有模型，但格式是 Beatrice `.bin`，尚未整合進本 repo。願景仍寫「不模仿特定人物」，與「網路上找得到的都可以用」並存；本輪優先列**通用或中文女聲**，角色／名人模型只作社群使用度對照，不列入優先下載候選（這是產品定位，不是授權篩選）。 |
| 3. 手動打字、與變聲同一音色，先 CosyVoice2 | 直播 TTS 不做 LLM／聊天室雙向文字串流（本階段）。第一驗證是：手動打字 → CosyVoice2 串流模式 → 與變聲同一段女聲參考音。若同參考音聽感不夠，再評估「任意 TTS → 同一個 RVC 女聲模型」統一音色（會多一段延遲，見 §3.2）。 |

VSF 對品質 TTS 的授權歸類（A 級，VSF 分支 `exp/voice-tts-compare` 提交 `df0641c`，本輪未重跑 VSF）：Breeze TTS 2 權重為 BreezeBlue 非商用 v1.1；Qwen3-TTS、VoxCPM2 為 Apache 2.0。依定案 1，三者都可以和 GPT-SoVITS 加速後端一起比首包與 RTF，不因非商用排除 Breeze。

---

## 2. 調整後 VC 候選

原則：**現成預訓練女聲模型、可直接即時用。** 不在本輪規劃自行訓練。

### 2.1 社群預訓練女聲從哪裡來、是什麼格式

| 來源 | 常見格式 | 說明 |
|---|---|---|
| [Hugging Face](https://huggingface.co/) | RVC v2：ZIP 或分開的 `.pth`＋`.index` | 最常見的直接下載點。本輪核對的三個優先候選都在這裡，連結有效。〔A〕 |
| [voice-models.com](https://voice-models.com/)／[v2.voice-models.com](https://v2.voice-models.com/) | 目錄頁＋指向 HF／Drive 的權重 URL；部分有 NISQA／MOS 試聽分 | 便於看近期活躍度與試聽分，權重本身多半仍在 HF。本週活躍榜見 https://v2.voice-models.com/top 。〔B〕 |
| [weights.gg](https://www.weights.gg/) | 同樣轉到 HF 或其他檔案託管 | 社群目錄之一；本輪優先候選未以這裡為唯一來源。〔D〕 |

`services/engines/rvc_runtime.py` 載入時會檢查 `weights` 必須是 `.pth`、`index` 必須是 `.index`，兩者都要已登錄。只有單顆 `.pth`、沒有 index 的發佈（例如部分角色模型只放了 `tingyun.pth`）不能直接丟進現有 Desktop RVC 路徑。〔A〕

### 2.2 引擎層比較（現成模型怎麼接）

| 引擎 | 優點 | 缺點 | 社群使用度 | 與現有引擎相容性 | 估計延遲 | 授權（只標示） | 證據 |
|---|---|---|---|---|---|---|---|
| **RVC v2（已整合）** | 預訓練女聲檔最多；載入即可即時；與 `rvc_runtime.py` 路徑一致 | 延遲高度依賴 chunk／路由，社群端到端常高於 300ms；音質看單一模型品質與男轉女調音 | WebUI 約 39.2k 星、w-okada VCClient 約 21.4k 星；voice-models 目錄以 RVC v2 為主 | **已整合**（CUDA、HuBERT、FCPE／RMVPE、`.pth`＋`.index`） | 模型延遲視 block；VCClient 在 RVC chunk 0.25s 時端到端約 817.5ms〔B〕。本機 E2E 尚未量 | 引擎本身多為 MIT（upstream `realtime_gui.py` 註記）；**各聲線模型授權另計**，社群檔多數未標 | 相容性與載入契約〔A，`rvc_runtime.py`〕；延遲〔B，https://zenn.dev/gokrack/articles/621a2872fd9ccd 〕 |
| **Beatrice v2（未整合）** | 作者目標約 50ms 級 VST 延遲；有社群／資料集預訓練聲線 | 格式是 `.bin`＋`model.toml`（paraphernalia），不能當 RVC 權重用；要新依賴與新 runtime；官方模型目錄目前幾乎不是通用女聲 | 官方 VST／VCClient 生態；HF 上有 VCTK 女聲 Beatrice 包（如 `Nekochu/RVC-VCTK_Voice-sample` 的 `F/p231` 等）及個別角色模型 | **未整合**；與 `rvc_runtime.py` 不相容 | VST 約 50.7ms、client（WASAPI）約 138.7ms〔B，同上 zenn〕 | 訓練器／部分權重標 MIT〔C，https://huggingface.co/fierce-cats/beatrice-trainer 〕；個別聲線可能另標 personal use | 延遲〔B〕；格式與模型存在〔C／A 目錄頁〕 |
| **MeanVC2（已整合，零樣本）** | 不必為每個聲線準備 `.pth`；換網路現成女聲參考音即可；模型 p95 已有本機數字 | 不是「下載聲線檔就能用」；自然度天花板與參考音品質綁在一起；社群預訓練「聲線包」不如 RVC 多 | 上游仍在維護（第 0 輪記錄最後 push 2026-09-13） | **已整合** | 模型 p95 94.7ms〔A，`realtime-vc-verification-latest.md` 2026-10-01〕；上游宣稱首包約 110ms〔C〕 | README 寫 Apache-2.0，第 0 輪記沒有 LICENSE 檔 | 延遲〔A／C，第 0 輪〕 |
| **X-VC（已整合，零樣本）** | 模型 p95 最低的已整合引擎之一；同樣用參考音即可換女聲 | 架構本身有 240ms 延遲，光模型路徑就可能吃掉大半 300ms 預算 | 相對新、社群聲線生態小 | **已整合** | 模型 p95 79.6ms〔A〕；架構延遲 240ms〔C，https://arxiv.org/abs/2604.12456 〕 | MIT | 〔A／C，第 0 輪〕 |
| **Seed-VC（已整合 tiny，零樣本）** | 可用現成女聲參考音；權重已有本機備份路線 | 上游已封存；Johnny 決定不評估 fork，只備份原版；模型延遲高於 MeanVC2 | 原版約 3.9k 星，已 archived | **已整合 tiny**；原版已依決策備份，不擴評估 | 模型 p95 175.7ms〔A〕 | GPL-3.0 | 〔A，第 0 輪〕 |

零樣本三條路（MeanVC2／X-VC／Seed-VC）的「現成女聲」是**參考音頻**，不是 RVC 權重。下一輪若走這條，應另備一段可公開取得的中文或通用女聲乾聲（本輪不下載）。

### 2.3 優先下載候選：2–3 個可下載、評價較穩的中文或通用女聲 RVC 模型

挑選條件（實用，不是授權篩選）：(1) 公開 URL 本輪 HEAD 為 200；(2) 套件內同時有 `.pth` 與 `.index`，能對上 `rvc_runtime.py`；(3) 標成中文或通用女聲，而非特定遊戲／VTuber／名人角色；(4) 有可引用的社群使用或品質分數，或授權與訓練說明清楚。以下**只列不下載**。

#### 候選 A：E-Girl（Realistic Girl Voice）— 通用女聲

- 規格：RVC v2、RMVPE、600 epochs；作者自述約 30 分鐘資料、偏寫實女聲。〔C，模型頁說明〕
- 目錄頁：https://v2.voice-models.com/model/1uZvOaYhqJv （本輪 HEAD 200）
- 權重（Hugging Face，本輪 HEAD 200，ZIP 221,389,729 bytes）：https://huggingface.co/pendmg/Models/resolve/main/egirl.zip
- ZIP 目錄（只讀中央目錄，未解壓）：`egirl.pth`（未壓縮 57,589,001 bytes）、`added_IVF2182_Flat_nprobe_1_egirl.index`（未壓縮 268,856,419 bytes）。〔A〕
- 社群使用度：2026-11-20 查 `v2.voice-models.com/top` 列第 3，近 7 日約 77 名活躍使用者；平台試聽分峰值約 5.02 MOS，女聲參考音 pitch 0 約 4.89 NISQA。〔B〕
- 優點：通用女聲、活躍度在本週榜上最高之一、格式完整、與現有 RVC runtime 相容。
- 缺點：資料與授權未在 HF 倉庫標明（`pendmg/Models` 無 LICENSE）；index 很大（解壓後約 256 MiB），載入與磁碟佔用較高；「寫實」是作者與平台分數，本 repo 尚未聽評。〔C／D〕
- 估計延遲：與其他 RVC v2 模型同一 runtime，延遲差在模型大小與 index 探查，預期仍由 chunk／路由主導，而不是這顆權重本身。〔D〕
- 授權（只標示）：倉庫未標授權；社群重分配，權利狀態不明。
- 證據等級：連結與檔案清單 **A**；活躍度與平台分數 **B**；音質與即時聽感 **C／D**（尚未本機聽評）。

#### 候選 B：Chinese Bluetooth Speaker lady（Meeco，350 epochs）— 中文女聲

- 規格：RVC v2、RMVPE、Ov2 pretrain、40 kHz、350 epochs；目錄標 Chinese／female。〔C，https://v2.voice-models.com/model/1qKNXLdLcSy 〕
- 目錄頁：https://v2.voice-models.com/model/1qKNXLdLcSy （本輪 HEAD 200）
- 權重（Hugging Face，本輪 HEAD 200，ZIP 53,927,764 bytes）：https://huggingface.co/Meeco/MeecoRVC/resolve/main/chinesebluetooth.zip
- ZIP 目錄（只讀中央目錄，未解壓）：`chinese_bluetooth_speaker.pth`（未壓縮 55,231,605 bytes）、`added_IVF39_Flat_nprobe_1_chinese_bluetooth_speaker_v2.index`（未壓縮 4,835,739 bytes）。〔A〕
- 社群使用度：2024-01-29 已在目錄上架，屬流傳較久的中文女聲包；平台「收藏」數偏低（本輪目錄頁顯示約 2 saved），且沒有 E-Girl 那種本週活躍榜名次。〔B／D〕
- 優點：中文、通用裝置聲線而非特定角色、檔案小、`.pth`＋`.index` 完整、與 `rvc_runtime.py` 相容。
- 缺點：index 很小（IVF39），音色鎖定可能弱於大 index 模型；平台缺少本輪可引用的穩定 MOS 表；授權未標；聲線來源（藍牙音箱示範音等）權利狀態不明。〔D〕
- 估計延遲：權重與小 index 理論上對載入較友善，執行期仍應接近其他 40k RVC v2。〔D〕
- 授權（只標示）：`Meeco/MeecoRVC` 未標授權。
- 證據等級：連結與檔案清單 **A**；「使用久、目錄仍在」**B／D**；音質 **D**（本輪無獨立聽評）。

同聲線另有較新的 200 epoch 包（標題與資料夾名稱的 epoch 不一致，下載檔是 `Bluetoothlady_200e.pth`），本輪亦 HEAD 200：https://huggingface.co/SunShineFlower/Chinesebluetoothlady_400epoch/resolve/main/Bluetoothlady.zip （內含 `Bluetoothlady_200e.pth` 與 `added_Bluetoothlady_v2.index`）。〔A〕若候選 B 損壞或下架，可當備援，不當第一選擇。

#### 候選 C：maobailing_rvc — 中文女聲，說明最完整

- 規格：RVC v2、40 kHz、f0＝1、HuBERT 768＋RMVPE；作者建議 `index_rate=0.6`、`f0_method=rmvpe`。〔C，模型卡〕
- 模型卡：https://huggingface.co/maotianchen/maobailing_rvc （本輪 HEAD 200）
- 權重（本輪 HEAD 200）：https://huggingface.co/maotianchen/maobailing_rvc/resolve/main/maobailing_rvc.pth （55,225,035 bytes）
- Index（本輪 HEAD 200）：https://huggingface.co/maotianchen/maobailing_rvc/resolve/main/maobailing_rvc.index （92,566,459 bytes）
- 另有 `maobailing_rvc_trained.index`、`LICENSE`（Apache-2.0）、`PARAMS.md`。〔A，HF API 檔案清單〕
- 社群使用度：HF API 本輪讀到 downloads＝488、likes＝2；沒有出現在本週 voice-models 活躍榜。〔A／B〕
- 優點：中文女聲、`.pth`／`.index` 分檔清楚、訓練參數與建議設定寫明、授權清楚，最容易對上 repo 的 model register。
- 缺點：訓練資料聲明為 IndexTTS 2 的克隆產物、沒用真人錄音〔C，模型卡〕，音色可能帶 TTS 腔，和「聽不出是變聲」的願景可能衝突，必須聽評後才能量產；活躍度低於 E-Girl。
- 估計延遲：與其他 40k RVC v2 同量級。〔D〕
- 授權（只標示）：Apache-2.0（權重倉庫 `LICENSE`）。訓練資料來自 IndexTTS 2 輸出，使用時仍須遵守該上游與場景限制（作者模型卡亦如此提醒）。
- 證據等級：連結與檔案存在 **A**；訓練來源與推薦參數 **C**；音質與即時穩定性 **D**。

### 2.4 已在本機、可先試但不列入「新下載」的模型

`docs/reference/current-rvc-model-inventory.md`（盤點 2026-09-20）已有成對的 `Sage_CN_HeroicFemale`（中文英雄女聲）與 `Kafka_CN_Yujie`（角色名），狀態都是 `candidate / metadata waiting`，來源與授權尚未核完。下一輪若要先聽現成檔，可從 `Sage_CN_HeroicFemale` 開始，不必先下載；不把角色模型當產品預設聲線。〔A〕

### 2.5 有活躍度、但本輪不列入優先下載的例子（對照用）

- Furina CN（原神中文，約 39 名 7 日活躍使用者、平台約 4.46 MOS）權重在 Google Drive，不在 HF：https://v2.voice-models.com/model/9Qd 〔B〕
- 停云／Tingyun（崩壞：星穹鐵道，平台有試聽分）HF 上目前只有 `tingyun.pth`、沒有 index，對不上 `rvc_runtime.py`：https://huggingface.co/jsnsbsbjwj/ty/resolve/main/tingyun.pth （本輪 HEAD 200）〔A〕

這些說明「中文女聲在社群很活躍」，但要嘛是特定角色、要嘛格式不完整，故不進 §2.3。

---

## 3. 調整後直播 TTS 候選

使用方式已定：**手動打字**，音色必須和變聲**同一人**。不做本階段的 LLM 雙向文字串流。

### 3.1 路線 (a)：CosyVoice2 零樣本串流，共用同一段女聲參考音（第一驗證）

- 做法：變聲（若走零樣本引擎）與 TTS 都用同一段女聲參考音；若變聲改走 RVC 預訓練模型，TTS 仍用該聲線的參考乾聲（或從該模型輸出錄一小段）做 CosyVoice2 prompt，目標是聽起來像同一人。
- 優點：CosyVoice2 已在現有環境，**不需新依賴**；支援串流；零樣本克隆與中文語境成熟。
- 缺點：首包數字依硬體、是否 Triton／TRT-LLM、以及「整句打完再串流輸出」還是「逐詞雙向串流」差異很大；PC2 RTX 2060 12GB 尚未量過。
- 首包／RTF（須標清情境，不可混為一個數字）：
  - 作者宣稱首包可到約 150ms，品質損失很小。〔C，https://fun-audio-llm.github.io/cosyvoice2/ 〕
  - 官方 Triton／TRT-LLM、單張 L20、concurrency＝1：串流首塊平均約 190–220ms，RTF 約 0.12；開 `use_spk2info_cache` 時平均約 190ms。〔C，https://github.com/FunAudioLLM/CosyVoice/blob/main/runtime/triton_trtllm/README.Cosyvoice2.Unet.md 〕
  - 社群在單張 RTX 4090、concurrency＝1：P50 約 335ms，RTF 約 0.114。〔B，https://github.com/FunAudioLLM/CosyVoice/issues/1835 〕
  - 獨立論文在 A100 上測 **full-stream（逐詞餵入）**：CosyVoice2 首包 1643ms、RTF 0.85。這是雙向文字串流情境，**不是**本輪「整句打完再念」的主情境，只作對照。〔B，https://arxiv.org/abs/2509.15969 〕
- 授權（只標示）：依上游 CosyVoice／權重頁標示（本輪不展開篩選）。
- 證據等級：現有環境可跑、不必新裝 **A**（整合狀態，第 0 輪／契約）；延遲數字 **C／B**；PC2 實測尚無，標 **WAITING**。

### 3.2 路線 (b)：任意 TTS → 再過同一個 RVC 女聲模型，統一音色

- 做法：TTS 可用預設聲或另一段參考音快速出聲，輸出 PCM 再送進與麥克風變聲同一顆 RVC 女聲模型（§2.3 下載的其中一顆，或本機 `Sage_CN_HeroicFemale`）。
- 優點：TTS 選型與聲線解耦；即使 CosyVoice2 克隆不夠像，也能硬性統一到 RVC 目標聲。
- 缺點：多一段轉換，延遲與偽影都會疊加；TTS 腔再經 RVC 可能有雙重人工感。〔D〕
- 額外延遲估算（尚未實測，**D**）：
  - **同一行程內**把 TTS PCM 直接餵給已載入的 RVC：大約再加一個 RVC block／chunk＋SOLA。社群 VCClient 在 chunk 0.25s 時端到端約 817.5ms，其中含裝置緩衝；若只計模型路徑，粗估 **＋80–300ms**。〔D，外推自上述 B 級量測〕
  - **再繞一圈虛擬裝置**（TTS → 虛擬線 → 與麥克風同一條 VC 鏈）：會再疊「即將量到的麥克風 E2E」，很容易超過 100–300ms 預算。〔D〕
- 建議：第一驗證走 (a)；只有 (a) 聽感明顯不像同一人時，才用 (b)，並且必須行程內串接，避免第二跳裝置。

### 3.3 備選加速／替代（授權只標示，不篩選）

皆需新依賴或新權重管線，**不可在未批准前安裝**。數字多半是作者或官方基準，硬體優於 PC2。

| 系統 | 首包／TTFA | RTF | 授權（只標示） | 與同音色路線的關係 | 證據 |
|---|---|---|---|---|---|
| **GPT-SoVITS 加速後端：GSV-TTS-Lite** | 作者在 RTX 3050 Laptop：原版串流 436ms；Lite 關 FlashAttention 150ms；開 FlashAttention **133ms** | 0.125／**0.108**（同上，Lite） | 依該專案與 GPT-SoVITS 上游標示 | 可用參考音靠近目標聲，或把輸出再送進 RVC（路線 b） | 〔C，https://github.com/chinokikiss/GSV-TTS-Lite 〕 |
| **GPT-SoVITS 加速後端：Aqua-TTS** | 維度文已列為候選加速層；本輪未在其 TECHNICAL.md 抽到可單獨引用的首包表，數字待批准後實測 | 未在本輪核到可單獨引用的官方 RTF 表 | 依該專案與上游標示 | 同上，屬執行策略加速，不換權重 | 〔C，https://github.com/Lucas1479/Aqua-TTS ；細節待補〕 |
| **Qwen3-TTS** | 模型卡／技術報告：端到端首包低至約 **97ms**（0.6B 檔） | 本輪未逐表核對報告中的 RTF，不寫死 | Apache 2.0〔A，VSF `df0641c`〕 | 支援參考音克隆，可走路線 (a) 的替代引擎，或輸出再進 RVC | 〔C，https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base 、https://arxiv.org/abs/2601.15621 〕 |
| **VoxCPM2** | 官方模型卡**沒有**公布首包；本輪不採用極低 TTFA 的第三方 Turbo 數據集數字（可能含快取靜音，證據不足） | 官方：RTX 4090 約 **0.30**（PyTorch）、約 **0.13**（Nano-vLLM） | Apache 2.0〔A，VSF `df0641c`；模型卡亦寫 commercial-ready〕 | 支援短樣克隆與串流 `generate_streaming`，可當 (a) 的替代 | 〔C，https://huggingface.co/openbmb/VoxCPM2 〕 |
| **Breeze TTS 2** | 官方站 TTFA p50 127.2ms、有串流 API〔C〕；HF 模型卡稱 H100 熱路徑 TTFA **低於 40ms**〔C〕 | **本 repo 在 RTX 5060 Ti 實測 RTF 4.3–11.4，離即時很遠**〔A，`breeze-tts2-verification-latest.md`，維度文已引用〕；HF 稱 H100 熱路徑 RTF 0.32〔C〕 | 權重：BreezeBlue Research and Non-Commercial License／VSF 歸類為 BreezeBlue 非商用 v1.1〔A，VSF `df0641c` 與維度文〕。依定案 1 **不因此淘汰**。原始碼另標 Apache-2.0，與權重授權分離〔C，HF 模型卡〕 | 已整合為配音引擎，有 `FastBreezeStreamingRuntime`〔A，`tools/breeze-tts2-infer.py`〕；中文女聲 Voice Design／Clone 在 repo 已有 PASS〔A〕。但以本機 RTF 來看，**不適合作直播即時主力**，除非之後批准專門的即時路徑並重測 | 本機 RTF **A**；官方低延遲數字 **C**（硬體是 H100，與 PC1／PC2 不可比） |

比較結論（不做總排名，只約束下一輪）：要驗證「手動打字、與變聲同一人」，成本最低的是路線 (a) 的 CosyVoice2（已在環境裡）。GPT-SoVITS 加速、Qwen3-TTS、VoxCPM2 的作者數字看起來都有機會接近或優於 CosyVoice2 的社群首包，但都要新依賴，須先批准。Breeze TTS 2 不因非商用排除，可是本機 RTF 已顯示不是即時主力。

---

## 4. 下一輪計畫（最小實驗，已排序）

1. **E2E 直通基線＋MeanVC2**（環境重建完成後）：在 `exp/bench-e2e-latency` 先跑 `-Engine none`，再跑 `-Engine meanvc2`（及其他已整合引擎，視時間）。先登記 `D:\BotOps\locks.md` 再使用 GPU。這仍是第一優先，用來量麥克風到輸出的端到端，而不是模型卡數字。
2. **CosyVoice2 串流模式量首包與 RTF**：用現有環境，不裝新依賴。情境對齊定案 3：手動打完整句、串流輸出、固定一段女聲參考音。記錄硬體（先寫 PC2 RTX 2060 12GB 或實際所用機器）、首包、RTF、是否與參考音像同一人（聽感，不偽裝成儀器 PASS）。
3. **下載 1–2 個預訓練 RVC 女聲模型到 `D:\AetherTune-exp\models\`，試即時**：模型權重下載不算新套件，但仍要先登記 `D:\BotOps\locks.md` 才用 GPU。建議順序：本機已有的 `Sage_CN_HeroicFemale`（若檔案還在）聽一輪 → 再下載候選 B（中文、檔小）與候選 A（通用、活躍度高）之一或之二。候選 C 作授權／文件最清楚的備援。登錄進 experimental 目錄，不寫入 main 的 model register，除非另有決策。
4. **需批准的新依賴清單**（本輪只列，不安裝）：
   - GPT-SoVITS 加速後端：建議先在 GSV-TTS-Lite（`pip install gsv-tts-lite`，另視情況需要 FlashAttention 輪子）與 Aqua-TTS 之間擇一再開卡，不要兩套同時裝。
   - Qwen3-TTS：`pip install -U qwen-tts` 與對應權重（例如 `Qwen/Qwen3-TTS-12Hz-0.6B-Base`）；官方另建議可選 `flash-attn`。
   - VoxCPM2：`pip install voxcpm` 與 `openbmb/VoxCPM2` 權重（官方建議 Python ≥ 3.10、PyTorch ≥ 2.5、CUDA ≥ 12.0，VRAM 約 8GB）。
   - Breeze TTS 2 不另列為「新引擎依賴」（配音路徑已整合），若要為直播重測串流熱路徑，只申請該次 GPU 時間與是否啟用額外加速旗標，不預設新裝。

完成 1–2 後，用實測首包／E2E 再決定要不要把第 4 項開成批准卡。

---

## 5. 來源清單

- 定案來源：2026-11-20 13:47，內容架構師轉達 Johnny 親口定案（Q1–Q3）。
- VSF 授權歸類：`exp/voice-tts-compare` `df0641c`（A 級，本輪未重跑）。
- RVC 目錄與活躍榜：https://v2.voice-models.com/top 、https://v2.voice-models.com/model/1uZvOaYhqJv 、https://v2.voice-models.com/model/1qKNXLdLcSy
- 權重 URL：見 §2.3；另 https://huggingface.co/maotianchen/maobailing_rvc 、https://huggingface.co/SunShineFlower/Chinesebluetoothlady_400epoch/resolve/main/Bluetoothlady.zip
- Beatrice 模型例：https://huggingface.co/Nekochu/RVC-VCTK_Voice-sample 、https://github.com/Project-Beatrice-V2/Beatrice-voice-models 、https://huggingface.co/fierce-cats/beatrice-trainer
- 延遲（Beatrice／VCClient）：https://zenn.dev/gokrack/articles/621a2872fd9ccd
- CosyVoice2：https://fun-audio-llm.github.io/cosyvoice2/ 、https://github.com/FunAudioLLM/CosyVoice/blob/main/runtime/triton_trtllm/README.Cosyvoice2.Unet.md 、https://github.com/FunAudioLLM/CosyVoice/issues/1835 、https://arxiv.org/abs/2509.15969
- GSV-TTS-Lite：https://github.com/chinokikiss/GSV-TTS-Lite
- Aqua-TTS：https://github.com/Lucas1479/Aqua-TTS
- Qwen3-TTS：https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base 、https://arxiv.org/abs/2601.15621
- VoxCPM2：https://huggingface.co/openbmb/VoxCPM2
- Breeze TTS 2：https://huggingface.co/BreezeBlue/Breeze-TTS-2 、https://breezeblue.ai/breeze-tts-2
- 本 repo：`services/engines/rvc_runtime.py`、`docs/reference/current-rvc-model-inventory.md`、[維度文](2026-11-20-realtime-vc-tts-dimensions.md)、[第 0 輪](2026-11-20-round0-seedvc-engines-latency-tts-split.md)
