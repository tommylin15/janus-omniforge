> **封存歷史文件｜不得作為現行 TODO／排程／部署指令。** 最新工作看 [TODO](../todo.md)、[管理入口](../project-management.md)。

# 文件盤點與改進結果

日期：2026-10-13。範圍：repository README 與 `doc/` Markdown 的文件入口、路徑、角色及優先序檢索；深入核對持股／報價／交易／UI／模型／WBS／AI 指示。歷史 archive 只保留追溯，不逐筆重新驗證 runtime；未讀取外部 Drive 版本。這是文件審查，不是全庫程式稽核或 live 驗收。

## 主要問題與本次處理

| 重要性 | 發現 | 處理與後續影響 |
|---|---|---|
| P0 | README、User App 仍寫暫停；TODO 已恢復 | 修正入口，歷史失敗／暫停記錄保留，不再作開工禁令 |
| P0 | AI 指示先 B9／CEO 再持股，與最新需求衝突 | 改成持股完整 → 通用圖表 → 模型有效後報告；解除產品與模型研究的循環依賴 |
| P0 | 全市場報價與研究 500 容易混淆 | 補官方名冊分母、TWSE／TPEx 分市場 coverage；全量 EOD 保存、盤中按需，不將全抓解讀為全市場分鐘抓取 |
| P0 | 「損益重算」未明確分開試算、成交及報表 | 新契約分操作與版本；成交已實現損益不等市場價格或長批次，正式報表維持 exact checkpoint |
| P0 | 快速只有 timeout／單次讀取紀錄，缺端到端目標 | 補暖／冷首屏、試算、成交更新目標及 P50／P95／失敗率／quote age；目標不是已達成成績 |
| P1 | 個股健康分數／分析文字排在通用圖表前 | 初期改為事實圖表與中性說明，五分析師有效才啟用整合報告；研究狀態收合 |
| P1 | 圖表種類多，初版閱讀密度與預設不明 | 定義折線、K 線切換、長條、事件時間軸；一次一圖、不堆指標、明確單位／缺口與可及性 |
| P1 | reference README 的 A／B 相對連結少一層 | 修正為 `../../`，保留原 PNG bytes；圖片解讀與現行順序分開 |
| P1 | UI 索引把所有持股數字都寫成只能等 Private Mart | 區分 backend operational 估值／試算和 Private Mart 正式報表，保持 canonical 與 owner 邊界 |
| P2 | operations ledger 逾 2,000 行，UI 工程單混有舊盤點及後續實作 | 標示歷史 checkpoint，指向 status；後續按 PROJECT_RULES 移舊證據到 archive，不在本次大量搬移以免失去證據連結 |

## 文件責任與接手入口

- [持股優先契約](../spec/holdings-first.md)：功能、資料、交易損益、速度目標及模型報告 gate。
- [四頁 UI](../ui/visual-first-four-pages.md)：頁面順序、簡圖選型、外部官方參考與閱讀規範。
- [AI 作業指示](../codex-execution-plan.md)：可直接貼用的後續開發 prompt、程式入口、順序與驗收方式。
- [TODO](../todo.md)：唯一 active queue；[status](../status.md)：實際進度。舊 WBS ID 保留，不另建平行待辦系統。

## 驗證與限制

已實際檢視四張 reference PNG，查閱 TradingView 與 Fidelity 官方圖表／持股頁說明，核對既有 backend `MOVING_AVERAGE` 成本計算。外部來源連結及採用範圍見 UI §3.1；不依外部券商的稅法或成本法改寫 Janus。

本次只更新文件，檢查 Markdown 相對路徑、執行順序、責任與 diff。先前未提交的程式、migration 054、Private Mart 鎖與 Flutter 改動仍待測試／review／同源部署及實際驗收。未因這次文件整理修復或重新認定 queue E2E、P95、財報可比期間、模型品質，也未重跑雲端工作。

文件檢查結果：納入 repository README 與 doc 共 171 份 Markdown 的結構／路徑盤點，72 份非 archive 文件的 Markdown 本地連結全部可解析；`git diff --check` 通過。此計數不代表逐份全文內容或歷史 runtime 已重新驗證。
