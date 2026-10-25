# Janus 目前狀態

更新：2026-10-25（Asia/Taipei）。SEQ-01／SEQ-02／SEQ-03 已完成文件、程式與離線 CI 可交接：SEQ-01 [#40148605544](https://github.com/tommylin15/janus-omniforge/actions/runs/40148605544)；SEQ-02 [#40151187692](https://github.com/tommylin15/janus-omniforge/actions/runs/40151187692)；SEQ-03 [#40152197002](https://github.com/tommylin15/janus-omniforge/actions/runs/40152197002)。以上舊收據不涵蓋後續新時段修改。

SEQ-04 最新使用者批准時段：每日00:30 PostgreSQL備份、每日02:30市場收取、平日04:30全市場分析、平日06:30私人更新（Asia/Taipei）。同一每兩小時 `30 */2 * * *` Cloud Scheduler、Stage每日22:30／Iceberg週六22:30不變。Controller／screening／測試／SPEC／WI已提交main；本次變更離線 CI 尚待新來源結果。02:30以前一完成交易日為輸入，04:30使用實際最新Core資料日期；週六維護查實際02:30 Core ready收據。此為待部署版本，**未修改 Dev Scheduler、Jobs、VM、migration 或live**，不宣稱新時段生效。

**唯一下一入口：SEQ-04／部署前同SHA測試與發版設計**，依[AI執行卡](execution-cards/sequential-delivery.md#seq-04)及[統一批次WI](runbook-unified-batch-ai.md)核對排程、備份、還原、既有Worker digest與回滾，再一次集中切換並讀回。四模型正式 serving 另歸SEQ-05～08。

## 沿用的歷史基線

更新：2026-10-24。**研究稽核精簡已 CLOSED／PASS（有界 Dev 驗收）**。已完成離線測試、GHCR Release、四個既有 Dev Jobs Rollout、API 100% 切流，以及一次獨立唯讀 Runtime 讀回。正式 API source：`cf69def50209ec590e464fcc7298ca4ece44bc6f`；Scheduler ENABLED，退役 `data-quality` 不在新版批次定義。

驗收：[完整 Release #40084702607](https://github.com/tommylin15/janus-omniforge/actions/runs/40084702607)／[Jobs #40085601337](https://github.com/tommylin15/janus-omniforge/actions/runs/40085601337)／[API #40087061995](https://github.com/tommylin15/janus-omniforge/actions/runs/40087061995)／[Runtime #40087520948](https://github.com/tommylin15/janus-omniforge/actions/runs/40087520948)。完整界限見 [結案 WI](runbook-research-simplification-wi.md)，不可冒稱真人登入、舊 pending DB 終態或備份復原已驗證。


OPS-P0-1 已於2026-10-24有界結案；當日Daily 40,587,735 bytes、唯讀 [#40095061967](https://github.com/tommylin15/janus-omniforge/actions/runs/40095061967) 與dry-run [#40095324398](https://github.com/tommylin15/janus-omniforge/actions/runs/40095324398)通過，歷史隔離還原沿用，不宣稱10/24新檔已重做restore。SEQ-03／04驗新版7/4/6政策，不重開舊故障。

RV-02純函式與RV-03 adapter已有既有CI收據；RV-03真實2330／2882覆蓋仍待驗，RV-04…06尚未完整接線／發布，現併SEQ-05／08。詳見 [Valuation SPEC](spec/valuation-range.md)。

P0-2、C1-A、A-CHANGE、D01～D06、FINOPS-AB及研究精簡保持既有結案；取消項不變PASS。實際證據查 [Operations](spec/operations-and-testing.md)，不以本文件取代runtime。

新增[分析Mart](spec/analyst-input-mart.md)為CODE／DOC；真實因子覆蓋未知，四模型feature schema／Valuation mapping／完整API UI仍按SEQ-06…08處理，非四模型已上線。
