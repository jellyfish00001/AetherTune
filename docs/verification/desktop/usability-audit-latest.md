# Desktop 操作與畫面審查

日期：2026-10-01（Asia/Taipei）。本頁擁有本輪 Desktop 畫面的未完成／多餘項目、修正及 UI 證據。操作以 [Desktop 手冊](../../guides/desktop-user-guide.md) 為準；模型、串流與回錄證據以 [四 VC 驗證](realtime-vc-verification-latest.md) 為準。本輪 UI 審查沒有重新生成語音或進行實體聽評。

## 能否每個項目都按 START 說話

不能將所有可切換的項目解讀為麥克風變聲，也不能以 START enabled 或預檢 PASS 當成實體開箱驗收。

| 畫面選項 | 實際操作／本機證據 | 未通過的範圍 |
|---|---|---|
| Streaming VC：RVC／MeanVC2／X-VC／Seed-VC | 麥克風模式按 START，等待 RUNNING；先前四引擎原生 START／metrics／STOP PASS，短時間音訊與路由分項證據見四 VC 報告 | 實體說話→實際耳機、人耳音質、600 秒、Discord／外部 Rack 全鏈；所有角色與所有進階參數組合未逐一驗收 |
| RVC 的來源 WAV | START 轉換並播放指定音檔，沒有讀麥克風；File＋FX＋CABLE 已有音訊證據 | 不能由此推論 Mic 全鏈通過 |
| Text → Voice：CosyVoice／Breeze TTS 2 | 輸入文字後按 Speak；完整 WAV 生成後播放 | 不是麥克風即時變聲；本輪只重驗 UI，原生語音證據見 Manual TTS 報告 |
| Speech Reconstruction | 目前沿用同一套文字發聲流程；介面明確標為「目前僅文字」 | 麥克風 STT→TTS、即時字幕及 Agent Reply 尚未完成 |

本輪裝置保存值為 HyperX QuadCast S 麥克風與喇叭、Windows DirectSound。裝置可以開啟不代表使用者耳機接在 HyperX 上；實際耳機／喇叭接點尚未由使用者確認。若耳機接 Realtek、USB／藍牙或螢幕，必須選對播放端；虛擬線路則須設定接收端或自己監聽。沒有將自動選擇裝置稱為已完成實體路由。

## 畫面發現與修正

修正前後均先保存畫面；所有證據位於 `artifacts/desktop/usability-audit-20261001/`，不納入 Git。

| 優先度 | 修正前問題／影響 | 處理與結果 |
|---|---|---|
| P1 | Full 的 START 在首屏以外：1040×740 下 RVC bottom=1022.4，其他三個 bottom=834.4；必須捲動才能開始 | START／STOP 移至 Mode／Engine 與來源提示後。修正後四引擎 bottom=439.6，原生首屏可見且 enabled |
| P1 | RVC File 在 Compact 沒說明來源差異，Mini 錯標 Mic | Full／Compact 顯示 WAV 不讀麥克風；Mini 顯示 WAV，Mic 模式恢復後才顯示 Mic |
| P1 | Speech Reconstruction 名稱容易被當成麥克風流程；TTS footer 顯示 VC 的 OFFLINE | 加上目前僅文字標示與 Speak 提示；TTS footer 使用「文字發聲」 |
| P2 | `M2 skeleton`、空白 `Transcript M4`、重複 Audio WAITING 佔位讓頁面顯得未接通 | 移除工程佔位與空面板；驗收限制保留在可展開說明，沒有將分類升成 LIVE-ready |
| P2 | Mini 的 RVC 名稱／長裝置文字擠壓操作，VC 還有無作用的 `[T]` | 簡短引擎／Mic／WAV 標示並保留 tooltip；文字快輸入按鈕僅 TTS 顯示 |

## 仍未完成或需要調整

- 實體聽評、600 秒與整條路由驗收尚未完成，故保留 Candidate／WAITING。四引擎的預設測試配置有輸出，不代表每個模型與所有設定都已開箱驗收。
- 引擎 START／切換仍會 cold-load；先前原生 session 實測載入＋預熱約 11.7～95.8 秒且會波動。沒有 ETA、熱切換或取消後常駐保證，使用者須等待 RUNNING。
- Streaming VC 的 Reference WAV 仍為路徑欄位；完整 Voice Library、VC preset 保存／切換，以及 Seed／Mean／X 進階參數 UI 尚未提供。現有預設可執行，不需要先完成這些進階功能。
- Speech Reconstruction 與 Text → Voice 仍共用文字工作區；保留產品模式並明確標示目前邊界，不能宣稱兩者已有不同麥克風流程。即時字幕／ME／REMOTE 紀錄與 Agent Reply 仍未提供。
- RVC index blend 覆蓋與聲音品質待調整，Voicemeeter B1 的 RVC duplex 擷取仍 WAITING，精確數值由四 VC 報告擁有。
- 完整原生 `test:ui` 先前於拖曳位移斷言失敗，該問題未在本輪修正。不能把本輪 UI 專項 PASS 稱為所有視窗／快捷鍵／Tray 測試 PASS。

## 驗證範圍與產物

| 能力／命令 | 結果與範圍 |
|---|---|
| Codex 內建 Browser：`http://127.0.0.1:1420/`、1280×720 | 修正前後畫面複核；預覽無程序控制，不能測音訊。`01-browser-vc.png`、`13-browser-vc-after.png` |
| Edge Playwright preview：`npm run test:ui` | PASS：模式／引擎篩選、裝置／音效欄位、首屏 START、File Mini WAV 與 VC 無文字快輸入按鈕 |
| `npm run test:manual-tts-ui` | PASS：文字輸入、IME、Queue／取消／錯誤、三種視窗與 mocked IPC；同步舊 RVC 專用監聽 selector 至共用標籤。Mock 不代表真實發聲 |
| 原生 WebView2 CDP：`http://tauri.localhost/`、1040×740、DPR 1.25 | 修正前 `capture-native.mjs` 與修正後 `check-after.mjs` PASS；四引擎 validate／START 可見 enabled、File Full／Compact／Mini、兩個文字模式與最後設定恢復；console／network errors=[] |
| `npm run build`、`cargo build --bins --features tauri/custom-protocol` | PASS；根目錄獨立 exe 已更新，不依賴 Vite |
| 文件本機連結與 `git diff --check` | PASS：79 份 Markdown、713 個本機連結；無 whitespace error |

根目錄 `AetherTune.exe` SHA-256：`9719cb6b65b50a43db14eb9bc56066bcffc1f7cb29d82968e40fab6b5f7354a2`。日常啟動不保留測試 CDP port。審查後恢復 Full／Streaming VC／RVC Mic／實體 HyperX 路由、音效 bypass，沒有留下 File 或 CABLE 測試設定。

原生修正前 `native-audit.json`、修正後 `after/report.json` 保存斷言與 viewport；畫面：`after/rvc-full.png`、`after/meanvc2-full.png`、`after/rvc-file-compact.png`、`after/rvc-file-mini.png`、`after/speech-reconstruction.png`、`after/ready.png`。這些檔案支持 UI 結論，不升級音訊或 LIVE gate。
