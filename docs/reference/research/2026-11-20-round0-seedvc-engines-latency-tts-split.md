# AetherTune 第 0 輪研究：Seed-VC 封存、替代引擎、延遲缺口、配音拆分（2026-11-20）

證據等級：A=AetherTune repo 實測；B=社群獨立量測（附連結）；C=論文或作者宣稱；D=論壇個案。
基準：origin/main 05b1ec4，全程唯讀調查。

## 1. Seed-VC 封存
- Plachtaa/seed-vc：archived=true、GPL-3.0、約 3.9k 星，最後一次 commit 51383ef（2025-04-20）。AetherTune 釘住同一版本（tools/seed-vc-assets.json），外部 checkout 到 tools/external/seed-vc，不是 submodule。〔A〕
- 封存日期兩邊說法不一：README 寫 2025-11-21，評估報告推 2025-04。GitHub API 不提供封存日期，未核實。〔D〕
- HF 權重 2026-11-20 實測都回 HTTP 200：Plachta/Seed-VC@257283f 的 tiny 和 v1、CosyVoice-300M/hift.pt、funasr/campplus、wav2vec2-xls-r-300m。〔A〕
- 唯一還在維護的 fork：jiaheguo521/seed-vc-realtime（GPL-3.0，最後 push 2026-07-17）。Johnny 決定不評估，只備份原版。
- 風險：
  - 沒有人修 bug，例如推論時間越跑越長 https://github.com/Plachtaa/seed-vc/issues/155 、resampler 雜音 https://github.com/Plachtaa/seed-vc/pull/123 。〔D〕
  - 依賴老化：torch 手動釘在 2.7.1+cu128（seed-vc-setup.ps1:144）。
  - 權重放在個人 HF 帳號，可能下架，需要本機備份。
  - GPL-3.0：散布才有義務，自用影響小。

## 2. 替代引擎
- MeanVC2：模型 p95 94.7ms〔A，realtime-vc-verification-latest.md 2026-10-01〕；上游宣稱首包約 110ms〔C〕；最後 push 2026-09-13；README 寫 Apache-2.0 但沒有 LICENSE 檔；已整合。
- X-VC：模型 p95 79.6ms〔A〕，但架構本身有 240ms 延遲〔C，https://arxiv.org/abs/2604.12456 〕；MIT；已整合。
- RVC：社群最大（WebUI 39.2k 星、w-okada 21.4k 星）；w-okada 端到端約 0.8–1.7 秒〔B，https://zenn.dev/gokrack/articles/621a2872fd9ccd 〕；已整合。
- Seed tiny：模型 p95 175.7ms〔A〕。
- Beatrice v2：VST 約 51ms、client 約 139ms〔B，同 zenn〕；要先訓練模型、授權有限制、新依賴；未整合。

## 3. 延遲缺口
- 以上 A 級數字都是「模型延遲」，從麥克風到輸出的端到端延遲從沒量過。所以不知道離 100–300ms 目標還差多少。這是第一優先（exp/bench-e2e-latency）。
- 現行路由：引擎 → CABLE Input → Light Host（VST）→ Voicemeeter → B1，48kHz、960 frame、WASAPI 共享（audio-rack/routing/seed-vc-virtual-route.json）。每多一跳都增加緩衝延遲。〔A〕
- PC2 沒裝 VB-CABLE 和 Voicemeeter，只有 Voicemod 和 Voxal 虛擬裝置；GPU 是 RTX 2060 12GB。〔A〕
- 社群常見問題：取樣率不一致會爆音，要統一 48kHz；只在 Discord 卡頓的案例，有人建議把 CABLE 換成 VAC https://github.com/w-okada/voice-changer/issues/1280 ；Win11 power throttling 會讓音訊斷續 https://voicemeeter.com/quick-tips-stutters-crackling-sound-robot-voice/ 。〔D〕
- 開源路由：App 內用 Rust cpal 或 WASAPI 混音，不用裝驅動，可以省掉兩跳；送進 Discord 仍要虛擬麥克風，開源選項是 https://github.com/VirtualDrivers/Virtual-Audio-Driver （MIT，要裝驅動）。

## 4. 配音拆分分析（Johnny 13:23 定案：先凍結、後拆）
- 純配音（可凍結後交給 VSF）：CosyVoice2 和 Breeze TTS 2（非串流整檔生成，contracts/engines/*.json 寫 supports_streaming_tts=false）；services/tts 的 adapters、wsl_job、storage、snapshot、validation、service 佇列；tools 裡的 tts-resident-worker、cosyvoice-*、breeze-tts2-*；contracts/voices；前端 SpeechWorkspace.tsx、SpeechMiniStatus.tsx；相關測試和驗證文件。
- 必須先搬出才能拆的共用部分：
  - services/tts/playback.py 負責 RVC 的播放和路由（runner_service.py:71、rvc_runtime.py:279 有引用）。
  - 裝置清單是 TTS service 提供的（speech.ts:410 → service.py:338）。
  - TTS service 跑在 Seed-VC venv（speech_manager/mod.rs:33,140）。
  - Seed-VC 聲碼器用的是 CosyVoice-300M 的 hift.pt，不能刪。
  - main.rs:102 的 speech_blocks_vc 互鎖要一起拆。
- 工作量估計：凍結約 0.5–1 天；完整移除約 2–4 天。
- 直播用即時串流 TTS 歸 AetherTune（Johnny 13:23），品質模型從 VSF 引用。
