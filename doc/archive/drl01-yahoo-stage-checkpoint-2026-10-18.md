# DRL-01 Yahoo EPS／Stage修復停止checkpoint

使用者2026-10-18要求：優先DRL-01即時工程收尾；自然daily／weekly Ledger需等待時間，改列後續觀察；更新完停止，先回寫文件及同步GitHub。以下PARTIAL不是結案，不自動續行新持股／關注股工程。

## 已完成與錯誤定位

- 正式兩年PE/PB API六股×2共12/12、5876手機／桌面PE/PB 4/4 PASS；Admin `data_readiness_ledger` key及獨立重算PASS；Market Volume四slices沿用PASS。原證據見operations。
- 六股2025Q4 Yahoo單季EPS：1513=2.08、2327=3.29、2382=5.76、3231=2.69、3711=3.39、5876=0.5。這些是供應者口徑，不認證跨期TTM或歷史PIT。
- 首版來源`da1c5093061d333c29e1a87595f9d1a8dcbc04db`完整Release #39123873496、候選 #39124350076、auth #39124501524、Preview #39126117546、Jobs #39124887578（8/8 canary）PASS。
- 首次補收 #39126135612 FAIL：operation `14e5e4e7-64be-4228-8cb1-02f5699a1ab2`、execution `janus-ingestion-core-6fc7l`已終態；兩次task attempt都在第一個Stage HTML寫入前失敗，receipt items=[]。唯讀診斷 #39126920718明確讀回`ValueError: HTML Stage payload is limited to official MOPS financial reports`。不是EPS無來源，不可再回到官方分母阻擋。
- 修正`stage.py`只允許MOPS／Yahoo的financials HTML；其他HTML仍拒收。新增Yahoo→Stage→Core正規化回歸，34項PASS；Windows TEMP權限造成的初次本機錯誤改用workspace temp後通過。候選／Jobs／API發布契約109項PASS。

## 修正版發布

- 映像來源完整SHA：`e3e0098399846eb337dd2ed1f8b636240bc88c20`。
- 完整Release #39126918277 SUCCESS：Python、Flutter、四映像、匿名digest全部通過。
- 0%候選 #39127304288 SUCCESS；同源自動auth #39127497388 SUCCESS。
- API：`ghcr.io/tommylin15/janus-api@sha256:5cf4121aabb60e8196f1542674ad2ac48264fc403210051fe2e98a2fa4e75365`。
- ingestion/controller：`ghcr.io/tommylin15/janus-ingestion-core@sha256:59fbf1b58196df048f90e63fb78f761787095ce8ab16555931a3ca84c1287506`。
- Preview #39127627078：BLOCKED／FAIL；收據phase=ACQUIRE_LEASE、preview_tag_mutation_attempted=false、canonical_traffic_write=false、jobs_or_scheduler_write=false。尚未作Preview變更，固定Preview仍為先前da1c5093版；不重送、不強制清鎖。
- Jobs #39127659349：最後讀回IN_PROGRESS，尚非成功；既有workflow有失敗recovery。已送出的雲端執行不因本地停止而自動取消；未取消正在更新的Job，避免中斷恢復程序。下次先確認8/8 canary、Scheduler ENABLED與部署lease釋放，再決定是否接續。
- 正式API仍為前版`b5df7e30bc02676a41d0d3300325b9ca5d6fb553`，尚未送出新版正式promotion。`ops/ghcr-active-baseline.json`保留API b5df7e30及Jobs da1c5093各自真實可回滾基準。

## 下次由使用者續行

1. 先讀取上述Preview／Jobs終態與收據；不盲目重送。如果更新失敗，先完成既有recovery確認Scheduler／lease狀態。
2. Jobs修正版PASS且固定digest一致後，以既有`drl01-yahoo-eps.yml`的`supplement`執行一次；`ops/drl01-yahoo-eps-request.json`已指向修正版，範圍仍六股2025Q4。不新增來源費用、Scheduler或Owner交易。
3. 保存Stage／Core／serving六股逐筆真實收據與snapshot，再從Preview公開`/api/v1/public/stocks/{symbol}/visual-series?metric=eps&limit=20`核對2025-12-31點與Yahoo來源。
4. 更新`ops/ghcr-api-promote-request.json`為目前`promote-authenticated-reversible-ghcr-dev` schema、修正版release/jobs/auth與API b5回滾基準，review後依既有promotion流程；舊request還是舊schema，不可直接拿來送出。
5. 正式API六股與實際畫面讀回PASS後，才可將DRL-01工程結案；自然daily／weekly保留後續觀察，不要求等時間才能結案。新持股／關注股背景補收另有已核准契約，尚未實作，本次停止不接續。

本機診斷、原始Yahoo頁面、收據與驗證腳本存忽略目錄`.tmp/drl01-yahoo/`；不把私人畫面或原始內容推上GitHub。其他未追蹤Admin驗收檔與token-savior目錄不屬本次，不提交。
