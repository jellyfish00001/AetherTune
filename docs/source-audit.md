# 開源專案與工具來源審核

審核日期：2026-09-26（Asia/Taipei）

本文件只記錄目前查到的上游事實與採用判斷；下載、安裝、執行與模型授權仍需另外驗證。

2026-09-26 交叉檢查並新增 MeanVC2、X-VC 候選列；其他元件列保留先前審核日期與範圍，沒有藉此代表全表已重新審核。

| 元件 | 上游來源 | 目前確認 | 採用判斷 |
|---|---|---|---|
| RVC 訓練/推論 WebUI | [RVC-Project/Retrieval-based-Voice-Conversion-WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) | 公開、MIT；README 目前列 Python 3.12 x64，RTX 50 系列使用 CUDA 12.8 Torch 依賴；支援 RMVPE 與 `.pth`/`.index` 目錄 | 主訓練基線；已在專案 `.venv` 完成依賴與 runtime smoke test |
| VCClient | [w-okada/voice-changer](https://github.com/w-okada/voice-changer)／[official HF packages](https://huggingface.co/wok000/vcclient000) | 公開；本次採 `vcclient_win_cuda_2.1.4-alpha.zip`，SHA-256 `58CED135E0768A9F382461FAB13A8967520FDE2D307D39C0AB4B830040F9C70F`；Web UI HTTP 200，但啟動有 RTX 5060 Ti `sm_120` PyTorch 警告 | 即時推論前端已部署；角色模型產生後重新驗證 GPU，必要時評估 ONNX/DirectML 或更新版 |
| Audio Slicer | [openvpi/audio-slicer](https://github.com/openvpi/audio-slicer) | 公開、MIT；RMS 靜音切片，支援 CLI/API | 第一版資料切片候選 |
| UVR GUI | [Anjok07/ultimatevocalremovergui](https://github.com/Anjok07/ultimatevocalremovergui) | 公開、MIT；README 說明依賴 FFmpeg 處理非 WAV，GPU 需求與模型計算量需注意 | 只有來源含噪音/殘響時才引入，不能預設加入管線 |
| VST host | [Light Host Modern](https://github.com/heide-oficial/Light-Host-Modern) | 公開、GPL-2.0-or-later；本次採官方 `v1.3.1` portable，ZIP SHA-256 `39BD85FBC1EED130E3B48B5950A82FC7850349A0A99805B42967CAE92DAFBFD8`；支援 VST3/VST2 與 Windows audio backend | 目前 Windows 新人基線；Carla 保留為開源 host 備案 |
| 開源 VST host 備案 | [falkTX/Carla](https://github.com/falkTX/Carla) | 公開、GPL-2.0-or-later；支援 DirectSound、VST2/VST3 等多種格式 | Light Host 掃描或低延遲不穩時再切換，需重新做裝置與 loopback 驗證 |
| 修音 plugin | [Auburn Sounds Graillon](https://www.auburnsounds.com/products/Graillon.html) | 官方免費版 `3.2`；ZIP SHA-256 `D9ED254BD6AC89D5C5E670383DEC2CB1ACF43A72C62EBF2E4401D039FF6BDA18`；已安裝 VST3/VST2 | 免費第三方修音；不列入開源元件，仍待 host chain 與人工聽測 |
| MAutoPitch | MeldaProduction 官方產品 | 免費使用不等於開源；本輪未下載/驗證授權條款 | 只能列為免費第三方插件，不納入「全開源」宣稱 |
| VB-CABLE / Voicemeeter | [VB-CABLE](https://vb-audio.com/Cable/)／[Voicemeeter](https://vb-audio.com/Voicemeeter/) | 免費／免費授權路由工具不等於開源；本次 VB-CABLE Driver Pack 45 ZIP SHA-256 `B950E39F01AF1D04EA623C8F6D8EB9B6EA5C477C637295FABF20631C85116BFB`；Windows endpoint 已驗證 | 接受第三方閉源元件後採用；目前標準版 Voicemeeter，若需更多 bus 再考慮 Banana/Potato |
| MeanVC2 | [ASLP-lab/MeanVC2](https://github.com/ASLP-lab/MeanVC2)／[arXiv:2606.09050](https://arxiv.org/abs/2606.09050) | 上游 repo 標示 Apache-2.0，提供 streaming zero-shot runtime；上游報告 40 ms chunk、110 ms first-packet latency。此為上游數字，不是本機結果 | Streaming VC 下一順位 priority candidate；尚未固定 revision、審核 checkpoints 條款、安裝或測量 Windows／RTX 5060 Ti |
| X-VC | [Jerrister/X-VC](https://github.com/Jerrister/X-VC)／[arXiv:2604.12456](https://arxiv.org/abs/2604.12456) | 官方 repo 將其描述為 codec-space zero-shot streaming VC、提供 streaming inference script，repo 採 MIT license | 新 streaming zero-shot candidate；依 MeanVC2 比較矩陣完成後再做 revision、checkpoint/license、依賴與本機環境 intake |
| Seed-VC | [Plachtaa/seed-vc](https://github.com/Plachtaa/seed-vc)／[Plachta/Seed-VC model](https://huggingface.co/Plachta/Seed-VC) | 官方 README 提供 zero-shot VC、real-time GUI 與 offline／V2 profiles；本機 repo commit `51383efd921027683c89e5348211d93ff12ac2a8`；已下載 realtime tiny `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88` 與 offline checkpoint `8EC8841B20BB46DF9F7E8E570A6946A4B87B940133C7F0E778487FF33841F720` | 先採獨立環境做離線 candidate；GUI latency、provider 與 reference voice 使用權仍需實測 |
| CosyVoice 2 | [QwenAudio/CosyVoice](https://github.com/QwenAudio/CosyVoice)／[FunAudioLLM/CosyVoice2-0.5B](https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B) | 官方 model card 標示 Apache-2.0，支援 multilingual zero-shot voice cloning；安裝基線為 Python 3.10/Conda，Windows native 尚未驗證 | STT → TTS 語音重建候選；先在 WSL2／獨立環境，不與 RVC `.venv` 混裝 |
| Breeze TTS 2 | [BreezeBlue/Breeze-TTS-2](https://huggingface.co/BreezeBlue/Breeze-TTS-2)／[breeze-tts source](https://github.com/breezeblue-ai/breeze-tts) | 官方 model card 支援 voice clone/design/direction 與中英雙語；weights、derivatives、self-hosted outputs 為 research/non-commercial；quick start 以 Linux、CUDA、約 12 GB VRAM 為基線 | WSL2、Torch 2.9.1 cu128、16 GB GPU 已完成 Voice Design 與男女 reference clone 輸出；品質與 license 邊界仍依官方限制 |
| JVNV reference samples | VCClient 內附 `JVNV/readme.md` 與 [JVNV source](https://sites.google.com/site/shinnosuketakamichi/research-topics/jvnv_corpus) | 目前複製一個 F1 與一個 M1 sample；上游 readme 標示 CC BY-SA 4.0；hash 已寫入 `dataset/manifests/reference-register.csv` | 僅作本機研究 reference voice，保留 attribution，不視為使用者自有聲線 |

## 目前結論

1. 核心開源路徑可先用 RVC + Audio Slicer + Carla 做研究驗證；本次為了 Windows 新人操作，實際 host 先採 Light Host Modern。
2. VCClient 可作即時前端，但必須以當日 release/edition 與硬體對應為準；本次固定包只作可重現基線，不把它視為 RTX 5060 Ti GPU 相容性已證明。
3. 「100% 開源免費」改為「核心流程可由開源元件組成；路由與部分 VST 可選免費閉源元件」。
4. 所有模型、語音資料與 TTS 聲線要個別登記來源與使用權，不因上游程式採 MIT 就自動取得資料或模型的商用權。

## 本次採用的固定版本

RVC 官方倉庫於 2026-09-19 查得 `main` 為 `81eed5e8f68b6bed1789f682fe78cdd324495afc`；AetherTune 已 clone 並 detached 到此 revision。RVC 訓練資產 `lj1995/VoiceConversionWebUI` 本次固定 HF revision `e6d0c1a17da07c33557852f9dfa2bd44cc75737d`，不是浮動的 `main`；下載 metadata 與本機檔案 hash 已保留在外部 repo cache。使用的 RTX 50/Python 3.12 requirements 檔 SHA-256 為 `F68F1CD32868C4EF5D3B22B9C654CF82317DA6B991D166207A5A7AC844DFFCA5`。後續若上游變更，必須重新審核而不是直接更新工作目錄。

本次部署後的可執行檔與下載包都在 `tools/external/`，已由 `.gitignore` 排除；完整路徑、狀態與未完成項目見 `docs/wiring-deployment-report.md`。
