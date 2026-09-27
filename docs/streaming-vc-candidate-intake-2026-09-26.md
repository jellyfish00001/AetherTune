# Streaming VC 候選 intake：MeanVC2 與 X-VC

更新日期：2026-09-26（Asia/Taipei）

> 歷史快照：此文件記錄 2026-09-26 的 intake 前狀態。MeanVC2 與 X-VC 後續已在隔離環境完成安裝及雙向 CUDA WAV 驗證；目前狀態與剩餘 LIVE gate 以 [`live-gate.md`](live-gate.md)、[`agent-implementation-status-latest.md`](agent-implementation-status-latest.md) 為準。本文件只保留當時的來源／依賴／授權審核流程。

本文件是候選研究清單，不是安裝或採納記錄。兩個候選都維持 `candidate / not installed / no local runtime evidence`；尚未 clone 候選 repo、安裝依賴或下載 checkpoints。先完成 Seed-VC physical mic／audio-rack baseline，再依下列順序 intake。

## MeanVC2：優先候選

來源：[ASLP-lab/MeanVC2](https://github.com/ASLP-lab/MeanVC2)、[arXiv:2606.09050](https://arxiv.org/abs/2606.09050)。上游 GitHub 頁面標示 Apache-2.0；README 列出 Python 3.11、Torch／TorchAudio 2.5.1 CUDA 12.1，依賴包含 S3PRL、Fairseq、FunASR、SoX／PyWorld、pedalboard 等。README 報告的 40 ms chunk 與約 110 ms first-packet latency 屬上游結果，不是 AetherTune 測量。

官方 README 提及 Windows standalone executable 為 CPU-only。這不構成 native Python GPU 支援或不支援的證據；Windows 11、RTX 5060 Ti、CUDA 與 Python 安裝路線都要另測。repo 的 code license 也不能代替 checkpoint、訓練資料與衍生權重的使用條款審核。

intake gate：

1. 由上游確認當下預設分支與最新 commit，選定固定 revision；先記錄 revision、來源 URL、code license 與本機檔案 hash。
2. 對照 requirements 與官方安裝文件，記錄 Python／Torch／CUDA pins、Linux-only script、可能編譯的套件及 license；不直接安裝到 AetherTune 現有環境。
3. 取得權重前，確認每個 checkpoint 的下載來源、revision、sha256、模型卡／terms、dataset provenance 與可接受使用範圍；缺任何一項就停止在 `WAITING`。
4. 只有上述 gate 通過後，才建立獨立 venv 做小型 import／device smoke。不得以 standalone CPU executable、下載成功或 provider 清單宣稱 GPU runtime PASS。
5. 若可執行，再用同一 corpus、同一 reference、同一機器與 route 跑 offline/headless stream、physical capture、audio-rack pair、LIVE_GATE 與盲測。保留 upstream benchmark 與本機 evidence 的區別。

## X-VC：MeanVC2 之後的研究候選

來源：[Jerrister/X-VC](https://github.com/Jerrister/X-VC)、[arXiv:2604.12456](https://arxiv.org/abs/2604.12456)。repo 採 MIT，README 的推論入口為 shell scripts；requirements 包含 Python 3.10 生態與 Torch 2.5.1、DeepSpeed 0.14.4 等依賴。文件提及 GLM-4-Voice tokenizer、ERes2Net 與 X-VC checkpoint 等獨立模型資產；它們的條款與來源應個別記錄，不能由 repo MIT 推定。

目前沒有足夠的官方證據證明 native Windows／RTX 5060 Ti GPU 路線可直接運作。DeepSpeed 與 shell-script 依賴需要先做平台相容性盤點；不要為了測候選而改 AetherTune 主 venv。X-VC 順序在 MeanVC2 的來源、runtime 與同 corpus 比較矩陣完成之後。

intake gate：

1. 等 MeanVC2 baseline 完成後再固定 X-VC upstream commit，保存來源、revision、code license 與必要腳本清單。
2. 分開查核 tokenizer、speaker encoder、VC checkpoint 的官方 model card、使用條款、版本與 hash；不清楚或互相衝突的權利一律標 `WAITING`。
3. 先判定 DeepSpeed 及其他 native dependency 在隔離 Windows 環境是否有官方支援，或是否只能在另一個明確記錄的 Linux/WSL profile 執行。
4. 在不下載大權重前完成靜態依賴與平台審核；通過後才由使用者決定是否取得模型。採用後仍須通過相同 corpus、音質 objective、human listening、rack pair 與 LIVE_GATE。

## 比較 corpus 與人評

固定 corpus 登錄空白欄位位於 [`benchmarks/corpus/sample-register.csv`](../benchmarks/corpus/sample-register.csv)，不含合成台詞、角色或預填語音。Human Listening 使用 [`benchmarks/subjective/listening-template.csv`](../benchmarks/subjective/listening-template.csv)；rater／pair 匿名代碼應由評測流程產生，不提交可識別個人聲音、姓名、私人授權文件或錄音。欄位定義及採集邊界見 [`benchmarks/corpus/README.md`](../benchmarks/corpus/README.md) 與 [`benchmarks/subjective/README.md`](../benchmarks/subjective/README.md)。

在 corpus 權利、reference 使用權與 holdout 分組完成前，不以公開 sample 替代正式比較資料；本次只建立 schema，不宣稱任何候選的品質分數或本機勝負。
