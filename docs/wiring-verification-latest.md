# AetherTune Wiring Verification

檢查時間：2026-09-20 23:42:51 +08:00

摘要：PASS=15；WAITING=5；BLOCKED=1

RunInferenceProbes：True；FailOnWaiting：False

| 元件 | 狀態 | 證據 |
|---|---|---|
| AetherTune Python venv | PASS | D:\AetherTune\.venv\Scripts\python.exe |
| RVC 官方 repo | PASS | path=D:\AetherTune\tools\external\Retrieval-based-Voice-Conversion-WebUI revision=81eed5e |
| RVC training assets | PASS | pretrained=12, pretrained_v2=12, mute=11 |
| 角色模型（.pth/.index） | WAITING | 模型已登記且 hash 合法，但沒有 status=ready 的可用模型；candidate/retired 不得作為推論輸入 |
| FFmpeg/FFprobe | PASS | C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe |
| VCClient package | PASS | path=D:\AetherTune\tools\external\VCClient\2.1.4-alpha\dist\main\main.exe process=0 |
| VCClient bundled CUDA runtime gate | WAITING | VCClient embedded torch=2.7.0+cu118; detected GPU capability=NVIDIA GeForce RTX 5060 Ti (12, 0); log=available=True not found; cuda_build=; path=D:\AetherTune\tools\external\VCClient\2.1.4-alpha\dist\main\vcclient.log; package log must be validated with a real role model because cu118/sm_120 is not proven compatible |
| Light Host Modern | PASS | path=D:\AetherTune\tools\external\LightHostModern\app\Light Host Modern.exe process=0 |
| Graillon VST3 binary | PASS | C:\Program Files\Common Files\VST3\Auburn Sounds Graillon 3.vst3\Contents\x86_64-win\Auburn Sounds Graillon 3.vst3 |
| Graillon loaded in Light Host | WAITING | VST3 binary 存在，但尚未以 Light Host chain、bypass/active loopback 證明已載入與處理音訊 |
| Windows audio endpoint inventory | PASS | PortAudio inventory=111; CIM=0; cim_error=拒絕存取 |
| Endpoint: CABLE Input playback | PASS | CABLE Input (VB-Audio Virtual C; input=0; output=16 \| CABLE Input (VB-Audio Virtual Cable); input=0; output=16 \| CABLE Input (VB-Audio Virtual Cable); input=0; output=2 |
| Endpoint: CABLE Output recording | PASS | CABLE Output (VB-Audio Virtual ; input=16; output=0 \| CABLE Output (VB-Audio Virtual Cable); input=16; output=0 \| CABLE Output (VB-Audio Virtual Cable); input=2; output=0 \| CABLE Output (VB-Audio Point); input=16; output=0 |
| Endpoint: Voicemeeter Input playback | PASS | Voicemeeter Input (VB-Audio Voi; input=0; output=8 \| Voicemeeter Input (VB-Audio Voicemeeter VAIO); input=0; output=8 \| Voicemeeter Input (VB-Audio Voicemeeter VAIO); input=0; output=2 |
| Endpoint: Voicemeeter Out B1 recording | PASS | Voicemeeter Out B1 (VB-Audio Vo; input=8; output=0 \| Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO); input=8; output=0 \| Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO); input=2; output=0 |
| Endpoint: physical microphone recording | PASS | 麥克風 (HyperX QuadCast S); input=2; output=0 \| 麥克風 (HyperX QuadCast S); input=2; output=0 \| 麥克風 (HyperX QuadCast S); input=2; output=0 \| 麥克風 (Realtek HD Audio Mic input); input=2; output=0 \| 麥克風 (HyperX QuadCast S); input=2; output=0 |
| VB-CABLE synthetic loopback | PASS | report=D:\AetherTune\artifacts\virtual-cable-loopback.json; frames=144000/144000; rms=0.346613883972168; peak=0.98504638671875; sha256=f1102260c95a378eafd63fa6c8453c65128455f453dd127e9147e1708bd0ee6f |
| Voicemeeter B1 synthetic loopback | WAITING | 已實際執行但訊號未通過；frames=144000/144000; rms=0; report=D:\AetherTune\artifacts\voicemeeter-b1-loopback.json |
| VCClient localhost Web UI | WAITING | 尚未啟動或 port 18000 無法連線 |
| RVC venv CUDA runtime | PASS | 2.7.1+cu128 True 64.0 ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider'] |
| Project ONNX synthetic inference | BLOCKED | 本次 probe exit=2；未採用舊 artifact。output=找不到 sample ONNX：D:\AetherTune\tools\external\VCClient\2.1.4-alpha\dist\main\model_dir\0\kikoto_kurage_v2_40k_e100.onnx |

這是唯讀驗證；沒有錄製實體麥克風、沒有改寫預設音訊裝置。合成 loopback 與 ONNX probe 只會寫入 artifacts/ 證據，不代表角色音色品質或 Discord/OBS 已驗收。
