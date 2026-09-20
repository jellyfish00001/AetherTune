# dataset/manifests

保存資料批次的 metadata 與 provenance manifest。這些 CSV 可以進 Git，但不得包含音訊內容、密鑰或個人敏感資料。

- `source-register.csv` 是人工維護的來源／授權／批次登記；它不能由 audit 工具取代或推測。`source_sha256` 必須是目前 WAV 的合法 64 位 SHA-256，音檔替換後必須重新登記。
- `raw-audit.csv` 是機器產生的技術檢查結果，每列對應 `dataset/raw/` 下的一個音訊檔，包含格式、取樣率、聲道、長度、音量摘要、檔案 SHA-256、來源批次、source hash 與審核狀態。
- audit 重新執行時只會保留既有 `manual_notes`，並重新產生機器 `notes`；舊的機器 `notes` 不會自動遷移成人工備註。新的人工備註請直接填 `manual_notes`，來源資料則寫入 `source-register.csv`。
- `--fail-on-invalid` 會在空資料集、缺少 provenance、非規格音訊、損壞檔案或疑似靜音時回傳非零狀態。原始檔的 `parent_relative_path` 可留空，但 `derivation` 必須說明它是原始資料；衍生檔則應填入父檔。

填寫流程：先放入 WAV 並執行一次不帶 `--fail-on-invalid` 的 audit 取得檔案 SHA-256，再把該值填入 `source-register.csv` 的 `source_sha256`，最後重新執行帶 `--fail-on-invalid` 的 gate。舊 manifest 的來源欄位不會再替目前 register 補值。

範例欄位與填寫方式見 `source-register.example.csv`。來源資料若涉及第三方聲音，請不要只填「網路下載」；應記錄可核對的授權或使用權說明。
