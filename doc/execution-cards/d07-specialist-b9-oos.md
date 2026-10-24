# D07｜因子、四模型與現役舊 event 事實相容 — 唯一 AI 卡
更新：2026-10-21。狀態/授權只看[TODO](../todo.md)，本輪文件更新不啟動訓練或部署。

## 可複製指令
> 執行D07。先讀AGENTS.md、doc/PROJECT_RULES.md、doc/todo.md、本卡、doc/spec/specialist-engines.md、doc/spec/model-feature-time-contract.md及研究採集SPEC。核對main與現有Risk Ridge實作，先建共享清洗/as-of/交易日/公司行動/滾動X/成熟Y，再Risk→Quant；Fundamental/Valuation依資料期數，Event 僅保留事實／A-CHANGE rules，不再訓練第五模型；04 Valuation 共用 PE/PB 研究及估值區間情境的資料與發布治理。人工Colab訓練與時間外評估，Janus只做受控匯入/推論/rollback。不要每日重抓歷史或每日重訓，不恢復GAS/BQ/Cloud Run訓練路線。逐角色獨立baseline/challenger與promotion，未驗證模型不輸出機率，不阻擋方案A有效事實。完成本包tests/CI、必要dev整合與真實推論/Admin readback後結案。

## 最小來源
[四模型角色/X/Y](../spec/specialist-engines.md)、[窗口與前處理](../spec/model-feature-time-contract.md)、[採集](../spec/research-collection-gas-drive-colab.md)、[WBS](../wbs/wbs-5-specialist-engines.md)、[Colab README](../../research/colab/README.md)。
程式入口research/colab/risk_pilot.py、run_risk_folder_pilot.py、monthly_folder_io.py、collect_tw_equities.py；正式specialists.py/specialist_runtime.py、packages/analysis_product.py及相關tests。開工核對目前路由，不照舊snapshot猜功能。

## 執行順序
1. D07-PRE讀回真實研究檔、hash/日期/欄位/母體/來源權利，列已可用與缺資料，不能以fixture或目前名冊冒充歷史全市場。
2. 共用feature builder：明示交易日lookback/min_points、raw單位、as-of版本與可得時間、缺值/停牌/company action；train/serving相同sample算得同X。
3. label builder與mature_at獨立；同交易日所有股票同fold，purge交疊label，preprocessing只fit train，validation選型/校準，最後test不參與調參。
4. 重用Ridge試點作baseline對照；每角色只比較必要低複雜度候選。記錄實際訓練期間/獨立日季數/版本/seed/hash與同市場OOS；輸出品質不足保留規則，不硬湊模型數量。
5. Janus registry核model/feature/label/schema/授權/hash，重放代表樣本，比對研究與正式X；不安全反序列化未知artifact。固定受控模型版本、前處理與rollback。
6. 真實dev日常推論保存analysis_as_of/cutoff/horizon/有效期與證據；Admin展示各角色quality，User只展示有效語意。D08另包；A-CHANGE不等D07。

## 驗收與範圍
至少驗跨月/休市/缺一日/停牌、20日窗口與121價warmup、盤後公告、負/零同比、修訂/公司行動、label未成熟/跨fold、相同日期分組、train-serving一致、模型回退與Owner隔離。
研究70%與正式Core90%/70%及模型品質分開；訓練/OOS/匯入/推論狀態分開。Colab需人工掛載或啟動時提供具體操作，不偽稱無人值守完成。
舊GCP/BQ退役保持CLOSED，不再每輪盤點；正式Core/Owner/ETF/Stage48h/週Iceberg保留。不新增付費API/GCP或擴權、不大量刪真資料。

## 回報
完整SHA、實際欄位/月份/cohort、X/Y/label maturity、各角色baseline/OOS、artifact hash、CI與dev inference/Admin讀回、回退及具體缺口；唯一狀態回TODO，證據入Operations。


## 完整模型週期交付
執行D07時一併讀[生命週期SPEC](../spec/model-lifecycle.md)及[Colab→GCS→批次→月評估AI卡](d07-model-lifecycle.md)。以既有同一工作包完成notebook/資料清洗貼標、各角色訓練、candidate/registry/shadow、日週批次與成熟結果回收，不另立五套queue。資料量不足照SPEC列實收/建議差距；允許rules交付，不冒稱ML發布。

