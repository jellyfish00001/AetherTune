# AetherTune 系統架構

## 目的

提供低延遲即時變聲鏈路；先確保音訊可穩定通過，再調整音色自然度與微量修音。

## 邊界與資料流

```text
┌──────────────┐   clean PCM   ┌────────────────┐
│ 實體麥克風   │ ─────────────→ │ VCClient/RVC   │
└──────────────┘                └───────┬────────┘
                                        │ converted PCM
                                        ▼
                                ┌────────────────────────────┐
                                │ VB-CABLE                    │
                                │ CABLE Input → CABLE Output  │
                                └──────────────┬─────────────┘
                                         │ received PCM
                                         ▼
                                ┌────────────────────────────┐
                                │ Light Host Modern           │
                                │ Graillon Free VST3         │
                                └──────────────┬─────────────┘
                                        │ processed PCM
                                        ▼
                                ┌────────────────────────────────────────┐
                                │ Voicemeeter Input → B bus              │
                                └────────────────┬───────────────────────┘
                                        ▼
                         Discord / game / OBS input
```

## 路由語意

Windows 音訊裝置名稱必須以實際裝置清單確認，文件不直接假設方向名稱：

- 應用程式的輸出端連到虛擬線路的播放端。
- 下一個處理程式的輸入端選該虛擬線路的錄音端。
- 最終通訊程式只選處理完成的輸出，不直接選實體麥克風。

正式驗證時要以「裝置名稱、取樣率、聲道、buffer、meter/loopback 錄音」逐項記錄，避免只憑名稱判斷方向。

目前 Windows 端點基線：

- VCClient output：`CABLE Input (VB-Audio Virtual Cable)`（播放端）。
- Light Host input：`CABLE Output (VB-Audio Virtual Cable)`（錄音端）。
- Light Host output：`Voicemeeter Input (VB-Audio Voicemeeter VAIO)`。
- Voicemeeter Standard：在接收 `Voicemeeter Input / VAIO` 的虛擬輸入 strip 啟用 UI 上的 `B` bus；`A` 只作為選用的實體監聽，不是 Discord 的輸出。Windows 錄音端點可能列為 `Voicemeeter Out B1`，這是裝置名稱，不是 Standard strip 上的按鈕名稱。
- 終端應用 input：本機列舉到的 `Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)`；不要用模糊的 `Voicemeeter Output` 文字猜測端點。
- VB-CABLE 合成 loopback 需同時具備 WAV、JSON metrics 與 SHA-256 才算 PASS；Voicemeeter B1 loopback 若全零，只能判定訊號尚未通過，必須檢查 mixer 引擎、mute、音量、B bus 與錄音端點。

## 音訊與模型責任

- Dataset：保存授權與處理 provenance；不把 TTS 合成資料視為真人音色等價證據。
- RVC：負責訓練 `.pth` 與 `.index`；訓練成功不代表即時延遲或自然度已驗證。
- VCClient：負責即時推論；chunk、f0、pitch、index rate 必須用矩陣測試，不把單一預設值視為最佳值。
- VST host：只處理轉換後聲音；修音程度需以可聽比較和延遲資料共同驗收。
- Virtual route：只負責音訊搬運；路由成功不代表 Discord/OBS 已收到正確訊號。
