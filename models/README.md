# models

這一層只保存角色模型的交接資訊；實際大型模型檔案不進 Git。

## 來源與交接

RVC WebUI 的訓練過程會在外部 RVC repo 內產生不同用途的檔案：

1. `logs/<experiment>/G_*.pth`、`D_*.pth` 是訓練 checkpoint，不是日常推論交付物。
2. `assets/weights/<name>.pth` 是由 RVC 的 checkpoint extraction 產出的推論權重；目前上游 `train/process_ckpt.py` 的 `savee()` 就寫入此路徑。
3. `logs/<experiment>/added_*.index` 是同一個 experiment 的特徵索引。
4. 完成訓練與 extraction 後，才把最終 `.pth` 複製到 `models/weights/`，把配對的 `.index` 複製到 `models/indexes/`。

不要直接把 `G_*.pth` 改名冒充推論模型，也不要只依檔名猜 index 配對。每次交接都要在 `models/model-register.csv` 登記：

- `model_id`、兩個相對路徑與各自 SHA-256。
- 取樣率、f0、RVC version、訓練資料 `dataset_batch_id`。
- RVC repo revision、訓練時間、來源 URL、授權／使用權、訓練環境與 verification artifact。

`model-register.example.csv` 是欄位範例；真正模型產生後，複製相同欄位到 `model-register.csv`，不可把 `REPLACE_WITH_SHA256` 留在 `ready` 記錄。

目前工作區已有 4 組同名 `.pth`／`.index`，已登記為 `candidate` 並保留 hash；來源、授權、取樣率、f0、版本、訓練環境與測試證據仍是 `WAITING`。用 `tools/rvc-model-audit.py` 會逐列重算 hash 並列出缺欄，不會把 unknown 猜成真值。

## 建議登記命令

新模型不要手動猜 hash；使用註冊腳本，它會確認檔案位於 repository、檔案副檔名、hash 與 duplicate model id：

```powershell
& .\tools\rvc-register-model.ps1 `
  -ModelId my-role `
  -WeightsPath .\models\weights\my-role.pth `
  -IndexPath .\models\indexes\my-role.index `
  -SampleRate 40000 -F0 fcpe -Version v2 `
  -DatasetBatchId raw-2026-09-21 `
  -RvcRevision '<固定 commit>' `
  -SourceUrl '<來源頁面>' `
  -LicenseOrPermission '<授權或本人錄音同意>' `
  -TrainingEnvironment '<Python/Torch/GPU>' `
  -Status candidate
```

先加 `-DryRun` 只計算 hash；確認資料正確後再移除。完成後執行：

```powershell
& .\.venv\Scripts\python.exe .\tools\rvc-model-audit.py
```

## 可接受狀態

- `candidate`：可做離線比較，尚未成為日常 preset。
- `ready`：`.pth`、`.index`、hash、取樣率、資料批次及保留測試集證據均已登記。
- `retired`：保留追溯用途，不再載入即時前端。

驗證器只會把具有可追溯 register 的模型配對提升為 PASS；`candidate`、unknown provenance、hash mismatch、未登記配對或缺少 verification artifact 都不能成為 `ready`。
