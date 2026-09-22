# Common Audio Rack

`audio-rack/` 是跨 backend 的共用音訊基礎設施，不是第五個模型 backend，也不屬於 RVC。所有 Streaming VC 與需要播放／loopback 的 Speech Reconstruction 都應使用同一套可記錄的 rack profile，才能公平比較模型本身與後製鏈的差異。

## 目標鏈路

```text
backend output
  → corrective EQ
  → de-esser
  → compressor
  → saturation
  → optional pitch correction
  → very-light ambience
  → limiter
  → virtual audio routing
```

每個元件都必須能以 `bypass`／`active` 兩種狀態重跑。Pitch correction 預設為 `optional`，不得強制套用到所有 backend；過度修音可能破壞 Seed-VC、MeanVC2、CosyVoice 或 Breeze 的自然韻律。

## 目前狀態

- `PASS`（契約／路由 smoke）：已登記 Seed-VC virtual route、Graillon candidate profile、neutral preset 與 rack evidence schema；VB-CABLE／Voicemeeter synthetic route 有可重跑證據。
- `WAITING`（runtime）：目前尚未以同一 source、同一輸出、同一 route 完成 Light Host plugin bypass/full-chain A/B、Δ latency 與人工聽測。
- 既有 Light Host、Graillon、VB-CABLE、Voicemeeter 文件與實際部署保留；它們只是目前 Windows 實作候選，不是所有 backend 的架構定義。

## 子目錄

- `presets/`：只放明確版本化的研究 preset；不可把未實測參數寫成 approved default。
- `plugin-profiles/`：記錄 plugin、version、format、license、latency evidence 與 bypass 狀態。
- `routing/`：記錄裝置方向、取樣率、buffer 與 loopback evidence。
- `benchmarks/`：記錄 rack bypass、full-chain 與 Δ latency 測量規則。

目前 profile：

- `presets/seed-vc-neutral.json`：candidate-unverified；bypass／full-chain 都必須補 evidence。
- `plugin-profiles/graillon-free-3.2.json`：binary PASS、host loading／latency WAITING。
- `routing/seed-vc-virtual-route.json`：synthetic virtual route PASS；physical mic E2E WAITING。
- `benchmarks/rack-evidence-v1.schema.json`：固定 A/B evidence 欄位，不產生假 artifact。

## 安全邊界

本目錄不保存授權聲音、不保存帳號或 token，也不把 VST binary、第三方 installer、模型權重或音訊 artifact 放進 Git。Windows 端點必須以實際 inventory 與 loopback 證據確認，不能只憑裝置名稱猜方向。
