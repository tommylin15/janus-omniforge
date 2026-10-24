# 04 Valuation｜RV-01 現役資料接線盤點（2026-10-24）

狀態：**STATIC_READER_MAPPING_PASS／LIVE_COVERAGE_NOT_VERIFIED**。此頁是 RV-01 的精簡工程接線清冊，不是第三方來源稽核、全歷史 PIT 驗證或正式區間發布收據。以 [04 子契約](../spec/valuation-range.md) 為準，正式角色仍只有 Quant／Risk／Fundamental／Valuation。

## 現有可重用 reader 與直接缺口

| 資料／用途 | 目前 `main` 實際入口 | 能做的事 | RV-03 前缺口 |
|---|---|---|---|
| 歷史 PE／PB | `jobs/ingestion-core/ingestion_core/valuation_history.py` → Core `valuation` → `control.stock_valuation_five_year`；`infra/postgres/migrations/063_stock_valuation_five_year.sql` → `publication.stock_valuation_five_year`；`services/api/public_runtime.py:read_valuation_profile` | 既有指定股票 **2 年每日觀測分布**和 profile。 `packages/web_api/core.py:visual_series` 也可透過近期 `publication.stock_serving_recent` 顯示 PE/PB 序列 | **不是 RV 區間的 60 月有效月末樣本**；不得拿 2 年每日點直接當 24 個月末，也不可把研究 Parquet 當正式 serving |
| 財報／單季 EPS | `financial_publication.py` 的 MOPS XBRL 研究標準化；`yahoo_eps.py` 的已核准 2025Q4 六股單季 EPS；`serving_projection.py` → `publication.market_serving_recent`；`packages/web_api/core.py:_comparable_single_quarter_eps` | 原有前台 EPS 日期點：有 explicit single-quarter EPS，另 Q1 YTD 可視為當季；不以 Q2～Q4 YTD EPS 相減 | **尚無可對全體普通股直接交付「同一每股基準、同一報表範圍、連續四季」的 TTM reader**。需用現有 row 逐股聚合，不以零填缺、不同分母硬加 |
| BVPS | `financial_publication.py` 已辨識 `equity_parent` / `total_equity` 等金額資料；現有 `market_serving_recent` 可以保存金融財報類 row | 能重用資產負債表原始事實 | **未找到已核准且可直接供 RV 使用的正數 TWD/share BVPS reader**。不能把權益總額除以猜測的股數；金融股要缺值或 blocked_basis |
| 股票種類／產業 | `control.stock_master` 用於已啟用股票可見性；現有股票與研究資料可供候選 | 可區分現有上市／上櫃 symbol 群 | 實際 `security_type`、是否金融業、每股基準／除權的發布口徑，接線前需讀真實 schema/row；ETF 返回 `not_applicable` |
| 來源／時點／權限 | Serving row 保存 `source_id`、`provenance_id`、`availability_at` 等已有欄位；2025Q4 Yahoo EPS 經 migration 065 的有界來源契約 | 保留已知時間／來源、排除已知未來欄位；現有合格值可重用 | 缺失的歷史 first-observed 不自行造值，不要求重新補證全歷史 PIT；權利不明的資料不得直接宣稱已授權發布 |

## RV-01 → RV-02/03 最小接線契約

1. **RV-02 已實作純函式**：`packages/valuation_range.py:calculate_reference_range`；只接受 caller 給定的 approved、可比較財務季度與逐月月末正 PE/PB。正 TTM EPS 連續四季 × PE 分位；金融正 BVPS × PB 分位。60 月窗口、有效 24 月以上才有價格帶；ETF、資料不足、不可比、權限不明均明確不輸出價格；只做 Decimal 量值，不做前台顯示取整。
2. **RV-03 才接真實資料**：以現有 Core/serving reader 查 `symbol`、市場、種類、最近四季單季 EPS 或金融股 BVPS、可用月份的 PE/PB，補齊最小 adapter。不得新增第五模型、獨立 canon 價帶、第二套 publication authority、付費服務或將研究 overlay 直接發布。
3. **RV-01 完成邊界**：本次讀到真實的程式、migration、API reader 位置；未透過 PostgreSQL 按 symbol 查日／季樣本，尚不能宣稱來源覆蓋率、適用股票數、24 月有效值及 BVPS 均已 PASS。完成 RV-03 前不可啟用公開 API/唯一卡。

## 後續最短執行序

- 用最小真實樣本驗 `publication.stock_serving_recent`、`publication.market_serving_recent`、`publication.stock_valuation_five_year` 的日期/來源/單位/股票類型；只有實際缺少的欄位才補資料讀端。
- 補 adapter 與 targeted tests，必要時再加 versioned migration；檢查同 04 研究 reader 相容，然後 RV-04 API、RV-05 單一 UI 價帶及 RV-06 dev 驗收。
- 本輪無 DB/GCS 寫入、模型訓練、Registry、ACTIVE、API 部署或第三方 API 收費。研究 `≥30` 月樣本目標與本產品 `≥24` 月門檻是兩個不同條件，不互相更改。
