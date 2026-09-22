# AetherTune benchmark workspace

Benchmark 分成三層，不能互相代替：

| 層級 | 主要問題 | 目前狀態 |
|---|---|---|
| Live Technical | 完整 capture → backend → rack → routing 是否 `<= 5 秒`、穩定且沒有 dropout | `PLANNED`；gate 契約見 [`docs/live-gate.md`](../docs/live-gate.md) |
| Acoustic Objective | WAV 是否有效、內容／聲學 proxy、同 sample rate／loudness policy 下的可比訊號資料 | 既有 signal-level 工具 `PASS`；品質結論仍 `WAITING` |
| Human Listening | 自然度、目標音色相似、原始表演／情緒保留、噪音與可接受度 | `PLANNED` |

所有正式比較都要以固定 corpus、固定 reference、固定 hardware、固定 Post-FX policy 與 source／output hash 配對。模型 upstream benchmark 不可直接當成本機 PASS。
