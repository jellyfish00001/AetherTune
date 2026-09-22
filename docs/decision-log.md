# AetherTune 選型與替代方案紀錄

本文件不是永久綁定；每個模組都可替換，但替換時要重新做相容性、授權、延遲與音質驗證。

## 2026-09-22：從 RVC-centric 改為 Research Workbench

決定：將 AetherTune 的核心定義改為「本地 Streaming VC 與 Speech Reconstruction 比較工作台」，以完整端到端 `<= 5 秒` 作為 `LIVE` 分類門檻；`> 5 秒` 只列為 `OFFLINE`，不與 Live 混排。

理由：現有 RVC packaged realtime 有 invalid／全零 chunk，Seed-VC headless evidence 比較接近即時主線，而 CosyVoice／Breeze 的 runtime／RTF 證據不能代替完整 mic E2E。把 Post-FX、routing、benchmark 從 RVC 抽成共用層，才能公平比較模型與後製鏈。

採納內容：

- `audio-rack/` 是 cross-cutting infrastructure，不是第五個 backend。
- benchmark 分為 Live Technical、Acoustic Objective、Human Listening；任何一層都不能冒充另一層。
- RVC 降為 historical baseline；Seed-VC upstream 保留為 established baseline。
- Seed-VC realtime fork、MeanVC2、CosyVoice3 只建立 candidate intake，不在本輪下載權重或宣稱 runtime PASS。
- Pitch correction 必須 optional；VST latency 用 bypass/full-chain 實測 Δ，不用元件數量猜測。

撤回／回滾：保留既有 RVC verifier、模型 register、runtime artifact 與 Windows route 文件；若新候選 intake 失敗，只移除候選 profile，不回退到把 RVC 稱為唯一主線。完整契約見 [`architecture.md`](architecture.md)、[`live-gate.md`](live-gate.md)、[`audio-rack/`](../audio-rack/) 與 [`benchmarks/`](../benchmarks/)。

## 2026-09-22：Audio Rack profile 與 evidence contract

決定：先把 `audio-rack/` 的 profile、route、preset 與 A/B evidence schema 登記完成，再進行 Light Host 實際 plugin loading；任何 profile 的 `candidate-unverified`、`WAITING` 與 synthetic route `PASS` 都不代表人類批准或完整 LIVE。

證據：`audio-rack/routing/seed-vc-virtual-route.json` 對應已通過的 VB-CABLE／Voicemeeter synthetic route；`audio-rack/plugin-profiles/graillon-free-3.2.json` 保留 binary PASS、host loading WAITING；`audio-rack/benchmarks/rack-evidence-v1.schema.json` 與 `tools/audio-rack-evidence-validate.py` 固定 paired bypass/full-chain、Δ latency、輸出 hash 與 continuity 欄位。

下一步：以同一 Seed-VC source、同一 route 完成 Light Host bypass 與 Graillon full-chain paired run；若缺少實際 plugin output、timing 或人工聽測，維持 `WAITING`。

## 目前選擇

| 模組 | 目前選擇 | 選擇原因 | 何時改選 |
|---|---|---|---|
| 訓練核心 | [RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) | 有完整 Windows/Python/CUDA 路徑、`.pth`/`.index` 產物、RMVPE 與少量資料訓練流程，適合自訂角色音色 | 需要不同模型格式、商業支援或明確歌唱優化時 |
| f0 | FCPE（推薦首選）/ RMVPE（備用） | FCPE (Fast-Context-based Pitch Extractor) 專門改善 RVC 氣音、假音、快語速與電音破音問題；VCClient 2.1.4 與專案 `.venv` 已內建並通過 CUDA 驗證。RMVPE 保留為相容性備選。 | 若推論資源極端受限時可退回 RMVPE；已在 `tools/fcpe_probe.py` 提供驗證 probe |
| 即時前端 | [VCClient](https://github.com/w-okada/voice-changer) 候選 | 可獨立於訓練 WebUI，支援 RVC 與 Windows CUDA/ONNX edition，適合拆開即時鏈路 | 需要單一程式、最少元件或使用 RVC 自帶 realtime GUI 時 |
| 切片 | RVC revision 內的 `slicer2.py` 候選 | 與已固定訓練程式同源，避免額外版本漂移 | 需要批次管理、標記或 GUI 時改用 [openvpi Audio Slicer](https://github.com/openvpi/audio-slicer) |
| 去噪/分離 | [UVR](https://github.com/Anjok07/ultimatevocalremovergui) 只作選配 | 乾聲資料不應預設通過分離模型，避免音色瑕疵 | 原始資料含伴奏、殘響或不可接受噪音時 |
| VST host | [Light Host Modern](https://github.com/heide-oficial/Light-Host-Modern) `v1.3.1` portable | Windows 原生、可攜、支援 VST3/VST2 與 serial chain，對新人比完整 DAW 簡單 | 掃描、device recovery 或低延遲不穩時比較 Carla；接受閉源工作流時比較 Cantabile |
| 修音 plugin | [Graillon Free](https://www.auburnsounds.com/products/Graillon.html) `3.2` | 官方免費版、具 pitch correction，已安裝 VST3/VST2；比 MAutoPitch 更容易取得固定官方下載 | 自然度、延遲或授權不符合時比較其他免費插件；不能稱為開源 |
| 虛擬路由 | [VB-CABLE](https://vb-audio.com/Cable/) + [Voicemeeter](https://vb-audio.com/Voicemeeter/) Standard | 已安裝並通過 Windows endpoint/FFmpeg 列舉；可拆成兩段路由 | 嚴格要求全開源、只需一段路由或需要 ASIO/JACK 拓撲時重新評估 |

## 替代路線簡表

### A：目前規劃的模組化 Windows 路線

```text
RVC train → VCClient → VB-CABLE → VST host → Voicemeeter B1 → Discord/OBS
```

優點是每段可單獨替換、測量與除錯；缺點是安裝項目多、音訊裝置方向容易設定錯。

### B：RVC 自帶 realtime GUI

```text
RVC realtime GUI → 虛擬輸出 → Discord/OBS
```

優點是元件少；缺點是後製、路由與日常 preset 管理較不獨立。

### C：純開源優先

```text
RVC → Carla → 開源/相容 plugin → 可接受的開源路由方案
```

優點是授權邊界清楚；缺點是 Windows 裝置、VST bridge、低延遲與相容性需要更多實測。

### D：不訓練自有模型

```text
VCClient + 已授權既有模型 → 路由/後製
```

優點是可以立即測試即時鏈路；缺點是受既有模型音色、授權與可用性限制。

## 變更規則

替代方案都要重新記錄：上游 URL、revision、版本與授權；GPU/CPU、取樣率、buffer、chunk 與端到端延遲；模型格式；loopback 與終端驗收；以及新增的閉源、付費、雲端或帳號依賴。

## 部署後修正

- VCClient 已採用官方 HF 的 `vcclient_win_cuda_2.1.4-alpha.zip`。其 Web UI 可用，但首次啟動輸出顯示內建 PyTorch 對 RTX 5060 Ti `sm_120` 有相容性警告；角色模型產生後必須重新做 GPU/ONNX 實測，必要時改用 DirectML/ONNX 或更新前端。
- 目前仍保留 Carla 作為開源 host 備案；沒有因為 Light Host 已部署就宣稱 Carla 不需要。
- 最新狀態與剩餘缺口以 `docs/wiring-deployment-report.md`、`docs/wiring-verification-latest.md` 為準。
