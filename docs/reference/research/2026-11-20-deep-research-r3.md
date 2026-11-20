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
| 音高（transpose） | 男轉女 **+10～+12**，不超過 +14；本音與模型接近時 +3～+5 | 太高 → 卡通、緊繃；「花栗鼠音」 | 太低 → 女聲模型唱男音、混濁 | contract 預設 **0**（範圍 −24～+24）；尚未系統掃描男轉女音高 | D〔miaoyin 110137／110248、xportstudio〕、C〔w-okada 教學 +12〕 |
| 共振峰（formant） | 與音高**同向小幅抬高**；少女音略抬、御姐音音高 +10 且共振峰略壓 | 太高 → 小孩聲 | 不動 → 「音高變了腔體沒變」，大腦立刻識破 | **固定 0.0**：`services/engines/rvc_runtime.py` 呼叫 `RVC(values["pitch"], 0.0, …)`，第二個參數就是上游的 formant | A〔repo 程式碼〕；C〔上游 `infer/rtrvc.py`、`realtime_gui.py`「性别因子/声线粗细」滑桿 −2～+2〕；D〔miaoyin〕；C〔Applio formant shifting〕 |
| Index rate（檢索比例） | 0.3～0.75；沒有 index 時 0；即時用途比離線低 | 更像目標，但訓練資料的噪音也會被拉進來、更吃效能 | 更乾淨、但更像自己的音色 | contract 預設 **0.75**（社群即時用途建議較低） | B〔Samer Al-Qaisi〕、C〔AI Hub docs〕、D〔miaoyin 0.2～0.5〕 |
| Protect（無聲子音保護） | 0.33；0.5＝關閉 | — | 太低 → 字被吞掉、「不像人」 | **即時路徑沒有這個參數**：上游 `infer/rtrvc.py` 只有 key／formant／index_rate，protect 與 RMS mix 只在離線推論 | A〔`contracts/engines/rvc.json`〕、C〔上游 rtrvc.py、AI Hub docs、xportstudio〕 |
| f0 方法 | 即時：FCPE 或 RMVPE；crepe 太慢不適合即時 | RMVPE 準但聲音略「硬」 | FCPE 快但較怕噪音 | **fcpe**（最佳組合） | C〔FCPE 論文 RTF 表〕、B〔pitch-benchmark〕、D〔AI Hub：RMVPE 略刺、FCPE 較柔〕 |
| RMS mix rate | 說話 0～0.25（保留自己的音量起伏） | 越高越跟模型訓練音量走，動態變平 | 保留表演 | **即時路徑沒有**（同上） | C〔xportstudio、DeepWiki RVC 參數表〕 |
| Filter radius | 3（只對 harvest／dio 有效） | — | — | 不適用（fcpe） | C〔OpenVoiceChanger 環境變數說明〕 |
| 模型本身 | 選與本音「條件接近」的：清亮年輕男聲 → 少女；低沉男聲 → 中性女聲／御姐 | 跨度太大必失真 | — | Sage／ChineseBluetooth_F／EGirl_F 三選一，試聽檔待做 | D〔miaoyin 第 4 條〕 |

**關鍵發現：**
- 「音高 +12、共振峰不動」是社群最常點名的經典破綻。**上游 RVC realtime 早就有共振峰參數，AetherTune 只是寫死成 0.0**〔A，`services/engines/rvc_runtime.py` 第 130 行 `RVC(values["pitch"], 0.0, …)`〕。上游做法是把輸出長度乘上 `2^(formant/12)` 再重採樣、同時把 f0 key 扣掉 formant〔C，上游 `infer/rtrvc.py` 約第 279–287 行〕；上游 GUI 的滑桿範圍是 −2～+2、步進 0.05〔C，`realtime_gui.py`〕。**這代表補共振峰不需要任何新依賴**，只要把 values 裡多一個 `formant` 傳進去，是本輪找到 CP 值最高的一個實驗。
- **即時 RVC 能調的其實只有四個：音高、共振峰、index rate、f0 方法**（加上 chunk／crossfade／extra）。社群教學常提的 protect、RMS mix、filter radius 只存在於離線推論〔C，上游 `infer/rtrvc.py` 建構子只收 key／formant／index_rate〕；AetherTune 的 contract 也只暴露 pitch（預設 0）、index_rate（預設 0.75）、f0_method、chunk（最小 80）、crossfade、extra_time〔A，`contracts/engines/rvc.json`〕。所以教學裡「protect 調 0.33」的建議對我們的即時路徑**不適用**，不要浪費實驗時間。
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

---

## 3. 維度三：現成女聲模型的來源與評價

前序[第 2 輪 §2.1–2.5](2026-11-20-decisions-and-candidates-r2.md)已列出來源格式與三個優先候選（E-Girl、Chinese Bluetooth Speaker lady、maobailing_rvc）。本節補「怎麼判斷一個社群模型穩不穩」與新增的來源。

### 3.1 來源比較

| 來源 | 強在哪 | 弱在哪 | 付費 | 證據 |
|---|---|---|---|---|
| **Hugging Face**（個人 repo 與合集，例 `chaye741/RVC-Voice-Models`、`maotianchen/maobailing_rvc`） | 權重直鏈、可看 commit 歷史；部分作者附推論參數 | 品質參差、多數沒有試聽與授權說明 | 免費 | C〔各 repo 頁面〕 |
| **voice-models.com／v2.voice-models.com** | 有活躍榜、epoch 數、部分試聽與 NISQA 分；權重多指回 HF | 目錄站，不保證檔案還在 | 免費 | B〔第 2 輪已核對〕 |
| **weights.gg** | 社群最大的線上目錄之一 | 本輪沒有核對到可直接下載的中文女聲；常需登入 | 免費（有付費功能） | D |
| **AI Hub（aihub.gg 文件＋Discord）** | 社群知識庫最完整（推論參數、訓練、dataset、artifacting 說明） | 模型本身多散在 Discord 與 HF | 免費 | C〔docs.aihub.gg〕 |
| **妙音变声（miaoyin.store）** | 宣稱 842 款中文音色、48k、自研 RVC 預訓練底模；教學文章寫得最實際 | **付費會員制**，本輪不評估、不下載；教學內容可參考 | **付費** | C〔官網自述〕 |
| **Beatrice 聲線（`Project-Beatrice-V2/Beatrice-voice-models`、`wok000/vcclient_model`）** | VCClient 可直接匯入 `beatrice_paraphernalia_*` 格式 | 不是 RVC 格式，接不進現有 `rvc_runtime.py` | 免費 | C〔GitHub／HF〕 |

### 3.2 判斷社群 RVC 女聲模型「穩不穩」的指標

| 指標 | 為什麼重要 | 證據 |
|---|---|---|
| 訓練預訓練底模（TITAN、Ov2 Super、KLM 系列） | TITAN 被描述為對口音與噪音較穩、需要的 epoch 較少；Ov2 Super 適合乾淨小資料、明亮聲音；KLM 偏韓日與歌聲 | C〔`blaise-tk/TITAN`、`Anonlestia/RVC_pre-train` 說明〕、D〔AI Hub training docs〕 |
| 取樣率（40k／48k） | 48k 高頻較完整，但過 Discord Opus 後差距會縮小 | D（推論） |
| 是否附 `.index` | 沒有 index 時 index rate 要設 0；現行 `rvc_runtime.py` 要求 `.pth`＋`.index` 都已登錄 | A〔第 2 輪 §2.1〕 |
| 作者是否附推論參數 | 例：maobailing 建議 rmvpe、index 0.6、rms mix 0.5、protect 0.4、女聲音高 +0～+2 | C〔HF model card〕 |
| 訓練資料是「說話」還是「唱歌」 | 歌聲模型說話時常有奇怪的拉長與顫音；直播用說話資料訓練的較自然 | D〔xportstudio：用實際用途的素材測試〕 |
| 資料乾淨度 | 有殘響或背景音樂的資料會讓 index 帶噪音、齒音刺耳 | C〔AI Hub dataset／artifacting docs〕 |

### 3.3 本維度最強的 1–2 個選項

| 選項 | 強在哪 | 弱在哪 | 證據 |
|---|---|---|---|
| **先用本機已有的三個（Sage、ChineseBluetooth_F、EGirl_F）做「過 Discord 後」的盲聽**，再決定要不要下載第 2 輪的 maobailing_rvc | 已在 PC2 能跑、延遲已量；不需新下載 | 只有 3 個樣本，可能都不是最佳 | A〔PC2 已量 Sage〕 |
| **maobailing_rvc**（中文女聲、40k、作者附完整推論參數） | 中文說明最完整，參數可直接當起點 | 單一作者，社群評價少 | C〔HF〕 |

---

## 4. 維度四：直播 TTS 的加速與其他串流 TTS

### 4.1 本機已量（A 級，PC1 RTX 5060 Ti 16GB 獨占）

見 `exp/live-tts-bench` 的 `docs/reference/research/2026-11-20-live-tts-acceleration.md`（`255c12a`、腳本 `7eba880`）。摘要：GSV-TTS-Lite 首包 87–128 ms、RTF 0.10–0.13、VRAM 0.58 GiB；VoxCPM2 6 步首包 101–127 ms、RTF 0.76–0.78、5.5 GiB；CosyVoice2（WSL）首包 4.4–7.1 s；Qwen3-TTS 開源版非串流 6.1–24.2 s。

### 4.2 加速方式：社群與官方數字

| 引擎 | 加速方式 | 首包 | RTF | VRAM | 硬體 | Windows 可行性 | 證據 |
|---|---|---|---|---|---|---|---|
| GPT-SoVITS | **GSV-TTS-Lite**（CUDA Graph、巢狀 KV cache、continuous batching） | 150 ms（無 FA）／133 ms（FlashAttention） | 0.125／0.108 | 0.8 GB | RTX 3050 Laptop | pip 可裝；FA 需 Windows 預編 wheel | C〔README〕；A〔本機 87–128 ms〕 |
| GPT-SoVITS | **Aqua-TTS**（Graph＋SDPA／FA2） | p50 短句 86–101 ms、中句 128–169 ms、長句 203–284 ms | — | — | RTX 4070 Ti SUPER（USB4）、Windows | 作者就是 Windows 量的 | C〔README，360 次量測，作者自測〕 |
| GPT-SoVITS | GPT-SoVITS-cpp TensorRT 串流 | 0.46 s | 0.12 | 2.3 GB | RTX 2080 Ti | C++ 專案、要自建 engine | C〔README〕 |
| GPT-SoVITS | minimal_inference ONNX 串流／TRT | 1.0 s／2.0 s | 0.31／0.21 | 4.5／3.4 GB | RTX 2080 Ti | — | C〔README〕 |
| GPT-SoVITS | TRT 轉換踩雷 | 首段 4.6 s、短句音色怪 | 1.24 | — | Jetson 8G | 作者回覆「精度崩了」 | D〔minimal_inference issue #6〕 |
| GPT-SoVITS | 原版 API streaming_mode 1／3 | Mode 1 首次播放 1.1–1.37 s；Mode 3 0.79–0.88 s 但長句音質劣化 | — | — | RTX 4070 | 官方 API | B〔hodaru 部落格，29 次實機請求〕 |
| VoxCPM2 | **Nano-vLLM-VoxCPM v2.0.5** | 單併發 TTFB p50 36 ms（短）／43 ms（長） | 0.086／0.10 | 會多約 2.5 GB CUDA graph | RTX 4090 | **需 flash-attn**，Windows 要自備 wheel；依賴 `triton-windows<3.5`；不支援 Windows 多卡 | C〔PyPI 頁，作者量測〕 |
| VoxCPM2 | 官方 PyTorch | — | 約 0.30 | 約 8 GB | RTX 4090 | 已裝 | C〔README〕；A〔本機 t10 RTF 1.10–1.15、t6 0.76–0.78〕 |
| VoxCPM2 | vLLM-Omni | — | — | — | Linux | vLLM 不支援原生 Windows → 要 WSL／Docker | C〔README〕、D〔推論〕 |
| CosyVoice2 | **TensorRT-LLM＋Triton（官方 runtime）** | 單併發 185 ms（spk cache）／218 ms | 0.12 | — | L20 | Linux／Docker | C〔runtime README〕 |
| CosyVoice2 | 同上，社群 | 單併發 p50 335 ms；併發 4 時 P99 1.47 s | 0.11 | — | RTX 4090 | Linux | B〔issue #1835〕 |
| CosyVoice2 | 同上，社群 | 單併發約 160 ms | — | — | H100 | Linux | B〔issue #1806〕 |
| CosyVoice2 | 原版 `load_jit`／`load_trt`／`fp16` | TRT plan 要對 GPU 重建；fp16 本機反而更慢 | — | — | — | Windows 可，但要 TensorRT 與 ORT CUDA | C〔cosyvoice.py〕、A〔fp16 5.1–9.2 s〕 |
| Qwen3-TTS | vLLM-Omni 串流（async chunk＋CUDA Graph） | TTFP 64 ms（未優化 733 ms） | — | — | H200 | Linux | C〔vLLM-Omni 設計文件、PR #1438／#1583〕 |
| Fish S2 Pro | audio.cpp GGUF Q4_K | 0.14–0.31 s | 中位數 1.00 | 7.0 GB | **RTX 5060 Ti 16GB、Windows 11** | 可，要 VS Build Tools 自編 | B〔andreaabcj-cmd 實測〕 |
| Fish S2 Pro | 串流程式 | 380 ms | — | — | RTX 5090 | — | B〔r/LocalLLaMA〕 |
| Fish S2 Pro | vLLM-Omni | 約 100 ms | — | — | RTX PRO 6000 | Linux | C〔fish-s2-rtx〕 |
| IndexTTS2 | Faster IndexTTS-2 串流 | 中文 396 ms（1 秒 chunk）／596 ms（2 秒） | — | — | GPU | — | C〔arXiv 2607.21042〕 |
| IndexTTS2 | index-tts-vllm | 約 365 ms（暖 speaker cache） | — | — | RTX 4090 | vLLM → Linux | C〔repo 說明，搜尋摘要〕 |
| Spark-TTS | TensorRT-LLM＋Triton | p50 210 ms（單併發） | — | — | L20 | Linux | C〔runtime README、NVIDIA 技術部落格〕 |
| F5-TTS | 串流 | 使用者回報首包太長、RTF > 1 | > 1 | — | — | — | D〔issue #1225〕 |

**中文品質旁證**（只作參考，來源是彙整資料集，不是本機聽評）：IndexTTS2 中文 CER 1.04%、相似度 0.765；CosyVoice2 1.29%／0.751；F5-TTS 1.64%／0.760；Spark-TTS 1.58%／0.659。〔D，`qwer-asdfzxcv/tts-baselines_opensource` 彙整〕

**關鍵發現：**
- 「首包 < 150 ms 而且 RTF 遠低於 1」在 Windows 原生能做到的，目前只有 **GPT-SoVITS 加速系（GSV-TTS-Lite、Aqua-TTS）**〔A＋C〕。其他引擎的漂亮數字幾乎都來自 **Linux＋vLLM／TensorRT-LLM＋資料中心卡**〔C〕。
- VoxCPM2 是唯一一個「Windows 有路」的 vLLM 系加速（Nano-vLLM-VoxCPM 明寫支援 Windows，但 flash-attn 要自己裝）〔C〕。這和 Johnny 16:21 核准的 triton-windows 實驗方向一致。
- CosyVoice2 要快就得離開 WSL 原版、改走 Triton＋TRT-LLM（Docker）。這屬於系統層變更（Docker／WSL 設定），依 13:10 規則應交 PC 管家 Bot。〔D〕

### 4.3 本維度最強的 1–2 個選項

| 選項 | 強在哪 | 弱在哪 | 證據 |
|---|---|---|---|
| **GSV-TTS-Lite 主線＋FlashAttention（Windows wheel，只裝實驗 venv）** | 本機已是最快；FA 在作者數字裡再省約 11% 首包與 RTF | 長句尾段截斷仍待修〔A〕；FA wheel 要對上 torch／CUDA 版本 | A、C |
| **VoxCPM2＋Nano-vLLM-VoxCPM** | 作者數字 RTF 降到約 0.09、TTFB 約 40 ms；口齒本機最清楚〔A〕 | 需 flash-attn＋triton-windows；多 2.5 GB VRAM；和 RVC 同卡時要確認不擠爆 16 GB | C、A |

---

## 5. 維度五：變聲與 TTS 怎麼保持同一個人

| 做法 | 強在哪 | 弱在哪 | 延遲成本 | 證據 |
|---|---|---|---|---|
| **(a) 用 RVC 女聲的輸出當 TTS 參考音**（zero-shot 克隆） | 只多一次離線準備；本機已做：VoxCPM2 念一段 → RVC Sage → 9 秒參考音，GSV-TTS-Lite 首包 87–128 ms、短句 CER 0 | 音色相似度受 zero-shot 天花板限制；參考音太短（約 3 秒）會吃字 | 0（離線） | A〔`exp/live-tts-bench` a837289／255c12a〕 |
| **(b) TTS 輸出再即時過同一個 RVC** | 音色由同一個 RVC 決定，最一致；GPT-SoVITS 社群用 RVC 壓 v3 電音並恢復音質 | 兩次轉換可能疊加破綻；同一張卡同時跑 TTS＋RVC | 約一個 RVC chunk＋運算（推論約 80–130 ms，依 2.1 的 RVC 數字） | B〔GPT-SoVITS issue #2246〕、C〔JarodMica/rvc-tts-pipeline〕、D〔延遲為推論〕 |
| **(c) 兩者都做**：(a) 產參考音，(b) 再把輸出過 RVC | 社群建議「GPT-SoVITS 與 RVC 用同一份乾淨資料」時最一致 | 我們不自己訓練（Johnny 13:47），只能做到 (a)＋(b) 的近似 | 同 (b) | C〔GPT-SoVITS issue #634：克隆音色跟著參考音走〕 |

**關鍵發現：**
- GPT-SoVITS 的克隆音色主要跟著**參考音**走（issue #634 的回答）〔C〕。所以 (a) 的品質上限就是那段 RVC 參考音的品質；參考音要選**乾淨、9 秒以上、語調自然**的一段〔A：3 秒會吃字〕。
- (b) 的延遲可以預估但還沒量：GSV 首包約 0.1 s＋RVC 一個 chunk 約 0.1 s，打字到出聲約 0.2–0.25 s，仍在直播可接受範圍〔D，推論〕。但麥克風 VC 與 TTS→VC 是否要共用同一個 RVC 實例、會不會互搶 GPU，需要實驗。〔D〕

最強選項：**(a) 已可用（A 級）；(b) 列為實驗 E7，若 Johnny 盲聽覺得 (a) 的音色和變聲差太多才上。**

---

## 6. 維度六：Discord／OBS 直播的音訊路由與音質設定

| 設定 | 建議 | 理由 | 證據 |
|---|---|---|---|
| Discord 輸入裝置 | 選 Voicemeeter／CABLE 的虛擬輸出 | 既有路由 | A〔`audio-rack/routing/seed-vc-virtual-route.json`〕 |
| Discord 雜訊抑制（Krisp） | **關閉（None）** | 會把變聲當噪音處理、切字頭、發悶 | B／C〔Soundpad FAQ、VoxBooster、Resound help〕 |
| Discord 回音消除、自動增益 | **關閉** | 二次處理＝發悶＋電音；AGC 會壓平動態 | D〔miaoyin 第 8 條〕、C〔Soundpad FAQ〕 |
| Discord 輸入模式 | 用 Push-to-Talk 或手動調低語音偵測門檻 | 自動語音偵測可能切掉轉換後較輕的字頭與氣音 | D（推論，未找到量測） |
| Discord 頻道位元率 | 預設 64 kbps；Boost Lv1／2／3 可到 128／256／384 kbps | 低位元率會抹掉高頻；聽評要用實際位元率 | C〔Discord 官方 FAQ〕 |
| 取樣率 | 全鏈 48 kHz 一致（Discord／Opus 原生 48 kHz） | 每次重採樣都多一點延遲與失真；VCClient 要求所有裝置同取樣率 | C〔DeepWiki w-okada 音訊設定〕、A〔現行 48 kHz〕 |
| OBS | 變聲後的聲音用「監聽並輸出」送到虛擬線，或直接擷取 Voicemeeter 匯流排；OBS 的濾鏡（壓縮、EQ）只在 OBS 那條，不要和 Voicemeeter 重複 | 避免同一段處理做兩次 | C〔techtactician、Bossett Wiki〕 |
| 自己監聽 | 監聽要聽「過 Discord 前」的訊號，但聽評要錄「過 Discord 後」的訊號 | 兩者音質不同 | D（推論） |

最強選項：**「Discord 三個開關全關＋全鏈 48 kHz＋用實際頻道位元率錄聽評樣本」**，這是零成本、社群最一致的建議。〔B／C〕

---

## 7. 建議納入規範／值得採用（待 Johnny 確認）

本節只是提案，**本輪沒有改任何正式文件**。每項要 Johnny 同意後，再由 AetherTune Bot 在分支上改對應文件。

| # | 建議內容 | 理由 | 證據等級 | 預計併入的正式文件 |
|---|---|---|---|---|
| R1 | 延遲數字只認「聲學量測」（錄音比對）；引擎 trace、GUI 顯示的 `res`／`buf` 一律標 partial | 本機 trace 比聲學少 90–240 ms；VCClient GUI 130 ms 實測 622 ms | A＋B | `docs/specs/verification-plan.md`（效能 baseline 與改善判定）、`docs/specs/live-gate.md`（測量欄位） |
| R2 | 延遲報告固定拆成「引擎淨延遲」與「路由延遲」兩欄，並記錄每一跳的緩衝設定 | 路由佔 120–130 ms，是目前最大可壓項 | A＋C | `docs/specs/live-gate.md`（測量欄位） |
| R3 | 在 LIVE_GATE 之外，另訂「直播目標」等級：完整鏈路 p50 ≤ 300 ms（Johnny 目標 100–300 ms）；現行 `LIVE` 門檻 ≤ 5000 ms 只是可用下限 | 現行規範把 5 秒當 LIVE，和產品目標差一個量級 | A（規範現況） | `docs/specs/live-gate.md`、`docs/reference/decision-log.md` |
| R4 | LIVE_GATE「研究優先級」把 RVC＋FCPE 從 `historical-baseline` 改回主線候選 | PC2 實測 RVC 是唯一進目標的引擎（淨 p50 102.5 ms），Seed-VC 533 ms、MeanVC2 478 ms 且不穩 | A | `docs/specs/live-gate.md`（研究優先級）、`docs/reference/decision-log.md` |
| R5 | 聽評樣本一律錄「過 Discord（實際位元率）之後」的版本，另附過 Discord 前的版本 | Opus 64 kbps 會改變破綻是否被聽見 | C＋D | `docs/specs/verification-plan.md`、`docs/specs/live-gate.md`（human_review） |
| R6 | 操作指南加「Discord 三個開關全關、全鏈 48 kHz、PTT」與「男轉女說話方式」段落 | 社群最一致的零成本建議 | B／C／D | `docs/guides/operation-guide.md`、`docs/guides/user-guide.md` |
| R7 | RVC 參數矩陣加入 `formant`（上游已有、目前寫死 0.0），與 `pitch`、`index_rate`、`f0_method` 一起掃；標明 protect／RMS mix 在即時路徑不存在 | 共振峰是社群點名的第二大破綻；不需新依賴 | A＋C＋D | `docs/reference/parameter-matrix-template.csv`、`contracts/engines/rvc.json`、`docs/specs/voice-conversion-architecture.md` |
| R8 | 直播 TTS 研究只把「Windows 原生可跑」與「需 Linux／WSL／Docker」分兩欄報告；後者屬系統層，交 PC 管家 Bot | 加速數字大多來自 Linux＋資料中心卡，混在一起會誤判 | C | `docs/specs/live-gate.md`（Speech Reconstruction）或新的直播 TTS 驗證報告 |
| R9 | TTS 參考音規範：同人參考音至少 9 秒、附逐字稿、由 RVC 女聲轉出，記錄 hash | 3 秒參考音會吃字；克隆音色跟著參考音走 | A＋C | `docs/verification/desktop/manual-tts-verification-latest.md`、`docs/specs/verification-plan.md` |

---

## 8. 可以在本機驗證的實驗清單

每項都只在 `exp/<主題>` 分支或實驗 venv；用 GPU 前先登記該機 `D:\BotOps\locks.md`，量完刪除。

| ID | 實驗 | 機器／GPU | 需要新依賴？ | 怎樣算成功 | 對應維度 |
|---|---|---|---|---|---|
| E1 | `rvc_runtime.py` 把 formant 從 0.0 改成參數；掃 formant {0, +0.5, +1, +1.5, +2} × 音高 {+10, +12}，三個女聲各錄一段「過 Discord 前／後」樣本 | PC2 或 PC1；GPU | 否 | 延遲不增加超過 5 ms；Johnny 盲聽選得出偏好 | 1 |
| E2 | index_rate {0, 0.3, 0.5, 0.75}（現行預設 0.75），量延遲、RTF 與聽感變化（protect 在即時路徑不存在，不掃） | 同上 | 否 | 找出「延遲不變、聽感最好」的組合 | 1、2 |
| E3 | f0 方法 fcpe vs rmvpe，在同一組 chunk 下量延遲與破音次數（含笑聲、長 s、氣音句） | 同上 | 否 | 列出兩者的延遲差與破音差 | 1 |
| E4 | 路由逐跳量測：引擎→CABLE、CABLE→Light Host、Light Host→Voicemeeter、Voicemeeter→B1，各自用 loopback 錄音量 | PC2 或 PC1；不需 GPU（可用 passthrough） | 否 | 找出 120–130 ms 裡最大的一跳 | 2 |
| E5 | 縮緩衝：VB-CABLE 最大緩衝降到 ≤ 2048、Voicemeeter A1 改低延遲驅動、引擎端 WASAPI 低延遲；或砍掉 Light Host 一跳 | 同上 | 否（不裝新驅動，只改既有設定；系統層設定交 PC 管家） | 路由延遲 ≤ 60 ms 且 600 秒無 underrun | 2 |
| E6 | RVC chunk 64 ms／crossfade 16 ms 再試一輪（目前最佳 80／20；contract 最小 chunk 是 80，要在 exp 分支放寬） | PC1（5060 Ti 比 2060 快） | 否 | 淨 p50 ≤ 90 ms 且無 underrun；否則確認 80 ms 是下限 | 2 |
| E7 | TTS→RVC：GSV-TTS-Lite 串流輸出接 RVC Sage 即時轉換，量打字到出聲延遲、和麥克風變聲同時跑時的 GPU 佔用 | PC1；GPU | 否 | 打字到出聲 ≤ 300 ms；與 (a) 做盲聽 | 4、5 |
| E8 | GSV-TTS-Lite＋FlashAttention（Windows wheel，只裝實驗 venv） | PC1；GPU | **是**（flash-attn wheel；屬 Johnny 16:21 核准的「加速套件只裝實驗環境」範圍，但仍先寫完成標準） | 首包與 RTF 比不加速好 ≥ 10% | 4 |
| E9 | VoxCPM2＋Nano-vLLM-VoxCPM（需 flash-attn、triton-windows<3.5） | PC1；GPU | **是**（同上範圍） | RTF ≤ 0.3、首包 ≤ 150 ms、VRAM 與 RVC 同時跑不爆 | 4 |
| E10 | Discord 設定 A/B：Krisp／回音消除／AGC 開 vs 關，64 vs 128 kbps，各錄一段 | 任何一台；不需 GPU（要 Discord 測試頻道） | 否 | 錄音頻譜與盲聽可分辨 | 6 |
| E11 | Fish S2 Pro Q4_K（audio.cpp）在 PC1 重現社群數字 | PC1；GPU | **是**（要編譯 audio.cpp，需 VS Build Tools，屬系統層 → 先問 Johnny／交 PC 管家） | 重現 0.14–0.31 s 首包；若 RTF≈1 則確認不適合 | 4 |

---

## 9. 哪些維度還不夠深

| 維度 | 缺什麼 | 下一步 |
|---|---|---|
| 1 自然度 | 沒有一篇有**盲聽量測**的「男轉女 RVC 被識破率」研究；大部分是教學與經驗（D） | 本機 E1–E3 自己做盲聽；Bilibili／YouTube 影片的實際試聽本輪沒有逐支看 |
| 2 延遲 | 沒有找到 Voicemeeter＋Light Host 這條路由的獨立量測；VB-CABLE 手冊 PDF 沒有完整讀 | E4 逐跳量測 |
| 3 模型 | weights.gg 與 AI Hub Discord 需要登入，本輪沒有實際核對中文女聲；沒有任何模型的獨立聽評分數 | 做 E1 時順便比較三個本機模型＋maobailing |
| 4 TTS | 大多數加速數字是作者在 Linux／資料中心卡量的（C）；Windows＋5060 Ti 只有 Fish 一筆（B） | E8、E9、E11 |
| 5 同人音色 | (b) 的延遲與疊加破綻完全沒有量測 | E7 |
| 6 Discord／OBS | Discord 內部的音訊處理鏈（Opus 參數、Go Live 音訊）沒有官方技術文件可查 | E10 |

---

## 10. 來源清單

**自然度與參數**
- https://miaoyin.store/110137.html 、https://miaoyin.store/110248.html 、https://miaoyin.store/110249.html （付費商店的免費教學）
- https://xportstudio.com/blog/best-rvc-settings
- https://sameralqaisi.me/voice-generation/techniques-and-tools/rvc-and-real-time-voice-changing/
- https://docs.aihub.gg/rvc/resources/inference-settings/ 、https://docs.aihub.gg/rvc/resources/dataset-isolation/ 、https://ai-hub-docs.vercel.app/rvc/resources/artifacting/ 、https://docs.aihub.gg/rvc/resources/training/
- https://deepwiki.com/fumiama/Retrieval-based-Voice-Conversion-WebUI/4.5-inference-parameters-reference
- https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/infer/rtrvc.py 、https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/realtime_gui.py
- https://deepwiki.com/IAHispano/Applio/5.4-post-processing-effects 、https://docs.applio.org/reference/cli/
- https://arxiv.org/html/2509.15140 （FCPE）、https://github.com/lars76/pitch-benchmark
- https://github.com/m96-chan/babiniku.rs/issues/48
- https://aivoicedetector.com/blog/how-to-tell-if-someone-is-using-a-voice-changer
- https://github.com/sioaeko/OpenVoiceChanger
- https://www.reddit.com/r/TransVoicechangers/comments/1eldh6h/every_time_i_use_a_voice_changer_people_clock_me/
- https://note.com/uunin/n/n085e2f748f3b 、https://note.com/shellbe/n/ne47f7a2ed997

**延遲**
- https://zenn.dev/gokrack/articles/621a2872fd9ccd
- https://blog.natade.net/2024/07/27/vrchat-ai-rvc-voice-changer/
- https://cg202.exblog.jp/34026650/
- https://github.com/w-okada/voice-changer/blob/master/tutorials/tutorial_rvc_en_latest.md 、https://github.com/w-okada/voice-changer/issues/1525 、https://github.com/w-okada/voice-changer/issues/1305 、https://deepwiki.com/w-okada/voice-changer/6-audio-device-configuration
- https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md 、https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/issues/1283 、https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/RVCRealtimeVST/README.en.md
- https://github.com/IAHispano/Applio/pull/1245
- https://aivoices.gg/learn/rvc-live-conversion-benchmark
- https://forum.vb-audio.com/viewtopic.php?t=600 、https://vb-audio.com/Cable/VBCABLE_ReferenceManual.pdf 、https://vb-audio.com/Voicemeeter/Voicemeeter_UserManual.pdf
- https://learn.microsoft.com/en-us/windows/win32/api/audioclient/nf-audioclient-iaudioclient3-initializesharedaudiostream 、https://learn.microsoft.com/en-us/windows-hardware/drivers/audio/low-latency-audio

**模型來源**
- https://huggingface.co/maotianchen/maobailing_rvc 、https://huggingface.co/chaye741/RVC-Voice-Models 、https://v2.voice-models.com/model/a2Y 、https://v2.voice-models.com/model/1w6EMKUoZSo
- https://huggingface.co/blaise-tk/TITAN 、https://huggingface.co/Anonlestia/RVC_pre-train 、https://huggingface.co/SeoulStreamingStation/RVC_KLM-X-10_Pretrained-Model
- https://github.com/Project-Beatrice-V2/Beatrice-voice-models 、https://huggingface.co/wok000/vcclient_model

**直播 TTS**
- https://github.com/chinokikiss/GSV-TTS-Lite 、https://github.com/Lucas1479/Aqua-TTS 、https://github.com/GPT-SoVITS-Devel/GPT-SoVITS-cpp 、https://github.com/GPT-SoVITS-Devel/GPT-SoVITS_minimal_inference 、https://github.com/GPT-SoVITS-Devel/GPT-SoVITS_minimal_inference/issues/6
- https://blog.hodaru.com/posts/project/bettergi-questvoice/systems/gpt-sovits-streaming-pipeline/
- https://github.com/OpenBMB/VoxCPM 、https://pypi.org/project/nano-vllm-voxcpm/ 、https://github.com/a710128/nanovllm-voxcpm
- https://github.com/funaudiollm/cosyvoice/blob/main/runtime/triton_trtllm/README.Cosyvoice2.Unet.md 、https://github.com/FunAudioLLM/CosyVoice/issues/1835 、https://github.com/FunAudioLLM/CosyVoice/issues/1806 、https://github.com/FunAudioLLM/CosyVoice/blob/main/cosyvoice/cli/cosyvoice.py
- https://github.com/vllm-project/vllm-omni/blob/10906e3a/docs/design/qwen3_omni_tts_performance_optimization.md 、https://github.com/vllm-project/vllm-omni/pull/1438 、https://github.com/vllm-project/vllm-omni/pull/1583
- https://github.com/andreaabcj-cmd/fish-audio-s2-pro-realtime-local-tts 、https://www.reddit.com/r/LocalLLaMA/comments/1ru77ua/fishspeech_s2_pro_streaming_code_380ms_ttfa/ 、https://github.com/Genesis1231/fish-s2-rtx
- https://arxiv.org/abs/2607.21042 、https://github.com/yangohuang/index-tts-vllm
- https://github.com/SparkAudio/Spark-TTS/blob/main/runtime/triton_trtllm/README.md 、https://developer.nvidia.cn/blog/nvidia-triton-tensorrt-llm-tts-app/
- https://github.com/SWivid/F5-TTS/issues/1225
- https://huggingface.co/datasets/qwer-asdfzxcv/tts-baselines_opensource

**同人音色**
- https://github.com/RVC-Boss/GPT-SoVITS/issues/2246 、https://github.com/RVC-Boss/GPT-SoVITS/issues/634 、https://github.com/JarodMica/rvc-tts-pipeline/

**Discord／OBS**
- https://support.discord.com/hc/en-us/articles/11635925354775-Audio-Bitrate-FAQ
- https://www.leppsoft.com/soundpad/en/help/faq/voice-discord 、https://getresound.app/help/discord 、https://voxbooster.com/blog/voice-changer-discord-krisp-conflict/
- https://techtactician.com/how-to-use-obs-audio-with-discord-quick-tutorial/ 、https://wiki.bossett.io/books/general/page/using-obs-for-audio-processing-in-discord-and-streaming
