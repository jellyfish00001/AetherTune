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

另外核對的環境資料（四案原始 JSON 產生於 metadata 欄位新增前）：code revision `51383efd921027683c89e5348211d93ff12ac2a8`；checkpoint SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`；GPU NVIDIA GeForce RTX 5060 Ti。輸入為既有 `voice-male-m1.wav`，SHA-256 `3A4A5A048154CFF60D717FC1FCE929EBEBC887F7C9222C56222DAD48ADB60662`，由 callback 注入，未要求使用者先說話。實際 GUI 畫面見本機 `C:\Users\User\AppData\Local\Temp\codex-shot-2026-09-27_06-06-55.png`，22050 Hz／VC mode／reference／MME／VB-CABLE 與 2.5 秒 context 的診斷測試均已目視核對；最終四案回復 5 秒 context。

Cable 在 case 切換時可能殘留 buffer，故不把單獨 cable-first-nonzero 當延遲；本表也不宣稱完整 mic/rack/Discord latency。實體 mic、600 秒穩定、full-chain rack 與人工音質仍 `WAITING`，它們不阻止本次基本安裝測試判定。

最後 metadata 複核：相同 tiny／5 秒 context／4 CPU worker／female-young-f004 命令，輸出到 `artifacts/seed-vc/tiny-final-metadata`，exit 0／`PASS`；report 已包含 checkpoint hash、code revision、Torch 2.7.1+cu128、CUDA 12.8、CUDA 0 與 GPU 名稱。該次首次 callback 非零輸出 `12.623 秒`，顯示啟動／warm-up 會變動；前表的約 1–2 秒不能作為每次冷啟動保證，也不能推導 LIVE <= 5s。基本非零音訊 PASS 保留，LIVE timing 仍 `WAITING`。

## 本輪優先序

先完成有效 GUI 輸出，再下載安裝 MeanVC2／X-VC，實測 source + reference → WAV；Python 統一延後。保留現有 `tools/external`、`tools/venvs`、`models`、`artifacts`，採少量命令 wrapper，不新增常駐服務、registry framework 或資料庫。

## 階段 2：MeanVC2／X-VC 安裝與 CUDA 音訊 — PASS

兩個 backend 已完成公開模型下載、隔離環境安裝、`pip check`、必要權重 hash，以及實際男→女／女→男 file-driven streaming WAV。新安裝腳本已在本機既有環境重跑成功，沒有宣稱全新 Windows 主機 bootstrap。MeanVC2 使用 Python 3.11，X-VC 使用 Python 3.10，兩者 Torch 2.7.1+cu128／CUDA 12.8；不為統一 Python 版本阻止使用。

| Backend | 程式碼 revision | 主模型 HF snapshot | 本機安裝／音訊 |
|---|---|---|---|
| MeanVC2 | 13acf84c1bf135ea5edad9c245b345289b06b33e | 39cdd19522fe896c227da691314d9a0e3b995486 | `PASS`；40ms 男→女、120ms 女→男；ASR CPU，VC／speaker／vocoder CUDA 0 |
| X-VC | 49df8c591eafc48b096e466d96f9839f9c0dd739 | 9e54747d8c4d1ef544b903e2300a4ba040dcc126 | `PASS`；雙向 current=160、chunk=2400、future=80、smooth=20；主模型 CUDA 0 |

實際 source/reference：`voice-male-m1.wav` 14.87965 秒／hash 見階段 1；`voice-female-f1.wav` 13.40198 秒／SHA-256 `37976F69F73FB13D6FEFAF80268794D545D6E19BE5059437DB067455A795F406`。以下四案均 finite、RMS > 0.0001、16 kHz，通過的是有效模型音訊，不是自然度或目標音色的人工分數。

| Backend／方向 | Artifact（在 artifacts/ 下） | 秒數 | RMS | SHA-256 |
|---|---|---:|---:|---|
| MeanVC2 男→女 40ms | meanvc2/male-to-female.wav | 14.87 | 0.063649 | A976AA1993C64BEFA1AC5529564135A951759B6016C3301C91DFAB3380866ED3 |
| MeanVC2 女→男 120ms | meanvc2/female-to-male.wav | 13.31 | 0.082724 | 8DA7D146364C88EFA302F525B17391520DC6969F73B7D58992415AC902D482AC |
| X-VC 男→女 | xvc/male-to-female/voice-female-f1_voice-male-m1_stream_chunk_2400_current_160_smooth_20_future_80.wav | 14.88 | 0.034192 | A51DADB11B608651B96FED4DC2DCC518DC97B417FD49AFA7C39BB01FDFE47CCF |
| X-VC 女→男 | xvc/female-to-male/voice-male-m1_voice-female-f1_stream_chunk_2400_current_160_smooth_20_future_80.wav | 13.44 | 0.056723 | 7C786E4480B7E0F62CBB10A5A0D59AA25FC858F6591BF8E6FCE39A05FFE43A10 |

初次 MeanVC2 40ms file inference 約 12.5 秒／RTF 0.843，120ms 約 4.0 秒／RTF 0.299；這兩案方向不同且有首次 warm-up 差異，不作同條件速度排名。X-VC final evidence 的 model load + inference 為 42.406 秒，不能當 first-packet latency。wrapper 都不宣稱 GUI、mic 或 LIVE PASS。

實際安裝重跑命令（exit 0）：

```powershell
pwsh -NoProfile -File tools/streaming-backend-setup.ps1 -Backend meanvc2 -Python C:/Users/User/AppData/Roaming/uv/python/cpython-3.11.15-windows-x86_64-none/python.exe
pwsh -NoProfile -File tools/streaming-backend-setup.ps1 -Backend xvc
# 已安裝環境平日只需唯讀重驗，不重新 pip/checkout/download：
pwsh -NoProfile -File tools/streaming-backend-setup.ps1 -Backend meanvc2 -VerifyOnly
pwsh -NoProfile -File tools/streaming-backend-setup.ps1 -Backend xvc -VerifyOnly
```

setup 在已有 venv 時優先解析其 base Python；新環境可明確提供 `-Python`。它不下載 Python，也不覆寫其他 backend。上游 MeanVC2 initialization 的 WavLM GitHub URL 實際 404，改用 [Microsoft 官方 README](https://github.com/microsoft/unilm/blob/master/wavlm/README.md) 的 Google Drive；finetune 依 MeanVC2 官方 initialization 所列 Drive，兩者 bytes 已固定 hash。X-VC 主模型與 GLM tokenizer 固定 HF revision；ERes2Net 上游 immutable revision 未取得，以 observed weight hash 固定，變更就停止。

實際推論命令（兩方向均 exit 0；每次新目錄）：

```powershell
& tools/venvs/meanvc2/Scripts/python.exe tools/meanvc2-run.py --source dataset/reference-voices/voice-male-m1.wav --target dataset/reference-voices/voice-female-f1.wav --output artifacts/meanvc2/my-male-to-female.wav --model 40ms
& tools/venvs/meanvc2/Scripts/python.exe tools/meanvc2-run.py --source dataset/reference-voices/voice-female-f1.wav --target dataset/reference-voices/voice-male-m1.wav --output artifacts/meanvc2/my-female-to-male.wav --model 120ms
& tools/venvs/xvc/Scripts/python.exe tools/xvc-run.py --source dataset/reference-voices/voice-male-m1.wav --target dataset/reference-voices/voice-female-f1.wav --output-dir artifacts/xvc/my-male-to-female
& tools/venvs/xvc/Scripts/python.exe tools/xvc-run.py --source dataset/reference-voices/voice-female-f1.wav --target dataset/reference-voices/voice-male-m1.wav --output-dir artifacts/xvc/my-female-to-male
```

WAV 與 JSON 證據留在 artifacts；MeanVC2 使用 `<WAV stem>.run-evidence.json`，防止兩方向覆寫同一報告；X-VC 使用 `run-evidence.json`，拒絕含既有 WAV 的 output directory。安裝資產記錄為 `artifacts/{meanvc2,xvc}/install-assets.json`；原始批次 hash／WAV 指標為 `artifacts/backend-install-evidence.json`。final wrapper evidence 保留 load 時間、實際 parameter device、code revision、source/reference/model/output hash。weights、cache、env、WAV 全部 ignored，不進 Git。

MeanVC2 另可執行 `--realtime --target <reference.wav>`，進入官方互動式選裝置；本輪只實測 file mode，故麥克風模式仍 `WAITING`。X-VC 使用官方 CLI，沒有新增 web app／服務。兩者人工聽評、mic、rack、600 秒與正式感知評估留待基本安裝測試完成之後。
