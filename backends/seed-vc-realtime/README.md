# Seed-VC realtime fork（研究候選）

狀態：`PLANNED / candidate`。這不是已安裝或已驗證的 backend。

本候選追蹤 [jiaheguo521/seed-vc-realtime](https://github.com/jiaheguo521/seed-vc-realtime)，其 README 說明它從已 archived 的 Seed-VC upstream 延伸，並重做 audio engine、device handling、VAD、worker thread 與 A/V latency。這些是上游描述，不是 AetherTune 的本機證據。

## 與既有 Seed-VC 的關係

- `backends/seed-vc/` 保留 Plachtaa/seed-vc 的既有 offline-v1 與 headless realtime evidence，作 `established-baseline`。
- 本 fork 另建 runtime profile，不覆蓋既有 venv、checkpoint 或 artifacts。
- 只有完成固定 corpus、真實 mic → model → audio-rack → virtual route → loopback，並保存 revision／license／device／latency evidence 後，才可改成 `LIVE` 或 `WAITING` 的本機結論。

## 首次驗收

1. 固定 fork revision 與 source hash。
2. 確認 upstream code/model license 與 reference voice provenance。
3. 建立獨立 environment，不修改 RVC `.venv` 或既有 Seed-VC venv。
4. 以 `docs/live-gate.md` 的 schema 測量 bypass/full-chain、60 秒 screening 與 600 秒 stability。
