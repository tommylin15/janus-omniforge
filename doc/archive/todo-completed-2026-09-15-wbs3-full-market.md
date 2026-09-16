# TODO 完成紀錄：WBS-3 full enabled market（2026-09-15）

## 範圍

使用者將當時 enabled universe 的 5 檔視為 full enabled market：
`1102`、`2327`、`2330`、`2381`、`4958`。沿用既有 market-scope 單次抓取與
symbol fan-out，複用 8 個核准 source／dataset；驗收用 config 完成後停用，保留 audit。

## 實際證據

- 首次 execution `janus-ingestion-core-rpwnz` 因 fallback query 未宣告 `s` alias 而以
  `UNDEFINEDTABLE` 失敗；`config_symbols()` 已修正為帶 alias 的 PostgreSQL query。
- Cloud Build `8f9e9ca1-8373-4fdb-af37-ff263f68528c` SUCCESS；image digest
  `sha256:248c170a8a1fe8422dd95ab078eb8d7259ab4ea22b9a86e32978c86d547bead2`。
- `python -m pytest -q tests/test_postgres_admin_cursor.py`：6 passed；`git diff --check` 通過。
- `FORCE_REFRESH=true` 實抓 execution `janus-ingestion-core-tf66g` SUCCESS（約 4:42）；
  control execution `2191139b-2dab-4bf4-886b-12735e6cdc02` 為 `succeeded`。
- `requested=8`、`staged=11`、`skipped=0`、`failed=0`、`empty=1`；FinMind financials
  `2381` 為唯一合法 empty，故 `expected=12`、`received=12`、`missing=0`、`failed=0`。
- Core `as_of=2026-09-14`、`row_count=1982`；snapshot id
  `sha256:8adc893ae302055caa227db8b22551cacdd13d59ebd938d84631af3c0aeafee3`。
  `analysis_enabled=false`，因此沒有 Mart 觸發；本次未選 OHLCV，不宣稱 OHLCV null-profile。

未部署 production、未建立新 GCP／付費資源；下一個 WBS 不在本次範圍。
