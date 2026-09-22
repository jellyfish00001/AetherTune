# AetherTune Wiring Verification

檢查時間：2026-09-22 19:27:55 +08:00

摘要：PASS=17；WAITING=4；BLOCKED=1

RunInferenceProbes：True；FailOnWaiting：False

| 元件 | 狀態 | 證據 |
|---|---|---|
| AetherTune Python venv | PASS | D:\AetherTune\.venv\Scripts\python.exe |
| RVC 官方 repo | PASS | path=D:\AetherTune\tools\external\Retrieval-based-Voice-Conversion-WebUI revision=81eed5e |
| RVC training assets | PASS | pretrained=12, pretrained_v2=12, mute=11 |
| 角色模型（.pth/.index） | BLOCKED | Chinese_Narrator_Uncle: f0 仍是未知或 placeholder; Chinese_Narrator_Uncle: dataset_batch_id 仍是未知或 placeholder; Chinese_Narrator_Uncle: rvc_revision 仍是未知或 placeholder; Chinese_Narrator_Uncle: source_url 仍是未知或 placeholder; Chinese_Narrator_Uncle: license_or_permission 仍是未知或 placeholder; Chinese_Narrator_Uncle: training_environment 仍是未知或 placeholder; Kafka_CN_Yujie: f0 仍是未知或 placeholder; Kafka_CN_Yujie: dataset_batch_id 仍是未知或 placeholder; Kafka_CN_Yujie: rvc_revision 仍是未知或 placeholder; Kafka_CN_Yujie: source_url 仍是未知或 placeholder; Kafka_CN_Yujie: license_or_permission 仍是未知或 placeholder; Kafka_CN_Yujie: training_environment 仍是未知或 placeholder; Sage_CN_HeroicFemale: f0 仍是未知或 placeholder; Sage_CN_HeroicFemale: dataset_batch_id 仍是未知或 placeholder; Sage_CN_HeroicFemale: rvc_revision 仍是未知或 placeholder; Sage_CN_HeroicFemale: source_url 仍是未知或 placeholder; Sage_CN_HeroicFemale: license_or_permission 仍是未知或 placeholder; Sage_CN_HeroicFemale: training_environment 仍是未知或 placeholder; Wukong_HeroicMale: f0 仍是未知或 placeholder; Wukong_HeroicMale: dataset_batch_id 仍是未知或 placeholder; Wukong_HeroicMale: rvc_revision 仍是未知或 placeholder; Wukong_HeroicMale: source_url 仍是未知或 placeholder; Wukong_HeroicMale: license_or_permission 仍是未知或 placeholder; Wukong_HeroicMale: training_environment 仍是未知或 placeholder |
| FFmpeg/FFprobe | PASS | C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe |
| VCClient package | PASS | path=D:\AetherTune\tools\external\VCClient\2.1.4-alpha\dist\main\main.exe process=0 |
| VCClient bundled CUDA runtime gate | WAITING | VCClient embedded torch=2.7.0+cu118; detected GPU capability=NVIDIA GeForce RTX 5060 Ti (12, 0); log=available=True; cuda_build=11.8; path=D:\AetherTune\tools\external\VCClient\2.1.4-alpha\dist\main\vcclient.log; package log must be validated with a real role model because cu118/sm_120 is not proven compatible |
| Light Host Modern | PASS | path=D:\AetherTune\tools\external\LightHostModern\app\Light Host Modern.exe process=0 |
| Graillon VST3 binary | PASS | C:\Program Files\Common Files\VST3\Auburn Sounds Graillon 3.vst3\Contents\x86_64-win\Auburn Sounds Graillon 3.vst3 |
| Graillon loaded in Light Host | WAITING | VST3 binary 存在，但尚未以 Light Host chain、bypass/active loopback 證明已載入與處理音訊 |
| Windows audio endpoint inventory | PASS | PortAudio inventory=107; CIM=0; cim_error=拒絕存取 |
| Endpoint: CABLE Input playback | PASS | CABLE Input (VB-Audio Virtual C; input=0; output=16 \| CABLE Input (VB-Audio Virtual Cable); input=0; output=16 \| CABLE Input (VB-Audio Virtual Cable); input=0; output=2 |
| Endpoint: CABLE Output recording | PASS | CABLE Output (VB-Audio Virtual ; input=16; output=0 \| CABLE Output (VB-Audio Virtual Cable); input=16; output=0 \| CABLE Output (VB-Audio Virtual Cable); input=2; output=0 \| CABLE Output (VB-Audio Point); input=16; output=0 |
| Endpoint: Voicemeeter Input playback | PASS | Voicemeeter Input (VB-Audio Voi; input=0; output=8 \| Voicemeeter Input (VB-Audio Voicemeeter VAIO); input=0; output=8 \| Voicemeeter Input (VB-Audio Voicemeeter VAIO); input=0; output=2 |
| Endpoint: Voicemeeter Out B1 recording | PASS | Voicemeeter Out B1 (VB-Audio Vo; input=8; output=0 \| Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO); input=8; output=0 \| Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO); input=2; output=0 |
| Endpoint: physical microphone recording | PASS | 麥克風 (HyperX QuadCast S); input=2; output=0 \| 麥克風 (HyperX QuadCast S); input=2; output=0 \| 麥克風 (HyperX QuadCast S); input=2; output=0 \| 麥克風 (Realtek HD Audio Mic input); input=2; output=0 \| 麥克風 (HyperX QuadCast S); input=2; output=0 |
| VB-CABLE synthetic loopback | PASS | report=D:\AetherTune\artifacts\virtual-cable-loopback.json; frames=144000/144000; rms=0.0826212912797928; peak=0.159999847412109; sha256=b64c2daa4de64d2c07751acb82c50385e7ed2d11c11f1e1cfe741d5d30347a5c |
| Voicemeeter B1 synthetic loopback | PASS | report=D:\AetherTune\artifacts\voicemeeter-b1-loopback.json; frames=144000/144000; rms=0.0824916288256645; peak=0.159999847412109; sha256=bc6f5e27414a587e4ffc12cb50bde88444803a8655c4d23ff06474bab4b42025 |
| Voicemeeter B1 Remote API route diagnosis | PASS | report=D:\AetherTune\artifacts\voicemeeter-b1-route-check.json; frames=144000/144000; rms=0.0825825557112694; nonzero_api_levels=15; sha256=cf0997902c0f5574f2b41bfb32046c90ef7cc8f60d941abfa1bb8ce3e843ce98 |
| VCClient localhost Web UI | WAITING | 尚未啟動或 port 18000 無法連線 |
| RVC venv CUDA runtime | PASS | 2.7.1+cu128 True 64.0 ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider'] |
| Project ONNX synthetic inference | WAITING | run_id=60cc74df-e14b-4cf6-bfc8-7bdd1295cb00; model_sha256=725cd4ff3a0858c5c738f2b07b5b469fa6708ef67f13c26aa7b8723dc5f1e0e5; inference 成功但實際 provider=CPUExecutionProvider（目前不是 CUDA）；requested=CUDAExecutionProvider; artifact=D:\AetherTune\artifacts\onnx-runtime-probe.json |

這是唯讀驗證；沒有錄製實體麥克風、沒有改寫預設音訊裝置。合成 loopback 與 ONNX probe 只會寫入 artifacts/ 證據，不代表角色音色品質或 Discord/OBS 已驗收。
