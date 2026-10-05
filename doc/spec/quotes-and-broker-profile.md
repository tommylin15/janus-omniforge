# Operational Quote Router／Broker Profile

## 行情契約

`GET /api/v1/me/portfolio/quotes` 只依 authenticated owner 的
`private.current_positions` 取持股；不掃描 Private Mart，亦不接受 caller 指定 owner。
先讀 `control.operational_last_quotes`，再由 response background task 有界刷新。
最後成功值為可重建 operational model，與 Core OHLCV／EOD valuation 分離。

目前 `quote-router.v1` 只有既有 MIS route；沿用 `JANUS_MIS_QUOTES_ENABLED`
授權 gate，不啟用新來源或付費服務。未核准時 `refresh_status=blocked`。
regular session 依台北週一至週五 09:00–13:30 與既有 holiday overrides 判定；
calendar 無法讀取時 `closed_or_unknown`，不猜測開市。

- `quote_at`：成交時間；`received_at`：最後成功接收時間，非最新讀取時間。
- `source`／`route_version`：來源與版本；`checked_at`：本次讀取時間。
- 同日且成交距今 ≤120 秒為 available；其餘最後成功值為 stale。
- 尚無成功報價：missing；市場價格為 null，受影響 aggregate withheld，不補 0。
- 上游失敗、無成交、非法價格／時間不覆寫最後成功值；冷啟動仍從 DB 讀回。
- 舊成交不得覆寫較新成交。共享表不含 owner、持股數、成本或 user-symbol mapping。
- 沒有 persisted quote 時不把 EOD valuation 偽裝成盤中成交價；fallback 明示 missing。
- Background task 不承諾 durable delivery；失敗由下次 active page read 再嘗試。

正式 Private Mart valuation／PnL 不受此 operational 顯示影響。

## Broker Profile

`GET /api/v1/me/broker-profile` 回 owner 的最新 profile；尚無設定為 version 0。
`PUT` 要求 `Idempotency-Key`、`expected_version`，版本衝突回 409。
欄位：fee_discount_multiplier（0–1）、minimum_fee（非負 TWD）、
cash_strategy（reserve／balanced／invested）、declared_cash／cash_as_of（同時有值或皆 null）。
每次變更新增 immutable `private.broker_profile_revisions`，保留 rule_version、
版本、日期與 owner audit change；重送同 key 回原 revision。

申報現金是使用者手填 snapshot，**不是 canonical cash ledger balance**，
不參與正式 portfolio aggregate／cash ratio。設定不追溯改寫已儲存交易的 fee／tax。
目前沒有新增 CASH_IN／CASH_OUT，也沒有券商同步或成本法切換。
完整可稽核 cash ledger、profile fee 自動計算／交易 rule snapshot 尚未由此切片交付；
若其為 A 組所需 acceptance，狀態維持 partial，不以 profile CRUD 當成完成。

私人匯出包含完整 profile revisions；既有刪除 pipeline 在同一 owner 範圍清除 revisions。
共享 public quote 不屬私人資料，刪除 owner 不刪除它。UI 顯示申報現金／日期與版本，
讀取／儲存失敗可重試；不得把申報值呈現為正式餘額。

## 交付 gate

新增 migration 044；沿用既有 ingestion runtime 與 janus_control，無新 IAM／資源。
先部署 ingestion，再執行 044，API／Private Pipeline 部署依賴 migration success。
041／042／043 不因本切片重跑。
本文件與本機 tests 不構成 GCP migration／runtime／browser acceptance evidence。
