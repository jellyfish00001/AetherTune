# reference voices

這裡放 Seed-VC、CosyVoice 與 Breeze TTS 2 使用的參考聲音；音檔不進 Git。

目前先提供兩個本機可用的公開資料樣本：

| label | 檔案 | 來源 | 用途 | 注意 |
|---|---|---|---|---|
| `female-f1` | `voice-female-f1.wav` | VCClient 內附 JVNV partial sample | Seed-VC／TTS reference | 需以 STT 產生或人工核對 exact transcript |
| `male-m1` | `voice-male-m1.wav` | VCClient 內附 JVNV partial sample | Seed-VC／TTS reference | 需以 STT 產生或人工核對 exact transcript |

另加入四個供 Seed-VC 比較用的中文女性聲音候選。這四個名稱是依初步音高／聽感方向命名，不代表說話者的真實年齡或身分：

| label | 檔案 | 初始方向 | 來源／授權 | 用途與限制 |
|---|---|---|---|---|
| `female-young-f004` | `female-young-f004.wav` | 明亮、較高音域，先作「妹妹感」候選 | MatrixStudio/TTS-SCDuFSC，CC BY-NC-ND 4.0 | 僅本機非商業測試；不得重新散布或商用 |
| `female-sister-f003` | `female-sister-f003.wav` | 自然、清楚，先作「姐姐感」候選 | MatrixStudio/TTS-SCDuFSC，CC BY-NC-ND 4.0 | 僅本機非商業測試；不得重新散布或商用 |
| `female-warm-f005` | `female-warm-f005.wav` | 較低、較溫暖，先作「媽媽感」候選 | MatrixStudio/TTS-SCDuFSC，CC BY-NC-ND 4.0 | 僅本機非商業測試；不得重新散布或商用 |
| `female-fresh-f006` | `female-fresh-f006.wav` | 明亮但不過高，先作「清爽大姊感」候選 | MatrixStudio/TTS-SCDuFSC，CC BY-NC-ND 4.0 | 僅本機非商業測試；不得重新散布或商用 |

這四檔是從資料集的四位不同女性說話者各取一個短句，已保留原始逐字稿於 reference register；實際角色分類仍以 Seed-VC 轉換後的人工聽測為準。

來源資料夾內的 `readme.md` 標示 JVNV 為 CC BY-SA 4.0；不要移除 attribution，也不要把參考音聲線當成使用者自有角色。詳細 hash 與來源登記見 `dataset/manifests/reference-register.csv`。

參考音聲只用於本機研究與測試。若改用真人、網路下載或商用聲音，必須先補齊同意、授權與用途範圍。
