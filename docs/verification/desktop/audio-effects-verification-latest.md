# 六引擎音效設定與 TTS 處理驗證

日期：2026-10-01（Asia/Taipei）。本頁擁有 SETTINGS 音效設定、六引擎獨立紀錄、TTS 生成後處理與本輪證據。操作以 [Desktop 手冊](../../guides/desktop-user-guide.md) 為準；四 VC 串流／模型證據仍見 [VC 報告](realtime-vc-verification-latest.md)，本頁不重判實體音訊或 LIVE。

同日後續繁中／英文與原生系統匣更新由 [介面語言報告](ui-language-verification-latest.md)擁有；下方 exe hash 與畫面為音效實作階段，最新 exe 見後續報告。

## 實作

- 音效的唯一編輯位置為 SETTINGS → 音效設定。選 RVC／MeanVC2／X-VC／Seed-VC／CosyVoice／Breeze，各自保存一份啟用、dry-wet、三頻 EQ、壓縮、殘響及增益；同引擎不同角色／參考音目前共用該紀錄。
- `aethertune.audio-effects.v1` 以 engine ID 保存獨立資料；切換直接讀該引擎紀錄，避免切換 effect 在保存時污染另一個引擎。數值保留輸入草稿，離開欄位才校驗／保存，可正常輸入負值；保存失敗明確回報。重設只影響目前項目。
- 舊版共用 `vc-settings.v1.postfx` 只移轉到預設 RVC；其他引擎保留 bypass 預設。WORKSPACE 只有狀態與「到設定調整」入口；Compact 會展開 Full 設定頁。
- VC 於下一次 START 套用。TTS `metadata.postfx` 於 submit 深拷貝並校驗，已排隊的句子不受後續設定變動影響。
- TTS 沿用共用 DSP，在完整生成 WAV 後、Playback 前以 4096-frame block 處理，保持取樣率、聲道與 frame 數；保留原始 WAV，音效結果另存 `.postfx.wav`。主輸出與監聽播放同一份結果。Bypass 不新增音效檔；處理可取消，失敗不記完成 Transcript。
- Evidence 保存原始／處理後路徑與 SHA-256、設定及處理時間；metrics 保存 `postfx_enabled`、`postfx_seconds` 與 `playback_audio_path`。沒有改模型、重載機制或外部 VST host。

## 程式與畫面驗證

| 命令／能力 | 結果與證據範圍 |
|---|---|
| `.venv/Scripts/python.exe -m unittest services.tts.test_postfx services.tts.test_service` | 41 tests PASS：真實 WAV bypass／wet=0／聲道與 frame 保留／取消；service 音效快照、非法設定拒絕與處理檔送至 playback；含既有 queue／storage／取消回歸。Service 的 generation／playback 使用明確 fake，不代表模型或實體 endpoint |
| `npm run test:audio-effects-ui` | Edge preview PASS：六引擎隔離、舊設定移轉、reload 保存、負值 EQ、單項重設、Workspace／Compact 設定入口 |
| `npm run test:ui`、`npm run test:manual-tts-ui` | PASS：既有 UI、文字／Queue／IME、mock TTS／RVC 請求傳入各自音效，沒有改播放端或監聽設定 |
| `npm run test:contracts`、`npm run build` | PASS：SpeechRequest 音效欄位與既有契約、TypeScript／Vite |
| `cargo build --bins --features tauri/custom-protocol` | PASS：獨立 exe，無需 Vite server |
| Codex 內建 Browser | `http://127.0.0.1:1420/`、1280×720；先確認舊 SETTINGS 沒有音效，修改後六引擎選擇、欄位與提示複核 |
| 原生 WebView2 CDP，`AETHERTUNE_CDP=http://127.0.0.1:9222 node tests/audio-effects.mjs` | 根目錄 exe、`http://tauri.localhost/`、1040×740、DPR 1.25；六引擎保存／還原、單項重設、Compact→Full PASS；console／network errors=[]。原始設定已恢復 |
| 完整原生 App Exit／重啟 | MeanVC2 wet=0.23 保存後，退出並重新啟動仍為 0.23；PASS，測試前紀錄已還原。不是只測 page reload |

Artifact 根目錄：`artifacts/desktop/audio-effects-20261001/`。`preview-report.json`、`native-report.json`、`restart-report.json` 為專項結果；`browser-settings.png` 與 `native-default-settings.png` 是預覽／恢復預設後的原生畫面。80 份 Markdown、726 個本機連結與 `git diff --check` PASS。完整原生拖曳／Tray 等驗收不由本頁升格。

根目錄 `AetherTune.exe` 已更新，SHA-256 `9acfaadedd850d7f34a0c81736640692db517077f6791ff0018994080281abdb`。單一實例限制令第一次平行 test exe 沒有建立第二個 WebView；確認現有 VC OFFLINE、目前 TTS session 無 active request 後更新重啟。後續原生測試已在實際根目錄 exe 通過；日常重開不保留 CDP port。

## 正式 TTS 環境與既有生成 WAV

使用 production `tools/venvs/seed-vc/Scripts/python.exe`，Python 3.10.11。輸入來自已驗證的 resident-smoke `8ab12b6f-29ff-4a17-a066-d734dea1f2b4` 的兩引擎次句 WAV；先核對當時 SHA-256，再處理。這次沒有重新跑模型或原生 Speak。設定：enabled=true、wet=0.5、low=+3 dB、high=-2 dB、reverb=0.15，其他值沿用預設。

| 引擎 | 取樣率／frames | 輸出 RMS | 原始與輸出差異 RMS | 處理後 WAV SHA-256 |
|---|---|---:|---:|---|
| CosyVoice | 24 kHz／89280 | 0.049706 | 0.006585 | `aefd205d100faa9ac8dd7bb595c0f9bcb328fca6022a5168acf5ce1dcffc23c1` |
| Breeze | 24 kHz／65280 | 0.019089 | 0.001920 | `76ab49cb80e5164ca76d99cb07f83dbdbb627ff7e818b1d819b1dd00d8225dec` |

兩個結果 finite／nonzero、聲道與長度不變，原始檔 hash 未改。完整來源路徑／hash／參數見 `tts-render-report.json`。

再將 Breeze 處理後 WAV 用正式 playback 送 `CABLE Input / Windows DirectSound`，以 `CABLE Output / Windows DirectSound` 獨立回錄：PASS，RMS=0.014136、peak=0.143921、capture errors=[]，播放 frames=130560、underrun=0。擷取 SHA-256 `af23667ca494fe53e2485fe6daede4fec803de6939e09c66a6a084d6756bb205`。Artifact：`breeze-cable/report.json` 與 WAV。

```powershell
.\tools\venvs\seed-vc\Scripts\python.exe app\tests\manual-playback-diagnostic.py artifacts\desktop\audio-effects-20261001\breeze-postfx.wav --output artifacts\desktop\audio-effects-20261001\breeze-cable
```

這是既有真實生成 WAV 的音效處理與 CABLE 播放／擷取證據；本輪新生成→原生 Speak＋FX 全鏈、實體耳機聽評與 600 秒／外部 Rack／Discord 仍另驗。六引擎記錄通過不代表全部模型與路由都已開箱驗收。
