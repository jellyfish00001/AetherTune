# Seed-VC Windows 安裝資產清單

更新日期：2026-09-26（Asia/Taipei）

這份清單只涵蓋官方 Seed-VC `realtime-tiny` GUI。第三方 repo、模型、快取、Python venv 與產物都留在 `.gitignore` 範圍；setup 與 GUI launcher 不會 clone repo 或自動下載主要 checkpoint。

## 固定來源與必備檔案

| 用途 | 專案路徑 | 來源／識別 | 必須由使用者準備 |
|---|---|---|---|
| 官方程式碼 | `tools/external/seed-vc/` | [Plachtaa/seed-vc](https://github.com/Plachtaa/seed-vc)，已封存 upstream revision `51383efd921027683c89e5348211d93ff12ac2a8`；upstream repo 顯示 GPL-3.0 | 是；setup 不會 clone 或改寫 third-party repo |
| Python 依賴清單 | `tools/external/seed-vc/requirements.txt` | 固定上述 upstream revision；GUI 依賴 FreeSimpleGUI、sounddevice、FunASR 等 | 隨 repo 取得 |
| 即時 tiny checkpoint | `models/seed-vc/checkpoints/realtime-tiny/DiT_uvit_tat_xlsr_ema.pth` | [Plachta/Seed-VC model card](https://huggingface.co/Plachta/Seed-VC)；目前本機已核對 SHA-256 `C853EA578B409F625F961BCB15D5CFF1F8EF9A75F3209EC21D9B7C73AB422E88` | 是；約 142 MB，不會由 launcher 自動下載 |
| 即時模型 config | `tools/external/seed-vc/configs/presets/config_dit_mel_seed_uvit_xlsr_tiny.yml` | 同一 upstream revision；目前檔案 SHA-256 `9559600F7A8EFCD46979073E431785820F6B2DBAE477A18CF0BFDE3E740E758B` | 隨 repo 取得；hash 隨 upstream 固定版本檢查 |
| Seed-VC venv | `tools/venvs/seed-vc/` | Python 3.10；專案安裝基線 Torch／TorchAudio／TorchVision `2.7.1+cu128` | 由 `tools/seed-vc-setup.ps1` 建立 |

README 所列 upstream 延遲只作來源說明。上述 checkpoint 的 license、地區使用限制及 reference 音檔授權要分別核對；程式碼 license 不會自動授權模型或他人聲音。

## 即時 GUI 還會讀取的本機模型快取

以下是 upstream loader 的實際模型來源。預設 GUI launcher 會先找本機檔案；任一必要檔案缺少時停止，避免啟動後無提示地向外下載：

| 依賴 | 本機路徑模式 | 上游來源 |
|---|---|---|
| XLS-R content encoder | `tools/external/seed-vc/checkpoints/models--facebook--wav2vec2-xls-r-300m/snapshots/<revision>/pytorch_model.bin` | Hugging Face `facebook/wav2vec2-xls-r-300m` |
| CampPlus speaker encoder | `tools/external/seed-vc/checkpoints/models--funasr--campplus/snapshots/<revision>/campplus_cn_common.bin` | Hugging Face `funasr/campplus` |
| HiFT vocoder | `tools/external/seed-vc/checkpoints/models--FunAudioLLM--CosyVoice-300M/snapshots/<revision>/hift.pt` | Hugging Face `FunAudioLLM/CosyVoice-300M` |
| FunASR VAD | `%USERPROFILE%\.cache\modelscope\hub\models\iic\speech_fsmn_vad_zh-cn-16k-common-pytorch\` | ModelScope `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` |

這些是 Seed-VC runtime dependencies，不代表其 license 已和 Seed-VC code 一併審查。取得時應記錄來源、revision、檔案 SHA-256 和各自使用條款。目前 launcher 固定採 offline local-cache 模式；任一必要輔助模型缺失時會停止，不支援執行時網路下載，也不會下載主要 realtime checkpoint。

## 新 clone 準備順序

1. 安裝具 Tcl/Tk 的 64-bit Python 3.10；setup 可從 `python3.10`、`python` 或 `py -3.10` 找到它，也可用 `-Python310` 指定路徑。
2. 由使用者自行 clone 並固定官方 Seed-VC revision：

   ```powershell
   New-Item -ItemType Directory -Force .\tools\external | Out-Null
   git clone https://github.com/Plachtaa/seed-vc.git .\tools\external\seed-vc
   git -C .\tools\external\seed-vc checkout 51383efd921027683c89e5348211d93ff12ac2a8
   ```

3. 閱讀官方 code/model license，從官方 model card 手動取得 `DiT_uvit_tat_xlsr_ema.pth` 並放入表格指定位置；再按上表準備必要的本機快取。不可把私人聲音、token 或 credentials 寫進 repo。
4. 先唯讀盤點，再安裝依賴：

   ```powershell
   & .\tools\seed-vc-setup.ps1 -PreflightOnly
   & .\tools\seed-vc-setup.ps1
   ```

   setup 會在任何 `pip install` 前列出 Python、upstream source、checkpoint、config 與快取缺口。缺 upstream source、requirements 或 Python 3.10 時以 `BLOCKED` 結束；只有 GUI checkpoint/config 缺漏時可以建立 venv，但 GUI 仍是 `WAITING`。setup 不會下載模型權重。
5. 以 [README.md](../../README.md) 的 Seed-VC 步驟列舉、選擇音訊裝置與啟動官方 GUI。只使用本人或已獲授權的 reference voice。

## 重新計算檔案 hash

```powershell
Get-FileHash .\models\seed-vc\checkpoints\realtime-tiny\DiT_uvit_tat_xlsr_ema.pth -Algorithm SHA256
Get-FileHash .\tools\external\seed-vc\configs\presets\config_dit_mel_seed_uvit_xlsr_tiny.yml -Algorithm SHA256
git -C .\tools\external\seed-vc rev-parse HEAD
```

任何 revision、checkpoint、設定或 auxiliary model 變更都要重新盤點與驗證。不要把檔案存在當成 GUI、GPU、mic capture 或 LIVE PASS。
