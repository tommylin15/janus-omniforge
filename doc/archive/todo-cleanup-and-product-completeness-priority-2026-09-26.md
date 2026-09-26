# TODO cleanup 與 Product Completeness reprioritization — 2026-09-26

狀態：歷史決策／清理紀錄；不是 active execution queue。

## 背景

Dev Pilot Entry 已通過並開始六個月 operational evidence window，但實際使用回饋指出 User market home、portfolio valuation／股票名稱、Admin operability 與全市場基礎 coverage 仍有明顯產品完整度缺口。進入 observation window 不應被解讀為「功能已完成」或「六個月內不再補既有產品缺口」。

## 本次治理修正

1. `WBS-8-DEV-PILOT-RUN` 保持長期 evidence lane，狀態仍為 partial；它不再獨占 foreground implementation queue。
2. 新增 Product Completeness foreground，先處理 portfolio completeness、deterministic market home、full-market base coverage 與 Admin main path，再處理進階 Mart／AI capability。
3. 舊 `High-Completion Dev Pilot Target` 是 Entry 前的 Day-1 planning marker；Entry 已通過後不再在 active TODO 重複標示。其歷史意義保留於既有 archive／operations evidence。
4. Pilot Feature Freeze 重新界定為 discretionary net-new feature freeze；correctness、security、data-integrity、market coverage、portfolio valuation、User baseline usability、Admin operability、cost regression 與 Pilot blocker fix 不在 freeze 內。

## 從 active TODO 移出的已完成項目

### `WBS-6-TRANSACTION-UX-2`

既有 Flutter/API targeted tests、canonical dev authenticated read-only acceptance、transaction／portfolio presentation、missing／stale／partial state semantics 等 evidence 保持有效；詳細 evidence 仍以 `spec/operations-and-testing.md` 與已完成 archive 為準。

**完成邊界修正：**這項 completion 只代表該次 presentation／read-path／state acceptance，不代表全市場行情 coverage、canonical 股票名稱 join、aggregate portfolio market value／unrealized PnL／return 或整體 User App 已達產品完整。

### `WBS-8-CHATGPT-MCP-ACCEPTANCE`

OAuth／tool discovery／bounded reads／owner isolation 等既有 acceptance 保持完成；active TODO 不再重複保存已完成 checklist。詳細 evidence 仍在 `spec/operations-and-testing.md` 與既有 archive。

## 文件衛生原則

- `status.md` 只保留現在判定、兩條主線與下一步，不複製完整 runtime ledger。
- `todo.md` 只保留未完成 acceptance；完成內容移入 archive／operations。
- `pilot-operational-evidence.md` 保存 observation window 新增 checkpoint。
- `spec/operations-and-testing.md` 保存完整 implementation／test／deployment／runtime evidence ledger。
- UI shell 已存在不等於資料 completeness；任何完成宣稱仍需 implementation、tests、deployment、live data 與 integration evidence 綜合判定。
