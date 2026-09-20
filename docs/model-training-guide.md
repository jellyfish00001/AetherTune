# RVC 模型訓練與模型管理

這份文件只處理 RVC。Seed-VC、CosyVoice、Breeze TTS 2 的一般使用不需要先訓練一個 RVC 角色 `.pth/.index`。

## 1. 訓練前要準備什麼

- 已取得授權的單一說話者乾聲。
- 沒有背景音樂、嚴重殘響、剪輯爆音或多人重疊。
- 建議準備 5–15 秒切片，另外保留未參與訓練的測試句。
- `dataset/raw/` 只放原始來源；衍生檔放 `dataset/sliced/` 或 `dataset/augmented/`。
- 每批資料要在 `dataset/manifests/source-register.csv` 登記來源、授權、batch、父檔與 hash。

不要先把網路下載的角色 `.pth` 當成自己訓練的模型，也不要把 TTS 生成語音默認當作真人乾聲。

## 2. 資料檢查

```powershell
Set-Location D:\AetherTune
& .\.venv\Scripts\python.exe tools\dataset_audit.py `
  --root dataset\raw `
  --manifest dataset\manifests\raw-audit.csv `
  --source-register dataset\manifests\source-register.csv `
  --fail-on-invalid
```

先查看 manifest，再做人工抽查：取樣率、聲道、空白比例、RMS、peak、噪音、殘響、切片長度與授權欄位。audit 通過只表示資料格式與基本 gate 通過，不表示模型品質會好。

## 3. 切片與資料集分割

使用固定 RVC revision 內的 slicer 或既有 WebUI 工具切片。建議：

1. 將過長句切成約 5–15 秒。
2. 保留短句、子音、尾音、停頓與不同音高。
3. 留出一批完全不參與訓練的 test set。
4. 不要把同一句話的微小剪輯同時放入 train 與 test。
5. 不覆寫 `dataset/raw/`，衍生檔要能回溯 parent hash。

## 4. RVC 訓練

啟動既有 RVC WebUI：

```powershell
Set-Location D:\AetherTune\tools\external\Retrieval-based-Voice-Conversion-WebUI
# 依該 revision 的官方啟動方式啟動 WebUI；不要另建第二份 RVC repo
```

在 WebUI 中依序完成：

1. 指定 experiment／角色名稱與訓練資料目錄。
2. 設定 sample rate；後續 register、VCClient 與測試裝置要一致。
3. 先執行 preprocess、f0 extraction、HuBERT feature extraction 的小批次檢查。
4. pitch extraction 優先使用 FCPE；若該上游 WebUI revision 沒有 FCPE 選項，使用 RMVPE 並在 register 記錄 `rmvpe`。
5. 先做候選訓練，約 150–300 epochs 作為起點；epoch 不是品質保證。
6. 用保留 test set 聽測，不要只看訓練 loss。

目前專案的 FCPE 是 runtime 首選，但「訓練介面是否提供 FCPE」要以實際固定 revision 的 WebUI 為準。不要把 runtime 的 FCPE 設定倒推成訓練 metadata。

## 5. 交接 `.pth` 與 `.index`

訓練完成後，從 RVC repo 找到同一個 experiment 的 `.pth` 與 `.index`，複製到：

```text
models/weights/<model_id>.pth
models/indexes/<model_id>.index
```

命名的 basename 必須一致。先產生 hash：

```powershell
$modelId = 'my-role'
$weights = "models\weights\$modelId.pth"
$index = "models\indexes\$modelId.index"
Get-FileHash $weights -Algorithm SHA256
Get-FileHash $index -Algorithm SHA256
```

再依 `models/model-register.example.csv` 將實際資料寫入 `models/model-register.csv`。至少填入：

- `model_id`
- weights/index 相對路徑與各自 SHA-256
- sample rate
- 真實 f0 method：`fcpe` 或 `rmvpe`
- RVC version、固定 revision、dataset batch、訓練時間
- `candidate` 或 `ready`
- 來源、授權與備註

`ready` 只代表檔案與 metadata 完整仍不夠；還要完成離線聽測、VCClient 真實載入、延遲與路由驗收。

## 6. RVC 推論驗收

先跑固定 test set，再測參數矩陣。一次只改一個參數：

| 參數 | 起始候選 | 觀察項目 |
|---|---|---|
| pitch | `+6 / +9 / +12` | 音域、自然度、破音 |
| index rate | `0.0 / 0.5 / 0.7` | 音色、咬字、金屬聲 |
| chunkSec | `0.25 / 0.50 / 0.75` | 延遲、斷音、穩定度 |
| extraFrameSec | `0.04 / 0.08 / 0.12` | 尾音與延遲折衷 |
| f0 | FCPE／RMVPE | 音高追蹤、抖動與失真 |

記錄到 `docs/parameter-matrix-template.csv` 的欄位，包含 model/hash、test sentence、sample rate、p50/p95 latency、underrun、dropout、artifact 與人工聽測。

## 7. 接到 VCClient 與即時路由

只有離線結果穩定後才接：

```text
麥克風 → VCClient/RVC → VB-CABLE → Light Host + Graillon
→ Voicemeeter → Discord／遊戲／OBS
```

完整裝置方向、VST 掃描、B1 bus 與 loopback 步驟見 [`operation-guide.md`](operation-guide.md)。目前 VCClient Web UI 已可開啟，但工作區角色模型載入與真實 GPU 推論仍未完成，因此不要把整條鏈路標成 ready。

## 8. 另外兩條路線為什麼不需要這份訓練流程

- Seed-VC：下載 checkpoint，給 source 與 reference，直接做 zero-shot conversion；使用 [`backends/seed-vc/README.md`](../backends/seed-vc/README.md)。
- CosyVoice／Breeze：先做 STT，再把 transcript 與 reference audio 送入 TTS；需要 exact transcript 與獨立環境，不使用 RVC `.pth/.index`。使用 [`backends/speech-reconstruction/README.md`](../backends/speech-reconstruction/README.md)。
