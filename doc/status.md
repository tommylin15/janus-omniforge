# Janus 目前狀態

更新：2026-10-25（Asia/Taipei）。SEQ-01 已完成靜態差異修正與契約補充；同程式 SHA 7ab83e0 的 selective CI #40147914267 SUCCESS。完整離線腳本及 Flutter Admin 測試未執行；無部署、migration、Scheduler 切換、live 或 Registry 變更。

統一批次主要程式已於 [77b5565](https://github.com/tommylin15/janus-omniforge/commit/77b5565f2b23c5023c9128121a9dfad05ed58376) 提交main，該版仍未測試／部署／驗收。新兩小時Scheduler與VM保留政策未由本輪切換；四模型正式上線也尚未由本輪完成。

**下一個唯一入口：SEQ-01／完整離線腳本與 Flutter Admin targeted 測試**；通過後轉 **SEQ-02／文件設計**。接著依 [TODO](todo.md) 順序到SEQ-08，完整操作見 [AI卡](execution-cards/sequential-delivery.md)。四模型正式serving／報告UI納入本版，研究調校延至2027年第一季由使用者重新啟動，不形成發布前置。

## 沿用的歷史基線

更新：2026-10-24。**研究稽核精簡已 CLOSED／PASS（有界 Dev 驗收）**。已完成離線測試、GHCR Release、四個既有 Dev Jobs Rollout、API 100% 切流，以及一次獨立唯讀 Runtime 讀回。正式 API source：`cf69def50209ec590e464fcc7298ca4ece44bc6f`；Scheduler ENABLED，退役 `data-quality` 不在新版批次定義。

驗收：[完整 Release #40084702607](https://github.com/tommylin15/janus-omniforge/actions/runs/40084702607)／[Jobs #40085601337](https://github.com/tommylin15/janus-omniforge/actions/runs/40085601337)／[API #40087061995](https://github.com/tommylin15/janus-omniforge/actions/runs/40087061995)／[Runtime #40087520948](https://github.com/tommylin15/janus-omniforge/actions/runs/40087520948)。完整界限見 [結案 WI](runbook-research-simplification-wi.md)，不可冒稱真人登入、舊 pending DB 終態或備份復原已驗證。


OPS-P0-1 已於2026-10-24有界結案；當日Daily 40,587,735 bytes、唯讀 [#40095061967](https://github.com/tommylin15/janus-omniforge/actions/runs/40095061967) 與dry-run [#40095324398](https://github.com/tommylin15/janus-omniforge/actions/runs/40095324398)通過，歷史隔離還原沿用，不宣稱10/24新檔已重做restore。SEQ-03／04驗新版7/4/6政策，不重開舊故障。

RV-02純函式與RV-03 adapter已有既有CI收據；RV-03真實2330／2882覆蓋仍待驗，RV-04…06尚未完整接線／發布，現併SEQ-05／08。詳見 [Valuation SPEC](spec/valuation-range.md)。

P0-2、C1-A、A-CHANGE、D01～D06、FINOPS-AB及研究精簡保持既有結案；取消項不變PASS。實際證據查 [Operations](spec/operations-and-testing.md)，不以本文件取代runtime。

新增[分析Mart](spec/analyst-input-mart.md)為CODE／DOC；真實因子覆蓋未知，四模型feature schema／Valuation mapping／完整API UI仍按SEQ-06…08處理，非四模型已上線。
