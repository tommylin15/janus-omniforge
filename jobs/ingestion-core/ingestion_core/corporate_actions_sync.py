"""盤後公司行動（除權息）同步模組，掛載於既有統一盤後採集流程中。"""
from __future__ import annotations

from typing import Any, Callable

from packages.corporate_actions import (
    CorporateActionRecord,
    fetch_tpex_ex_dividend_preview,
    fetch_twse_ex_dividend_preview,
    merge_corporate_actions,
)


def _upsert_actions(cursor: Any, records: tuple[CorporateActionRecord, ...]) -> int:
    for item in records:
        cursor.execute(
            """INSERT INTO control.corporate_actions (
                   action_id, symbol, market, security_type, ex_date, payment_date,
                   action_type, cash_dividend_per_share, stock_dividend_ratio,
                   par_value, source_name, source_updated_at
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (symbol, ex_date, action_type) DO UPDATE SET
                   market = EXCLUDED.market,
                   security_type = EXCLUDED.security_type,
                   payment_date = COALESCE(EXCLUDED.payment_date, control.corporate_actions.payment_date),
                   cash_dividend_per_share = EXCLUDED.cash_dividend_per_share,
                   stock_dividend_ratio = EXCLUDED.stock_dividend_ratio,
                   par_value = EXCLUDED.par_value,
                   source_name = EXCLUDED.source_name,
                   source_updated_at = EXCLUDED.source_updated_at""",
            (
                item.action_id,
                item.symbol,
                item.market,
                item.security_type,
                item.ex_date,
                item.payment_date,
                item.action_type,
                item.cash_dividend_per_share,
                item.stock_dividend_ratio,
                item.par_value,
                item.source_name,
                item.source_updated_at,
            ),
        )
    return len(records)


def run_daily(
    *,
    transport: Callable[[str], bytes] | None = None,
    control: Any | None = None,
) -> dict[str, object]:
    """抓取 TWSE 與 TPEx 除權息資料並寫入 control.corporate_actions（失敗不覆蓋既有快照）。"""
    owns_control = control is None
    if control is None:
        from .__main__ import _control_plane

        control = _control_plane()

    try:
        with control._tx() as cur:
            cur.execute("SELECT to_regclass('control.corporate_actions')")
            row = cur.fetchone()
            if not row or row[0] is None:
                return {"status": "skipped", "reason": "schema_not_installed", "upserted_count": 0}

        # 於資料庫交易外抓取公開市場來源，單邊來源失敗不影響另一邊
        batches: list[tuple[CorporateActionRecord, ...]] = []
        source_errors: dict[str, str] = {}
        for name, fetcher in (
            ("twse", fetch_twse_ex_dividend_preview),
            ("tpex", fetch_tpex_ex_dividend_preview),
        ):
            try:
                batches.append(fetcher(transport=transport))
            except Exception as error:
                source_errors[name] = type(error).__name__[:64]

        if not batches:
            return {
                "status": "unavailable",
                "upserted_count": 0,
                "source_errors": source_errors,
            }

        merged = merge_corporate_actions(*batches)
        if not merged:
            return {
                "status": "partial" if source_errors else "succeeded",
                "upserted_count": 0,
                "source_errors": source_errors,
            }

        with control._tx() as cur:
            count = _upsert_actions(cur, merged)

        return {
            "status": "partial" if source_errors else "succeeded",
            "upserted_count": count,
            "source_errors": source_errors,
        }
    finally:
        if owns_control:
            control.close()
