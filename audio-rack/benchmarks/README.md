# Audio Rack benchmarks

至少要有兩次可配對測量，並使用同一 source、model revision/checkpoint、hardware identity 與 route。source 必須明確標註 `source_type`：`physical_microphone`、`synthetic_callback` 或 `file_injection`。宣告的 `sample_rate_hz`/`channels` 需符合 source WAV header；fixture 可使用 synthetic/file source，這不會讓 rack 證據成為 LIVE：

1. backend → routing，rack `bypass`。
2. backend → full Post-FX chain → routing。

每個 run 都必須保存獨立 run id、開始時間、輸出 WAV、WAV SHA-256、output metadata（sample rate、channels、frames、duration）、metrics JSON 與其 hash、signal validation、first-packet latency、p50/p95、dropout／underrun。hash-bound metrics 必須核對 pair id、rack mode、source type 與實際 source WAV metadata、model/route/output identity、該 run 的 output metadata，以及 paired run 的 output hash/metadata。source 宣告、run 的 `output_metadata`、metrics 和 WAV header 不一致都會 `BLOCKED`；即使只重算 WAV hash，也不能保留舊 metrics metadata 通過。pair 的 `delta_latency_ms` 必須等於 `full_chain.e2e_first_packet_ms - bypass.e2e_first_packet_ms`。欄位契約見 `rack-evidence-v1.schema.json`。

證據欄位示例（metrics JSON 另記錄完整 frames/duration）：

```json
{
  "source": {
    "source_type": "file_injection",
    "sample_rate_hz": 48000,
    "channels": 1
  },
  "runs": {
    "bypass": {
      "output_metadata": {
        "sample_rate_hz": 48000,
        "channels": 1,
        "frames": 4800,
        "duration_sec": 0.1
      }
    }
  }
}
```

`tools/audio-rack-evidence-validate.py` 會實際讀取並驗證 source/output WAV 與 metrics JSON；檔案不存在、空白／全零、舊檔、hash 不符、WAV header metadata 不符、run identity 不符或 A/B 不配對時不會 PASS。它只判定成對 rack 技術證據，**rack PASS 不能升格為 LIVE**；真實麥克風完整鏈路要另外通過 `tools/live-gate-validate.py`。

目前 route smoke 已 PASS，但沒有 Light Host plugin output 的 paired evidence 時，bypass/full-chain 必須維持 `WAITING`。
