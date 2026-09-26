# Backend 安裝與基本音訊測試

更新日期：2026-09-27（Asia/Taipei）

## 階段 1：Seed-VC realtime-tiny GUI — PASS

這次實際測試使用 tiny checkpoint、XLS-R、Hifi-GAN、FP32、CUDA 0，沒有以 offline-v1 替代。日常 GUI bootstrap 將 Torch CPU worker 限制為 4；測試工具新增明確 profile，修正 XLS-R cache 路徑，保留足夠首次 warm-up 時間，並將 GUI 設定寫入 artifact overlay。原本 5 秒 encoder context 可用，不需換模型或增加服務。短的擷取視窗加上未限制的 CPU worker 會在首次 callback 完成前停止，造成零輸出或未擷取到輸出；不能把這種結果解讀為模型本身全零。

實際命令：

```powershell
& tools/venvs/seed-vc/Scripts/python.exe -u tools/seed-vc-gui-userflow-test.py --profile realtime-tiny --capture-loopback --output artifacts/seed-vc/tiny-four-references
& tools/venvs/seed-vc/Scripts/python.exe tools/seed-vc-gui-settings-regression.py
pwsh -NoProfile -File tools/seed-vc-gui-run.ps1 -PreflightOnly
```

四案 settings、backend callback、WASAPI CABLE Output loopback 全數 `PASS`；設定均 17/17，音訊 finite、RMS > 0.0001、輸出與來源不同。

| Reference | Callback RMS | Cable RMS | 首次 callback 非零輸出 ms | Callback WAV SHA-256 |
|---|---:|---:|---:|---|
| female-young-f004 | 0.015578 | 0.015336 | 2030.086 | B3D36A404B350E12D5A75A48AB2012FE68AB51521929CA387099A21BAFBEC7BF |
| female-sister-f003 | 0.021780 | 0.034708 | 1092.083 | 2EEAC7150D80F2E9062231790DD42F22D31C63CEE0996DDB18D406BD4E351D55 |
| female-warm-f005 | 0.015548 | 0.016583 | 1532.030 | 5D2EBD1CD2E9EADAF5E576F1327D86380473A4E03350FCDF2330C189468DB00C |
| female-fresh-f006 | 0.030590 | 0.028459 | 1546.440 | 443C6A0B0CEC6DEFF660DDAD8196C1B4F9986EA6385A09679AE3CB7EF8F78DCE |

證據：`artifacts/seed-vc/tiny-four-references/gui-userflow-report.json`、各 case 的 `gui-output-after-vc.wav` 與 `cable-output-loopback.wav`；完整 console 為 `artifacts/seed-vc/tiny-four-references.log`。設定回歸 2/2、launcher preflight exit 0／missing=[]。

模型 code revision `51383efd921027683c89e5348211d93ff12ac2a8`；checkpoint SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`；GPU NVIDIA GeForce RTX 5060 Ti。輸入為既有 `voice-male-m1.wav`，由 callback 注入，未要求使用者先說話。實際 GUI 畫面見本機 `C:\Users\User\AppData\Local\Temp\codex-shot-2026-09-27_06-06-55.png`，22050 Hz／VC mode／reference／MME／VB-CABLE 與 2.5 秒 context 的診斷測試均已目視核對；最終四案回復 5 秒 context。

Cable 在 case 切換時可能殘留 buffer，故不把單獨 cable-first-nonzero 當延遲；本表也不宣稱完整 mic/rack/Discord latency。實體 mic、600 秒穩定、full-chain rack 與人工音質仍 `WAITING`，它們不阻止本次基本安裝測試判定。

## 本輪優先序

先完成有效 GUI 輸出，再下載安裝 MeanVC2／X-VC，實測 source + reference → WAV；Python 統一延後。保留現有 `tools/external`、`tools/venvs`、`models`、`artifacts`，採少量命令 wrapper，不新增常駐服務、registry framework 或資料庫。
