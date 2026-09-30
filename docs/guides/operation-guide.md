# Windows 音訊路由操作手冊

**文件邊界：**本頁只負責 backend 聲音產生**之後**，在 Windows 將輸出接到 VB-CABLE、Light Host／VST、Voicemeeter 與 Discord／OBS，並說明如何取得線路證據。Seed-VC／RVC／STT → TTS 的啟動和模型參數看[後端使用手冊](user-guide.md)與各 backend README；RVC 訓練看[訓練手冊](model-training-guide.md)；Desktop 的 Output 欄位看[Desktop 手冊](desktop-user-guide.md)。版本、PASS／WAITING 與實測數字看[線路驗證](../verification/audio/wiring-verification-latest.md)和對應 backend 報告，不在本頁維護第二份狀態表。

## 1. 先確認方向

```text
實體麥克風／檔案 → backend → CABLE Input（播放端）
                           → CABLE Output（錄音端）
                           → Light Host input → VST bypass/full-chain
                           → Voicemeeter Input → B1 → Voicemeeter Out B1
                           → Discord／OBS microphone input
```

`CABLE Input` 是前一個程式**寫入**的播放端，`CABLE Output` 是下一個程式**讀取**的錄音端。Windows 與 PortAudio 可能為同名裝置列出不同 Host API；每次須以完整裝置名稱、方向與 Host API 唯一匹配，不照抄其他電腦的截斷名稱。Desktop 不會自動插入 VST，也不會替使用者更改 Windows 預設裝置。

先用唯讀檢查盤點端點與現有元件：

```powershell
Set-Location D:\AetherTune
& .\tools\voice-backend-check.ps1
& .\tools\verify_wiring.ps1
```

這些報告是環境／線路盤點，不是聲音已從實體麥克風送到終端的證明。需要指定 Output／Host API 時，依[後端使用手冊](user-guide.md)或[Desktop 手冊](desktop-user-guide.md)的對應欄位操作。

## 2. Backend → CABLE

1. 在 backend 或 Desktop 選定本機 inventory 中**唯一**的 `CABLE Input (VB-Audio Virtual Cable)` 播放端點及匹配的 Host API。不要選 `CABLE Output` 當 backend 的播放端。
2. 先以短句／短 WAV 確認 backend 有本輪 finite、非零輸出，再用 `CABLE Output` 擷取同一時間窗。只看到 model load、meter 或 GUI 表面狀態，不算輸出證據。
3. 若只需將 Desktop Manual TTS 送給接收程式，該程式可直接讀 `CABLE Output`；若需要 Post-FX，接下一節。每輪記錄來源、模型、裝置、Host API、route、WAV 與 hash。

可用 `tools/virtual_cable_loopback.py` 先做**合成音**線路 smoke；它不代替本輪 backend、實體麥克風或最終收音。具體 runner 命令由各 backend 文件擁有。

### 直接接 Discord

只需要讓對方聽到 AetherTune 文字生成的語音時，在 Discord 的「使用者設定 → 語音與視訊」指定：

| 位置 | 裝置 |
|---|---|
| AetherTune「輸出裝置」 | `CABLE Input (VB-Audio Virtual Cable)` |
| Discord「輸入裝置」 | `CABLE Output (VB-Audio Virtual Cable)` |
| Discord「輸出裝置」 | 實際使用的耳機／喇叭 |

不要把 Discord 的輸出也選 CABLE，以免將對方的聲音回送。VB-CABLE 的播放端／錄音端方向見[官方說明](https://vb-audio.com/Cable/VirtualCables.htm)，Discord 裝置選擇見[官方語音指南](https://support.discord.com/hc/en-us/articles/33030151293079-Discord-Voice-Video-Streaming-Guide)。此配置傳送的是 TTS，沒有混入實體麥克風原音；若要直接傳麥克風，在 Discord 改選實體麥克風。

不想聽到自己時，關閉 App 的[自己監聽](desktop-user-guide.md#自己監聽)。若仍有自己的聲音，檢查 CABLE Output 的 Windows「聆聽此裝置」與外部 mixer 的監聽路徑。Discord 的「麥克風測試」會把輸入送回輸出，檢查完請按「停止測試」；見[官方麥克風測試說明](https://support.discord.com/hc/en-us/articles/360020641332-Mic-Testing)。上述設定說明不等於這台機器的 Discord 接收 E2E 已通過。

## 3. Light Host／VST

本機已登錄的宿主入口在 `tools/external/LightHostModern/app/Light Host Modern.exe`；Graillon Free 3 VST3 的常見安裝位置為 `C:\Program Files\Common Files\VST3\Auburn Sounds Graillon 3.vst3`。實際檔案、版本與授權以[來源審核](../reference/source-audit.md)、[plugin profile](../../audio-rack/plugin-profiles/README.md)及本機檢查為準，不因這些路徑寫在手冊就當成安裝完成。

1. 啟動 Light Host，在 Audio 設定輸入 `CABLE Output`、輸出 `Voicemeeter Input`，核對各自 Host API、sample rate 和 channel 方向。
2. 在 Plugins 掃描已安裝的 VST3 路徑，加入 Graillon；先用 **bypass** 確認訊號不靜音，再使用微量參數測 **full-chain**。插件順序與 preset 契約由 [audio-rack/README.md](../../audio-rack/README.md)、[presets/README.md](../../audio-rack/presets/README.md)負責。
3. 以**同一 source、backend/model、hardware、route**成對保存 bypass 與 full-chain WAV／metrics，實測 `delta_latency_ms`，不能按 VST 名稱推估延遲。成對證據欄位由 [audio-rack/benchmarks/README.md](../../audio-rack/benchmarks/README.md)負責。

此路徑仍需實際 Host 掃描、路由擷取與人工聽測；合成 tone 通過只證明相應的虛擬線路。

## 4. Voicemeeter → 終端程式

在 Voicemeeter Standard，找出接收 `Voicemeeter Input` 的 strip，打開 UI 上對應的 **B1** bus；需要本機監聽時才另開 A bus。Discord／OBS 的麥克風選 inventory 中實際列出的 `Voicemeeter Out B1`，避免同時把終端監聽回送至輸入造成 feedback。

`tools/voicemeeter-route-check.py` 可讀 Remote API 設定及測合成 B1 線路；它不會替使用者修改 B1、Mute 或 Gain。線路有訊號後，仍要在 Discord／OBS 做同輪終端 loopback／錄音，才能證明最終程式確實收到了指定 backend 的聲音。

VCClient 是 RVC 的歷史對照路徑：要先依[VCClient runtime gate](../specs/vcclient-runtime-gate.md)和[RVC backend 文件](../../backends/rvc/README.md)核對角色 slot／模型，再將其實際輸出接到同一後段路由。VCClient HTTP 200 或空 chunk 不能當成前段聲音已通過。

## 5. 驗收分界與故障分流

| 現象 | 先檢查 | 證據 owner |
|---|---|---|
| backend WAV 非零，但 CABLE 擷取全零 | Output 名稱、Host API、方向與同輪時間窗 | backend 驗證＋[線路驗證](../verification/audio/wiring-verification-latest.md) |
| CABLE 非零，但 Light Host 無輸入 | Host input 是否為 `CABLE Output`、sample rate／channel／buffer | [audio-rack routing](../../audio-rack/routing/README.md) |
| bypass 有聲，full-chain 無聲 | VST 掃描、plugin bypass／mute、Host output | [plugin profile](../../audio-rack/plugin-profiles/README.md)＋Rack evidence |
| Voicemeeter meter 有聲，Discord／OBS 無聲 | B1 bus、終端 input 選擇、終端錄音 | [線路驗證](../verification/audio/wiring-verification-latest.md) |

`LIVE` 的時序、600 秒、dropout、identity 與人工聽評條件**只由**[LIVE gate](../specs/live-gate.md)定義。未取得同輪 physical mic → backend → Rack → virtual route → terminal artifact 時，不把單段 WAV、CABLE tone 或局部線路 PASS 寫成完整 LIVE。
