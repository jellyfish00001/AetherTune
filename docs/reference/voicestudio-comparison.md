# VoiceStudio 技術比較

本頁只擁有 VoiceStudio 的固定版本研究與 AetherTune 可採納方向。AetherTune 的 Desktop 即時修復與實測結果由 [Desktop VC 驗證](../verification/desktop/realtime-vc-verification-latest.md)負責；本頁不判定本機音訊就緒。

查核日期：2026-10-01；VoiceStudio revision：`0834c8be28460fc4e0518bdb31eb57c494b253b2`。僅讀公開文件與 source，未安裝或執行 VoiceStudio。

| 面向 | VoiceStudio 的 source fact | AetherTune 的 source fact |
|---|---|---|
| Desktop | Electron 44、React 19、Vite 8，renderer 與 Python HTTP/WebSocket backend 分離 | Tauri 2、React 19、Vite 7，Rust IPC／Job Object 管理 Python 隔離 backend |
| 主要用途 | 文字生成、聲音複製、配音、轉錄、批次製作 | 麥克風 VC、角色模型、zero-shot reference VC；另外提供 Manual TTS |
| 串流 | 文字 → PCM 的 streaming TTS；mic → ASR 的 dictation | RVC rolling/SOLA；Seed／Mean／X 的 Desktop 常駐核心與 capture/output |
| Voice conversion | `/convert` 接上傳片段，ASR → TTS → WAV；可選 RVC 檔案後處理 | 保留 source 的表演，直接轉換 mic／WAV 的聲學訊號 |
| 音效 | `audio_dsp.py` 有 preset、EQ、compressor、reverb、limiter；主要用於生成後音檔 | Desktop 共用 EQ／壓縮／殘響／乾濕混合；外部 VST Rack 另有契約與驗收 |

「兩者都有 streaming」不表示處理同一種輸入。此次檢查沒有找到 VoiceStudio 的 **mic → VC → output duplex** 實作；這是基於已查路由的結論，不是其所有功能的執行測試。

## 值得採納的工程方法

1. **健康檢查與真正 self-test 分開。** `TTSBackend` 統一 `is_available()`／`ensure_ready()`／生成／卸載；engine `/health` 不載入模型，`/selftest` 執行有界限的合成。AetherTune 沿用檔案預檢、warmup、stream、非零輸出各自回報，讓模型 READY 與可聽音訊可分辨。
2. **模型安裝狀態給出可操作錯誤。** 完整 snapshot、只有 config、截斷 cache、磁碟不足與下載失敗有不同狀態。AetherTune 已有固定 revision/hash；後續應在 UI 呈現具體缺項，避免只顯示 candidate 或 WAITING。
3. **共用 Post-FX 與明確 bypass。** 效果由同一條鏈套用到主輸出與監聽；乾聲表示「變聲完成但未加效果」，不混入原始 mic。此次 Desktop 實作使用現有 NumPy/SciPy，沒有複製 VoiceStudio 程式或引入另一個服務框架。
4. **維持模型常駐，分開控制與 PCM。** 同一 START session 重用 reference conditioning、模型與 streaming cache；PortAudio callback 只搬運音訊，模型 worker 另行處理。RTF、backlog、drops 必須可見，不能用不斷加 buffer 掩蓋慢推論。

此研究不支持更換 Electron、引入 FastAPI/MCP、擴增更多模型或重做 Desktop 的必要性。當前直接的改善收益來自把已存在的引擎接到真實音訊鏈路。

## 固定來源

- [Electron dependencies](https://github.com/debpalash/VoiceStudio/blob/0834c8be28460fc4e0518bdb31eb57c494b253b2/electron/package.json)、[Python dependencies](https://github.com/debpalash/VoiceStudio/blob/0834c8be28460fc4e0518bdb31eb57c494b253b2/pyproject.toml)。
- [TTSBackend](https://github.com/debpalash/VoiceStudio/blob/0834c8be28460fc4e0518bdb31eb57c494b253b2/backend/services/tts_backend.py)、[health/selftest](https://github.com/debpalash/VoiceStudio/blob/0834c8be28460fc4e0518bdb31eb57c494b253b2/backend/api/routers/engines.py)。
- [audio_dsp](https://github.com/debpalash/VoiceStudio/blob/0834c8be28460fc4e0518bdb31eb57c494b253b2/backend/services/audio_dsp.py)、[voice_convert](https://github.com/debpalash/VoiceStudio/blob/0834c8be28460fc4e0518bdb31eb57c494b253b2/backend/api/routers/voice_convert.py)。
- [streaming TTS](https://github.com/debpalash/VoiceStudio/blob/0834c8be28460fc4e0518bdb31eb57c494b253b2/backend/api/routers/tts_stream.py)、[mic dictation capture](https://github.com/debpalash/VoiceStudio/blob/0834c8be28460fc4e0518bdb31eb57c494b253b2/backend/api/routers/capture_ws.py)。

VoiceStudio repository 使用 AGPL-3.0；各模型仍有獨立條款。此處屬外部研究參考，不是 AetherTune installed backend 或已採納 Skill。
