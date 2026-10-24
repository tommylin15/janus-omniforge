> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../spec/research-simplification.md) 按需評估；不把取消視為 PASS。

> **ARCHIVED／SUPERSEDED（2026-10-24 當日較新決策）：**本頁「新補收限近兩年」的執行指示已撤銷。最新權威為 [04 Valuation ≥30 有效月末盤點](valuation-min30-ordinary-preflight-2026-10-24.md)：PE/PB 分開，先重用已有36月、不足時核查向前追溯，普通股與 PIT/IPO 正式核驗後才決定 FinMind；此頁1,977股與98組僅供歷史清冊參考。原 ZIP 在 Drive 已改名 `ARCHIVED_已取代_...`，不再用舊Notebook執行。

# Janus 04 Valuation｜2026-10-24 兩年普通股定向補收前盤點

狀態：**PARTIAL / INVENTORY ONLY**。本次 FinMind 財報 API 請求數 = **0**；publication_allowed=false。最終合格普通股數、PE/PB可訓練數仍 **NOT_VERIFIED**。

## 使用者最終範圍
只對 04 Valuation 研究所需、TWSE/TPEx 一般普通股、近兩年 2024-10～2026-09 的確證缺口進行補收。原已收 2023-10～2024-09 的月末估值及較早財報繼續保留作 TTM/YoY、36月研究暖機；不能因補收窗口兩年就刪除或忽略已有歷史。PE 與 PB 研究分開、金融業獨立分群，不為原撤銷的第五模型開新來源或發布路徑。

## 已讀來源與初篩（不等於可訓練）
基礎：Drive JanusDataset_v3_202610/canonical/release-0bbae8d9c1ca7d8d；CURRENT SHA256 0b64ac6927805fb98260121da94624d7e08ac423f0aa13b8349d4c304f0135cd；manifest SHA256 7b80d441efabbc307d359ea5d15cd9202ccee5e2930cf4c3cc337496c95eb542。對既有 P0/P1 壓縮稽核的財報 inventory.csv.gz 逐列整理。

- 不重複財報股票代號 1,977（TWSE 1,085／TPEx 892），皆為非0開頭4碼代號，但**尚未經官方股票主檔核普通股資格**。
- 2025Q3、2025Q4、2026Q1、2026Q2 四季 income+balance 均有原始紀錄的代號 1,965；不合此粗篩 12。
- 2024Q4～2026Q2 七季，整份收入/資產負債表無紀錄的股票×報表資料集待核查 **98** 組（income 49；balance 49）；**待核查不等於可直接發送98個 FinMind API 請求**。
- 已有財報全部存在原始單位、合併/單季口徑、歷史 published_at/PIT 缺口，不能因檔案存在就標模型 ready；新抓 FinMind 也無法自動補到過去公告版本。
- 已讀 release manifest 36份估值 Parquet metadata，但 **24/36月的逐股 PE/PB 正值還未從實際 Parquet 解碼讀回**。成熟研究建議 30 個以上有效月訊號；只補兩年不代表訓練也限制兩年。
- 2026Q3 財報於當前日期不視為全部公司都已公布，不能直接當逾期缺口。

## 可下載明細與安全 Colab
原始輸出在 **janusChatGPT/模型研究/valuation/Janus_Valuation_兩年普通股補收前盤點_20261024.zip**：
https://drive.google.com/file/d/1l_3k_gCeemMtKg3hMIlSmd4Cr7-ef03V/view

ZIP 含逐股初篩 1,977 檔 CSV、股票×報表整季無紀錄98組待查 CSV、摘要 JSON、操作說明、19_Valuation_普通股_兩年定向補收前盤點.ipynb。Notebook **RUN_FETCH=False**；會在 Colab 掛載 Drive、核對官方公司主檔＋36個月逐股 PE/PB＋7季度財報，產出可觀測的研究候選與較精準的缺口，不發財報請求。

## 仍需依序驗收
1. 官方上市／上櫃公司名冊普通股與排除 ETF/ETN/TDR/基金/特別股/權證；新上市日期與退市/歷史母體無法用今日快照冒充 PIT。
2. 讀取現有 valuation 月末正 PE/PB 的逐股觀測，研究期間原36月及補收近24月分開計數；單月不能補值假造觀測。
3. 對實際落在普通股與有效估值交集的個股核財報、營收、單位、季期、首次公布時間及公司行動；缺 metadata 先補證而不是重抓同樣數值。
4. 只有明確數值缺口才產 FinMind 免費資料請求，每個 symbol×dataset 合併二年日期範圍、受控速率/額度/斷點/原始bytes hash/授權；研究不觸碰 CURRENT/ACTIVE。

此文件是靜態初盤收據與已決策的工作範圍，**不是實際 FinMind 補收、訓練、上線或最終有效股票清冊**。
