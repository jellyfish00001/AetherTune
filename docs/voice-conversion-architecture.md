# AetherTune 多後端語音架構

## 目標

把「語音變聲」拆成可互相比較的三種方法，而不是把所有模型塞進 RVC 的 `.pth/.index` 流程：

```text
                         ┌─ RVC + FCPE/RMVPE ── VCClient ── 即時路由
來源語音 ──┬─────────────┤
           │             └─ Seed-VC ─────────── 參考聲音 ── 離線/準即時 WAV
           │
           └─ STT ── transcript ──┬─ CosyVoice ──┐
                                  └─ Breeze TTS 2 ─┴─ 參考聲音/voice design ── WAV
```

## 路線責任

| 路線 | 保留什麼 | 需要什麼 | 適合的問題 |
|---|---|---|---|
| RVC | 內容、部分韻律與即時聲學表現 | 訓練角色 `.pth/.index`、f0 | 長時間即時通話與低延遲調校 |
| Seed-VC | 來源內容與表現，目標聲線來自 reference | 1–30 秒 reference；不用訓練 | 快速比較男／女聲線與 zero-shot VC |
| STT → CosyVoice/Breeze | 文字內容，重新生成聲學表現 | STT transcript、reference transcript 或 voice design | 跨語言、重寫文字、情緒／速度控制 |

## 使用決策

```text
需要即時麥克風？
├─ 是 → RVC + FCPE/RMVPE
└─ 否 → 需要保留原始語氣與表演？
          ├─ 是 → Seed-VC（source + reference，不訓練）
          └─ 否 → STT → TTS（CosyVoice／Breeze，可改寫文字）
```

不要用「模型大小」或「看起來能 import」選方法；先看輸入、延遲與是否要保留原始 acoustic performance。人類操作入口見 [`docs/user-guide.md`](user-guide.md)，RVC 訓練入口見 [`docs/model-training-guide.md`](model-training-guide.md)。

## 共用資料契約

每次實驗要能回溯：

1. source WAV 與 SHA-256。
2. target/reference WAV 與 SHA-256；若使用 voice design，記錄 prompt。
3. model id、上游 URL、revision、license、runtime environment。
4. STT transcript；TTS voice clone 必須標示 `exact`、`machine-generated` 或 `manual-verified`。
5. 實際 device/provider、取樣率、RTF／延遲、輸出 hash 與聽測結果。

## Windows 執行邊界

- 現有 RVC `.venv` 保持穩定；CosyVoice、Breeze 與 STT 使用各自的 WSL2／Python environment，不混裝大型或 Linux-specific 依賴。
- Seed-VC 已使用獨立 Python 3.10 環境完成 offline-v1 雙向 WAV 推論；real-time tiny model 仍待 latency 測試。
- CosyVoice 官方安裝文件以 Python 3.10、Conda 與 Linux 依賴為基線；本機已用 WSL2 + uv 建立環境並完成 GPU zero-shot／reference clone 輸出。
- Breeze TTS 2 官方 quick start 要求 Linux、CUDA 與約 12 GB 以上 VRAM；本機 16 GB 顯存已完成 eager CUDA 安裝與 Voice Design／reference clone 輸出。

## 驗收順序

1. 先驗證參考聲音存在、授權與 hash。
2. Seed-VC 用同一個 source 分別轉成 female/male，確認離線輸出與 CUDA/CPU provider；此項已完成初版。
3. STT 對同一批 source 產生 transcript，人工抽查；錯誤 transcript 不送 voice clone。
4. CosyVoice 與 Breeze 各自輸出同一段文字，再比較內容一致性、聲線、情緒與延遲。
5. 最後才接回 VB-CABLE／Discord／OBS；離線 WAV PASS 不代表即時鏈路 PASS。
