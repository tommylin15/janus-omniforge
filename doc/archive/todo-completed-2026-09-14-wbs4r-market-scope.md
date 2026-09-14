# TODO 完成紀錄（2026-09-14：WBS-4R／市場範圍切片）

## 完成項目

- WBS-4R investment profile、Private Iceberg revision、effective-time exposure、typed
  XIRR、deterministic stress test、typed API 與 Flutter dashboard source／contract 完成。
- market-scope、coverage、screening 與去識別化 watchlist membership source／contract 完成；
  未觸發實際全市場抓取。
- PostgreSQL migration Cloud Build `f91eca7b-6147-4eec-87e7-245ede6300aa` 成功，使用
  immutable image `sha256:cdb9d546d2135b38d8dd695d245a68107a15fcb4da08f16fa15804834cab0c16`。
- `janus-api` dev revision `janus-api-00076-2sr`、100% traffic，API image digest
  `sha256:5de7428d15c2aebdf5757739c73ee587a97039936287d78eb397ad8e053d21b8`；API deploy
  build `348ba66d-2015-4faa-8b59-41424ed409f7` 成功。
- `janus-private-pipeline` secret wiring deploy build `194841bf-7b5c-4d6c-a2f1-ad780749acf9`
  成功；execution `janus-private-pipeline-8sj24` 成功。
- GCP dev API context／WBS-4R acceptance Cloud Build
  `de4d8e89-de83-4800-a108-7273a4aa4653` 成功。
- 本機相關 targeted pytest `49 passed`、shell `bash -n`、`git diff --check` 通過；Flutter
  Cloud Build `1d1ec15c-280b-48ec-afe7-ac8a6b007737` 成功。
- 驗收用 Secret accessor 與 service-account impersonation 暫時 IAM 均已撤銷；未部署
  production、未建立新 GCP 資源。

## 尚待條件

- WBS-3 Scheduler 5-stock canary 仍為 2/3；canary 3/3 前不得執行實際全市場抓取。
- 分 K／Tick、新聞、研究等來源仍須逐一完成授權與成本核准。
