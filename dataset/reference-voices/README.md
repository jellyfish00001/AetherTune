# reference voices

這裡放 Seed-VC、CosyVoice 與 Breeze TTS 2 使用的參考聲音；音檔不進 Git。

目前先提供兩個本機可用的公開資料樣本：

| label | 檔案 | 來源 | 用途 | 注意 |
|---|---|---|---|---|
| `female-f1` | `voice-female-f1.wav` | VCClient 內附 JVNV partial sample | Seed-VC／TTS reference | 需以 STT 產生或人工核對 exact transcript |
| `male-m1` | `voice-male-m1.wav` | VCClient 內附 JVNV partial sample | Seed-VC／TTS reference | 需以 STT 產生或人工核對 exact transcript |

來源資料夾內的 `readme.md` 標示 JVNV 為 CC BY-SA 4.0；不要移除 attribution，也不要把參考音聲線當成使用者自有角色。詳細 hash 與來源登記見 `dataset/manifests/reference-register.csv`。

參考音聲只用於本機研究與測試。若改用真人、網路下載或商用聲音，必須先補齊同意、授權與用途範圍。
