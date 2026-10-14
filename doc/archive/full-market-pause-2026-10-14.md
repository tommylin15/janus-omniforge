# 全市場／總控／持股／四頁：2026-10-14 暫停交接

使用者明確要求暫停並將目前全部進度同步 GitHub。本工作包狀態為 **PAUSED／PARTIAL**；暫停後不新派送 Release、migration、Jobs 或 acceptance。resume 從下方未完成項目接續。

## 已部署與真實證據

- 已部署 runtime 來源：`085456e3cdf2075cc399977dfe4c2414340fdae8`。完整 Release [#38530995776](https://github.com/tommylin15/janus-omniforge/actions/runs/38530995776) PASS：Python 1149、Flutter 90／analyze／web build、四個 immutable GHCR images／匿名 pull。
- 同源 0% candidate [#38531845062](https://github.com/tommylin15/janus-omniforge/actions/runs/38531845062)、OAuth/private boundary [#38532482767](https://github.com/tommylin15/janus-omniforge/actions/runs/38532482767)、固定 Preview [#38533380447](https://github.com/tommylin15/janus-omniforge/actions/runs/38533380447) PASS。
- 四 Jobs [#38533451889](https://github.com/tommylin15/janus-omniforge/actions/runs/38533451889) PASS：兩輪共 8 次真實 canary；readback 四個 exact digest 與設定指紋均符合，Scheduler ENABLED／原設定不變，舊 GHCR source `50eda171ef6ffb3971a4d140ad09bac870ead6c1` 回滾映像可匿名拉取。沒有實際演練這次舊映像回滾，不混稱 rollback exercised。
- migration 054～056 PASS。正式 API 100% 流量仍為前版；migration 057 尚未執行。
- Preview `/market-home` 本機 Windows 網路 API-only 30 暖樣本：0 失敗、P50 375 ms／P95 437 ms，首筆 484 ms 單列；未強制 cold start，不是手機端到端或 cold P95。

## 真實全市場驗收：FAIL，快取尚未啟動

- bootstrap [#38537012683](https://github.com/tommylin15/janus-omniforge/actions/runs/38537012683) FAIL，Cloud Run `janus-ingestion-core-zrjsx` 已終止；一次既有 Cloud Run 自動 retry 亦未通過，沒有額外盲目重派。Job 永久設定與 API traffic 未修改。
- 官方固定名冊共 **1988 檔：TWSE 1095、TPEX 893**。第一輪當日價量成功 TWSE 1093／1095、TPEX 868／893，均符合 ≤10%；但其他必要資料集與整體 coverage 未通過，不能稱全市場 PASS。
- 原驗收强制選當日，部分收盤資料尚未發布；財報分市場已成功卻又被要求不存在的 ALL receipt。修正選用既有上一完成交易日規則、財報分 TWSE/TPEX 及上櫃法人指定日端點，commit `0fe5faaae62256d75d8bc6f1b1dfe21430d03556`；相關 54 tests PASS，真實 2026-10-13 法人端點可解析 895 種證券／三類法人，同日 OpenAPI 數字群組已核對。
- 同日期、固定 893 檔上櫃普通股名冊的唯讀預查仍有超標：法人 773／893（缺120）、融資 802／893（缺91）、當沖 723／893（缺170）；估值 886／893、借券 815／893 通過。這是預查，未形成 Stage/Core business PASS。價量另一次指定日預查為 887／893。不得用縮分母、將未知補零或聚合上市成功掩蓋上櫃失敗；下一步需確認官方適用資格／排除證據與有界補漏。
- cached phase 尚未執行。須先取得新來源完整 bootstrap PASS，再核對固定名冊版本、分市場 receipts、相同 Core snapshots／來源與 `staged=0`，不能以 fixture 或一般 container SUCCESS 代替。

## 另一個 AI 的工作已同步 main，驗收仍有界限

- `318f950`：統一診斷工具 `ops/diagnose.py`。
- `8ab85d1`：workflow 治理與進度文件；117 份 workflow 收斂，89 份移入 archive、28 份留在 active 入口。
- `5bd72e82acbdd8ce44061d48c9092a5fe5b92616`：首頁寫入時預聚合、migration 057、API snapshot fast path 與單元測試。程式已提交／單元測試通過，**尚未部署、不具 <5 ms 或已消除 cold latency 的真實證據**。
- `acd4ef4105ee781ecd1285a33ca4f1cd7b827a2c`：operational quote／serving 批次分片寫入；已提交，真實效能尚待新來源驗收。
- `b566edce0e90e87864c9ee283f19c7c73fa7f7c7`：歸檔 workflow 測試路徑相容與 057 執行入口／publication-owner ACL 驗收補齊。兩條 migration 執行路徑皆有測試；057 真實 migration 尚待完整 Release PASS。
- 沒有將另一 AI 的來源不明改動覆寫或丟棄；本輪讀到的上述變更均已 commit。兩個獨立巢狀 repository `.cicd-v2-work/`、`token-savior/` 留在本機，不加入 Janus repository；前者含歷史登入及驗收暫存，不公開 auth/session 或 private artifacts。

## 完整 CI 尚未 PASS

- source `0fe5faa…` Release [#38541322491](https://github.com/tommylin15/janus-omniforge/actions/runs/38541322491)：Python 1136 PASS／18 FAIL（歸檔 workflow 路徑未同步），Flutter PASS，publish SKIP。
- source `b566edc…` Release [#38542355436](https://github.com/tommylin15/janus-omniforge/actions/runs/38542355436)：Python **1154 PASS／2 FAIL／2 legacy deselected**，Flutter PASS，publish SKIP。最後兩項為 `test_cicd_v2` 與 `test_ghcr_candidate_lease_guard` 的動態歸檔路徑，暫停同步前已修；兩檔 targeted **55 PASS**。尚未以修正後新 SHA 重跑完整 Release，不宣稱 full CI PASS。
- 先前 targeted 路徑／migration 回歸：150 PASS／1 FAIL；失敗為既有 Linux SIGALRM 測試在 Windows 不支援。Linux 上該測試在完整 CI 通過；本機結果不累加為全套成績。
- [serving schema CI #38542355434](https://github.com/tommylin15/janus-omniforge/actions/runs/38542355434) PASS；不等同 057 已在 dev 執行。

## 恢復入口

1. 先確認另一 AI 有無新變更，以一個完整 SHA 重跑完整 CI／四映像，不用已失敗 Release 進部署。
2. 在既有受控路徑完成 057 migration，候選與同源 OAuth boundary，再按當前 live baseline 取得四 Jobs fence／兩輪 canary／回滾收據。不得沿用錯 source 或舊 rollback baseline。
3. 解除上櫃必要資料集的真實 coverage gap；固定官方適用名冊與日期，先驗證排除規則／來源，再執行一次 bootstrap 及 cached receipt 對照。
4. 完成公開圖表 readback、持股／試算／保存 P50/P95 與四頁 authenticated screenshot。外部 Chrome 分頁控制未提供，本輪曾用 Windows 控制而被網址辨識安全機制停止；使用者指定後續只用分頁控制。測試帳號已由使用者指定，寫入前仍須驗證登入 owner；不能寫入本人帳本製造測試交易。
5. 備份 executor install [#38509036396](https://github.com/tommylin15/janus-omniforge/actions/runs/38509036396) IAM BLOCKED，CI 缺 `compute.instances.get`。VM 已啟用 OS Login，安裝涉及 IAP／sudo／VM 身分權限，須依 PROJECT_RULES §1.3 另行核准；目前未擴 IAM、原備份 timer 保留，controller backup／isolated restore／handoff 仍未完成。
6. 所有適用驗收真正 PASS 後才考慮正式 API promotion；後置模型研究／CEO 報告不由本輪啟動。
