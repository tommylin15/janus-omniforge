# 四頁 UI｜資料、分析與呈現責任對照
更新：2026-10-21。已結案 D02/D03/DRL 不重開；本檔只保留有效交接，不維護短期狀態。
舊VF工作單/部署流水帳已[封存](../archive/visual-first-delivery-before-plan-a-2026-10-21.md)。
| 責任 | 現役契約/工程入口 |
|---|---|
| 正式行情/財報/估值/法人/事件的數字與時點 | 既有Core→serving；[資料治理](../spec/data-governance.md)，有具體新缺陷才修 |
| 圖表/金額/單位/缺值/尺寸 | [唯一四頁UI](visual-first-four-pages.md)、[User UI](user-app.md) |
| 數字轉事實/變化/盤前盤後/下一觀察 | [A-CHANGE SPEC](../spec/change-analysis.md)與[AI卡](../archive/document-cleanup-2026-10-25/execution-cards/a-change-analysis.md) |
| 研究X/Y、窗口、前處理 | [因子時間契約](../spec/model-feature-time-contract.md) |
| 五模型/OOS/正式推論 | [D07 SPEC](../spec/specialist-engines.md)及[AI卡](../archive/document-cleanup-2026-10-25/execution-cards/d07-specialist-b9-oos.md) |
| 手動CEO/Owner報告 | [D08卡](../archive/document-cleanup-2026-10-25/execution-cards/d08-ceo-admin-owner-report.md) |
基本事實不等模型；每句/圖/Fact Pack同源。只缺某公式就停該公式，不清空可用數值；缺值不補0、不假造歷史或因果。UI以真實dev資料與必要手機/桌面驗收，來源數值PASS不冒稱畫面PASS。
狀態與授權只看[TODO](../todo.md)；不保留第二張VF待辦。
