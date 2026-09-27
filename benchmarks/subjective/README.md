# Human Listening Benchmark

人工盲測至少記錄：sample pair id、backend／profile（評分表可匿名化）、自然度、目標音色相似度、內容正確性、原始表演／情緒保留、噪音／破音、偏好與備註。

目前沒有人工評分結果，不能把 signal-level PASS 或模型下載成功寫成主觀品質 PASS。

[`listening-template.csv`](listening-template.csv) 目前是空白 header template。以隨機匿名代碼填入兩個輸出的 A/B 欄位，並保存 presentation order seed；盲測評分人員不應看到 backend、model 或調參條件。1–5 欄位由 1（低）至 5（高）；`noise_artifacts` 也採 1（少／不明顯）至 5（嚴重），所以偏好比較要結合備註解讀。`preference_a_b_tie` 僅接受 A、B、Tie。

不得把評分人員姓名、可識別聲音、私人錄音或授權文件寫入此 CSV 或 Git。未執行盲測前保持空白；不可填入預測分數。
