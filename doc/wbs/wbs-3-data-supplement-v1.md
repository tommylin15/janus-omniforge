# WBS-3-DATA-SUPPLEMENT-V1 — 補資料第一版

狀態：Completed（依使用者資料優先驗收）
模型：【Sol】
更新：2026-10-03

## 目前結論

本 WBS 已完成，五位分析師目前版本的資料前置條件已滿足，可接續 Provider 與每日運作鏈路驗收。不得再以 2026-10-02 舊 checkpoint 的資料缺口或原嚴格 minimum floor 阻擋後續工作，也不要求先消除所有 unknown／missing。

完成與真實 dev 驗收見 [結案證據](../archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)；日常維運見 [操作與檢核文件](../runbook-data-supplement.md)。

## 本版交付與驗收範圍

1. 五檔代表性標的（1102、2327、2330、4958、5876）具備 12 季財報、12 月營收及至少 121 日合格行情。
2. 官方資料經公司、期別、單位、報表範圍及單季／累計口徑核對，寫入 Stage／Iceberg Core，保留 hash、receipt availability、版本與不可變快照。
3. 固定 Core 快照可供 Mart feature v2 及 30 份 Fact Packs 重建與 readback；未知事件 severity 保留 null，不填零。
4. 每日增量僅處理缺期、新公告、更正及最近一期重查；獨立週六 deterministic 品質檢查不依賴 LLM。
5. Admin 顯示品質結果、需處理狀態及完整檢核文件；通知限 Admin，不另建 Email 或 Codex automation。
6. 適用測試、CI／deployment、真實 dev 資料與 authenticated Admin acceptance 已完成；詳細證據統一留在結案文件。

## 已接受限制與持續有效的治理

- 歷史首次公告與原始更正版次未全部證明，部分 EPS／ROE／同業基準／事件 severity／長窗口籌碼仍有 unknown 或 missing reason。這些是已接受的第一版限制，不是重新開啟本 WBS 或 Provider 的前置阻礙。
- 目前研究可用不等於歷史 PIT 可用；不得將 receipt time 當首次公告時間，或把未知版本倒填到取得前的 as-of。
- 個別 feature／role 的 missing-data honesty、validator、source authorization、publication gate、owner isolation 維持有效。資料前置完成不代表每份角色輸出必然完整或可發布。
- 本次資料／Fact Pack 驗收未呼叫模型；補資料後的五角色真實輸出、auth lifecycle、全 target 情境及自然每日 execution，仍由 Provider／daily-operation acceptance 證明。
- 每日與週六長期自然運作觀察寫入 Pilot evidence，不新增補資料工程 TODO。

## 範圍邊界與歷史入口

全市場所有歷史無缺口回補、S3～S6 新聞／供應鏈／券商／社群擴張、額外歷史 PIT 校準目前不做，見 [Parking Lot](../parking-lot.md)。新付費來源、權限擴張或 production 仍需明確授權。

原 S0～S2 詳細規劃、checkpoint minimum floor 與 Stop-and-Discuss 條件保留於 [已取代規劃](../archive/wbs-3-data-supplement-v1-plan-superseded-2026-10-03.md)；原始查核見 [歷史 S0 evidence](../data-supplement-s0-evidence.md)。兩者均不得作為新的開工或完成閘門。新的確定需求須由使用者明確加入 active TODO。
