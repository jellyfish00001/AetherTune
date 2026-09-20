# 共用模型與資源

這裡記錄可以被多個後端共用的資源規則，不直接提交大型權重。

- 參考聲音放 `dataset/reference-voices/`，並在 `dataset/manifests/reference-register.csv` 登記來源、license、speaker label、transcript status 與 SHA-256。
- STT 模型、TTS 模型與 VC checkpoint 仍在各自後端目錄管理，避免不同 license、取樣率或 runtime 被混用。
- 只有真的共用且版本／license 相容的 tokenizer、音訊轉檔工具，才可放在這層。
