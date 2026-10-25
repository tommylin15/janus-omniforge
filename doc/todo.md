# Janus — 唯一 Active TODO

更新：2026-10-25（Asia/Taipei）。本次新增分析輸入Mart／營收15月補收／週期事實報告程式與文件；未執行測試、部署、migration或模型啟用。

## 唯一順序線

依序 **SEQ-01 → 02 → 03 → 04 → 05 → 06 → 07 → 08**。不再分線派工；舊 UB／RV／D07／D08 是對照ID，不是另一份佇列。
每項固定拆為文件設計、程式開發、測試驗收、部署，完整指示見 [AI逐項指令](execution-cards/sequential-delivery.md)。

| 順序／任務 | 整併舊項 | 目前基線 | 部署歸屬 | AI 指示 |
|---|---|---|---|---|
| SEQ-01 收取、清理與市場分析總控 | UB-01 | 設計與程式差異修正已提交；離線 CI 待讀回，live 未驗 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-01) |
| SEQ-02 持股、買賣與觀察設定快照 | UB-03、4J／4R 的本次增量 | 已有快照與 API，完整語意／UI 待補驗 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-02) |
| SEQ-03 日週月備份、保留清理與回復範圍 | UB-04（不是重開 OPS-P0-1） | 已有 VM／migration069／保留程式，未測試／部署 | SEQ-04 | [四階段指示](execution-cards/sequential-delivery.md#seq-03) |
| SEQ-04 基礎批次集中部署與兩小時切換 | UB-05：UB-01／03／04 合流 | 未執行 | 本項集中部署 | [四階段指示](execution-cards/sequential-delivery.md#seq-04) |
| SEQ-05 Valuation 真資料、唯一估值卡契約 | RV-01…06、UB-02 的 Valuation 子功能 | RV-02／03 有既有 CI；RV-03 live 待驗，RV-04…06 待開發 | SEQ-08 | [四階段指示](execution-cards/sequential-delivery.md#seq-05) |
| SEQ-06 四模型正式上線模式、版本與共用快取 | UB-02、D07 serving、Risk API/UI、D07-CROSS-JOB-MODEL-CACHE；FACTOR-FACTORY／X/Y 僅必要 serving 一致性 | 按四模型可發布前提設計；實際接線狀態逐角色確認 | SEQ-08 | [四階段指示](execution-cards/sequential-delivery.md#seq-06) |
| SEQ-07 分析報告、Owner history 與 UI 完整接線 | UB-02、D08、RV-05 合流 | 既有 Fact Pack／Gateway 可沿用；完整整合待做 | SEQ-08 | [四階段指示](execution-cards/sequential-delivery.md#seq-07) |
| SEQ-08 四分析師到報告 UI 集中發布驗收 | UB-02 完成 gate、RV-06、D08 發布 | 未執行；依賴SEQ-05…07 | 本項集中部署 | [四階段指示](execution-cards/sequential-delivery.md#seq-08) |

## 階段狀態與接手規則

- SEQ-01 已由使用者指定開工；本輪修正來源失敗與 Mart queue 狀態，不重寫既有 Controller／新建定時器。離線 CI 收據未取得前仍須驗證，下一順序待本項離線證據收斂。
- 本次文件整理完成，不等於每個任務的設計已審定或工程完成。上表基線來自 main 已提交程式／既有文件收據，沒有新的runtime驗收。
- 每次只執行使用者指定任務／階段；未指定階段時按該任務四階段指示完成可做範圍。遇跨任務集中部署，將部署及live驗收記為 `DEFERRED_TO_SEQ-04/08`，不是PASS；其餘前置交付完成即可往下一順序準備，不造成循環等待。
- SEQ-04結清SEQ-01…04；SEQ-08結清SEQ-05…08。測試驗收分部署前離線／Release與部署後真實驗收，不能在未部署時假稱live PASS。
- 記錄格式：`任務｜文件設計狀態｜程式狀態｜測試狀態（offline/live）｜部署狀態｜SHA/證據｜下一階段`。只在此維護active狀態；Operations保存收據。

### SEQ-01 四階段紀錄（2026-10-25）

`SEQ-01｜文件設計=CODE_REVIEWED／契約已補｜程式開發=CHANGES_COMMITTED｜測試驗收=OFFLINE_CI_PENDING／LIVE_DEFERRED_TO_SEQ-04｜部署=DEFERRED_TO_SEQ-04｜基線=73ba5e037a0089d215bf36a391063cec2ddc15e6、目標本次提交｜唯一下一入口=確認SEQ-01同SHA離線CI結果，通過後SEQ-02／文件設計`。

驗收至少涵蓋 `scripts/test-unified-batch.sh`（含15月收入窗口、真正來源失敗、queue partial/idle、8 claim／900秒、Stage 48h／lease與既有測試）及兩個Flutter Admin targeted tests。GitHub selective CI 的範圍不能冒稱全部上述驗證；新時段、migration、Dev Runtime／Scheduler 實機驗收均由SEQ-04負責。證據摘要見[Operations](spec/operations-and-testing.md)。

## 四模型正式上線與第二版邊界

Quant、Risk、Fundamental、Valuation **全部列入本次正式serving／版本／報告／UI／部署範圍**；不是只規劃、不以baseline或research-only代替完成。採既有可發布artifact，不要求先調參或重訓；若缺檔，列明角色、必要檔案與影響，不能捏造ACTIVE。CEO是整合層，Event只保留相容事實，沒有第五模型。

原 DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY／D07 X/Y 的必要推論一致性併SEQ-06；全面研究資料重整、四模型調校／新增因子／實驗與VAL-MIN30後續改善移至 [2027年第一季第二版](parking-lot.md#v2-2027-q1)。不阻塞本次正式上線，不建立自動啟動排程。

## 不重開與未授權範圍

C1-A、P0-2、OPS-P0-1、A-CHANGE、D01～D06、FINOPS-AB、研究稽核精簡保持既有有界結案。新備份政策驗收歸SEQ-03／04，不把歷史故障重開。
取消：逐來源稽核、全歷史PIT／名冊／公司行動重建、自然長期觀察、新20日cohort等待、例行週月模型稽核、第五模型、舊GAS/BQ/月度重訓。
暫不做：C1-B實體刪表欄、新付費來源／資源、production環境建立／IAM擴張、站外推播及其他 [Parking Lot](parking-lot.md)。本次「正式上線模式」指既有Dev個人真實服務中的四模型正式運作，不自動授權新建GCP production環境。

## 2026-10-25 分析因子與報告頻率增量（併原順序）

[分析Mart SPEC](spec/analyst-input-mart.md)／[AI驗測WI](runbook-analyst-input-mart-ai.md)。本次CODE／DOC已交付，TEST／LIVE／UI均NOT_VERIFIED，不新增SEQ編號。

| 原項 | 增量與仍未完成條件 |
|---|---|
| SEQ-01 | 15月營收缺口補收、TWD／千元共用；深度target掃描與共用benchmark；離線與既有Job驗測待做 |
| SEQ-05 | 補真實EPS／BVPS與估值有效月；不因新Mart而捏造已足量 |
| SEQ-06 | Core→analysis artifact已寫；四模型真artifact feature schema、Valuation會計mapping與正式推論接線待完成；必要train/serving parity本版做、調校留Q1 |
| SEQ-07 | 新增週期＋資料變更事實報告及重用狀態；四ML結果、Owner history／API／UI完整接線與日期語意待驗；CEO仍按需 |
| SEQ-08 | 集中驗2330／2882及既有持股觀察股的真實因子覆蓋→模型→報告UI，不能以新程式存在稱PASS |
