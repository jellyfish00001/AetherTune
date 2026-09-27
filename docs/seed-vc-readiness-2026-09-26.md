# Seed-VC realtime readiness recheck

更新日期：2026-09-26（Asia/Taipei）

> 歷史快照：本頁記錄 2026-09-26 的分支驗證，不是目前安裝狀態。2026-09-27 之後的實際狀態以 [`seed-vc-verification-latest.md`](seed-vc-verification-latest.md) 為準。當日使用的 `seed-vc-gui-config.py` 會直接改寫 upstream repo 的 `configs/inuse/config.json`；合併時已由新版隔離 session 的 launcher／device-selection helper 取代，該 standalone helper 與其 regression 不保留。

## 判定

工具與 evidence gates 已補齊並通過本地 regression；目前整條 realtime 路線仍為 `WAITING`，不能標成 `LIVE` 或 E2E `PASS`。本輪沒有啟動 Seed-VC GUI、沒有錄製麥克風、沒有下載模型，也沒有產生或聽測任何使用者聲音。

## 已確認

| 項目 | 狀態 | 證據與範圍 |
|---|---|---|
| 官方 Seed-VC revision | `PASS` | `D:\AetherTune\tools\external\seed-vc` 為 `51383efd921027683c89e5348211d93ff12ac2a8`；以 per-command `safe.directory` 讀取，未修改全域 Git 設定 |
| realtime-tiny checkpoint／config identity | `PASS` | checkpoint `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88`；config `9559600F7A8EFCD46979073E431785820F6B2DBAE477A18CF0BFDE3E740E758B` |
| Python 3.10 | `PASS` | D 環境 `pyvenv.cfg` 與直呼 base interpreter 確認 Python `3.10.11` |
| XLS-R／CampPlus／HiFT runtime assets | `PASS` | 新版唯讀 preflight 找到三個實際必要檔案，不只檢查 cache 資料夾存在 |
| FunASR VAD cache | `WAITING` | 唯讀 preflight 未找到 `%USERPROFILE%\.cache\modelscope\hub\models\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch\**\configuration.json`；offline launcher 實際輸出 `BLOCKED` 後停止，未寫 GUI 設定、啟動 GUI 或下載／安裝任何內容 |
| Windows WASAPI endpoint inventory | `PASS`（唯讀） | 以 D Seed-VC venv 執行兩個 inventory helper，未開 stream。識別到 `麥克風 (HyperX QuadCast S)`、`CABLE Input (VB-Audio Virtual Cable)`、`CABLE Output (VB-Audio Virtual Cable)`、`Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)`；裝置列舉不等於音訊訊號或 latency PASS |
| 工作樹本地 runtime assets | `WAITING` | 本 C worktree 沒有 ignored upstream repo、Seed-VC venv、checkpoint 或 reference WAV；實際安裝資產位於既有 D checkout，沒有複製進工作樹 |
| Physical mic → Seed-VC → rack → B1 | `WAITING` | 尚無本輪真人 mic capture、Light Host bypass/full-chain pair、人工聽測或 600 秒穩定性 evidence |

## 驗證命令與結果

以下程式 regression 均通過；關鍵回歸使用 Seed-VC Python 3.10.11：

| 命令 | 結果 |
|---|---|
| `python tools/live-gate-regression.py` | `PASS`：真實 PCM WAV／hash、靜音 input/reference/output、WAITING、OFFLINE、BLOCKED |
| `python tools/audio-rack-evidence-regression.py` | `PASS`：WAV／metrics run identity、paired A/B、雙向 latency delta、reciprocal pair 與負向 cases |
| `python tools/portaudio-callback-telemetry-regression.py` | `PASS`：callback flags、frame counts、timestamp gaps、missing timestamps |
| `python tools/seed-vc-gui-settings-regression.py` | `PASS`：GUI widget 更新及缺少 widget 的 WAITING 回報 |
| `D:\AetherTune\tools\venvs\seed-vc\Scripts\python.exe tools/seed-vc-gui-config-regression.py` | `PASS`：同 Host API 唯一 input/output 配對、重名拒絕、reference 路徑存在與 ASCII gate |
| D Seed-VC venv 執行 `live-gate-regression.py`、`audio-rack-evidence-regression.py`、`portaudio-callback-telemetry-regression.py` | 全部 `PASS`，Python 3.10.11 |
| 兩個 JSON Schema `json.loads` | `PASS`：LIVE_GATE v1 與 rack-evidence v1 JSON 語法 |
| PowerShell AST parse | `PASS`：`seed-vc-setup.ps1`、`seed-vc-gui-run.ps1`、`seed-vc-run.ps1` |
| Python `py_compile` | `PASS`：新增與變更的 validators、capture/config helper、regressions 及 GUI userflow；Python 3.10.11 與 3.12.10 |
| `git diff --check` | `PASS`；僅有 repo 原本的 LF/CRLF autocrlf 提示，沒有 whitespace error |
| `seed-vc-gui-run.ps1` 指向 D checkout、未加 `-AllowNetworkAssets` | `BLOCKED`（預期） | 三個 auxiliary cache PASS、VAD WAITING；離線政策在 CUDA／device config／GUI 啟動前中止 |

唯讀 preflight 的 stdout 將 upstream source、requirements、Python、checkpoint、config 與 XLS-R／CampPlus／HiFT 列為 `PASS`，VAD cache 列為 `WAITING`。因此不能啟動本地 launcher 的 offline flow。若 VAD cache 在一般 Windows 使用者工作階段已備妥，重新執行 [`tools/seed-vc-setup.ps1`](../tools/seed-vc-setup.ps1) 的 `-PreflightOnly`，然後以 [`tools/seed-vc-gui-run.ps1`](../tools/seed-vc-gui-run.ps1) 做 GUI startup 檢查。

## 下一個人工步驟

1. 在實際 Windows 使用者工作階段確認 VAD cache 路徑與授權；不要加 `-AllowNetworkAssets` 來掩蓋缺少資產。
2. 從 [`docs/operation-guide.md`](operation-guide.md) 依 inventory 選裝置，使用本人或已授權的 reference WAV 啟動 GUI；確認 GUI input/output/reference 後由使用者按 Start。
3. 使用 [`tools/seed-vc-live-capture.py`](../tools/seed-vc-live-capture.py) 先錄 30 秒，再視結果由使用者選擇是否做 600 秒。聽測記錄由人類填寫，Agent 不代填主觀音質分數。
4. 先用同一個固定、已授權 corpus source/reference 跑 rack bypass/full-chain pair；真實 mic 每次錄音 hash 不同時不得偽裝成同 source pair。再獨立填入完整 LIVE_GATE timing 與實際 loopback output evidence。

目前任何可用結論都限於 `offline/headless PASS`、先前文件記錄的 GUI synthetic callback PASS，以及本輪新增 validator/tooling regressions PASS。physical mic E2E、完整 rack pair 和 LIVE classification 保持 `WAITING`。
