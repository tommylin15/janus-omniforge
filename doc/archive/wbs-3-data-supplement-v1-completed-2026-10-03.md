# WBS-3-DATA-SUPPLEMENT-V1 結案證據

日期：2026-10-03。依使用者「驗收放寬、有資料優先」決策完成；本次範圍為資料回補、每日增量、獨立週六品質檢查、Admin UI 與檢核文件。沒有啟動下一 WBS。

## 真實資料與固定快照

| 股號 | 產業樣本 | 財報季度 | 月營收月份 | 合格行情日 |
|---|---|---:|---:|---:|
|1102|水泥|12|12|126|
|2327|電子零組件|12|12|148|
|2330|半導體|12|12|148|
|4958|通信網路|12|12|148|
|5876|金融|12|12|148|

最終回補 `janus-ingestion-core-nhkvm` 成功，新增 41、重用 137、略過 124、失敗 0；約 100 秒。官方 MOPS 財報／月營收與 TWSE 行情先存 Stage，再寫 Iceberg Core；PostgreSQL 保存控制與 Iceberg catalog metadata，並非以 PostgreSQL 取代資料湖。先前 PostgreSQL nullable integer 型別錯誤已修正並完成實跑。

Core execution `537276d9-f4bb-4df9-8d9a-5ae449b5d981`；snapshot `sha256:cb5a66d91253699dbc66930a3fbfb6d0f496255ae3b8ef0112398afb73335e09`；manifest hash `sha256:36c14b4192a8802f99c2f00487cf9a135b27b4d03c9ccd2023f8817d7c21ddac`。原始憑證與數值不寫入此文件。

Mart readback `janus-intelligence-mart-8267t` 驗證五檔同快照 feature v2，未映射 severity 的 event risk score 保留 null。`janus-intelligence-mart-55hw7` Completed=True，使用持久化 request `9283354c-aaca-5f46-a7b0-01dbb824e298` 的 snapshot/hash/options 重建並驗證 6 個範圍、30 份 Fact Packs，模型呼叫 0、資料寫入 0。逐檔 feature presence／metric period counts／pack hashes 見 [安全 JSON](../../ops/data-supplement-dev-acceptance.json)，重跑程式見 [readback](../../ops/data-supplement-dev-readback.py)。

## 每日、週六與 Admin

既有單一 Scheduler `janus-ingestion-daily` ENABLED，每小時台北時間 :30 呼叫總控；總控每日 08:30 安排增量補資料，依賴 07:30 ingestion。先盤點 Core 缺期，僅抓缺失／新公告／修正及最近一期重查；依既有 first-batch 與去識別 portfolio coverage 取目標，不每日對全部股票完整回補。

實際 Scheduler → controller → daily child `janus-ingestion-core-7g6xk` 成功，約 76 秒：新增 0、更新 0、重用 114、略過 103、失敗 0，沒有排出新的 analysis execution。唯讀總控查核 `janus-batch-controller-slfzg` 確認 occurrence `data-supplement/2026-10-03/08` 持久化為 succeeded，依賴 ingestion 同樣 succeeded。每日預設四檔 1102、2327、2330、4958；5876 為額外金融樣本，沒有虛報其為每日設定目標。

獨立品質 Job 每週六 12:30，由同一總控排程，無 ingestion 成功依賴，與 ingestion／Mart 互斥。實跑 `janus-ingestion-core-6s2cq` 成功，四檔共 52 次官方來源比對，約 102 秒，issues 為空，`needs_daily_schedule_adjustment=false`，模型呼叫 0、不修改 Core。首次自然週六 12:30 週期尚未在本 checkpoint 觀察到；設定與獨立真實執行已驗證，長期自然觀察歸 Pilot。

authenticated `/app/admin` 實際顯示「檢查通過／目前不需調整每日補資料」，「結果與檢核文件」能開啟完整文件。先前權限失敗也正確顯示需處理；修復改用既有 ingestion 可讀目標，未擴權。通知依使用者決定只顯示 Admin，不建 Codex automation、不寄 Email。操作與修復程序見 [runbook](../runbook-data-supplement.md)。

## 驗證與部署

- Python 相關驗證：59 項 supplement／quality／controller／Core／control／API、25 項 API／deployment contract、16 項目標整合、2 項官方行情 adapter；Mart contract／pipeline 71 項通過。
- Flutter targeted 25 項通過；full CI fixture 已修正並通過。WSL `bash -n verify-dev.sh` 通過。
- GitHub dev workflow `37091319342` ingestion、`37091696158` Mart、`37092348839` API 最新同步均 success，包含 deployment／verify。程式 main HEAD `68831d5a1ed521cdffe893b2a04bdae4f0791d36`。
- 修復內容包括季度口徑、月營收檔案／千元轉換、Core additive schema、缺失行情月份、預設目標權限、runbook image inclusion、Legacy Admin redirect verify、未映射事件風險保留未知。舊 immutable feature v1 replay 保留。

## 明示限制

歷史首次公告／原始更正版次未全部證明，資料以真實 receipt time 與來源 hash 保留；目前研究可用不代表歷史 PIT 可用。EPS 股本口徑、ROE 平均權益、同業基準、事件 severity 及部分長窗口籌碼仍有缺值，五角色不得把缺值當完整研究。來源授權、validator、publication、auth／private isolation 邊界未放寬。未新增 production／付費資源或模型呼叫。
