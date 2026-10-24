> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Janus Valuation P0＋P1 靜態讀回與 Mapping 收據

執行日期：2026-10-24（Asia/Taipei）。研究限定；`publication_allowed=false`。

- 所用 CURRENT：`release-0bbae8d9c1ca7d8d`，CURRENT SHA256 `0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd`。
- 引用 manifest SHA256 `7b80d441efabbc307d359ea5d15cd9202ccee5e2930cf4c3cc337496c95eb542`，全部財報 15 季本輪逐檔 SHA256、列數與可解碼內容驗證 PASS。
- Financials rows 1,181,442，股票代號 1,977（非完整歷史母體）、raw labels 318 unique（321 dataset×label），income 493,867、balance 489,410、cashflow 198,165。
- 來源 mops 1,168,822、finmind 12,620；所有財務 rows 已知 `published_at` 為空，歷史 PIT `NOT_VERIFIED`，而單位及期間皆不可靠。
- exact-label mapped candidate rows 456,599；所有已存在財務記錄維持 `MAPPING_REQUIRED`（不將映射當成安全可衍生），`FETCH_REQUIRED` 為真正無已知 raw exact-label 匹配的候選，但補收仍需正式規劃及排除未映射名稱。
- `營業毛利（毛損）`、`營業毛利（毛損）淨額` 在原始檔中部分數值不同，v2 明確分為 `gross_profit_before_adjustment` 與 `gross_profit`，不可同時計同一因子。
- 本輪沒有 HTTP fetch、模型訓練、發布、部署、canonical 或 Registry 修改。無新來源帳密或收費。

本地分析並非 Colab runtime 驗收；15 個財務檔外的 140 個引用檔未在此一一重新驗 SHA、schema 和 row count。研究完整稽核文件留在 Drive `janusChatGPT` 的研究目錄，不將 raw 值、大型 CSV 或暫時輸出寫 GitHub。
