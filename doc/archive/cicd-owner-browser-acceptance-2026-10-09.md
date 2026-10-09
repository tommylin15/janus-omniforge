# GHCR 候選版 A／B／A 人工登入與唯讀驗收

驗收時間：2026-10-09T03:35:09Z。來源 SHA：`fbcc5f58a2fa31f2f36dc4c82702fb62910c7361`；候選 revision：`janus-api-00451-cuw`。

候選網址：`https://ghcr-fbcc5f58a2fa---janus-api-2oo7qbkd5q-uc.a.run.app/app/`。使用外部 Chrome、兩個真實 Google owner；登入由使用者操作。

- A：持股、交易紀錄、年度報表可讀。持股／紀錄／報表的 2026 年已實現損益一致；私人 API 回應 200。
- B：持股為空、交易歷史 0 筆；使用者另人工確認不能讀到 A。以 B 的有效身份讀取 history，指定 A 的既有 symbol、owner UUID 與 event UUID，回傳 200／0 筆，沒有 A owner 或該事件。
- 上述 history 契約只接受 symbol／year；owner／event 查詢參數不具選擇身份的作用。這項證據證明 caller 不能透過這些參數切換 owner，不代表存在單筆事件 GET 或已實測 mutation 越權。
- 切回 A：history 回應 200、89 筆；逐筆 event／owner 識別與原 A 集合一致。持股與年度已實現損益恢復，snapshot／quotes／history／recalculation-status／pnl 均回應 200。
- 未新增、更正、作廢或刪除私人資料；憑證與私人識別值未寫入證據。Janus Dev Private 依使用者指示 BYPASSED。

本輪需使用者操作的登入驗收完成。Jobs rollout／回滾、Scheduler fence、API 100% promotion／回滾仍未完成；此文件不宣稱整體 CI/CD PASS。
