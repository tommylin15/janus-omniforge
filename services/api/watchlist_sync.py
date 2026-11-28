"""Atomic owner-scoped watchlist batch synchronization."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from .models import WatchlistSyncIn


def _to_decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _fetch_eligibility(connection: Any, symbols: list[str]) -> dict[str, bool]:
    if not symbols:
        return {}
    rows = connection.execute(
        """SELECT s.symbol,
                  (ip.instrument_kind IN ('ETF','BOND_ETF')) AS is_etf
           FROM control.stock_master s
           LEFT JOIN control.official_instrument_identity_provenance ip
             ON ip.symbol=s.symbol
           WHERE s.symbol=ANY(%s)
             AND s.enabled
             AND s.market IN ('TWSE','TPEX')
             AND (ip.instrument_kind IN ('ETF','BOND_ETF') OR EXISTS(
               SELECT 1 FROM control.market_universe_members m
               WHERE m.symbol=s.symbol AND m.version=(
                 SELECT version FROM control.market_universe_versions
                 WHERE effective_from<=now() ORDER BY effective_from DESC LIMIT 1)))""",
        (symbols,),
    ).fetchall()
    return {str(row["symbol"]): bool(row.get("is_etf")) for row in rows}


def _active_strategy_b_capacity(connection: Any, user_id: UUID) -> int | None:
    row = connection.execute(
        """SELECT p.rules
           FROM private.personal_strategy_state s
           JOIN private.personal_strategies p
             ON p.version_id=s.active_version AND p.user_id=s.user_id
           WHERE s.user_id=%s""",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    rules = row.get("rules")
    if not isinstance(rules, dict) or rules.get("b_capacity") is None:
        return None
    return int(rules["b_capacity"])


def _fetch_active_watchlist(connection: Any, user_id: UUID) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT symbol, tier, tier_confirmed, sync_locked, target_price, sort_order, version
           FROM private.watchlist
           WHERE user_id=%s AND active
           ORDER BY sort_order, symbol""",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def sync_watchlist(
    repository: Any,
    user_id: UUID,
    value: WatchlistSyncIn,
    key: str | None,
    *,
    conflict_error_cls: type[Exception],
) -> dict[str, Any]:
    if not value.dry_run and not key:
        raise ValueError("idempotency key is required")

    with repository._connection() as connection:
        if not value.dry_run:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('private-watchlist-symbol-limit'))")
            connection.execute("SELECT user_id FROM private.users WHERE user_id=%s FOR UPDATE", (user_id,))
            replay = repository._mutation(connection, user_id, key)
            if replay:
                items = _fetch_active_watchlist(connection, user_id)
                return {
                    "dry_run": False,
                    "applied": False,
                    "replayed": True,
                    "sync_id": replay["entity_id"],
                    "mode": value.mode,
                    "source": value.source,
                    "changed_count": 0,
                    "new_version": max((int(item["version"]) for item in items), default=0),
                    "items": items,
                }

        lock_clause = " FOR UPDATE" if not value.dry_run else ""
        existing_rows = connection.execute(
            f"SELECT * FROM private.watchlist WHERE user_id=%s{lock_clause}",
            (user_id,),
        ).fetchall()
        existing_by_symbol = {str(row["symbol"]): dict(row) for row in existing_rows}
        active_rows = {sym: row for sym, row in existing_by_symbol.items() if row.get("active")}
        current_version = max((int(row.get("version") or 0) for row in active_rows.values()), default=0)
        before_count = len(active_rows)

        version_conflict = value.expected_version is not None and current_version != value.expected_version
        if version_conflict and not value.dry_run:
            raise conflict_error_cls("watchlist version changed")

        need_eligibility = [item.symbol for item in value.items if item.symbol not in active_rows]
        eligible_info = _fetch_eligibility(connection, need_eligibility)
        invalid_symbols = [sym for sym in need_eligibility if sym not in eligible_info]
        if invalid_symbols and not value.dry_run:
            raise conflict_error_cls(f"stock is not in the current listed/OTC universe: {','.join(invalid_symbols)}")

        locked_symbols = {
            sym for sym, row in active_rows.items()
            if value.preserve_locked and bool(row.get("sync_locked"))
        }
        incoming_symbols = {item.symbol for item in value.items}

        added: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        preserved_locked: list[dict[str, Any]] = []
        unchanged: list[str] = []
        final_active: dict[str, dict[str, Any]] = {}

        if value.mode == "upsert_only":
            for sym, row in active_rows.items():
                if sym not in incoming_symbols:
                    final_active[sym] = {
                        "tier": str(row.get("tier") or "C"),
                        "target_price": _to_decimal_or_none(row.get("target_price")),
                        "sort_order": int(row.get("sort_order") or 0),
                    }

        for sym in sorted(locked_symbols):
            row = active_rows[sym]
            final_active[sym] = {
                "tier": str(row.get("tier") or "C"),
                "target_price": _to_decimal_or_none(row.get("target_price")),
                "sort_order": int(row.get("sort_order") or 0),
            }
            preserved_locked.append({
                "symbol": sym,
                "tier": str(row.get("tier") or "C"),
                "target_price": _format_decimal(_to_decimal_or_none(row.get("target_price"))),
                "sort_order": int(row.get("sort_order") or 0),
                "in_incoming": sym in incoming_symbols,
            })

        for idx, item in enumerate(value.items):
            sym = item.symbol
            if sym in locked_symbols:
                continue
            desired_order = item.sort_order if item.sort_order is not None else idx
            old = existing_by_symbol.get(sym)
            old_active = bool(old and old.get("active"))
            old_target = _to_decimal_or_none(old.get("target_price")) if old else None
            if value.update_target_price:
                if item.target_price is not None:
                    new_target = item.target_price
                elif value.clear_missing_target_price:
                    new_target = None
                else:
                    new_target = old_target
            else:
                new_target = old_target

            final_active[sym] = {
                "tier": item.tier,
                "target_price": new_target,
                "sort_order": desired_order,
            }

            if not old_active:
                added.append({
                    "symbol": sym,
                    "tier": item.tier,
                    "target_price": _format_decimal(new_target),
                    "sort_order": desired_order,
                })
                continue

            old_tier = str(old.get("tier") or "C")
            old_order = int(old.get("sort_order") or 0)
            old_confirmed = bool(old.get("tier_confirmed"))
            if (
                old_tier != item.tier
                or old_target != new_target
                or old_order != desired_order
                or not old_confirmed
            ):
                updated.append({
                    "symbol": sym,
                    "before": {
                        "tier": old_tier,
                        "target_price": _format_decimal(old_target),
                        "sort_order": old_order,
                    },
                    "after": {
                        "tier": item.tier,
                        "target_price": _format_decimal(new_target),
                        "sort_order": desired_order,
                    },
                })
            else:
                unchanged.append(sym)

        if value.mode == "mirror":
            for sym in sorted(active_rows):
                if sym not in incoming_symbols and sym not in locked_symbols:
                    row = active_rows[sym]
                    removed.append({
                        "symbol": sym,
                        "tier": str(row.get("tier") or "C"),
                        "target_price": _format_decimal(_to_decimal_or_none(row.get("target_price"))),
                    })

        capacity_error: str | None = None
        if len(final_active) > 50:
            capacity_error = "watchlist limit reached"
        else:
            other_global = {
                str(row["symbol"])
                for row in connection.execute(
                    "SELECT DISTINCT symbol FROM private.watchlist WHERE active AND user_id<>%s",
                    (user_id,),
                ).fetchall()
            }
            if len(other_global | set(final_active)) > 50:
                capacity_error = "deep-tracking symbol limit reached"
            else:
                b_capacity = _active_strategy_b_capacity(connection, user_id)
                if b_capacity is not None:
                    b_count = sum(1 for item in final_active.values() if item["tier"] == "B")
                    if b_count > b_capacity:
                        capacity_error = "B池已達策略容量"

        if capacity_error and not value.dry_run:
            raise conflict_error_cls(capacity_error)

        changed_count = len(added) + len(updated) + len(removed)
        if value.dry_run:
            return {
                "dry_run": True,
                "applied": False,
                "replayed": False,
                "mode": value.mode,
                "source": value.source,
                "before_count": before_count,
                "after_count": len(final_active),
                "current_version": current_version,
                "version_conflict": version_conflict,
                "invalid_symbols": invalid_symbols,
                "capacity_error": capacity_error,
                "changed_count": changed_count,
                "added": added,
                "updated": updated,
                "removed": removed,
                "preserved_locked": preserved_locked,
                "unchanged": unchanged,
            }

        sync_id = str(uuid4())
        for entry in removed:
            sym = entry["symbol"]
            connection.execute(
                """UPDATE private.watchlist
                   SET active=false, version=version+1, idempotency_key=%s, updated_at=now()
                   WHERE user_id=%s AND symbol=%s AND active""",
                (key, user_id, sym),
            )
            connection.execute("SELECT control.record_deep_tracking_demand(%s)", (sym,))

        for entry in added:
            sym = entry["symbol"]
            state = final_active[sym]
            connection.execute(
                """INSERT INTO private.watchlist(
                     user_id, symbol, target_price, sort_order, active, version, idempotency_key, tier, tier_confirmed
                   )
                   VALUES (%s, %s, %s, %s, true, 1, %s, %s, true)
                   ON CONFLICT (user_id, symbol) DO UPDATE SET
                     active=true,
                     tier=EXCLUDED.tier,
                     tier_confirmed=true,
                     sort_order=EXCLUDED.sort_order,
                     target_price=EXCLUDED.target_price,
                     version=private.watchlist.version+1,
                     idempotency_key=EXCLUDED.idempotency_key,
                     updated_at=now()""",
                (user_id, sym, state["target_price"], state["sort_order"], key, state["tier"]),
            )
            if not eligible_info.get(sym, False):
                connection.execute("SELECT control.record_deep_tracking_demand(%s)", (sym,))

        for entry in updated:
            sym = entry["symbol"]
            state = final_active[sym]
            connection.execute(
                """UPDATE private.watchlist
                   SET tier=%s,
                       tier_confirmed=true,
                       sort_order=%s,
                       target_price=%s,
                       version=version+1,
                       idempotency_key=%s,
                       updated_at=now()
                   WHERE user_id=%s AND symbol=%s AND active""",
                (state["tier"], state["sort_order"], state["target_price"], key, user_id, sym),
            )

        if changed_count > 0:
            change_version = repository._next_change_version(connection, user_id)
            repository._change(connection, user_id, change_version, "watchlist-sync", sync_id, None)
            repository._sync_supplement_demand(connection)
        repository._record_mutation(connection, user_id, key, "watchlist-sync", sync_id)

        final_items = _fetch_active_watchlist(connection, user_id)
        new_version = max((int(item["version"]) for item in final_items), default=current_version)
        return {
            "dry_run": False,
            "applied": True,
            "replayed": False,
            "sync_id": sync_id,
            "mode": value.mode,
            "source": value.source,
            "before_count": before_count,
            "after_count": len(final_active),
            "previous_version": current_version,
            "new_version": new_version,
            "changed_count": changed_count,
            "added": added,
            "updated": updated,
            "removed": removed,
            "preserved_locked": preserved_locked,
            "unchanged": unchanged,
            "items": final_items,
        }
