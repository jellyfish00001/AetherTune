# Live Technical Benchmark

Live benchmark 必須使用真實 capture、backend、共用 audio rack、virtual routing 與 loopback。至少分開保存 `Post-FX bypass` 與 `Post-FX full-chain` 兩組 evidence，並使用 [`docs/live-gate.md`](../../docs/live-gate.md) 的 `aethertune-live-gate/v1` schema。

`tools/live-gate-validate.py` 只做 evidence classification：`LIVE`、`OFFLINE`、`WAITING` 或 `BLOCKED`。它不會建立假 artifact，也不會把 headless inference 當成 mic E2E。
