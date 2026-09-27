# Fixed test corpus

Corpus 應至少涵蓋：一般對話、快速說話、低聲／氣音、大笑、驚叫、嘆氣、拉長音、高低音快速變化、中日英混合、60 秒連續說話與 10 分鐘 stability。

每個 sample 必須有 stable id、文字／語言、source hash、授權 provenance、預期測試標籤與是否適合人工盲測。沒有使用者提供且完成授權的語料前，不在這裡虛構角色或故事內容。

## 登錄表

[`sample-register.csv`](sample-register.csv) 目前只有 header，沒有真實 sample 或台詞。完成 provenance 與授權確認後，每列對應一個實際 source 檔：

| 欄位 | 用途 |
|---|---|
| `sample_id` | 穩定且不含個資的 sample ID |
| `source_path`、`source_sha256` | 本機／受控儲存位置及實際 SHA-256；不要把音訊 binary 放入 Git |
| `duration_ms`、`sample_rate_hz`、`channels` | 從實際檔案讀取的 metadata |
| `language_code`、`transcript_or_prompt`、`test_labels` | 語言、經授權可記錄的逐字稿／提示與測試標籤；沒有逐字稿權利時留空 |
| `source_owner_code`、`rights_status`、`rights_record_ref` | 匿名來源代碼、確認狀態與外部受控授權紀錄的引用；不要提交姓名或授權文件 |
| `split` | `train`、`validation`、`holdout` 或 `stability`；固定後不要跨組重用 |
| `blind_eligible`、`notes` | 是否可用於盲測及不含識別內容的限制備註 |

每個 sample 的使用權須允許該研究用途；只知道公開可取得不等於已獲授權。含私人聲音、可識別文字或授權文件的 CSV 不應提交到 repository。新增資料後另行保存 register 與音訊 artifact，不在這份空模板中預填示例語音。
