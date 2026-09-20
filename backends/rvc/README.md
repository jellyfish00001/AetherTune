# RVC（目前主線）

RVC 是目前 AetherTune 的即時變聲主線，沿用既有 `tools/external/Retrieval-based-Voice-Conversion-WebUI` 與 VCClient。

人類入口：先讀 [`docs/user-guide.md`](../../docs/user-guide.md)；要準備資料、訓練與登錄 `.pth/.index` 讀 [`docs/model-training-guide.md`](../../docs/model-training-guide.md)；要接 VCClient、VST、VB-CABLE、Discord／OBS 讀 [`docs/operation-guide.md`](../../docs/operation-guide.md)。

## 目前設定

- 訓練／推論：RVC WebUI，revision 以 `docs/source-audit.md` 的固定值為準。
- 音高擷取：**FCPE 首選，RMVPE 備用**。
- 現有模型交接路徑：`models/weights/`、`models/indexes/`、`models/model-register.csv`。這些舊路徑先保留，避免破壞既有 verifier 與文件。
- 目前有 4 組本機角色 `.pth/.index` 配對，已寫入 `models/model-register.csv` 作為 `candidate`；hash 已確認，但來源、授權與訓練 metadata 尚未補齊，且 VCClient REST conversion probe 仍被 packaged API error 阻塞。名稱與 hash 見 `docs/current-rvc-model-inventory.md`；RVC 基礎資產與環境通過不等於角色模型或端到端語音驗收通過。
- VCClient 的 role model 需要透過其 slot/upload path 建立到自己的 `model_dir`；AetherTune 不會把大型模型複製進 Git。最新同步、重啟與 conversion 結果見 [`docs/vcclient-rvc-probe-latest.md`](../../docs/vcclient-rvc-probe-latest.md)。

## 驗證順序

```powershell
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe tools\fcpe_probe.py --skip-vcclient --artifact artifacts\fcpe-probe.json
& .\tools\verify_wiring.ps1 -RunInferenceProbes -OutFile .\docs\wiring-verification-latest.md
```

FCPE probe 的 artifact 必須查看 `device`、實際執行 provider、輸出誤差與時間；不能只看套件存在或 provider 清單。
