# RVC + FCPE／RMVPE

**文件邊界：**本頁負責 RVC adapter 的模型格式、runtime 與 FCPE／RMVPE 參數；Desktop 步驟看[Desktop 手冊](../../docs/guides/desktop-user-guide.md)，訓練看[訓練手冊](../../docs/guides/model-training-guide.md)，實測結果看[RVC 音訊驗證](../../docs/verification/backends/vcclient-rvc-probe-latest.md)。Desktop 使用專案 headless runner 重用固定 RVC 推論核心；VCClient 是另外的歷史前端，其 [runtime gate](../../docs/specs/vcclient-runtime-gate.md) 不會被 Desktop 測試覆蓋。

人類入口：先讀 [`docs/guides/user-guide.md`](../../docs/guides/user-guide.md)；要準備資料、訓練與登錄 `.pth/.index` 讀 [`docs/guides/model-training-guide.md`](../../docs/guides/model-training-guide.md)；要接 VCClient、VST、VB-CABLE、Discord／OBS 讀 [`docs/guides/operation-guide.md`](../../docs/guides/operation-guide.md)。

## 目前設定

- 訓練／推論：RVC WebUI，revision 以 `docs/reference/source-audit.md` 的固定值為準。
- 音高擷取：**FCPE 首選，RMVPE 備用**。
- Desktop runtime：`.venv/Scripts/python.exe`；`services/engines/rvc_runtime.py` 讀固定 checkout 的 `infer/rtrvc.py`，在 48 kHz rolling buffer 進行 HuBERT、F0、index、角色模型及 SOLA 交疊。要求 CUDA；缺少資產、hash 不符或 GPU 不可用時回報錯誤，不暗中回退。
- 可調參數的型別、範圍與 defaults 由 `contracts/engines/rvc.json` 唯一宣告；`model_id` 只能選登錄的四個角色，`.pth/.index` 由 register 配對。RVC 不需要 zero-shot Reference WAV；Mic 與來源 WAV 使用同一轉換核心。
- 主輸出與自己監聽分開，監聽預設關閉；已知虛擬線路不可作監聽端。同一 CABLE 的一般／16ch 播放端不得回送來源端。Mic 串流目前要求輸入／主輸出使用同一 Host API，監聽可以用另一個 API。
- 現有模型交接路徑：`models/weights/`、`models/indexes/`、`models/model-register.csv`。這些舊路徑先保留，避免破壞既有 verifier 與文件。
- 角色模型名稱、配對與 hash 由 `models/model-register.csv` 及[人類可讀盤點](../../docs/reference/current-rvc-model-inventory.md)負責；離線推論和 VCClient realtime 分別驗證。
- VCClient 的 role model 需要透過其 slot/upload path 建立到自己的 `model_dir`；請使用 `tools/vcclient-rvc-register.ps1`，不要直接複製大型模型進 Git。最新 packaged 修復、限制與 conversion 證據見 [`docs/verification/backends/vcclient-packaged-repair-latest.md`](../../docs/verification/backends/vcclient-packaged-repair-latest.md)。
- RVC 輸出交給共用 [`audio-rack/`](../../audio-rack)；full-chain loopback 與延遲證據由[線路驗證](../../docs/verification/audio/wiring-verification-latest.md)負責。

## 驗證順序

```powershell
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe tools\fcpe_probe.py --skip-vcclient --artifact artifacts\fcpe-probe.json
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\verification\audio\wiring-verification-latest.md
```

FCPE probe 的 artifact 必須查看 `device`、實際執行 provider、輸出誤差與時間；不能只看套件存在或 provider 清單。

FCPE synthetic probe 的裝置、誤差與當次結果讀 `artifacts/fcpe-probe-latest.json`；它不能代替角色模型音訊或 packaged VCClient 驗證。

Desktop 原生 block／音訊 smoke 使用 `app/tests/rvc-audio-smoke.py`；舊離線 pipeline 仍用 `tools/rvc-fcpe-gpu-infer.py`。可重跑命令、輸出 hash 與各自驗證範圍見 [RVC 最新矩陣](../../docs/verification/backends/vcclient-rvc-probe-latest.md)。
