# AetherTune 系統架構

**文件邊界：**本頁是跨路線的**研究需求與系統分層**權威，不維護 backend 安裝結果、Desktop 按鈕、Windows 裝置操作或 `LIVE` 分類細則。backend adapter 責任看[多後端契約](voice-conversion-architecture.md)，Desktop 的產品需求／實作看[app-requirements.md](app-requirements.md)與[app-architecture.md](app-architecture.md)，驗收分類看[live-gate.md](live-gate.md)。目前狀態按[文件權責地圖](../README.md)進入各驗證報告。

## 研究問題與品質排序

AetherTune 在 Windows、本地 RTX 5060 Ti 16GB 的目標環境，比較「哪一條聲音路線更自然、更接近目標聲線，以及是否保留原始表演」。品質排序為：**自然度 → 目標音色相似度 → 原始表演／情緒保留**。互動用途另受完整鏈路首包 `<= 5 秒` 的硬門檻限制；達到延遲門檻也不會自動成為 `LIVE`，其他必要證據由[live-gate.md](live-gate.md)定義。

「免費」、「開源」、「open-weight」、「non-commercial」與「commercial-compatible」分開記錄。模型、reference voice、輸出聲音及第三方工具的使用權是不同問題；來源和授權事實由[source-audit.md](../reference/source-audit.md)及 register 記錄，不由架構推定。

## 五層資料流

```text
1. Capture／Preprocess       實體麥克風或固定 source，記錄來源與時間
             ↓
2. Backend Adapter          Streaming VC 或 Speech Reconstruction
             ↓
3. Common Audio Rack        相同條件的 bypass／full-chain 後製
             ↓
4. Virtual Audio Routing    明確端點、方向與終端 loopback
             ↓
5. Benchmark Pipeline       Live Technical／Acoustic Objective／Human Listening
```

Streaming VC 的目標是保留來源內容與聲學表演，Speech Reconstruction 則重新生成聲學表演，兩者分開比較。各 adapter 的輸入、輸出、profile 與界線由[多後端契約](voice-conversion-architecture.md)及對應 `backends/<name>/README.md` 擁有。

`audio-rack/` 與 `benchmarks/` 是跨 backend 的共用基礎設施，不是模型 backend，也不能因定義了 preset／schema 就寫成已通過實際鏈路。所有打算送往通話／直播端點的路線，都要能留下相同 source、model、hardware、route 身分的 bypass/full-chain paired evidence；Rack 的欄位和路由格式由 `audio-rack/` 的 README／schema 擁有。

## 系統不變條件

| 條件 | 權威位置 |
|---|---|
| 來源與 reference 要有 hash、provenance 和使用權 | `dataset/manifests/`、`models/*register.csv`、[source-audit.md](../reference/source-audit.md) |
| Backend 執行環境與依賴彼此隔離，不把 TTS／VC checkpoint 混用 | [多後端契約](voice-conversion-architecture.md)、各 backend README |
| 輸出須有本輪 finite／non-zero、hash、device/provider 與可追溯 runner manifest | 對應 backend verifier 與 [verification-plan.md](verification-plan.md) |
| 後製比較使用 paired bypass/full-chain，量實際 latency delta | [audio-rack/benchmarks](../../audio-rack/benchmarks/README.md) |
| 實體 mic、完整路由、穩定性與人耳聽評分層驗收 | [live-gate.md](live-gate.md)、[benchmarks](../../benchmarks/README.md) |

各層的 PASS 只回答那一層的問題。下載、import、GUI 可開啟、HTTP 200、離線 WAV 或合成 VB-CABLE tone，不能代替較後層的證據。客觀訊號檢查、人工聽評與 LIVE 技術檢查也不可互相升格。

## 變更系統架構時

新增 backend/profile 先決定它屬哪個研究組別、輸入／輸出契約和授權邊界，再更新[多後端契約](voice-conversion-architecture.md)、對應 `backends/` README、`contracts/` manifest/schema 與 register。改變跨路線的研究目標或分層才修改本頁；採納原因記入[decision-log.md](../reference/decision-log.md)。當次安裝與音訊結果應更新對應驗證報告，**不寫進本頁作為第二份現況表**。
