# Breeze TTS 2 最新驗證

更新日期：2026-09-22（Asia/Taipei）

## 結論

Breeze TTS 2 已完成獨立 WSL2 安裝與 CUDA 實際輸出，狀態為 `PASS`：

- source revision：`008f769016b0a24711becd7a4925030bc93f608c`
- model：`BreezeBlue/Breeze-TTS-2`
- model snapshot：`7,683,628,957` bytes，位於 `models/speech-reconstruction/breeze-tts-2/`
- environment：`tools/venvs/breeze-tts-wsl`、Python 3.10.20、Torch `2.9.1+cu128`
- GPU：NVIDIA GeForce RTX 5060 Ti、16 GB VRAM
- UI：上游沒有官方 WebUI；本專案的 `tools/breeze-tts2-webui.py` 是 project-local wrapper，呼叫同一套官方 runtime。

## 實際輸出證據

| 測試 | 狀態 | 輸出／證據 |
|---|---|---|
| Voice Design 男聲 | PASS | `breeze-design-male.wav`、24 kHz、8.24 s、RTF 6.1343、SHA-256 `b3bd7a220c8c9b05483238d7692a79eb99a1ec754659359b96ded15faf503109` |
| Voice Design 女聲 | PASS | `breeze-design-female.wav`、24 kHz、8.96 s、RTF 5.1164、SHA-256 `97f99c9fca1afbeaef000be3bc3efc2091dd32bd2eb3b4d1b83ff20bebcd60f7` |
| Voice Clone 男聲 | PASS（runtime） | `breeze-clone-male.wav`、24 kHz、9.68 s、RTF 4.2992、SHA-256 `46cfb54d9bb2c2c2f6e2a2baac96032f2d83b9f5c6ede3c529a2f6849aa02d35` |
| Voice Clone 女聲 | PASS（runtime） | `breeze-clone-female.wav`、24 kHz、9.68 s、RTF 4.4143、SHA-256 `92ccac7401f689cf76c142a7e89d39d71299a14b20c8c3c67548d4d9a8de2d4a` |
| Unified `speech-reconstruction-run.ps1` | PASS | `breeze-unified-wrapper-smoke.wav`、24 kHz、10.88 s、CUDA runtime、workflow manifest |
| CUDA runtime | PASS | `torch.cuda.is_available=True`、device=`NVIDIA GeForce RTX 5060 Ti` |
| Output WAV decode | PASS | 產出 WAV 可由 FFmpeg／soundfile 讀取 |
| `fast-all` eager CUDA graph | PASS | `breeze-fast-all.wav`、24 kHz、11.36 s；graph capture 成功；RTF `11.4196`；manifest `artifacts/speech-reconstruction/breeze-fast-all.json` |
| `flash_attention_2` | WAITING | `flash-attn==2.8.3` build 嘗試未產生可 import package；目前不能把此路徑標成 PASS |
| SoX system package | WAITING | Ubuntu repository 有 `14.4.2`，但 WSL 使用者沒有 sudo 密碼，不能寫入系統 package |
| SoX project-local extraction | PASS | `artifacts/sox-local/usr/bin/sox`，SoX `14.4.2`；搭配 local `libltdl7` 可執行，runner 會自動注入 PATH／LD_LIBRARY_PATH |
| fast-all + project-local SoX runner | PASS | `breeze-fast-all-sox-local.wav`、24 kHz、11.36 s、545,324 bytes；runner stdout 確認使用 `/mnt/d/AetherTune/artifacts/sox-local/usr/bin/sox` |
| Exact transcript | WAITING | 男女 reference 已有 Faster-Whisper STT draft；仍需人工逐字聽核 |

## 實際 UI 操作驗證

本輪以真實瀏覽器開啟 project-local UI，完成以下操作：上傳 female reference WAV、填入 exact transcript、修改女性 instruction、修改 seed、按下「生成音訊」，再以相同 UI 工作階段修改 seed 後再次生成。兩次都由官方 Breeze runtime 在 CUDA 執行，且瀏覽器 console 沒有 error（只有 Gradio `Method not implemented` warning）。

| UI 流程 | 狀態 | 證據 |
|---|---|---|
| UI 首次 eager reference clone | PASS | `artifacts/breeze-ui/run-20260922-170407-08873c93/output.wav`；24 kHz、7.92 s；`runtime_reused=false`；model load `82.4 s`、inference `36.3 s`；RTX 5060 Ti |
| UI 第二次 eager reference clone | PASS | `artifacts/breeze-ui/run-20260922-170851-c51e7232/output.wav`；24 kHz、7.76 s；`runtime_reused=true`；model load `0 s`、inference `32.5 s`；seed `124` |
| UI output validation | PASS | 兩個 WAV 均為單聲道 PCM16、finite、非靜音；對應 `output.json` 與 `ui-run.json` 保存參數、hash、runtime 與 timing |

啟動 UI：

```powershell
Set-Location D:\AetherTune
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/AetherTune; /mnt/d/AetherTune/tools/venvs/breeze-tts-wsl/bin/python -u tools/breeze-tts2-webui.py --port 50081'
```

瀏覽器開啟 `http://127.0.0.1:50081`。第一次生成會載入模型；同一 UI 工作階段只要維持 `eager`／`Fast-all` 設定不變，後續按「生成音訊」會重用模型。切換 `Fast-all CUDA graph` 或 attention backend 會重新載入，且 `flash_attention_2` 目前仍是 `WAITING`，不要當成預設值。

## 可重跑命令

```powershell
Set-Location D:\AetherTune
& .\tools\breeze-tts2-run.ps1 `
  -TextFile .\tools\fixtures\breeze-target-text.txt `
  -ReferenceAudio .\dataset\reference-voices\voice-male-m1.wav `
  -ReferenceTextFile .\tools\fixtures\breeze-reference-male-text.txt `
  -Output .\artifacts\speech-reconstruction\breeze-clone-male.wav
```

嘗試官方 fast path：

```powershell
& .\tools\breeze-tts2-run.ps1 `
  -TextFile .\tools\fixtures\breeze-target-text.txt `
  -ReferenceAudio .\dataset\reference-voices\voice-male-m1.wav `
  -ReferenceTextFile .\tools\fixtures\breeze-reference-male-text.txt `
  -Output .\artifacts\speech-reconstruction\breeze-fast-all.wav `
  -FastAll
```

程式也接受 `-AttentionImplementation flash_attention_2`；只有 WSL venv 成功安裝並可 import `flash_attn` 後才應使用。預設仍是 eager，避免把失敗的 optional path 當成主路線。

Voice Design：

```powershell
& .\tools\breeze-tts2-run.ps1 `
  -TextFile .\tools\fixtures\breeze-target-text.txt `
  -Instruction '一位溫柔明亮的成年女性，聲音清晰自然，語氣親切而帶有溫暖笑意。' `
  -CfgScale 4 `
  -Output .\artifacts\speech-reconstruction\breeze-design-female.wav
```

## 限制與授權

- 官方建議 eager inference 約 7.7 GiB VRAM；本機 16 GB GPU 已完成 `--fast-all` graph capture 與輸出，但 RTF `11.4196`，速度不代表官方 H100 benchmark。
- `flash-attn==2.8.3` 已嘗試安裝；專用 venv 原先缺少 pip，改用 uv 並補 setuptools／ninja 後仍未產生可 import package，因此目前使用 manual PyTorch path。
- SoX 系統套件仍未安裝（sudo 需要密碼），但已用 Ubuntu `.deb` 在被忽略的 `artifacts/sox-local/` 完成 portable runtime；`breeze-tts2-run.ps1` 會在該目錄存在時自動注入 local PATH／LD_LIBRARY_PATH，且 fast-all runner 已實際驗證通過。
- Breeze source code 是 Apache-2.0；model weights、derivatives 與 self-hosted outputs 受 [BreezeBlue Research and Non-Commercial License](https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE) 管轄，只可研究／非商業使用。官方安裝與 VRAM 條件見 [Breeze TTS 2 官方 README](https://github.com/breezeblue-ai/breeze-tts#readme)。
