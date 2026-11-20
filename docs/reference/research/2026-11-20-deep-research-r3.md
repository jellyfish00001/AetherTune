# AetherTune 研究：第 3 輪深入研究——RVC 自然度、低延遲極限、女聲模型、直播 TTS 加速、同人音色、Discord／OBS 路由（2026-11-20）

**文件邊界：**本頁是 2026-11-20 下午的研究快照，只供選型與實驗設計參考，**不是決策、不是驗收、也不改任何正式規範**。採用與否寫進[決策紀錄](../decision-log.md)；實測 PASS／WAITING／BLOCKED 以 `docs/verification/` 分項報告為準；分類規則以 [LIVE_GATE](../../specs/live-gate.md) 為準。本頁末尾的「建議納入規範」全部**待 Johnny 確認**，本輪沒有動任何正式文件。

- 前序研究（先讀過，本頁不重複）：[第 0 輪](2026-11-20-round0-seedvc-engines-latency-tts-split.md)（Seed-VC 封存、替代引擎）、[分維度選項](2026-11-20-realtime-vc-tts-dimensions.md)（§0 延遲預算、§1 VC 六個維度、§2 TTS 六個維度）、[第 2 輪定案與候選](2026-11-20-decisions-and-candidates-r2.md)（現成女聲 RVC 候選 A/B/C、TTS 路線 a/b）。
- 本輪新增的本機實測（A 級）來自兩條實驗分支，本頁只引用、不複製：
  - `exp/bench-e2e-latency` `80fbdca`：`docs/reference/research/2026-11-20-pc2-e2e-latency-results.md`（PC2 RTX 2060，聲學量測）。
  - `exp/live-tts-bench` `255c12a`／`7eba880`：`docs/reference/research/2026-11-20-live-tts-bench.md`、`docs/reference/research/2026-11-20-live-tts-acceleration.md`（PC1 RTX 5060 Ti 16GB，獨占 GPU 量測）。
- 本輪只做網路與文件研究：沒有安裝、沒有用 GPU、沒有碰 PC2、沒有改程式。外部內容只放連結，沒有把檔案、模型或權重放進 repo。
- 證據等級：**A**＝AetherTune 本機／repo 實測；**B**＝社群獨立實測（附連結）；**C**＝論文、官方 README 或作者聲稱；**D**＝論壇、教學、個案或推論。授權只標示、不篩選（Johnny 13:47／13:51 定案）；只有**付費**才特別標出。

---

## 0. 本輪最重要的 11 個發現（先看這段）

| # | 發現 | 證據 | 對 AetherTune 的意思 |
|---|---|---|---|
| 0 | **上游 RVC realtime 本來就有共振峰（formant）參數，AetherTune 寫死成 0.0**；社群公認男轉女要「音高與共振峰同向抬」 | A〔`services/engines/rvc_runtime.py` 第 130 行〕、C〔上游 `infer/rtrvc.py`〕、D〔miaoyin〕 | 不加依賴就能試的最大自然度改善；見 §1.1、實驗 E1 |
| 1 | 社群公認「男轉女聽起來假」的第一名不是音色，是**韻律（語調起伏、句尾、語速）**；第二名才是「只拉音高、不動共振峰」 | D〔miaoyin 教學 8 條、babiniku.rs #48 的排序假設〕 | 參數調完後，剩下的差距要靠**說話方式**與**韻律處理**，不是再換模型 |
| 2 | **下游 App 再處理一次**（Discord 雜訊抑制／Krisp、回音消除、自動增益）是最常見的「變聲發悶、電音」來源 | B／D〔Soundpad FAQ、VoxBooster、miaoyin 第 8 條〕 | Discord 端必須關掉三個開關；這是零成本、最高 CP 值的一步 |
| 3 | Discord 預設語音頻道位元率 64 kbps，Server Boost 才能 128／256／384 kbps | C〔Discord 官方 FAQ〕 | 64 kbps Opus 會把 RVC 的高頻細節與破綻一起抹平；聽評一定要「過 Discord 之後」再聽 |
| 4 | VB-CABLE 的內部延遲上限約 2048／2 樣本＝21.3 ms（48 kHz），作者估實際約 14.2 ms；真正吃延遲的是**接在兩端的 App 緩衝**與 Voicemeeter 的 A1 裝置 | C〔VB-Audio 作者論壇回覆〕 | 我們量到「兩條虛擬線約 120–130 ms」〔A〕遠大於線本身，表示大頭在 Light Host／Voicemeeter／WASAPI 共享緩衝，**可以壓** |
| 5 | RVC 官方 README 宣稱 realtime GUI 端到端 170 ms、ASIO 進出 90 ms | C〔RVC README.en〕 | 我們的 RVC 淨延遲 p50 102.5 ms〔A〕已接近官方 ASIO 數字；剩下的是路由 |
| 6 | VCClient 實際延遲約為 chunk 設定的 2–3 倍；GUI 顯示的 `res` 數字比實測小很多（顯示 130 ms、實測 622 ms） | B〔zenn gokrack、natade 日記〕 | 與我們「引擎 trace 比聲學量測少 90–240 ms」〔A〕一致：**只能信聲學量測** |
| 7 | 低延遲 pitch：FCPE 在 RTX 4090 上 RTF 0.0062，比 RMVPE 快約 5.3 倍；但獨立 benchmark 的準確度 RMVPE（F1 0.768）> FCPE（0.728），SwiftF0 0.781 且 CPU 很快 | C〔FCPE 論文〕、B〔lars76/pitch-benchmark〕 | 我們最佳設定用 fcpe〔A〕；若出現「破音、八度跳」，下一個要試的是 RMVPE 或 SwiftF0，不是 crepe |
| 8 | 直播 TTS：VoxCPM2 用 Nano-vLLM 在 RTX 4090 單請求 TTFB 約 36 ms、RTF 約 0.086，但**一定要 flash-attn**，Windows 要自備 wheel；依賴 `triton-windows<3.5` | C〔nano-vllm-voxcpm PyPI v2.0.5〕 | 這是把 VoxCPM2 從本機 RTF 0.76–0.78〔A〕拉到直播等級的最強候選；要 Johnny 核准再裝 |
| 9 | Fish S2 Pro 在**和 PC1 同型號的 RTX 5060 Ti 16GB**、Windows 上用 audio.cpp Q4_K GGUF：首音 0.14–0.31 s、RTF 中位數 1.00、VRAM 7.0 GB | B〔andreaabcj-cmd 實測 README〕 | 首包夠快但 RTF≈1，長句會斷；不如 GSV-TTS-Lite〔A：首包 87–128 ms、RTF 0.10–0.13〕。權重**非商用**（只標示） |
| 10 | CosyVoice2 的 TensorRT-LLM＋Triton 串流在 L20 單併發首包約 185–220 ms；RTX 4090 使用者回報 p50 約 335 ms；H100 使用者單併發約 160 ms | C〔官方 runtime README〕、B〔issue #1835、#1806〕 | CosyVoice2 能變快，但路線是 **Linux／Docker＋Triton**；我們在 WSL 原版 4.4–7.1 s〔A〕的差距主要是「沒走這條路」，不是模型本身 |

---

## 1. 維度一：RVC 即時變聲「聽起來自然」的關鍵

前序文件已比較引擎（RVC／Beatrice／MeanVC2／Seed-VC），本節只談**同一個 RVC 引擎裡，哪些設定與前後處理決定聽不聽得出來**。

### 1.1 參數總表（男轉女、說話用途）

| 參數 | 社群常見起點 | 調高的效果／風險 | 調低的效果／風險 | 我們目前（A） | 證據 |
|---|---|---|---|---|---|
| 音高（transpose） | 男轉女 **+10～+12**，不超過 +14；本音與模型接近時 +3～+5 | 太高 → 卡通、緊繃；「花栗鼠音」 | 太低 → 女聲模型唱男音、混濁 | RVC Sage 設定以 bench 預設為準，尚未系統掃描 | D〔miaoyin 110137／110248、xportstudio〕、C〔w-okada 教學 +12〕 |
| 共振峰（formant） | 與音高**同向小幅抬高**；少女音略抬、御姐音音高 +10 且共振峰略壓 | 太高 → 小孩聲 | 不動 → 「音高變了腔體沒變」，大腦立刻識破 | **固定 0.0**：`services/engines/rvc_runtime.py` 呼叫 `RVC(values["pitch"], 0.0, …)`，第二個參數就是上游的 formant | A〔repo 程式碼〕；C〔上游 `infer/rtrvc.py`、`realtime_gui.py`「性别因子/声线粗细」滑桿 −2～+2〕；D〔miaoyin〕；C〔Applio formant shifting〕 |
| Index rate（檢索比例） | 0.3～0.75；沒有 index 時 0；即時用途比離線低 | 更像目標，但訓練資料的噪音也會被拉進來、更吃效能 | 更乾淨、但更像自己的音色 | 依模型預設 | B〔Samer Al-Qaisi〕、C〔AI Hub docs〕、D〔miaoyin 0.2～0.5〕 |
| Protect（無聲子音保護） | 0.33；0.5＝關閉 | — | 太低 → 字被吞掉、「不像人」 | 0.33 類預設 | C〔AI Hub docs、xportstudio〕 |
| f0 方法 | 即時：FCPE 或 RMVPE；crepe 太慢不適合即時 | RMVPE 準但聲音略「硬」 | FCPE 快但較怕噪音 | **fcpe**（最佳組合） | C〔FCPE 論文 RTF 表〕、B〔pitch-benchmark〕、D〔AI Hub：RMVPE 略刺、FCPE 較柔〕 |
| RMS mix rate | 說話 0～0.25（保留自己的音量起伏） | 越高越跟模型訓練音量走，動態變平 | 保留表演 | 依預設 | C〔xportstudio、DeepWiki RVC 參數表〕 |
| Filter radius | 3（只對 harvest／dio 有效） | — | — | 不適用（fcpe） | C〔OpenVoiceChanger 環境變數說明〕 |
| 模型本身 | 選與本音「條件接近」的：清亮年輕男聲 → 少女；低沉男聲 → 中性女聲／御姐 | 跨度太大必失真 | — | Sage／ChineseBluetooth_F／EGirl_F 三選一，試聽檔待做 | D〔miaoyin 第 4 條〕 |

**關鍵發現：**
- 「音高 +12、共振峰不動」是社群最常點名的經典破綻。**上游 RVC realtime 早就有共振峰參數，AetherTune 只是寫死成 0.0**〔A，`services/engines/rvc_runtime.py` 第 130 行 `RVC(values["pitch"], 0.0, …)`〕。上游做法是把輸出長度乘上 `2^(formant/12)` 再重採樣、同時把 f0 key 扣掉 formant〔C，上游 `infer/rtrvc.py` 約第 279–287 行〕；上游 GUI 的滑桿範圍是 −2～+2、步進 0.05〔C，`realtime_gui.py`〕。**這代表補共振峰不需要任何新依賴**，只要把 values 裡多一個 `formant` 傳進去，是本輪找到 CP 值最高的一個實驗。
- Beatrice v2 的使用教學一律是「Pitch 與 Formant 一起往上調」〔D，note.com uunin、shellbe〕；Beatrice 把共振峰當一級參數，是它在 VTuber 圈評價自然的原因之一。〔D〕
- Index rate 不只影響音色：w-okada 教學說 index>0 會讓搜尋時間變長〔C〕；Applio 的即時化 PR 把 index 檢索改成純 PyTorch 暴力搜尋以省延遲〔C，Applio PR #1245〕。所以即時用途的 index rate 要和延遲一起掃，不能只憑耳朵。

### 1.2 社群公認的「破綻清單」與對應手段

| 破綻 | 什麼時候出現 | 對應手段 | 證據 |
|---|---|---|---|
| 韻律像男生（語調平、句尾硬、語速快） | 參數都對了還是被聽出來 | 說話方式訓練：起伏大一點、語速稍慢、尾音軟化；或 F0 輪廓正規化／擴張到參考女聲的統計範圍 | D〔miaoyin 110249「男變女，從音調練到說話習惯」、babiniku.rs #48 假設 1〕 |
| 「花栗鼠音」 | 只拉音高 | 共振峰同向抬、換跨度較小的模型 | D〔miaoyin〕 |
| 金屬聲、電流感 | chunk／緩衝壓太低，或推理時間長期大於 chunk | 加大 chunk 或降負載；看 RTF 是否 < 1 | D〔miaoyin 第 7 條〕、A〔我們 RTF 0.47 時無 underrun〕 |
| 「機關槍」斷續 | 推理追不上 | 同上；RVC GUI 使用者把 block 拉到 0.12 s 以下會在停頓時卡住 | B〔RVC issue #1283〕 |
| 發悶、高頻被抹掉 | 降噪開太滿（NVIDIA Broadcast、RVC 輸入／輸出降噪、Discord Krisp） | 只降「底噪」，不求「絕對安靜」；Discord 端關閉雜訊抑制 | D〔miaoyin 第 5、8 條〕、D〔w-okada issue #1525：sup1／sup2 會吃掉讓聲音自然的口腔小雜音〕 |
| 笑聲、咳嗽、氣音、長「ssss」變形或消失 | 非語音聲音本來就難轉 | 保留呼吸（protect 不要太低）、避免過強 noise gate；這些是「抓變聲」的人會故意測的 | D〔aivoicedetector 7 signs、AI Hub artifacting〕 |
| 高頻「閃爍」（synthetic shimmer） | 頻寬延伸（BWE）或 vocoder 造出 8 kHz 以上 | 這在 X-VC 特別明顯；對 RVC 而言是 index 與訓練資料品質問題 | D〔babiniku.rs #48 假設 2、AI Hub dataset docs〕 |
| 動態被壓平（聽起來「像錄好的」） | 輸出端 leveler／limiter 太重 | 壓縮輕一點、慢一點；RMS mix rate 低 | D〔babiniku.rs #48 假設 4〕 |
| 爆音／底噪被放大成電音 | 麥克風增益不對 | 說話峰值在電平 60%～75%、距離 15～20 cm | D〔miaoyin 第 1 條〕 |

### 1.3 前後處理鏈（EQ、壓縮、de-esser、降噪）

| 位置 | 社群做法 | 理由 | 證據 |
|---|---|---|---|
| **VC 前**：noise gate | −48～−60 dB 起，配輕微高通 | 讓 VC 不轉換底噪；太高會切掉字頭 | D〔Reddit TransVoicechangers 摘要、RVC Fabric 說明〕 |
| **VC 前**：降噪 | 適度；RNNoise／NVIDIA Broadcast 只開低強度 | 降噪越強，送進 HuBERT 的高頻越少，輸出越悶 | D〔miaoyin、w-okada #1525〕 |
| **VC 後**：EQ | 依目標女聲長期頻譜（LTAS）微調；babiniku.rs 正在做「輸出頻譜貼近參考說話者 LTAS」 | 補償模型與麥克風的頻響差 | D〔babiniku.rs #62 標題〕 |
| **VC 後**：de-esser | 只在「s／sh 刺耳」時用 | RMVPE 路徑社群描述「略刺」；過 Discord Opus 後齒音更明顯 | D〔AI Hub f0 說明〕＋推論 |
| **VC 後**：壓縮／limiter | 輕壓、慢 release；保留動態 | 動態被壓平是破綻之一 | D〔babiniku.rs #48〕 |
| **VC 後**：輕微 room reverb | 部分 VTuber 加極小殘響讓聲音不「貼臉」 | 本輪找不到可信量測，只列為待驗證 | D（推論，無來源） |

### 1.4 本維度最強的 1–2 個選項

| 選項 | 強在哪 | 弱在哪 | 證據 |
|---|---|---|---|
| **把上游 RVC 已有的 formant 參數接出來**（`rvc_runtime.py` 現在寫死 0.0；上游 GUI 範圍 −2～+2）；Applio 的 stft formant shifting（quefrency／timbre、m2f 預設）當第二備案 | 補上社群點名第二大的破綻；不換模型、不訓練、不加依賴 | 重採樣型 formant 會改輸出長度，要確認 SOLA 拼接與延遲不變；音質要人耳聽 | A〔repo〕、C〔上游 rtrvc.py、Applio〕、D〔miaoyin〕 |
| **把「說話方式」與「下游 App 關三個開關」寫進操作指南**，並用「過 Discord 後」的錄音做聽評 | 零成本；社群最一致的經驗 | 需要 Johnny 本人練習；聽評要有人耳 | D〔miaoyin 110248／110249〕、C〔Discord FAQ〕 |

---

## 2. 維度二：低延遲的極限

### 2.1 我們現在的延遲拆解（A 級，PC2 RTX 2060）

| 段落 | 數字 | 來源 |
|---|---|---|
| RVC 最佳設定（chunk 80 ms、crossfade 20 ms、extra 0.5 s、fcpe）扣掉虛擬線 | p50 102.5 ms、慢時約 115 ms、RTF 0.47、無 underrun | A〔`exp/bench-e2e-latency` `80fbdca`〕 |
| RVC 預設設定扣掉虛擬線 | 247.5 ms | A〔同上〕 |
| 兩條虛擬線（CABLE → Light Host → Voicemeeter） | 約 120–130 ms | A〔同上，第一輪 723c932〕 |
| 引擎 latency trace 與聲學量測差 | trace 少 90–240 ms | A〔同上〕 |

**推論：**淨 102.5 ms＋路由 120–130 ms ≈ 225–235 ms，已經在 100–300 ms 目標內；但 VB-CABLE 本身只有約 14–21 ms〔C〕，所以那 120–130 ms 大部分是 App 緩衝，還有約 60–100 ms 可以壓。〔D〕

### 2.2 每一段延遲的社群／官方數字

| 段落 | 數字 | 條件 | 證據 |
|---|---|---|---|
| 音訊介面＋WASAPI 本身 | 約 100 ms | UR12、WASAPI、beatrice-client 138.7 ms 扣演算法 36 ms | B〔zenn gokrack，前序文件已引用〕 |
| ASIO 128 frame 下 Beatrice VST 全程 | 約 50.7 ms | UR12、48 kHz | B〔zenn gokrack〕 |
| Beatrice VST 其他介面 | 50.1 ms（RME 256 樣本）、60.8 ms（RME 512）、63.5 ms（UR12 384） | ASIO | B〔aivoices.gg 彙整的獨立量測〕 |
| RVC realtime GUI | 170 ms；ASIO 進出 90 ms | 官方宣稱、未附條件 | C〔RVC README.en〕 |
| RVC Realtime VST 回報延遲 | 固定＝2 × block（例：40 ms block 回報 80 ms） | 原始碼 `CalculateLatencyFrames` | C〔RVCRealtimeVST 原始碼與 README〕 |
| VCClient RVC | chunk 0.25 s → 817.5 ms；chunk 341 ms → 1034 ms | RTX 2080 Ti、ASIO 128 | B〔zenn gokrack〕 |
| VCClient RVC（natade） | chunk 170.7 ms＋extra 16384 → 582 ms；GPU 比 CPU 少約 300 ms；f0 方法差約 100 ms；**無線麥克風 +117 ms**；VC→VRChat 用虛擬線比實體線少約 50 ms | Windows、OBS 錄音量測 | B〔blog.natade.net〕 |
| VCClient chunk 80（213 ms）＋extra 131072 | 作者體感約 0.2 s、原帖約 0.6 s；i7-8700 CPU 100% | 個案 | D〔cg202.exblog.jp〕 |
| Applio 即時化 PR | 處理時間 60–80 ms（chunk 256、crossfade 0.05、extra 0.1） | Google Colab，**不是麥克風到喇叭** | C〔Applio PR #1245〕 |
| RVC GUI block 0.12 s 以下 | 延遲 50 ms 左右但停頓時卡住 | RTX 3060、pm | B〔RVC issue #1283〕 |
| VB-CABLE 內部 | 上限約 21.3 ms、預期約 14.2 ms（內部 2048 樣本） | 48 kHz；連接的 App 緩衝要 < 682 樣本 | C〔VB-Audio 作者 Vincent Burel 論壇回覆〕 |
| VB-CABLE 預設最大緩衝 | 7168 樣本 ≈ 149 ms | 48 kHz | C〔VB-CABLE 參考手冊（搜尋摘要）〕 |
| Voicemeeter | 延遲先取決於 A1 輸出裝置；官方建議 A1 用最好的裝置、可能的話用 ASIO | — | C〔VB-Audio 論壇〕 |
| WASAPI 共享模式 | 預設引擎週期 10 ms；驅動支援時可用 `IAudioClient3::InitializeSharedAudioStream` 要更小的週期 | Windows 10+ | C〔Microsoft Learn〕 |
| w-okada server mode | ASIO／WASAPI 走 server device；WASAPI 可開 exclusive，但其他 App 就不能用該裝置 | — | C〔DeepWiki w-okada 音訊設定〕；B〔w-okada issue #1305：WASAPI 時其他錄音軟體抓不到〕 |

### 2.3 chunk 低於 80 ms 的做法與代價

| 做法 | 能省多少 | 代價 | 證據 |
|---|---|---|---|
| RVC GUI 把 block 壓到 50 ms、crossfade 10 ms | 理論上 block 少 30 ms | GPU 要能每 50 ms 完成一次；停頓時卡住是常見回報 | C〔RVC GUI 最小值〕、B〔issue #1283〕 |
| 加大 extra（過去音訊）換品質，chunk 維持小 | extra 對延遲影響小，主要吃算力（Transformer 平方成長） | CPU／GPU 負載上升 20–30% | C〔w-okada 教學〕、B〔w-okada issue #1525 使用者〕 |
| 換 Beatrice v2（40 ms 級演算法延遲） | VST＋ASIO 全程約 50 ms | 推論庫專有、要特定格式聲線，前序文件已列 | B〔zenn〕 |
| MeanVC2 40 ms chunk | 論文首包約 110 ms | 本機淨約 478 ms、不穩〔A〕 | A／C |

**關鍵發現：**在我們的數字裡，chunk 從 80 ms 再壓的收益最多約 30–40 ms，而虛擬線還有 60–100 ms 可以壓〔D，由 2.1 推論〕。**下一步該先壓路由，不是壓 chunk。**

### 2.4 本維度最強的 1–2 個選項

| 選項 | 強在哪 | 弱在哪 | 證據 |
|---|---|---|---|
| **砍掉一跳：引擎直接輸出到 Voicemeeter 虛擬輸入（或直接到 CABLE），VST 處理移進引擎或 Voicemeeter 內建 EQ** | 路由是最大的可壓項；不需新驅動（Johnny 13:23：用既有虛擬裝置） | 要改 rack 路由與 Post-FX 位置；Light Host 的 VST 若不可替代就省不了 | A〔120–130 ms〕、C〔VB-CABLE 14–21 ms〕、D〔推論〕 |
| **檢查並縮小每一跳的緩衝**：Voicemeeter A1 改 WDM／ASIO（若硬體有）、VB-CABLE 最大緩衝從 7168 降到 2048 以下、引擎端 PortAudio 用 WASAPI 低延遲或 exclusive（只用於不需共享的那一端） | 不換任何元件；每一跳都有明確數字可量 | exclusive 會讓其他 App 抓不到裝置；VB-Audio 稱 WDM exclusive 屬實驗性 | C〔VB-Audio 手冊與論壇、Microsoft Learn〕、B〔w-okada #1305〕 |
