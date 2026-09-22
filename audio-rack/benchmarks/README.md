# Audio Rack benchmarks

至少要有兩次可配對測量：

1. backend → routing，rack `bypass`。
2. backend → full Post-FX chain → routing。

報告必須同時保存輸出 WAV、hash、signal validation、first-packet latency、p50/p95（若有）、dropout／underrun 與 `delta_latency_ms`；欄位契約見 `rack-evidence-v1.schema.json`。不能用「掛了幾個 VST」推估延遲。

目前 route smoke 已 PASS，但沒有 Light Host plugin output 的 paired evidence 時，bypass/full-chain 必須維持 `WAITING`。
