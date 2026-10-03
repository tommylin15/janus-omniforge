# 五分析師引擎目前契約

每日 Mart 使用 `specialist_runtime`，不使用生成式 LLM。舊五角色引擎、prompt、compatibility 與 provider daily entry 已刪除；歷史資料僅保留作稽核。後續 On-demand CEO 不在本次驗收範圍。

## 覆蓋與資料

Market Coverage 由 `control.specialist_market_symbols(date)` 取得具 PIT 日期的 liquid-500 membership，最多 500 檔。篩選回報最新價/量/金額、5/20/60/120 日報酬、規則分數、排序與異常旗標，不自動加入自選股。

使用者 2026-10-03 指示：500 檔缺失比例 ≤10%（含恰好 50/500）可接受；超過時標記 `discussion_required`，不中止或直接判整批失敗。每檔最新交易日、價格、成交量及成交金額必須合格且對齊，否則算該檔 EOD 缺失；各歷史窗口另外列缺失比例，模型未訓練不算行情缺失。缺失仍保留 null，PIT/來源不合格資料先排除後計入缺失。

補資料共用既有交易所全市場日期批次，不建立新 fallback 或調度系統。正式 liquid-500 目前為 TWSE-listed-only，依實際 membership 選市場，不自行擴成上市櫃混合池。先使用已有資料與短批次，品質過差先討論，不為了填滿每欄展開複雜歷史補資料。

Deep Coverage 使用既有去識別化資料庫函式取得 active watchlist ∪ effective holdings，去重、離榜持股保留、清倉且不在 watchlist 才退出。成果物不包含 owner、持股數量、成本或損益。

所有輸入以 Core immutable manifest / table snapshot、availability / publication / observation 時點、provenance 與 source authorization 驗證；未合格資料不進特徵。缺資料及未驗證模型明示 partial / blocked，不填假機率。

## 成果物

新 `specialist.v1.json` 定義 Fundamental / Valuation / Quant / Risk / Event。財務可比值、PE/PB/殖利率、動能、波動/CVaR/回撤/對齊 beta、事件數與嚴重度採確定性計算；中文報告使用規則模板。DCF/reverse-DCF 有嚴格計算函式，但真實 Core 未提供完整每股自由現金流與核准假設時回報缺值。

`specialists/<output_hash>.json` 與 execution manifest 不可變、寫入後讀回驗證；相同 execution replay 只驗證並 reuse。不同 execution 可 reuse 同內容成果物，目前仍先計算規則指標；完整 dirty dependency graph 與月度 reconciliation 尚未完成。

## 歷史模型

Linear / LightGBM / CatBoost 使用逐月擴張訓練窗，訓練標籤必須已於測試日前成熟；5/20/60/120 交易日 cohort 不重疊，對齊 benchmark。至少 100 訓練樣本與三個訓練月份才能 fit。Rank IC/ICIR、decile spread、hit rate、after-cost Sharpe / drawdown / turnover 可計算；30 bps 僅研究敏感度，不是實際券商成本。當前 membership cohort 不是歷史母體重建，禁止自動 promotion。

Riskfolio-Lib 計算歷史 CVaR；statsmodels 二狀態 Markov variance challenger 需至少 252 筆 benchmark returns，僅 research fit，未通過 OOS 不輸出正式 regime probability。

尚未完成：Fundamental/Valuation 訓練標籤、Qlib DoubleEnsemble、台灣繁中 Event 人工標記資料與本機 encoder、SHAP 模型解釋、IC decay、機率校準、regime stability、歷史 membership replay 與 champion promotion。這些缺口使 WBS 保持 partial。

## 依賴與資源

LightGBM 4.6.0 MIT、CatBoost 1.2.8 Apache-2.0、Riskfolio-Lib 7.0.1 BSD-3、statsmodels 0.14.5 BSD、NumPy 2.2.6 BSD、scikit-learn 1.7.2 BSD-3。pandas 固定 2.3.3，避免 pandas 3 與 statsmodels 0.14.5 相容性錯誤。全部 Python runtime 依賴 pin version 並 hash lock，模型 fit 固定 seed / single thread，沒有下載遠端模型或執行 upstream 範例。

Cloud Run Job 固定 1 CPU / 1 GiB、單 task、單 parallelism。真實 acceptance 記錄 elapsed_seconds 與 peak_rss_mib；未確認需求前不提高資源。免費 pip-audit 2.10.1 掃描 83 個鎖定依賴，修正 urllib3 三項已知漏洞後固定 2.8.0，重掃沒有已知漏洞。此結果不保證未知漏洞或 container OS 安全；禁止付費 Artifact Analysis。

## 本次核准的簡單補資料

使用者選擇僅補最近 21 個交易日（2026-09-02 至 2026-10-02，扣除週末及官方 09-25/09-28 休市），共用既有 TWSE 全市場日期批次與既有 dev ingestion Job；不新增來源、排程或資源。市場行情中不合格列退出 OHLCV，仍記錄缺失/隔離，不使其他合格列一起失敗。Core manifest 以現有 data mutation lock 擷取所有 public Core table fence，價格更新不丟掉未改變的財報/事件 snapshot；backfill analysis_as_of 採本次接收日期，不假裝當年已接收到資料。Mart PIT 日界線統一採台北時間 EOD。
