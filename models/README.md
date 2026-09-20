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
- RVC repo revision、訓練時間、狀態與備註。

`model-register.example.csv` 是欄位範例；真正模型產生後，複製相同欄位到 `model-register.csv`，不可把 `REPLACE_WITH_SHA256` 留在 `ready` 記錄。

## 可接受狀態

- `candidate`：可做離線比較，尚未成為日常 preset。
- `ready`：`.pth`、`.index`、hash、取樣率、資料批次及保留測試集證據均已登記。
- `retired`：保留追溯用途，不再載入即時前端。

驗證器只會把具有可追溯 register 的模型配對提升為 PASS；檔案存在但缺少 register 時仍是 WAITING。
