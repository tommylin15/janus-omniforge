# GCS 容量與重複產物：唯讀盤點（2026-10-19）

屬 [D07-PRE/FinOps 非阻擋觀察](../todo.md) 的一次性容量歸因，不建立新 Scheduler／長期 Cron，不讀 Owner 私有 payload，不刪除或修改 GCS 物件。**本文件建立與程式提交不等於完成 2GB live 稽核**。

## 2026-10-19｜本輪實機執行結果（BLOCKED，未取得儲存容量）

- 初次 [#39245576636](https://github.com/tommylin15/janus-omniforge/actions/runs/39245576636) 因工作卡的 WIF Provider 多出反斜線，Google STS 拒絕 invalid audience，已修復。
- 修正後 [#39245782268](https://github.com/tommylin15/janus-omniforge/actions/runs/39245782268) 與 [#39246076678](https://github.com/tommylin15/janus-omniforge/actions/runs/39246076678)：WIF 初始化 PASS，8 項 Python 單元測試 PASS；程序在取得 GCP Access Token 階段 BLOCKED，**沒有發出 bucket/object LIST**。
- 最後 [#39246633901](https://github.com/tommylin15/janus-omniforge/actions/runs/39246633901)：WIF setup PASS、tests 8/8 PASS，但常規 `gcloud auth print-access-token` 與 ADC token 均為 sanitized `INVALID_CREDENTIAL:exit1`；`GCP_WIF_TOKEN_UNAVAILABLE`。不能根據目前錯誤斷言缺 `storage.objects.list`、已驗 GCS 完整或可清理多少。其餘 Selective CI [#39246633770](https://github.com/tommylin15/janus-omniforge/actions/runs/39246633770) SUCCESS，只代表程式 CI。
- 本輪狀態：**audit implementation + tests PASS／GCS live footprint NOT_VERIFIED（認證阻塞）**。跨 Bucket 總量、current/noncurrent/soft-delete bytes、MD5 疑似重複 bytes 與 GCS 「近2GB」口徑均 **UNKNOWN**；既有 222.7 MB Core 是10/18過往截面，非這輪。
- 下一步必須先由既有 GitHub dev WIF 管理路徑檢查 OIDC／STS／短效 credentials（**不要 log token/credentials，也不要先擴 IAM**），確認 read-only access token 能生成後**人工單次**重跑 `gcs-storage-footprint`。只在 token PASS 後才可能看到 project Bucket 完整/partial 分類；要操作清理，需另依 retention generation/current safety gate 和授權。**不把此診斷轉為新的長期 Scheduler**。

## 已有的歷史證據（不可當今次全專案即時容量）

- 2026-10-18 Core compaction 前後可見 8,437件/219,508,719 bytes → 8,682件/222,685,481 bytes；小於1MiB的物件增加。這是 *Core 一個 Bucket 的 current-visible 快照*，不包含所有 Bucket、非 current generations／soft deleted。來源：[Ops](../spec/operations-and-testing.md) 與 [FINOPS-AB 歷史](../archive/finops-ab-continuation-2026-10-18.md)。
- 同日唯讀 Core+Mart 清理候選 6,510 件／105,361,424 bytes，不等於真實刪除或可對帳節省空間；先前稽核鏡像與小檔歷史見 [D06](../archive/d06-finops-2026-10-16.md)。
- 因此「GCS 接近 2GB」還沒有全 Bucket/代際的同時點實測分母，不能直接推論 OHLCV 內容佔 2GB。

## 新的可重跑唯讀稽核

- 入口：既有 \`.github/workflows/finops-dev.yml\` 的 \`gcs-storage-footprint\`；一次性 request：\`ops/finops-gcs-storage-footprint.json\`；程式：\`scripts/gcp/finops_gcs_storage_footprint.py\`；tests：\`tests/test_finops_gcs_storage_footprint.py\`。
- 使用現有 dev WIF identity，先 \`buckets.list\` 取得同專案所有 Bucket；若缺 IAM，改僅依固定六桶 allowlist 做 partial，**不得稱為 2GB 全帳戶總量**。每桶最多20頁×1000筆的 versions LIST（含 current / noncurrent），必要時再讀 softDeleted LIST；總桶數上限15。只使用 LIST/metadata GET、不下載內容、不更動 IAM/版本/retention／清理。
- 輸出 Artifact \`gcs-storage-footprint-report.json\`：按 Bucket/類型 current bytes、noncurrent bytes、soft-deleted bytes、物件數、大小級距／Iceberg Parquet+Avro+metadata、Stage 原始/執行、Research/Private/Backup/CI、storageClass；相同 MD5 只報疑似同內容「數量與可能重疊 bytes」，**非可刪清單**。Private 只列統計，不列 object name／Hash／Owner identity／原始 payload。
- 上限或 IAM 無權時維持 \`PARTIAL_NOT_PROJECT_TOTAL\`，不把 observed lower bound 當 billable total。一次快照非原子，不保證與 Cloud Billing 庫存同時點一致；不估價、不把 logical object sizes 當完整 Storage SKU/最短存放費用。
- 拿到即時證據後，分類：① 正常 canonical/Stage/Research 必留；② Iceberg 非 current／過期小檔**僅候選**，需 current catalog/hold/generation/7日/rollback/backup fence；③ 多代同檔（versioning 造成）應先核完整生命周期設定；④ 非 Janus Bucket 不自動清；⑤ 跨 bucket 2GB 對不上則需 billing SKU／跨 project/非 current/soft-deleted 的限界證據。**本次不執行任何刪除。**
