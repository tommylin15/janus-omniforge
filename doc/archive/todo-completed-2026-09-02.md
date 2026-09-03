# Janus — TODO 完成紀錄（2026-09-02）

## P0 — 五檔 canary runtime 閉環

- [x] 以既有 5 檔 canary 從 Admin 完成手動 Collection、指定日期 backfill、同日
  replay、failure／retry 與 Stage cleanup；每次均可追至 execution item、Stage
  manifest／quarantine、Core commit fence 與 terminal status。cleanup execution
  `4e134da7-2a6d-488f-a704-b9c78b1cb87d` 刪除三筆已成功且具 Core commit fence 的
  45 個 Stage objects，三個 immutable fence 均保留；retention 設定經 Admin audit
  後恢復 30 天。完整 execution、image 與驗收證據記錄於
  `spec/operations-and-testing.md`。
