# VCClient 即時前端相容性 Gate

## 為什麼獨立驗收

專案 `.venv` 與 VCClient 是兩個不同 runtime。現在的本機證據是：

- AetherTune `.venv`：Torch `2.7.1+cu128`，RTX 5060 Ti `sm_120`，實際 CUDA tensor op 成功。
- VCClient `2.1.4-alpha cuda`：embedded Torch `2.7.0+cu118`；啟動 log 顯示 CUDA build `11.8`，並曾警告 `sm_120` 不在該 PyTorch build 的相容清單。官方 runtime repair 已可重現恢復 module/sample assets。
- 最新 probe 已以官方 ONNX sample 取得非零輸出 WAV；這證明 packaged RVC offline path 可用，但不是四組自有角色模型、GPU provider 或即時音訊鏈路的完整證據。

因此不能用專案 venv 的 PASS 代替 VCClient PASS，也不能因 Web UI `HTTP 200` 或 sample slot 存在就宣布即時變聲可用。

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

目前狀態：`PASS（official sample offline）/WAITING（custom roles, GPU provider, realtime chain）`。最新短音檔證據見 [`vcclient-rvc-probe-latest.md`](vcclient-rvc-probe-latest.md)；四組自有角色仍須各自輸出驗收。
