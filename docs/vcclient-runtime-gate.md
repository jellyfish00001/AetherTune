# VCClient 即時前端相容性 Gate

**文件邊界：**本頁只定義 packaged VCClient 與專案 RVC runtime 必須分開驗證的條件及失敗分流；實際版本、CUDA 警告、sample／角色輸出及當次 PASS／WAITING 由[packaged 修復報告](vcclient-packaged-repair-latest.md)、[RVC 音訊驗證](vcclient-rvc-probe-latest.md)及[線路驗證](wiring-verification-latest.md)負責。

## 為什麼獨立驗收

專案 `.venv` 與 packaged VCClient 各自內含模型執行環境；一方的 CUDA tensor、FCPE 或離線 WAV 成功，不會讓另一方自動通過。VCClient 須在自己的 embedded runtime 下產生同輪有效角色輸出，並記錄實際 GPU provider、slot 與模型身分。Web UI `HTTP 200`、sample slot 存在或官方 ONNX 範例的 chunk request 也不能代替可播放角色音訊。當次版本與錯誤細節請看上述分項報告。

## 有角色模型後的驗收順序

1. 確認 `models/model-register.csv` 的 `.pth/.index` 配對、hash、取樣率與資料批次完整。
2. 啟動 VCClient，載入該角色模型與 index；記錄 VCClient log 的 slot、model、f0、sample rate 與 device。
3. 使用同一段短測試語句，先測 `pass-through` 或最小 buffer，再做 RVC inference；不要先進 Discord 公開通話。
4. 記錄：VCClient process log、GPU device／GPU utilization、輸出 WAV、實際 p50/p95 latency、斷音與 underrun。
5. 只有當輸出不是空檔、log 沒有 CUDA fallback／unsupported kernel／exception，且 10 分鐘連續測試達到驗收門檻，才把 gate 改成 PASS。

## 失敗時的分流

- 若 embedded PyTorch 在 `sm_120` 失敗：先查官方 VCClient package 是否有與 CUDA 12.8／Blackwell 相容的 edition；不要把 Beatrice-only package 當成 RVC replacement。
- 若前端的 ONNX 模式可推論但 CUDA provider 失敗：保留 CPU/DirectML 作為相容性實驗，重新量測延遲；不能把 CPU 輸出標為 GPU 即時方案。
- 若只能載入模型、不能產生輸出：保留 WAITING/BLOCKED，並將錯誤 log 與測試 artifact 登記到報告。

RVC WebUI 離線輸出、packaged VCClient 輸出及下游實體線路的結果各在對應驗證報告，不可互相代替。
