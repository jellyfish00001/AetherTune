# Desktop 繁中／英文介面驗證

日期：2026-10-01（Asia/Taipei）。本頁擁有介面語言切換、持久保存與原生系統匣的本輪證據。操作由 [Desktop 手冊](../../guides/desktop-user-guide.md)擁有，資料設計見 [App 架構](../../specs/app-architecture.md)。本輪沒有生成音訊、讀取麥克風或重判 LIVE。

## 實作與範圍

- 設定頁新增繁體中文／English 選擇，預設繁中。工作區、四 VC、兩 TTS、音效、佇列狀態、Full／Compact／Mini、快捷鍵與系統匣使用同一份文案；HTML lang 為 zh-Hant／en。
- 305 筆雙語文案集中 `app/src/locales/messages.json`，React context 與 Rust 系統匣共用；內建 reference 名稱／說明翻譯，engine／model ID、裝置名稱、輸入文字與原始診斷資料保留。
- `aethertune.ui-language.v1` 獨立保存語言；無效值回到繁中，保存／系統匣更新失敗分別提示。切換直接重繪，不重載工作區、重設音效／路由或重送請求。
- 原生 `set_ui_language` 只接受 zh-TW／en，保留選單 ID 與既有動作，更新 menu item text 與 tooltip。原生開機先用繁中，前端讀取持久偏好後同步。
- UI controls 增加穩定 data-testid，既有測試不再依賴混用的 aria 字串；可見文案與可及性名稱另外驗證。

## 驗證

| 命令／能力 | 結果與界線 |
|---|---|
| `npm run test:i18n-ui` | Edge preview PASS：305 筆文案／插值完整性、JSX 漏接翻譯檢查、雙語文字與 aria、HTML lang、reload 保存、非法偏好 fallback、六引擎畫面、草稿與路由／音效紀錄不變；模擬儲存空間不足時，雙語錯誤提示正確 |
| `npm run test:ui`、`npm run test:audio-effects-ui` | PASS：三視窗、模式／引擎控制及六引擎音效隔離、移轉、保存／重設回歸 |
| `npm run test:manual-tts-ui` | Preview／明確 mock IPC PASS：IME／composer／Queue／錯誤與請求參數；切到英文時 Buffering、Current／Ready 更新，草稿不變且 submit count 不增加。Mock 不代表模型／音訊成功 |
| `npm run test:contracts`、`npm run build` | PASS：既有契約、TypeScript／Vite |
| portable Cargo `build --bins --features tauri/custom-protocol` | PASS：獨立 exe，編譯同一 JSON 系統匣文案 |
| Codex 內建 Browser | `http://127.0.0.1:1420/`、1280×720；實際複核繁中設定、英文設定與英文 TTS workspace，文字／欄位／參考聲音名稱一致 |
| `AETHERTUNE_CDP=http://127.0.0.1:9222 npm run test:i18n-ui` | 根目錄原生 exe、`http://tauri.localhost/`、1040×740、DPR 1.25；雙語與持久化 PASS，英文 Compact 420×490 六引擎沒有水平溢出，Mini Quick Input 420×260 關閉按鈕可見且保留草稿；原生 menu item text 讀回與非法語言拒絕 PASS，console／network errors=[]。完成後恢復原始語言、路由／音效與 session 資料 |
| 完整 App Exit／重新啟動 | 儲存英文、完整退出、重新啟動後 document lang、設定選項與原生 tray language 均為 en，PASS；最後恢復繁中 |
| 文件連結／差異檢查 | 81 份 Markdown、741 個本地連結 PASS；`git diff --check` PASS |

Artifact：`artifacts/desktop/i18n-20261001/` 的 `preview-report.json`、`native-report.json`、`restart-report.json`；`native-zh-settings.png`／`native-en-settings.png`／`native-en-restarted.png` 與 `browser-zh-settings.png`／`browser-en-tts.png` 為畫面。既有回歸報告仍在 `artifacts/desktop/ui/`。原生 menu item 的文字透過 Tauri 物件讀回，沒有以 OS 右鍵打開系統匣做實體點擊驗收。

既有原生 VC／TTS 音訊 smoke 的定位同步改為穩定 ID 與目前語系，VC 音效入口同步到設定頁並在測試結束還原音效紀錄。本輪只做語法檢查，沒有重新執行會發聲的 smoke。

本輪根目錄 `AetherTune.exe` SHA-256：`924b8db161a4c0f3fab54c18e022e8c57068a3474fbf8332a5fe2626bd41b815`，已更新並重開。日常啟動不保留 CDP port。前次四 VC 音訊與 TTS 音效結果仍由 [VC 報告](realtime-vc-verification-latest.md)及[音效報告](audio-effects-verification-latest.md)擁有；本輪只驗語言與 UI 回歸。
