# Janus — 唯一 Active TODO

更新：2026-10-24。依 [統一批次SPEC](spec/unified-batch-flow.md) 整併；下面 UB 是本輪新增工作編號，不冒充歷史WBS。
本輪只交付文件與程式；TEST／CI／DEPLOY／MIGRATION／LIVE ACCEPTANCE全部 NOT VERIFIED。
四模型按可正式發布設計；模型檔、feature parity、Registry與真實輸出由交接驗收，不自動造假啟用。

| 工作 | 整併來源／交付 | 依賴與退出條件 |
|---|---|---|
| UB-01 統一總控 | 收取＋增量補齊、Mart篩選＋分析queue；每兩小時喚醒，取消獨立supplement/mart定時；Admin新節奏 | CODE；依WI測試時區／跨日／重複／失敗／五天queue；同版Job＋cron讀回 |
| UB-02 四模型與報告 | D07四模型、Risk API/UI、D07-CROSS-JOB-MODEL-CACHE、D08合併同一產品路線 | 重用loader/cache／Fact Pack／Gateway；四模型實際版本與輸出、單一估值卡、Owner history／UI讀回；不做日常重訓／LLM全市場批次 |
| UB-03 私人快照 | 持股買賣、修正／沖銷、觀察設定、Private Mart實際輸入快照與Owner讀取API | CODE；Owner隔離、同內容去重、異動後重算與舊值提示驗收；不新增券商下單 |
| UB-04 備份清理 | 日／週／月共用PG dump、VM清理、migration069；刪GitHub備份清理workflow | CODE；備份與清理分離狀態、7/4/6、副本讀回、generation刪除與隔離還原；不重開已結案OPS-P0-1歷史故障 |
| UB-05 交接切換 | [AI測試部署驗收WI](runbook-unified-batch-ai.md)及可執行離線腳本 | UB-01/03/04測試→既有Dev部署→一次端到端有界驗收→UI；失敗修正，不宣稱本輪已PASS |
| RV-01…06／04 Valuation | 延續既有RV-01 reader、RV-02、RV-03 adapter；併入UB-02 Valuation輸入→Mart/API→唯一估值卡 | 真實2330／金融股讀回；缺24有效月或同口徑EPS/BVPS則明列缺口，不重建全歷史PIT |
| DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY／D07 X/Y | 合併為研究資料準備線：CURRENT→必要欄位／日期排序→滾動特徵→X/Y→train/serving一致 | 既有Colab資料，不放進兩小時業務批次；只補實際缺少資料 |
| D07／VAL-MIN30研究改善 | Quant、Risk、Fundamental、Valuation的baseline比較與效用改善保留研究線 | 四模型本次可發布規劃不等於研究結果全有效；VAL-MIN30 v25/v26已完成研究收據不重跑；需要時才新實驗 |

順序：UB-01/03/04程式與UB-05離線測試→migration／VM／Jobs→單一Scheduler切換→市場/私人/備份各一次有界驗收。
UB-02與RV延用已有模型／adapter；若實際模型檔未接入，明列差距，不用阻擋可用的事實報告。研究線不阻塞日常資料整併。

已結案保持：C1-A、P0-2、OPS-P0-1、A-CHANGE、D01～D06、FINOPS-AB、研究稽核精簡；證據查Operations／Git歷史。沒有新故障不重開。
取消保持：來源逐筆稽核、全歷史PIT／名冊／公司行動重建、自然觀察、新20日cohort等待、例行週月模型稽核、第五模型、舊GAS/BQ/月度重訓。
C1-B真實表／欄位刪除、Risk v2、新付費來源／資源、production／IAM擴張不在本輪實作。
