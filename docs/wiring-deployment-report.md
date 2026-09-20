# AetherTune 線路部署與新人操作報告

報告日期：2026-09-19（Asia/Taipei）
工作目錄：`D:\AetherTune`
用途：交給高階模型審查目前部署、證據、限制與後續補缺。

## 1. 結論先行

目前已完成「可開始準備素材」所需的本機軟體與虛擬音訊端點：

- RVC 官方 repo、專案 `.venv`、Torch CUDA、HuBERT、RMVPE 與 RVC 訓練基礎資產已完成。
- Windows 已安裝並列舉 `VB-Audio Virtual Cable`、`VB-Audio Voicemeeter VAIO`。
- 本機麥克風 `HyperX QuadCast S` 可由 FFmpeg DirectShow 列舉。
- VCClient `2.1.4-alpha cuda` 已初始化，Web UI `http://127.0.0.1:18000/` 回應 HTTP 200。
- Light Host Modern `v1.3.1` portable 可啟動；Graillon Free `3.2` 的 VST3/VST2 已安裝。

所以目前不是「所有聲音功能都已驗收完成」，而是：

> 安裝與端點層已就緒；現在主要剩下授權素材、4 組既有 RVC 角色模型的 provenance/register、角色模型載入，以及第一次由 Light Host 設定 input/output 後的 P2/P3 聲音驗收。

最新可重跑的唯讀結果：[`wiring-verification-latest.md`](wiring-verification-latest.md)，目前 `PASS=15 / WAITING=6 / BLOCKED=0`。這個摘要已把「角色模型檔案存在但尚未 register、VCClient embedded CUDA 尚未以角色模型驗證、Graillon 尚未在 host chain 通過、Voicemeeter B1 全零、VCClient localhost 未啟動、ONNX CUDA provider 未實際執行」分開列出。

## 2. 目標線路與實際 Windows 方向

```text
[HyperX QuadCast S 麥克風]
          │ input
          ▼
[VCClient / RVC]
  input: 麥克風
  output: CABLE Input (VB-Audio Virtual Cable)  ← 播放端
          │
          ▼
[VB-CABLE]
  CABLE Output (VB-Audio Virtual Cable)          ← 錄音端
          │
          ▼
[Light Host Modern]
  plugin chain: Graillon Free VST3
  output: Voicemeeter Input (VB-Audio Voicemeeter VAIO)
          │
          ▼
[Voicemeeter Standard]
  Voicemeeter Input / VAIO strip → B bus (Windows endpoint: Out B1)
          │
          ▼
[Discord / OBS / 遊戲語音]
  麥克風輸入選 Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)
```

「Input」與「Output」是 VB-Audio 的方向命名，初學者容易反過來：程式要把聲音送進虛擬線時選 `CABLE Input`；下一個程式要接收時選 `CABLE Output`。

目前已確認裝置存在，但還沒有擅自把 Windows 預設麥克風或 Discord 裝置改掉，也尚未把 Light Host 的音訊裝置設定寫成固定 preset。這樣可以避免在使用者沒有監聽的情況下製造 feedback。

## 3. 已部署元件、責任與證據

| 元件 | 責任 | 本機狀態 | 證據／位置 |
|---|---|---|---|
| Python `.venv` | 專案隔離依賴與 RVC 工具 | PASS | `D:\AetherTune\.venv`；Python 3.12.10 |
| RVC WebUI | 資料前處理、訓練、離線推論 | PASS | `tools/external/Retrieval-based-Voice-Conversion-WebUI`；revision `81eed5e8f68b6bed1789f682fe78cdd324495afc` |
| 專案 Torch | RVC 訓練／離線底層 | PASS | Torch `2.7.1+cu128`；實際 CUDA tensor op 成功 |
| VCClient embedded Torch | 即時前端自己的 runtime | WAITING | 內建 `2.7.0+cu118`；RTX 5060 Ti `sm_120` 尚未以角色模型完成推論 |
| HuBERT/RMVPE | 語音特徵與 f0 | PASS | 已完成 CUDA 載入與 220 Hz 合成音 smoke test |
| RVC 訓練資產 | 讓未來素材可以開始訓練 | PASS | `pretrained/` 12 個、`pretrained_v2/` 12 個、`logs/mute/` 11 個 |
| FFmpeg/FFprobe | 音訊檢查、切片與裝置列舉 | PASS | Gyan FFmpeg 9.0.1；已以絕對路徑驗證 |
| VB-CABLE | 第一段虛擬音訊傳輸 | PASS | Windows endpoint `VB-Audio Virtual Cable` |
| Voicemeeter Standard | 混音、第二段虛擬輸出與 B bus | PASS | Windows endpoint `VB-Audio Voicemeeter VAIO`；錄音端點可能列為 `Voicemeeter Out B1` |
| VCClient | 即時 RVC 前端 | PASS/待模型 | `tools/external/VCClient/2.1.4-alpha`；localhost HTTP 200 |
| Light Host Modern | VST3/VST2 host 與 serial chain | PASS/待設定 | `tools/external/LightHostModern/app/Light Host Modern.exe` |
| Graillon Free 3.2 | 微量 pitch correction | PASS/待 host chain | `C:\Program Files\Common Files\VST3\Auburn Sounds Graillon 3.vst3`；尚無 Light Host active/bypass 證據 |
| 角色 `.pth/.index` | 使用者角色音色 | WAITING | `models/weights/`、`models/indexes/` 有 4 組同名配對，已在 `models/model-register.csv` 登錄為 `candidate`；metadata、ready gate 與 VCClient conversion evidence 尚未完成；見 `docs/current-rvc-model-inventory.md` |

注意：RVC、Light Host Modern 等有開源部分；VB-CABLE、Voicemeeter、Graillon 是免費／免費授權第三方元件，不應統稱為 100% 開源。

### 3.1 資料夾責任切分

```text
D:\AetherTune\
├─ dataset\
│  ├─ raw\          原始、有授權、不可覆寫的乾聲
│  ├─ sliced\       由 raw 衍生的 5–15 秒切片
│  ├─ augmented\    變調等擴增結果
│  └─ manifests\    audit/provenance CSV，不放音訊本體
├─ models\
│  ├─ weights\      使用者角色 .pth
│  ├─ indexes\      使用者角色 .index
│  └─ model-register.csv  權重/index/hash/版本/批次配對登記
├─ tools\
│  ├─ dataset_audit.py          資料輸入 gate
│  ├─ verify_wiring.ps1         本機線路唯讀驗證
│  ├─ virtual_cable_loopback.py 合成音端點測試
│  └─ external\                 第三方 repo、整合包、下載檔；不進 Git
└─ docs\
   ├─ operation-guide.md         新人逐步操作
   ├─ wiring-deployment-report.md 本報告與架構判斷
   ├─ wiring-verification-latest.md 最新機器驗證
   └─ decision-log.md             選型、替代方案與變更規則
```

責任邊界是「原始資料不可被工具覆蓋、衍生資料可重建、模型檔與外部安裝包不進 Git、文件保留來源與驗證證據」。

## 4. 新人一次性操作流程

### A. 準備資料

1. 確認聲音來源本人或取得明確使用權。
2. 將乾聲 WAV 放入 `dataset/raw/`；不要直接覆蓋既有檔案。
3. 先在 `dataset/manifests/source-register.csv` 登記來源、授權／使用權、批次、父檔、衍生關係與目前 WAV 的 `source_sha256`。音檔替換後必須重新登記 hash。
4. 執行：

   ```powershell
   Set-Location D:\AetherTune
   & .\.venv\Scripts\python.exe tools\dataset_audit.py `
     --root dataset\raw `
     --manifest dataset\manifests\raw-audit.csv `
     --fail-on-invalid
   ```

5. 依 audit 結果處理取樣率、聲道、底噪、殘響與疑似靜音；原始檔留在 `raw/`，切片與變調放到對應衍生資料夾。
6. 用 RVC WebUI 做 preprocess、RMVPE f0、HuBERT feature extraction，再開始訓練。
7. RVC checkpoint 留在外部 repo；完成 extraction 後，把 `assets/weights/<name>.pth` 與同一 experiment 的 `logs/<experiment>/added_*.index` 複製到：

   ```text
   models/weights/角色.pth
   models/indexes/角色.index
   ```

8. 依 `models/model-register.example.csv` 建立 `models/model-register.csv`，登記兩檔 SHA-256、取樣率、f0、RVC revision、資料批次、訓練時間與狀態。placeholder hash、retired/candidate 狀態或沒有 register 配對資料，都不能作為 ready 推論模型。

### B. 載入與調整 VCClient

1. 執行 `tools/external/VCClient/2.1.4-alpha/dist/main/start_http.bat`。
2. 開啟 `http://127.0.0.1:18000/`。
3. 上傳／選擇角色模型與 index。
4. 注意 VCClient embedded `Torch 2.7.0+cu118` 與 RTX 5060 Ti `sm_120` 的相容性尚未證明；不要把專案 `.venv` 的 CUDA PASS 當成前端 PASS。先以角色模型完成一次實際推論，記錄 log、GPU 使用與輸出。
5. 初始測試使用 RMVPE；pitch 不要直接假設固定 `+12`，先比較 `+6/+9/+12`。
6. `chunkSec`、`extraFrameSec` 分開記錄，單位都是秒；每次只改一個參數並記錄聽感、p50/p95 延遲、斷音與 underrun。
7. VCClient output 先指定 `CABLE Input (VB-Audio Virtual Cable)`。

### C. 設定 VST host

1. 執行 `Light Host Modern.exe`。
2. 在 Audio 設定 input 選 `CABLE Output (VB-Audio Virtual Cable)`。
3. 設定 output 選 `Voicemeeter Input (VB-Audio Voicemeeter VAIO)`。
4. 在 Plugins 掃描 `C:\Program Files\Common Files\VST3`。
5. 將 Graillon Free 加入 chain；先使用自然、慢速、低深度設定。
6. 先觀察 input/output meter，再做 loopback 錄音；若出現回授，先停輸出，不要繼續提高音量。

### D. 設定 Voicemeeter 與終端

1. 在 Voicemeeter 硬體輸入／虛擬輸入確認有 meter 訊號。
2. 確認 Voicemeeter mixer 引擎、mute、音量與 meter；接收 Light Host output 的 `Voicemeeter Input / VAIO` 虛擬輸入 strip 必須有訊號。
3. Standard 版在該虛擬輸入 strip 啟用 UI 上的 `B` bus；`A` 只作為選用的實體監聽。Windows 錄音端點可能列為 `Voicemeeter Out B1`，這是端點名稱，不是 Standard strip 的 `B1` 按鈕。
4. Discord/OBS 的麥克風選本機列舉的 `Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)`。若錄回全零，先停用通話並逐項檢查上述狀態，再重跑 loopback。
4. 先用錄音或 OBS 本地測試，不要一開始就進公開通話。
5. 用固定測試句確認對方聽到的是變聲後訊號，而不是原始麥克風。

## 5. 日常啟動順序

```text
1. Voicemeeter
2. VCClient
3. Light Host Modern
4. 檢查兩段 meter 與 loopback
5. Discord / OBS 最後啟動或重新選擇 `Voicemeeter Out B1`
```

收工時反向關閉。不要同時在 Discord、OBS、Light Host 監聽同一輸出，除非確定沒有 feedback。

## 6. 驗證分級與目前缺口

| 等級 | 目前結果 |
|---|---|
| P0 來源、版本、授權 | RVC、VCClient、Light Host、Auburn、VB-Audio 官方來源已記錄；授權仍要依各元件條款管理 |
| P1 檔案、hash、GPU、裝置、localhost | 部分通過；專案 Torch 實際 CUDA op 成功，但 VCClient embedded cu118/sm_120 仍 WAITING；詳見 `wiring-verification-latest.md` |
| P2 真實角色模型離線推論 | 已完成 slot／pipeline 選擇層與 conversion probe；REST conversion 被 packaged API 的 `vc_chunk_sec/chunk_sec` AttributeError 阻塞，尚無可驗證輸出 WAV；register 來源／授權 metadata 仍待補齊 |
| P3 麥克風→VC→VST→loopback→Discord/OBS | 尚未完成；VB-CABLE 合成 loopback PASS，但 Voicemeeter `Input → B1` 合成 loopback 目前 RMS=0，Light Host 的實際 device/chain 與 Discord/OBS 仍需設定與聽測 |

合成音證據必須同時包含 WAV 與同名 JSON；JSON 保存 48 kHz、時長、frames、RMS、peak、測試參數與 WAV SHA-256。既有 WAV 若沒有 JSON，重新執行 loopback 後才能重新判定。Voicemeeter B1 全零只能表示當次沒有收到足夠訊號，不能直接推論單一原因。

另外，VCClient 2.1.4-alpha 啟動輸出出現內建 PyTorch 不認得 RTX 5060 Ti `sm_120` 的警告。這不影響目前「Web UI 可回應」的判定，但會影響 GPU 角色推論是否真的可用；模型產生後必須優先驗證，必要時改用相容 ONNX/DirectML 或更新前端。

VCClient 的獨立驗收步驟與失敗分流見 [`vcclient-runtime-gate.md`](vcclient-runtime-gate.md)。

## 7. 給高階模型的審查問題

1. VCClient 是否應改成與 RTX 5060 Ti `sm_120` 相容的更新版／ONNX 路徑？
2. Light Host Modern 是否能以目前版本穩定選到 `CABLE Output → Voicemeeter Input`，還是應改用 Carla／其他 host？
3. Voicemeeter Standard 的 `Voicemeeter Input → B1` 為何目前全零：mixer bus、mute/volume、引擎或 endpoint 哪一項仍未就緒？
4. 角色模型完成後，VCClient embedded `cu118` 是否能在 RTX 5060 Ti `sm_120` 實際輸出；若不能，應採相容 CUDA 包還是量測 ONNX/DirectML？
5. Light Host + Graillon 的 bypass/active 延遲與自然度比較結果，是否足以保留目前選型？

## 8. 可重跑命令

```powershell
Set-Location D:\AetherTune
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\wiring-verification-latest.md
git diff --check
```

本報告不把背景程序、下載完成或畫面能開啟當成完整聲音成功；最後判定仍以 P2/P3 的可追溯錄音、meter、延遲與終端收音證據為準。
