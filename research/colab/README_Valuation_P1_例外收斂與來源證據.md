# Janus／OmniForge｜P1 例外收斂與來源證據鏈（2026-10-24）

只做 Valuation 研究資料，`publication_allowed=false`。GitHub 初始 `main`：`ab5d07e301f522e77380511f1fc95a481f497708`；凍結 `CURRENT` 為 `release-0bbae8d9c1ca7d8d`，未異動。

## 實際逐筆核對

- P0 原始 1,181,442 rows 的 inventory gzip SHA256 `f85fd1c16c286628e02d067088b0f9f473932596d83a098561537cc172bc376c`，P1 舊跨來源 504 組比較，例外 113 組（4 數值差異，109 歧義）。
- `exception_evidence.csv`：113 組各自 source labels、數值、來源紀錄 identity hash、PIT／scope／原始檔證據空缺；外部佐證網址只作現值參考。
- `source_record_links.csv`：1,113 筆比較涉及的原始 inventory row，列出可重算 SHA identity 與缺少的原始 response bytes、revision、scope、published_at。
- `source_version_deltas.csv`：1103、1201 的 2022Q4：嘉泥資產與負債皆多 38,259 仟元；味全兩者皆多 51,181 仟元；權益不變。可能是版本或表達方式差異，原因尚未確定。
- 歧義拆解：60 筆 FinMind `IncomeAfterTaxes` 與 `TotalConsolidatedProfitForThePeriod` 不可直接視為一個淨利欄；45 筆 FinMind CFO 兩別名數值相同，屬候選 alias 重複；11 組欠上一季度 MOPS（與前述群組重疊），不可 YTD 差分。以來源 row 原始 `origin_name` 及合併別後續確認語意。
- FinMind 只要 source row 的 API `date` 是季末，不能把它當公告日。歷史 PIT 需要真正已保存的原始揭露及公告時間證據。

## 可安全運算 gate

`valuation_p1_source_lineage.proof_gate` 預設封鎖：必須同時有真實 payload 原始 bytes 與 SHA256、原始 FinMind type/stock_id/date/value 的唯一匹配、明確 accounting scope、金額單位、會計期間、財報版本；才能開放**算術用研究候選**。歷史 as-of 還須原始揭露 bytes/hash 與公告時間，且不得晚於 as-of；研究算術可用不代表訓練可用，更不代表發布。MOPS HTML 來源 adapter 尚無實際 row-attached 原文，因此不接受假單位或外部鏡像代替；此輪無任何現有 row 通過 gate。

## 官方／供應商說明（只作制度背景，不能代替現有 row 證據）

- 公開資訊觀測站三大財報口徑：<https://mopsfin.twse.com.tw/terms>。綜合損益與現金流顯示累計；資產負債為時點值。
- FinMind API 欄位與 EPS 風險：<https://finmind.github.io/tutor/TaiwanMarket/Fundamental/>。
- 1103 2022Q4 外部歷史表：<https://tw.stock.yahoo.com/quote/1103.TW/balance-sheet>。
- 1201 2022 年度公告第三方鏡像：<https://tw.stock.yahoo.com/news/公告-味全董事會通過111年度合併財務報告-094348507.html>。

## 執行與驗證

從 GitHub `main/research/colab/15_Valuation_P1_來源證據與安全輸入.ipynb` 以 Colab 開啟。Notebook 優先使用 Drive `CoLab程式/valuation_p1_source_lineage.py` 的正確 SHA 檔；若尚未獨立同步，則讀取已同步 Drive `模型研究/Valuation_P1_來源證據與安全輸入_20261024.zip` 的同版模組，SHA 驗過才執行，無需手動複製。輸入只用 `janusChatGPT/模型研究` 的 P0、P1 凍結 ZIP，SHA 鎖定；不需要 API token。`python -m pytest -q tests/test_valuation_p1_source_lineage.py` 本地 17/17 PASS；Drive Colab live 尚待實際執行回報，不稱已完成。

## 未解除障礙

仍缺現行 canonical 財報每筆原始 request ID／byte hash、MOPS header/合併別、FinMind 原始 origin_name 的可靠 row linkage、會計重編版本、歷史首次公告時間。`raw_payloads_exactly_linked=0`、`arithmetic_ready_rows=0`、`historical_asof_ready_rows=0`；符合設計的 fail closed，不是補造資料。
