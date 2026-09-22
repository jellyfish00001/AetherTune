# 尚待確認的決策

1. 目標角色聲線是否為使用者本人或已取得明確訓練/轉換/發布授權的資料？
2. 是否接受已部署的 Voicemeeter、VB-CABLE、Graillon 這類免費但非全開源元件？
3. Voicemeeter 的 `Voicemeeter Input → B1 → Voicemeeter Out B1` synthetic route 已通過；是否要以目前 route 作為第一個實際 backend／Light Host full-chain profile？
4. VCClient 2.1.4-alpha 對 RTX 5060 Ti `sm_120` 有警告；角色模型產生後要優先驗證 CUDA，還是直接採 ONNX/DirectML 備案？
5. 最終輸出優先支援 Discord、OBS、LINE、Teams，還是先做 loopback？
6. 低延遲目標是可接受語音延遲，還是要以實測端到端毫秒數作硬門檻？
7. Dataset 是否允許 TTS 合成音，或必須全部使用真人乾聲？
8. 最終取樣率要以 RVC/VCClient 相容性、裝置驅動或品質需求哪一項為主？
