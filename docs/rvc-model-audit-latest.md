# RVC 模型與訓練資料 Audit

更新日期：2026-09-21

## 最新結果

| Gate | 狀態 | 證據 |
|---|---|---|
| 四組 `.pth/.index` 配對、檔案存在與 SHA-256 | PASS | `artifacts/rvc-model-audit/rvc-model-audit.json` |
| model register schema | PASS | 已加入來源、授權、訓練環境、verification artifact 欄位 |
| provenance／訓練 metadata | WAITING | 四組目前仍是 `candidate`，sample rate、f0、version、dataset batch、revision、來源與授權保留 `unknown-*` |
| `dataset/raw` audit | BLOCKED | 執行 `tools/dataset_audit.py --fail-on-invalid`；目前沒有 WAV，只有 `dataset/raw/README.md` |
| ready gate | WAITING | 沒有任何模型符合完整 metadata、verification artifact 與 ready 條件 |

模型 audit 可重跑：

```powershell
Set-Location D:\AetherTune
& .\.venv\Scripts\python.exe .\tools\rvc-model-audit.py
```

若要在 CI／交接時把 WAITING 當錯誤：

```powershell
& .\.venv\Scripts\python.exe .\tools\rvc-model-audit.py -FailOnWaiting
```

這個工具會重新計算兩個檔案的 SHA-256、檢查未登記配對與欄位，不會自動修改 CSV，也不會把 `candidate` 升成 `ready`。

## 建立可訓練資料集的下一步

1. 只放已取得授權的單一說話者原始 WAV 到 `dataset/raw/`。
2. 在 `dataset/manifests/source-register.csv` 登記 `source_id`、原始檔 SHA-256、授權／同意、batch 與 derivation。
3. 執行 `tools/dataset_audit.py`，確認 sample rate、單聲道、RMS、peak、有效訊號比例與 provenance。
4. 留出不參與訓練的 test set，完成 preprocess／f0／feature extraction 後才訓練。
5. 用 `tools/rvc-register-model.ps1 -DryRun` 計算模型 hash，填入真實的 `fcpe`／`rmvpe`、RVC revision、dataset batch、訓練環境、來源與授權。
6. 完成離線輸出、VCClient 真實載入、latency／dropout 與人工聽測後，才提供 `verification_artifact` 並考慮 `ready`。

## 邊界

- 現有四組模型已可作為離線比較的 `candidate`，但不能宣稱是來源可追溯、可公開使用的 ready 模型。
- `RVC + FCPE + GPU` 的離線輸出證據與模型 provenance 是兩個不同 gate；前者 PASS 不會自動解鎖後者。
- 下載的第三方角色模型不能改名成自訓模型；來源頁面、license／permission 與用途限制要以人工可核對資料填寫。
