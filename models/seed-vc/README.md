# Seed-VC model cache

模型權重不進 Git。建議本機位置：

```text
models/seed-vc/checkpoints/
```

目前已下載兩個官方 checkpoint，並把 SHA-256 寫入 `models/backend-register.csv`：

- `realtime-tiny`：給官方 real-time GUI 使用。
- `offline-v1`：給 `tools/seed-vc-run.ps1` 的 `inference.py` 使用。

兩者都只是 `candidate`；完成實際 GPU/CPU provider、輸出 WAV、延遲與聽測後，才可提升為 `ready`。
