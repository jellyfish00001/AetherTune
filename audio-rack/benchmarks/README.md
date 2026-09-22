# Audio Rack benchmarks

至少要有兩次可配對測量：

1. backend → routing，rack `bypass`。
2. backend → full Post-FX chain → routing。

報告必須同時保存輸出 WAV、hash、signal validation、first-packet latency、p50/p95（若有）、dropout／underrun 與 `delta_latency_ms`。不能用「掛了幾個 VST」推估延遲。
