# AetherTune Desktop 快速使用

**輸入文字，選擇聲線，再把生成的語音送到指定音訊裝置。** 本頁供收到「已備妥語音資源的 Desktop 測試版」的使用者快速上手。現階段仍是開發版，尚無正式安裝包；如果手上只有原始碼，請先依[開發版建置與環境準備](desktop-user-guide.md)完成設定。

## 開始前

- 開啟 **AetherTune Desktop**。文字發聲功能在 Desktop 視窗，不在 `AetherTune.cmd` 控制台。
- 確認提供者已備妥 CosyVoice2 或 Breeze TTS 2、聲線所需的參考音訊，以及要使用的輸出裝置。
- 這個版本會**先生成整段語音再播放**；依文字長度和電腦狀況，可能需要一至數分鐘。送出後先看佇列狀態，避免重複提交。

## 第一次發聲

1. 在 **Full → LIVE** 頁面的 `Mode` 選 **Text → Voice**，或選 **Speech Reconstruction**。兩者目前共用文字發聲畫面。
2. 選擇 `Engine`、`Voice profile`、`Host API` 和 `Output`；`Input` 保持 **manual_text**。
3. 在文字框輸入想說的內容，按一次 **Speak**。需要依序播放多段文字時，使用 **Add to Queue**。
4. 查看 **Speech Queue** 的 `GENERATING → BUFFERING → PLAYING` 狀態；播放完成後，記錄會出現在 **Transcript**。

目前已有音訊擷取證據的設定是 `Host API = Windows DirectSound`、`Output = CABLE Input (VB-Audio Virtual Cable)`。請在要接收聲音的程式選 **CABLE Output**；這種設定下，電腦喇叭沒有直接出聲是正常的。若想直接從喇叭聽，請選列出的實體播放裝置及相符的 Host API，並另做播放測試。

## 常用操作

| 想做的事 | 操作 |
|---|---|
| 接著播放下一句 | 輸入文字後按 **Add to Queue** |
| 停止目前這句 | 按 **Stop Speaking**；已排隊項目仍保留 |
| 清掉還沒開始的句子 | 按 **Clear Queue**；目前這句不受影響 |
| 重用常用文字 | 在 **Recent／Favorites** 選取後再確認送出 |
| 縮小視窗 | 使用 **Compact／Mini**；Mini 的 `[T]` 可開啟文字輸入 |
| 完全關閉程式 | 從 **SETTINGS → Exit AetherTune** 離開；視窗右上角關閉可能只會收進系統匣 |

## 目前版本的界線

**Manual TTS 已有本機生成、播放及佇列測試證據**，但正式商品安裝、即時直播語音、實體麥克風轉文字、Agent 自動回覆及外部音效機架的完整驗收尚未完成。`microphone` 目前不會啟動持續收音，`agent_reply` 尚未開放。文字、工作紀錄與生成結果會保留在本機；關閉視窗不會自動清除它們。

遇到無聲、等待過久或啟動問題，請看[詳細操作與排錯手冊](desktop-user-guide.md)；開發或驗證人員可查[本輪測試範圍](manual-tts-verification-latest.md)。
