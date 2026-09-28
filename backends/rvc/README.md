# RVC（historical baseline）

**文件邊界：**本頁負責 RVC adapter 的模型格式、FCPE／RMVPE 與 VCClient 交接命令；訓練看[訓練手冊](../../docs/guides/model-training-guide.md)，實測結果看[RVC 音訊驗證](../../docs/verification/backends/vcclient-rvc-probe-latest.md)及[VCClient runtime gate](../../docs/specs/vcclient-runtime-gate.md)。RVC 沿用既有 `tools/external/Retrieval-based-Voice-Conversion-WebUI` 與 VCClient，保留作 latency、失真與路由的歷史對照。

人類入口：先讀 [`docs/guides/user-guide.md`](../../docs/guides/user-guide.md)；要準備資料、訓練與登錄 `.pth/.index` 讀 [`docs/guides/model-training-guide.md`](../../docs/guides/model-training-guide.md)；要接 VCClient、VST、VB-CABLE、Discord／OBS 讀 [`docs/guides/operation-guide.md`](../../docs/guides/operation-guide.md)。

## 目前設定

- 訓練／推論：RVC WebUI，revision 以 `docs/reference/source-audit.md` 的固定值為準。
- 音高擷取：**FCPE 首選，RMVPE 備用**。
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

四組角色的實際 FCPE + GPU 推論請使用 `tools/rvc-fcpe-gpu-infer.py`，最新矩陣見 [`docs/verification/backends/vcclient-rvc-probe-latest.md`](../../docs/verification/backends/vcclient-rvc-probe-latest.md)。
