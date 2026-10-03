# AetherTune 目標與任務進度

**文件邊界：**本頁是功能交付程度、工作狀態、優先順序與阻礙的唯一追蹤入口。功能定義在[產品規格](specs/app-requirements.md)，分層在[App 架構](specs/app-architecture.md)，驗收條件在[驗證計畫](specs/verification-plan.md)。實際 PASS／WAITING 由分項報告與可重跑 artifact 擁有，本頁只摘要並連結。

更新日期：2026-10-03（Asia/Taipei）。規格、資料 baseline、快照排序／投影與 request 驗證拆分，以及條列式需求單／A/A 波動診斷已推送至 `5484500`；功能相容 PASS，效能驗收仍 WAITING。本輪依授權完成 Computer Use 原生拖曳、快捷鍵、Quick Input、Settings Exit 與新 CosyVoice request 的限定補驗，並修正 CDP 拖曳的輸入干擾；只改測試與文件。後續依使用者授權略過 Tray 工具驗收，UI-01 限定範圍結案；冷啟動等待不阻擋離線手動 TTS，正式 LIVE 驗收延後。完整音訊路由／LIVE 的實測狀態未升級，已知路由問題保留；各輪證據以分項報告的日期與範圍為準。

## 怎麼看與追蹤

1. 想了解產品：先讀[條列式應用功能需求單](specs/application-feature-checklist.md)；詳細行為看[十項大功能與小功能](specs/app-requirements.md#f01)，用 F01～F10 對照下表。
2. 想知道進度：先看「已交付／缺口」，再看任務的狀態、依賴與完成條件；不要把已寫程式等同驗收完成。
3. 想安排下一輪：從第一批尚未完成且依賴已滿足的任務開始；Agent 只讀該功能、owner 與測試文件。
4. 想核對成果：由證據欄開報告，確認日期、commit、場景及 artifact。歷史官方 GUI／VCClient 不與 Desktop runner 混用。

| 維度 | 詞彙與含意 |
|---|---|
| 功能交付 | 已交付＝該列範圍已具備；部分交付＝仍缺子功能；未交付＝僅規格／契約。三者都不代表完整 LIVE |
| 任務狀態 | PLANNED 待做；IN_PROGRESS 已開始；WAITING 等明確外部條件；BLOCKED 已重現技術阻礙；DONE 達到該任務完成條件 |
| 驗證狀態 | PASS／WAITING／BLOCKED 均須附測試範圍；fixture、preview、native、模型 WAV、CABLE、physical／LIVE 分開 |
| 維護規則 | 完成後更新任務列及證據，不新增第二張待辦表；新任務追加 ID，舊 ID 不重用 |

本輪另交付載入階段／歷史時間提示、四 VC 參數保存、輸入降噪及資訊提示；證據由[調音與載入驗證](verification/desktop/audio-tuning-verification-latest.md)擁有。驗證在未提交工作樹進行，提交版本以 Git 歷史為準，不改寫前述已推送版本的歷史。

不計算整體百分比：目前大小功能的工作量與驗收成本不同，尚無可信權重。以逐項完成條件與每批出口監控；本次沒有宣稱完整效能或架構重構已完成。

## 功能進度總覽

| 功能 | 交付程度／已具備的小功能 | 尚缺什麼 | 證據／後續任務 |
|---|---|---|---|
| [F01 工作區／視窗](specs/app-requirements.md#f01) | 部分交付：三種 layout、WORKSPACE／SETTINGS、首屏 START、雙語與偏好保存；預設原生拖曳／快捷鍵／退出已補驗 | Tray 點擊未實測、本輪工具驗收略過；載入與錯誤流程再改善 | [UI](verification/desktop/usability-audit-latest.md#computer-use-20261003)、[語言](verification/desktop/ui-language-verification-latest.md)；UI-01／02、MOD-01 |
| [F02 四 VC](specs/app-requirements.md#f02) | 部分交付：四 VC 串流／RVC File、Start／Stop、manifest 參數表單與獨立保存、進階收合 | RVC index 覆蓋、physical／完整路由；bridge／runtime 預檢雙向依賴 | [調音](verification/desktop/audio-tuning-verification-latest.md)、[Desktop VC](verification/desktop/realtime-vc-verification-latest.md)；FEAT-01、AUDIO-01、LIVE-01、MOD-04 |
| [F03 Manual TTS](specs/app-requirements.md#f03) | 核心已交付：雙引擎、Queue／取消／快照、Recent／Favorites、完成播放寫 Transcript、同引擎 worker 重用 | 冷啟動與切換慢；完整 WAV 模式；近期新增音效仍需新生成原生 Speak 全鏈 | [Manual TTS](verification/desktop/manual-tts-verification-latest.md)、[音效](verification/desktop/audio-effects-verification-latest.md)；PERF-01、AUDIO-02 |
| [F04 常駐 STT／重建](specs/app-requirements.md#f04) | Desktop 未交付；已有離線 CLI、provider／source 契約，畫面重建模式目前僅文字 | physical Mic／Remote capture、VAD、常駐 STT、backend_stt 串接及共存 | [操作審查](verification/desktop/usability-audit-latest.md)、[後端手冊](guides/user-guide.md)；FEAT-03 |
| [F05 聲音／模型／Preset](specs/app-requirements.md#f05) | 部分交付：TTS catalogue、RVC register／模型選擇、四 VC 參數表單、來源 audit 工具 | Voice Library 管理、完整 Preset Save／Load；來源限制另驗 | [調音](verification/desktop/audio-tuning-verification-latest.md)、[模型 audit](verification/backends/rvc-model-audit-latest.md)；FEAT-01、SOURCE-01 |
| [F06 裝置／音效／路由](specs/app-requirements.md#f06) | 部分交付：裝置／監聽提示、六引擎音效、四 VC 輸入降噪、手動症狀排查；有 WAV／指定 CABLE 分項證據 | RVC duplex 的 B1 近零問題、外部 VST bypass/full-chain、接收端及聽評 | [調音](verification/desktop/audio-tuning-verification-latest.md)、[音效](verification/desktop/audio-effects-verification-latest.md)、[VC](verification/desktop/realtime-vc-verification-latest.md)；AUDIO-01／02／03、LIVE-01 |
| [F07 Session／歷史](specs/app-requirements.md#f07) | 部分交付：TTS SQLite、當前 Session Transcript、JSONL／TXT exports | 跨 Session GUI、搜尋／分頁、SRT、版本 migration、保留期限／復原 | [儲存 owner](../services/tts/storage.py)、[維護手冊](../.agent/reference/agent-maintenance-guide.md)；DATA-01、FEAT-02 |
| [F08 診斷／效能](specs/app-requirements.md#f08) | 部分交付：六引擎歷史載入範圍、階段／等待／程序存活／最後進度、TTS cold／warm、既有 metrics 與資料基準 | UI／IPC／資源與端到端控制量測、ACK timeout；尚無整體效能達標結論 | [調音](verification/desktop/audio-tuning-verification-latest.md)、[資料基準](verification/desktop/performance-baseline-latest.md)；BASE-01、UI-02、PERF-01／02 |
| [F09 設定／安裝](specs/app-requirements.md#f09) | 部分交付：本機開發版 exe、語言／音效／視窗偏好 | installer／portable、新機驗證、auto update、migration／失敗回復 | [Desktop 手冊](guides/desktop-user-guide.md)、[語言](verification/desktop/ui-language-verification-latest.md)；DATA-01、SHIP-01 |
| [F10 Agent Reply](specs/app-requirements.md#f10) | 未交付：只有停用契約，service 拒絕 agent source | API／Personality／Auto Reply、Phrase Hotkeys、來源與權限驗證 | [Manual TTS](verification/desktop/manual-tts-verification-latest.md)、[service](../services/tts/service.py)；FUT-01 |
| N01～N04 品質與維護 | 已有 UI 專項回歸、Agent 規則／owner 地圖／維護手冊；本輪補功能 ID 與追蹤 | UI、量測、程式／資料解耦依下列任務逐項交付 | DOC-01、BASE-01、MOD-01／02／03／04、DATA-01 |

### 最需要注意的現況

- 原生可見拖曳／lock、click-through 快捷鍵恢復、預設快捷鍵、Quick Input、關閉後恢復與 Settings Exit 已有 Computer Use 證據；CDP 拖曳另隔離實體游標干擾後 PASS。Tray 選單未實測，本輪依授權略過工具驗收；UI-01 限定範圍結案，不以註冊狀態或 IPC 補成 Tray PASS。
- TTS 同引擎第二句已有模型重用證據；cold start／engine switch 仍慢。不能把 warm 單句數字當每次啟動速度，也不能把完整 WAV 可用時間稱為 streaming 首包。
- 四 VC 短測有輸出；Seed／Mean／X 的 callback 輸入使用 fixture，RVC duplex B1 擷取仍 WAITING。physical 說話、音質、600 秒與 Discord／外部 Rack 未通過完整驗收。
- 舊 VCClient packaged 的 BLOCKED 與新版 Desktop headless RVC 是不同實作。前者不是後者的依賴；後者局部 PASS 也不修正前者。

<a id="acceptance-scope-20261003"></a>
### 2026-10-03 驗收取捨

依使用者「如果影響不大或是可以人為驗證，則可以跳過驗收」授權，採納下列範圍。略過驗收不新增測試證據；人工短測步驟由 [Desktop 手冊](guides/desktop-user-guide.md#personal-use-check)擁有。

| 項目 | 使用影響／本輪處理 |
|---|---|
| 系統匣選單 | 已有快捷鍵、重新啟動恢復及 Settings Exit 證據；略過 Tray 工具驗收，UI-01 按限定範圍 DONE。選單原始證據保持 WAITING，可自行確認，後續工作不再依賴 Tray 目標。詳見[UI 報告](verification/desktop/usability-audit-latest.md#tray-acceptance-20261003) |
| TTS 冷啟動等待 | 影響首句及切換引擎的等待，對即時對話明顯；本輪不作離線手動 TTS 的阻擋驗收，保留 BASE-01／PERF-01 量測與改善。數值與解讀只看 [Manual TTS 報告](verification/desktop/manual-tts-verification-latest.md#native-quick-input-20261003) |
| 完整路由／LIVE | 可人工短測指定耳機與接收端，正式 LIVE 驗收延後，不阻擋離線 TTS 或其他開發；尚未取得完整證據的配置仍 WAITING，不宣稱正式 LIVE。RVC B1 近零等已知問題仍由 AUDIO-01 追蹤，來源與新增 FX 驗收亦不因此略過 |

## 工作順序與每批出口

這是實作順序，不是日期承諾。責任模組是程式 owner，並非已指派 Agent。DOC-01 已完成；BASE-01 已取得資料層子範圍的證據；UI-01 已補原生操作，Tray 工具驗收略過後以限定範圍結案。PERF-02 已交付快照排序，MOD-02 已抽離快照投影及 request 資料驗證；效能控制量測仍不穩定，不將功能相容提升為效能 PASS。其餘依賴尚未完成的工作仍列 PLANNED。

| 批次 | 目的／工作 | 出口 |
|---|---|---|
| 0：已完成 | DOC-01 規格、進度、架構邊界與 Agent 交接 | 人能讀功能／進度，Agent 能由 ID 找 owner／驗收；文件檢核通過 |
| 1：先能看懂、量得準 | BASE-01、UI-01；再做 MOD-01、UI-02 | 保留現有 UI／音訊行為，有 baseline、可核對的載入／錯誤操作，原生拖曳問題有結論 |
| 2：處理根因 | MOD-02／03／04、DATA-01；依量測做 PERF-01／02 | 模組依賴與資料 writer 清楚，舊資料可升級／復原；改善前後有同條件數字 |
| 3：補產品缺口 | FEAT-01／02／03、AUDIO-02 | 可保存設定、找歷史、使用常駐 STT；各自有真實功能驗收，不能只靠 UI |
| 4：日常使用與交付 | LIVE-01、SHIP-01；FUT-01 排後續 | 指定配置與安裝目標逐項通過；沒有證據的引擎／路由保持原分類 |

AUDIO-01 與 SOURCE-01 可從第一批起獨立推進；physical／聽評可在已有合格配置時安排，不必等待全部新功能。不同任務不可同時佔用同一 GPU／音訊線路。

局部 source 優化若已有受影響範圍的 baseline、契約不變且可獨立回退，可先於整批出口交付；不把該子範圍通過視為 BASE／MOD／DATA 全部完成。PERF-02 的快照排序屬此情形，完整跨層更新仍按依賴執行。

## 任務登錄：每列都是可交接單位

完成條件中的基準與方法連到[優化驗收](specs/verification-plan.md#optimization-acceptance)；歷史 M0～M8 只是功能分組，不能用「走到 M6」推算 M4／M5 已完成。

| ID／優先度 | 功能與交付 | 責任模組／依賴 | 狀態 | 完成條件／證據 |
|---|---|---|---|---|
| DOC-01／首要 | N04：功能分層、任務、程式／資料邊界、Agent 最小讀取與交接 | `docs/`、`.agent/`；無 | DONE | `d478ee2` 已推送；功能／任務 ID、相對連結與檔案地圖核對；未改 runtime |
| BASE-01／首要 | F08、N02：固定 UI／cold／warm／長 Session baseline | app tests、TTS／VC metrics、storage；無 | IN_PROGRESS | [資料子範圍 PASS](verification/desktop/performance-baseline-latest.md)：隔離 DB、export、snapshot 及最終檔案核對。尚缺 UI／IPC／CPU／RSS、cold／warm／切換與品質矩陣；完整達到驗證計畫條件才 DONE |
| UI-01／首要 | F01.3：重現原生拖曳回歸與視窗逃生操作 | `app/src/main.tsx`、Rust window／tests；無 | DONE | [Computer Use 補驗](verification/desktop/usability-audit-latest.md#computer-use-20261003)：三版面可見、實際 drag／lock、click-through 恢復、Ctrl+Alt+A／V、Quick Input、Settings Exit／程序回收 PASS；CDP 干擾已由測試隔離，未改產品拖曳。2026-10-03 依[授權取捨](verification/desktop/usability-audit-latest.md#tray-acceptance-20261003)略過 Tray 工具驗收，按本輪預設操作範圍結案；Tray 原始證據 WAITING，不宣稱選單或所有配置通過 |
| MOD-01／高 | F01／03、N03：抽離 UI 狀態／訂閱與操作元件 | `app/src/main.tsx`、`components/SpeechWorkspace.tsx`、`services/`；BASE-01、UI-01 | PLANNED | 保持 command／testid／草稿／IME／queue 行為；元件不直接管原生程序，訂閱集中且可清理；UI 交叉回歸與不退步比較 |
| UI-02／高 | F08.1／3：載入階段、等待、取消與錯誤復原 | UI、speech／engine snapshot；MOD-01 | IN_PROGRESS | [載入子範圍 PASS](verification/desktop/audio-tuning-verification-latest.md)：三 layout、等待／存活／最後階段時間、歷史估計、TTS 次句重用、載入取消與參數失敗；未知 ETA 不造數。剩餘 ACK timeout／完整錯誤復原及 MOD-01 解耦不因本輪升級 |
| MOD-02／高 | F03、N03：拆出 request validation、queue policy、執行協調、evidence 組裝 | `services/tts/service.py`、`snapshot.py`、`validation.py`；協調／模型行為仍依 BASE-01 | IN_PROGRESS | [快照投影](verification/desktop/performance-baseline-latest.md#snapshot-projection-module)與[request 資料驗證](verification/desktop/manual-tts-verification-latest.md#request-validation-module)功能相容 PASS；[A/A 控制](verification/desktop/performance-baseline-latest.md#snapshot-jitter-controls)亦重現 p95 波動，效能 WAITING。下一步先界定 queue policy／evidence seam，維持 FIFO、取消、ACK、完成播放才寫稿及 cleanup failure；整體未完成 |
| MOD-03／高 | F06、N03：共用音效脫離 VC 專用層 | `services/engines/postfx.py`、`services/tts/postfx.py`；BASE-01 | PLANNED | 單一 DSP 實作、不依賴 VC／TTS orchestration；callers／tests／文件同步；相同 PCM／設定的 bypass、wet、取消與輸出相容 |
| MOD-04／中 | F02、N03：解除 VC bridge／runtime 共用預檢的雙向依賴 | `services/engines/runner_service.py`、`rvc_runtime.py`；純資料預檢可先隔離驗證，涉及 runtime／裝置行為仍依 BASE-01 | PLANNED | 依[架構邊界](specs/app-architecture.md#modular-boundaries)界定 helper owner；保留既有 validate payload／錯誤、模型 hash 與端點語意，runtime／bridge 單向依賴共用層；匯入不載模型或開裝置，預檢及相關 runner 回歸通過 |
| DATA-01／高 | F07.4／09、N03：資料版本、writer、migration 與復原 | `services/tts/storage.py`、contracts、UI／shell settings；BASE-01 | PLANNED | 依架構資料表界定 owner；migration 前可用備份、重跑冪等、失敗可復原；舊 session／requests／favorites／設定保留；未完成 queue 不自動重播 |
| PERF-01／高 | F02／03／08：縮短量測確認的冷載入／生成瓶頸 | adapters、WSL worker、streaming adapters；BASE-01、MOD-02 | PLANNED | 依 baseline 選一個最大成本改善；cold／warm 分報，品質／取消／GPU 回收不退步；沒有顯著改善則不宣稱成功 |
| PERF-02／高 | F07／08：降低重複更新與長 Session I/O 成本 | UI 訂閱、service snapshot、storage exports；排序子範圍依資料 baseline；跨層更新仍依 BASE-01、MOD-01／02、DATA-01 | IN_PROGRESS | [快照排序子範圍 PASS](verification/desktop/performance-baseline-latest.md#snapshot-order-comparison)：相同 payload、成對量測、TTS 回歸。事件／polling、全量 payload／export、有界更新／分頁仍未完成；漏事件恢復、durability、queue identity 均需維持 |
| FEAT-01／中 | F02.4／05：通用參數、Voice Library、Preset Save／Load | manifests／voices、UI forms、settings repository；MOD-01、DATA-01 | IN_PROGRESS | [四 VC 表單／獨立保存／RVC 移轉 PASS](verification/desktop/audio-tuning-verification-latest.md)，manifest 範圍與交叉限制生效。剩餘 Voice Library／完整 Preset round-trip、缺檔／版本復原仍未交付 |
| FEAT-02／中 | F07.2／3：Session history、搜尋、分頁與匯出 | storage query／export、Transcript UI；MOD-01、DATA-01 | PLANNED | 跨 session 篩選／分頁穩定；Clear View 不刪 DB；DB 可重建 TXT／JSONL，SRT 有時間檢查；長資料量案例與失敗恢復 |
| FEAT-03／中 | F04：Mic／Remote capture、VAD、STT、重建串接 | 新增模組限既有 `services/`、contracts、Rust／UI adapter；MOD-02、DATA-01 | PLANNED | physical Self 與 Remote source 分離；切 VC 不停 STT；backend_stt 不重跑辨識；CPU／GPU 共存及回授、取消、durability 驗收 |
| AUDIO-01／高 | F02／06：RVC duplex B1 與 index 警告定位 | RVC runtime、route、model register；無 | PLANNED | 分別重現路由近零與 index blend skip，不能混判；同輪 callback／獨立接收端證據及固定樣本品質比較；保留失敗報告 |
| AUDIO-02／高 | F03／06：新增 TTS FX 的完整原生發聲驗收 | Rust SpeechManager → generation → FX → playback；無，可在第三批前執行 | PLANNED | 兩個 TTS 引擎新 request 的原生 Speak、raw／processed hash、指定回錄、Transcript／cleanup 同輪證據；不能以舊 WAV replay 代替 |
| AUDIO-03／高 | F06.5：四 VC 共用輸入降噪與設定提示 | `services/engines/noise_reduction.py`、四 runtime、UI；無 | DONE | [DSP／模型 WAV／CABLE／UI 限定驗收 PASS](verification/desktop/audio-tuning-verification-latest.md)：bypass、連續性、尾端、延遲及固定底噪目標；實體 Mic 聽感、RVC duplex 與 LIVE 保持 WAITING |
| SOURCE-01／高 | F05.1／4：角色／reference 來源補齊 | models／dataset registers；需要可查證來源或使用者提供資料 | WAITING | 每個採用資產的 license／revision／dataset／hash 與人工採納記錄明確；未知維持 candidate，Agent 不代填 |
| LIVE-01／高 | F02／06／08：指定配置的 physical／Rack／接收端／600 秒／聽評 | audio-rack／benchmarks／終端；AUDIO-01（若採 RVC B1）、SOURCE-01（採用資產），需實體接點與使用者聽評 | WAITING | 本輪依[驗收取捨](#acceptance-scope-20261003)延後正式 LIVE 驗收，不阻擋離線 TTS／其他開發；個人使用可先人工短測。若要分類正式 LIVE，仍依 [LIVE gate](specs/live-gate.md) 逐配置驗，首包、持續穩定、路由、identity、human review 齊備才改分類 |
| SHIP-01／後續 | F09：安裝、更新、migration／復原與新機驗證 | app packaging／backend detection；DATA-01，發布清單需對應已驗收功能 | PLANNED | 固定發布功能清單與安裝前置；乾淨環境 install／upgrade／rollback 可重跑，不把 checkout exe 當 portable |
| FUT-01／後續 | F10：Agent Reply／Phrase Hotkeys | contracts／provider → 既有 speech queue；MOD-02，先確定權限及發聲觸發規格 | PLANNED | 來源、explicit enable、停止／取消、防回授、失敗不自動重送與測試案例先完備，再解除停用 |

## M0～M8 舊里程碑對照

這張表只連回同一批功能與任務，沒有另一套待辦或百分比。

| 舊里程碑 | 目前判讀 | 對照 |
|---|---|---|
| M0 需求／契約 | 已有；本輪補人與 Agent 共用索引 | DOC-01；契約不表示 runtime 全完成 |
| M1 Desktop shell | 預設原生操作已補驗；Tray 工具驗收略過，全部配置未窮舉 | F01、UI-01 |
| M2 engine lifecycle | 四 VC 已有實作與短測，完整鏈路未過 | F02、AUDIO-01、LIVE-01 |
| M3 參數／Preset | 四 VC manifest 表單／獨立保存已交付；完整 Preset 未交付 | F02／05、FEAT-01 |
| M4 STT／history | TTS persistence 已有，常駐 STT／history GUI 未交付 | F04／07、DATA-01、FEAT-02／03 |
| M5 Voice Library | catalogue 部分交付，管理介面未完成 | F05、FEAT-01、SOURCE-01 |
| M6 TTS | CosyVoice2／Breeze Manual 已接通，Mic 重建未完成；CosyVoice3 未安裝 | F03／04、FEAT-03；CosyVoice3 另行 intake |
| M7 Rack／routing | 內建 FX 與指定線路分項通過，外部 full-chain 未完成 | F06、AUDIO-01／02、LIVE-01 |
| M8 發行 | 本機開發版可建置；正式交付未完成 | F09、SHIP-01 |

## 歷史與獨立路線的證據入口

下列報告保留原日期與範圍，不用來覆蓋上方 Desktop 進度。細部命令、測量值與失敗輪次只留報告，不在本頁複製。

| 範圍 | 權威報告／限制 |
|---|---|
| VCClient packaged／矩陣 | [packaged repair](verification/backends/vcclient-packaged-repair-latest.md)、[latency matrix](verification/backends/vcclient-rvc-latency-matrix-latest.md)：原 packaged 阻礙未由 Desktop 修正 |
| Seed 官方 GUI／離線與 CLI backend | [Seed readiness](verification/backends/seed-vc-readiness-latest.md)、[Seed GUI](verification/backends/seed-vc-verification-latest.md)、[backend 安裝音訊](verification/backends/backend-install-test-latest.md) |
| RVC 模型／訓練 | [audit](verification/backends/rvc-model-audit-latest.md)、[訓練手冊](guides/model-training-guide.md)：ready 與音訊通過分開 |
| CosyVoice／Breeze 官方與 project-local UI | [CosyVoice](verification/backends/cosyvoice-verification-latest.md)、[Breeze](verification/backends/breeze-tts2-verification-latest.md)：各自 runtime／最佳化結果不直接套用 Desktop |
| 線路、音訊品質與 Rack | [wiring](verification/audio/wiring-verification-latest.md)、[客觀 WAV 比較](verification/audio/audio-quality-comparison-latest.md)、[Rack 契約](../audio-rack/README.md) |
| 候選／研究 | [來源審核](reference/source-audit.md)、[多後端架構](specs/voice-conversion-architecture.md)、[VoiceStudio 比較](reference/voicestudio-comparison.md)：未安裝候選不列為已交付 |

## 需要人提供或決定的條件

- UI-01：已按限定範圍結案；Tray 工具驗收略過，不再要求提供可操作目標。需要使用選單時可依手冊自行確認，實際發生問題才重開相應範圍。
- LIVE-01：正式驗收延後；需要使用外部路由時先人工短測指定接收端。日後要取得 LIVE 分類，再提供實際 Mic／耳機接點、接收端（例如 Discord 或 OBS）與聽評，並補齊量測證據。
- SOURCE-01：所採模型／聲音的可查證來源與使用範圍；現有未知項不影響文件及一般重構先行。
- BASE-01：先取得 baseline 再定個人可接受的 cold start／切換等待與音質取捨。完整 LIVE 的既有門檻不改寫。
- SHIP-01／FUT-01：發布目標與自動發聲權限在開始該任務時確定，不阻擋第一批工作。
