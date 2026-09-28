---
name: aethertune-doc-routing
description: 定位或更新 AetherTune 文件時，依任務找唯一 owner、相關契約與驗證；適用於文件整理、增修或查找。
---

# 文件定位與更新

先讀 [文件入口](../../../docs/README.md)選讀者與任務，再開該資訊的唯一 owner。程式檔定位使用 [Agent 快速地圖](../../reference/agent-quick-map.md)；只有需要單檔職責時才搜尋 [逐檔索引](../../reference/project-file-map.md)。

寫入時只更新 owner 文件與直接失效的入口／連結。操作放手冊；預期行為與分類放規格；日期、命令、hash、artifact、PASS／WAITING／BLOCKED 放對應驗證。歷史報告保留當日身分，不改寫成目前結論。以 source、`contracts/`、verifier 和本輪 artifact 核對事實。

新增、刪除或更名 Git 管理檔案時同步逐檔索引；移動文件後檢查 Markdown 連結與工具中的文件路徑。不要把整份索引、驗證數值或操作流程複製進本 Skill。
