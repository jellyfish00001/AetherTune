# AetherTune 專案架構與開箱狀態審查報告

更新日期：2026-09-27（Asia/Taipei）

## 審查結論

AetherTune 已從「多個變聲模型的安裝集合」整理為本機 Voice Transformation Research Workbench。研究路線、跨 backend 音訊基礎設施、證據狀態與正式 LIVE 條件已大致對齊；目前可重現的近期操作集中在 Seed-VC `realtime-tiny` GUI 啟動前檢查與畫面設定核對。

目前不能把整個專案稱為「開箱即可完成即時通話變聲」。最新 Seed-VC manifest-enabled setup／GUI preflight 與 GUI 畫面核對只證明本機啟動條件與設定顯示。Seed-VC inference GUI streaming、實體麥克風到最終虛擬收音端、clean-machine bootstrap、audio-rack full-chain、首包延遲、長時間穩定與人工音質判斷仍未完成或未取得本機證據。MeanVC2 與其後續 Streaming Zero-Shot 候選均未安裝。

## 研究架構

### 1. Streaming VC

這條路線保留輸入語音的時序、韻律與原始表演，目標是讓 source stream 即時轉成 reference speaker 的音色。

目前順序：

1. **Seed-VC upstream**：已建立的 offline／GUI baseline。`realtime-tiny` 是目前 manifest-enabled GUI gate 覆蓋的 profile；`offline-v1` 可供離線轉換與舊 GUI callback user-flow。兩者的權重、前處理及驗證範圍不能互相代替。
2. **MeanVC2**：下一順位的 `priority candidate / PLANNED`。需先固定上游 revision、模型與第三方權重來源、授權、Python／Torch／CUDA 相容性，再建立獨立環境與模型目錄。
3. **X-VC／後續新 Streaming Zero-Shot VC**：研究候選；在 MeanVC2 用固定 corpus、audio-rack 與共同 gate 完成比較前，不 intake 到本機主線。
4. **Seed-VC realtime fork**：獨立執行路徑候選，與模型品質比較分開評估。

官方 MeanVC2 README 描述其 40 ms chunk 路線及 110 ms first-packet latency 主張；這是上游報告值，並非本機 RTX 5060 Ti、AetherTune audio-rack 或完整虛擬路由測量。[上游 repository](https://github.com/ASLP-lab/MeanVC2)、[論文](https://arxiv.org/abs/2606.09050)。MeanVC2 的最新 main commit 尚未固定：目前可見觀測的 `01968bcb5e053d87dae8e1a70e5056868e36b2ae` 與 `0d39c8ae416a37edb9884db67334e4b9d0c3e308` 須再核對；官方 commit 頁面快取時間不同，且本機 `git ls-remote` 受網路限制，故不得在文件或安裝腳本中任選一筆宣稱為最新 tip。

MeanVC2 建議採獨立 Python 3.11 環境，不覆寫專案 `.venv`。上游 quick start 指定 Torch／TorchAudio 2.5.1 + CUDA 12.1；本機 `.venv` 是 Python 3.12.10、Torch 2.7.1+cu128。兩組相容性尚未測試，RTX 5060 Ti 可見於現有環境不構成 MeanVC2 CUDA 推論通過。上游 Windows 可執行檔是 CPU-only，不能代表 Python CUDA realtime 路徑。首階段應限制為依賴與來源盤點、模型 hash 固定、WAV offline inference、檔案模式逐塊串流及合成 loopback；實體麥克風放到其後。

### 2. Speech Reconstruction

CosyVoice／Breeze 路線是文字或 ASR transcript → 重新合成語音；這是新聲學表演，不保留原始 source waveform 的停頓、韻律和即時反應。CosyVoice2 有本機 CUDA TTS 證據但部分 frontend 固定 CPU；CosyVoice3 是 candidate。Breeze TTS 2 的 WSL2 runner、Voice Design／reference clone 與 fast-all 有已記錄的 runtime 證據，但 SoX、flash-attn 與人工聽測仍有 WAITING 項目。

### 3. 歷史路線與共用設施

- **RVC／VCClient**：保留作訓練模型及歷史對照。RVC 專案離線 GPU 推論與模型配對 audit 不等於 VCClient 即時路線可用；VCClient 仍有 packaged conversion／invalid WAV 問題，角色資料來源與授權 provenance 也未完整。
- **`audio-rack/` 與 `benchmarks/`**：跨 backend 共用的 Post-FX、routing、corpus 和 evidence 契約，不是第五種模型 backend。合成 route smoke 或 validator fixture 只測契約，不能代替物理裝置 runtime。

## Seed-VC 最新 UI／開箱證據

### 已通過的範圍

- 2026-09-27 一般 Windows user session 執行 `& .\tools\seed-vc-setup.ps1 -PreflightOnly`：exit 0、JSON `status=PASS`、Python 3.10.11 x64、Tcl 8.6.12／Tk available、`missing=[]`、不需下載模型。
- 2026-09-27 執行 `pwsh -NoProfile -File .\tools\seed-vc-gui-run.ps1 -PreflightOnly`：exit 0、CUDA visible、NVIDIA RTX 5060 Ti、MME／DirectSound／WASAPI／WDM-KS Host API inventory 完成；HyperX QuadCast S input 與 VB-Audio CABLE output 可由 Host API + endpoint 名稱唯一解析；checkpoint 與 VAD 本機 hash 通過。
- 已開啟官方 GUI 的 1110×660 畫面並目視核對 reference、DirectSound、HyperX input、VB-Audio CABLE output、Host API 清單、參數與按鈕。截圖是本機 ignored artifact：`artifacts/seed-vc/gui-userflow/20260927-manifest-host-ui/seed-vc-gui.png`，SHA-256 `E3FF99E1EC0E935B29C14D0D55DBCC86BC4A2C66B8ECF36C41493DB5EE182AED`。沒有按 `Start Voice Conversion`，沒有產生 mic stream。
- 舊有四組 GUI settings／callback／synthetic CABLE loopback 每案 17/17 欄位通過並錄得 finite／非零輸出；該 user-flow 使用 `offline-v1`，不是 `realtime-tiny` 推論證據。
- Seed-VC 離線雙向轉換、60 秒長音檔與 200 block／60 秒 headless GPU stream 有各自獨立的既有 PASS 證據。

### 尚未通過或尚未執行

- `realtime-tiny` GUI inference／Start-Stop stream 未驗證；preflight 與 GUI 畫面不是模型實際推論。
- Windows sandbox 的 Tcl `init.tcl` lookup failure 列為 sandbox-only `WAITING`，不覆寫 approved normal-session host PASS。
- clean-machine／新使用者 bootstrap 未測。現主機依賴 per-user Python 3.10 Tcl/Tk junction，不能當成 repo 可攜的自動安裝證據。
- offline-v1 clean setup 的 Whisper／BigVGAN helper completeness 不在 realtime-tiny manifest gate 範圍。
- 物理 mic → backend → audio-rack → virtual route 的第一個有效輸出需 `e2e_first_packet_ms <= 5000`；目前無完整鏈路 timing evidence。
- `LIVE` 另需同一 run 的 physical mic input/output artifact、model/config/GPU/device/driver/route identity、600 秒零 dropout／underrun 與人工聽評。上述證據均未完成。

## 安裝操作原則

1. 一般使用者先讀 `README.md`、`docs/user-guide.md` 與 `docs/operation-guide.md`，先執行 Seed-VC setup／GUI preflight，確認 `status=PASS`、`missing=[]`、實際裝置名稱與 Host API，再由使用者於 GUI 選 reference 並核對 endpoint。
2. 對尚未驗證的即時路線，文件須區分啟動前檢查、UI 設定、離線／headless inference、synthetic loopback、real-mic runtime 及完整 LIVE；每一層只可由對應證據升級狀態。
3. MeanVC2 intake 前固定程式 commit、模型 revision 與所有權重 hash／授權，獨立建立 Python 3.11 runtime；安裝只包含 40 ms inference 所需依賴，避免先跑會拉入訓練／評估依賴及多餘模型的整包流程。成功下載或載入不能當成音訊 E2E PASS。
4. 每一階段保留單獨、範圍明確的 Git commit；runtime 權重、音訊、第三方 checkout、venv、cache 與 artifacts 不提交。

## 請 GPT-6 Sol xhigh 檢視的問題

1. Streaming VC、Speech Reconstruction、RVC historical baseline 與共用 audio-rack 的邊界是否清楚，且是否正確回應最終目標「及時變聲」？
2. Seed-VC → MeanVC2 → X-VC／新 Streaming Zero-Shot 的 intake 順序，以及 Seed-VC realtime fork 的獨立比較路徑是否合理？
3. 所有文件是否把 `PLANNED`、preflight、GUI setting、synthetic loopback、inference、real mic E2E、LIVE 區分正確？目前 docs 同步修正是否涵蓋人類入口與狀態總表？
4. 相對路徑 resolver／Windows GUI launcher 的隔離方式，是否適合從非 repository working directory 啟動、保存及重開 UI 設定？檢視 branch commit `c5760b71d99457b266d9c42430a7245caba5429e` 時請保留根分支較新的 2026-09-27 readiness evidence。
5. MeanVC2 的 revision、license、dependency 與 GPU 架構 gate 是否足以決定安全可重現的安裝？若來源／授權／相容性尚未確認，應維持 `WAITING` 還是採取另一個可驗證的 intake 步驟？
6. 對「開箱可用」的最低驗收清單是否已涵蓋 clean-machine bootstrap、UI 操作、first-packet ≤ 5 秒、穩定性、audio-rack 與使用者聽評？請給出必要修訂及下一階段的 Luna Max 可執行 prompt。

## 參考文件

- [`README.md`](../README.md)
- [`docs/user-guide.md`](user-guide.md)
- [`docs/operation-guide.md`](operation-guide.md)
- [`docs/architecture.md`](architecture.md)
- [`docs/voice-conversion-architecture.md`](voice-conversion-architecture.md)
- [`docs/live-gate.md`](live-gate.md)
- [`docs/seed-vc-readiness-latest.md`](seed-vc-readiness-latest.md)
- [`docs/agent-implementation-status-latest.md`](agent-implementation-status-latest.md)
- [`backends/meanvc2/README.md`](../backends/meanvc2/README.md)
