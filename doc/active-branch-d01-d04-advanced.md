# D01/D02/D03/D04 進階驗收整合支線

建立：2026-10-17。本文件追蹤四項進階待辦的整合開發與驗收進度，方便新 chat 接續作業。

> **本文件是執行追蹤，不是第二份 TODO。** 唯一狀態以 [TODO](todo.md) 為準；完成後將證據移入 [operations](spec/operations-and-testing.md) 並更新 [status](status.md)。

## 整合範圍

| 工作包 | 待辦項目 | 相依性 | 驗收方式 |
|---|---|---|---|
| D01 | 股利/REVERSAL/更正/競態等進階場景 | 獨立 | 單元測試 + 整合測試 |
| D02 | authenticated 手機 P95 效能量測 | D01 資料契約 | 30 樣本量測 |
| D03 | 390×844/desktop authenticated 截圖 | D01/D02 | 真實截圖對照 |
| D04 | 新 executor timer active 後停原 timer | 獨立（需 VM access） | live readback |

## 執行原則

依 [PROJECT_RULES](PROJECT_RULES.md) §4：
- 合併同來源、共用整合路徑或可一起驗收的工作
- 不在內部 checkpoint 反覆停等
- 外部安全／授權 blocker 保持 BLOCKED 並記錄

依 [codex-execution-plan](codex-execution-plan.md)：
- D01～D05 既有授權及成功證據保留，不重做
- 共用 authenticated 路徑一起驗收

## 前置條件檢查

### 已完成的基礎（不重做）
- [x] D01 基本功能 USER_CONFIRMED_PASS（持股頁、現金交易連動、重算按鈕）
- [x] D02 PASS_READ_PATH（DB-first snapshot→API）
- [x] D03 PASS_READ_PATH_ONLY（16/18 圖表 available）
- [x] D04 PASS（隔離 DB restore、owner boundary）
- [x] D05 PASS（API 100% promotion #38996111382）

### 需確認的阻塞項
- [x] D04 VM IAP 權限狀態 → **已解除**（使用者已補單 VM OS Admin Login、postgres-vm actAs 及 SSH22 IAP）
- [x] authenticated 測試路徑可用性 → 需 GCP dev 環境執行

---

## 執行進度

### Phase 1：前置讀回與阻塞確認
狀態：**COMPLETED**

- [x] 讀回目前 VM IAP 權限狀態 → **已解除阻塞**
  - D04 安裝 #38991083134 SUCCESS
  - D04 交接 #38991644822 SUCCESS
  - D04 readback #38992105257 SUCCESS
- [x] 確認 authenticated 測試路徑 → 需要真實 dev 環境執行
- [x] 確認最新 main SHA：`4167a5fc`
- [x] 正式 API：`d739107` / revision `janus-api-00524-tot`

### Phase 2：D01 進階場景測試
狀態：**COMPLETED**

待辦：
- [x] 股利處理測試（4 tests PASS）
- [x] REVERSAL 測試（4 tests PASS）
- [x] 更正交易測試（4 tests PASS）
- [x] 競態/冪等測試（4 tests PASS）
- [x] 不同 Owner 隔離測試（4 tests PASS）
- [x] 邊界案例測試（5 tests PASS）

工程入口：
- `services/api/trade_calculation.py`
- `services/api/trade_fees.py`
- `services/api/private_recalc_queue.py`
- `tests/test_d01_advanced_scenarios.py`（新增 25 tests）

### Phase 3：D02 效能量測
狀態：**NOT_STARTED**

待辦：
- [ ] authenticated 手機冷啟動 P95
- [ ] authenticated 手機暖首屏 P95
- [ ] 30 樣本量測（每場景）
- [ ] 記錄 P50/P95/timeout/失敗率

目標：
- 暖首屏 P95 ≤ 2 秒
- 冷主資訊 P95 ≤ 5 秒
- 暖試算 ≤ 500ms

### Phase 4：D03 截圖驗收
狀態：**NOT_STARTED**

待辦：
- [ ] 390×844 手機 authenticated 四頁截圖
- [ ] desktop authenticated 四頁截圖
- [ ] 對照 `doc/ui/reference/user-app-final/` PNG
- [ ] 驗證 loading/empty/gap/stale/partial 狀態

### Phase 5：D04 停舊 timer
狀態：**NOT_STARTED**

前置條件：
- [ ] 確認 VM IAP 權限已解除阻塞
- [ ] 新 executor timer 已 active
- [ ] 新備份路徑已驗證

待辦：
- [ ] 停止原 VM timer
- [ ] 讀回確認只有一個有效備份執行入口
- [ ] 確認三代輪替正常

### Phase 6：合併發布（如有程式變更）
狀態：**NOT_STARTED**

- [ ] 合併測試 PASS
- [ ] 更新 operations-and-testing.md
- [ ] 更新 status.md
- [ ] 更新 todo.md

---

## 證據記錄

### D01 進階場景
| 測試項目 | CI Run ID | 結果 | 備註 |
|---|---|---|---|
| 股利處理 | local | **PASS** | 4 tests: cash_div, stock_div, requires_position, zero_shares |
| REVERSAL | local | **PASS** | 4 tests: void_buy, void_sell, remove_pnl, void_dividend |
| 更正交易 | local | **PASS** | 4 tests: update_price, validate_sells, preserve_order, chain |
| 競態/冪等 | local | **PASS** | 4 tests: exclude_reversed, include_replacement, cycle, ordering |
| Owner 隔離 | local | **PASS** | 4 tests: separate_positions, reversal_isolation, mixed_events, risk_marts |
| 邊界案例 | local | **PASS** | 5 tests: fractional, zero_price, backdated, missing_price, stale_price |

### D02 效能量測
| 場景 | 樣本數 | P50 | P95 | 最大 | 失敗率 |
|---|---|---|---|---|---|
| 手機冷啟動 | — | — | — | — | — |
| 手機暖首屏 | — | — | — | — | — |
| 暖試算 | — | — | — | — | — |

### D03 截圖
| 頁面 | 手機 390×844 | Desktop | 狀態 |
|---|---|---|---|
| 今日 | — | — | — |
| 關注 | — | — | — |
| 記帳 | — | — | — |
| 個股 | — | — | — |

### D04 備份交接
| 項目 | 證據 | 結果 |
|---|---|---|
| VM IAP 權限 | — | — |
| 新 executor active | — | — |
| 原 timer 停止 | — | — |
| 唯一執行入口確認 | — | — |

---

## 阻塞與風險

| 項目 | 狀態 | 說明 | 解決方案 |
|---|---|---|---|
| D04 VM IAP | **已解除** | 使用者已補單必要 IAM | D04 交接 #38991644822 SUCCESS |

---

## 下一步

1. **Phase 2 已完成**：D01 進階場景測試 25 tests 全部 PASS
2. **Phase 3-5 需要真實 GCP dev 環境**：
   - D02 authenticated 手機效能量測需要真實裝置或模擬器
   - D03 截圖驗收需要真實 authenticated session
   - D04 停舊 timer 需要 VM SSH access
3. **建議**：將新增的測試 commit 並推送到 main，觸發 CI 驗證

---

## 交接資訊

| 項目 | 值 |
|---|---|
| 建立時間 | 2026-10-17 |
| 最後更新 | 2026-10-17 11:30 UTC |
| 輸入 SHA | `4167a5fc` |
| 正式 API | `d739107aa26ae4641d6f3e1b9c80f2e9aa1a57b6` |
| API Revision | `janus-api-00524-tot` |

**接續作業時**：先讀本文件確認進度，再讀 [TODO](todo.md) 確認授權，最後依各 Phase 狀態繼續執行。
