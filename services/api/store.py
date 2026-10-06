"""Private Iceberg storage for note bodies, normalized events and marts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from copy import deepcopy
from functools import lru_cache
from decimal import Decimal
from enum import Enum
import json
import os
from typing import Any, Iterable
from uuid import UUID


class PrivateIcebergStore:
    TABLE_KEYS = {
        "note_revisions": ("user_id", "note_id", "revision"),
        "ledger_events": ("user_id", "ledger_version"),
        "watchlist_events": ("user_id", "symbol", "change_version"),
        "investment_profile_revisions": ("user_id", "version"),
        "mart_user_positions": ("user_id", "symbol", "currency", "ledger_version", "valuation_date"),
        "mart_user_realized_pnl": ("user_id", "event_id", "ledger_version", "valuation_date"),
        "mart_user_unrealized_pnl": ("user_id", "symbol", "currency", "ledger_version", "valuation_date"),
        "mart_user_annual_pnl": ("user_id", "year", "currency", "ledger_version", "valuation_date"),
        "mart_user_monthly_ledger_summary": ("user_id", "year", "month", "currency", "ledger_version", "valuation_date"),
        "mart_user_symbol_ledger_summary": ("user_id", "year", "symbol", "currency", "ledger_version", "valuation_date"),
        "mart_user_exposure": ("user_id", "industry", "currency", "ledger_version", "valuation_date"),
        "mart_user_annual_performance": ("user_id", "year", "currency", "ledger_version", "valuation_date"),
        "mart_user_stress_tests": ("user_id", "scenario_id", "currency", "ledger_version", "valuation_date"),
        "mart_user_portfolio_summary": ("user_id", "currency", "ledger_version", "valuation_date"),
    }

    ADDITIVE_FIELDS = {
        "mart_user_positions": frozenset({"stock_name","identity_status","identity_missing_reason","missing_reason"}),
        "mart_user_unrealized_pnl": frozenset({"unrealized_return","price_date","missing_reason"}),
        "mart_user_portfolio_summary": frozenset({"unrealized_return","aggregate_status","affected_symbol_count","affected_symbols"}),
    }

    TRANSACTION_DERIVED_MARTS = frozenset({
        "mart_user_realized_pnl",
        "mart_user_annual_pnl",
        "mart_user_monthly_ledger_summary",
        "mart_user_symbol_ledger_summary",
    })
    VALUATION_MARTS = frozenset({
        "mart_user_positions",
        "mart_user_unrealized_pnl",
        "mart_user_exposure",
        "mart_user_annual_performance",
        "mart_user_stress_tests",
        "mart_user_portfolio_summary",
    })

    def __init__(self, catalog: Any, warehouse: str, namespace: str = "private",
                 operational: Any | None = None) -> None:
        self.catalog, self.warehouse, self.namespace = catalog, warehouse.rstrip("/"), namespace
        self.operational = operational
        catalog.create_namespace_if_not_exists(namespace)

    @classmethod
    def from_env(cls) -> "PrivateIcebergStore":
        from packages.postgres_bundle import load_postgres_bundle
        load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
            "PRIVATE_DATABASE_URL": "database_url",
            "PRIVATE_CATALOG_PASSWORD": "catalog_password",
            "CORE_CATALOG_PASSWORD": "core_catalog_password",
        })
        from pyiceberg.catalog.sql import SqlCatalog
        from sqlalchemy import URL
        from .repository import repository_from_env

        required = {name: os.getenv(name, "") for name in (
            "POSTGRES_HOST", "POSTGRES_DB", "PRIVATE_CATALOG_USER", "PRIVATE_CATALOG_PASSWORD",
            "PRIVATE_ICEBERG_WAREHOUSE", "GCP_PROJECT_ID",
        )}
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"missing Private Iceberg settings: {','.join(missing)}")
        uri = URL.create("postgresql+psycopg", username=required["PRIVATE_CATALOG_USER"],
                         password=required["PRIVATE_CATALOG_PASSWORD"], host=required["POSTGRES_HOST"], port=5432,
                         database=required["POSTGRES_DB"], query={"sslmode": os.getenv("POSTGRES_SSLMODE", "require"), "options": "-csearch_path=catalog"})
        catalog = SqlCatalog("janus-private", type="sql", uri=uri, warehouse=required["PRIVATE_ICEBERG_WAREHOUSE"],
                             init_catalog_tables="false", **{"py-io-impl":"pyiceberg.io.pyarrow.PyArrowFileIO",
                             "gcs.project-id":required["GCP_PROJECT_ID"], "pool_size":1, "max_overflow":0, "pool_timeout":5})
        return cls(catalog, required["PRIVATE_ICEBERG_WAREHOUSE"], operational=repository_from_env())

    def write_note(self, *, user_id: Any, note_id: Any, revision: int, body: str, symbol: str | None,
                   trade_event_id: str | None, needs_follow_up: bool) -> str:
        ref = f"private.note_revisions/{note_id}/{revision}"
        self.upsert("note_revisions", [{"user_id":str(user_id),"note_id":str(note_id),"revision":revision,"body":body,
                    "symbol":symbol,"trade_event_id":trade_event_id,"needs_follow_up":needs_follow_up,
                    "created_at":datetime.now(timezone.utc),"artifact_ref":ref}])
        return ref

    def read_notes(self, user_id: Any, indexes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        wanted = {row["artifact_ref"]: row for row in indexes}
        if not wanted: return []
        rows = self.rows("note_revisions", user_id)
        return [{**wanted[row["artifact_ref"]], **row} for row in rows if row.get("artifact_ref") in wanted]

    def mart(self, table: str, user_id: Any, **filters: Any) -> list[dict[str, Any]]:
        """Serve only marts that match the latest canonical ledger checkpoint.

        ``rows`` remains the raw persisted Iceberg read. This serving method adds a
        freshness gate so an older Private Mart snapshot is never presented as if it
        reflected a newer operational ledger mutation.
        """
        rows = self.rows(table, user_id, filters=filters)
        latest_rows: list[dict[str, Any]] = []
        if rows:
            latest=max((str(row.get("valuation_date","")),row.get("ledger_version",0)) for row in rows)
            latest_rows=[row for row in rows if (str(row.get("valuation_date","")),row.get("ledger_version",0))==latest]
        operational = getattr(self, "operational", None)
        if operational is None:
            return latest_rows
        freshness_tables = self.TRANSACTION_DERIVED_MARTS | self.VALUATION_MARTS
        if table not in freshness_tables:
            return latest_rows
        current_version = int(operational.latest_ledger_version(user_id))
        mart_version = max((int(row.get("ledger_version", 0) or 0) for row in latest_rows), default=-1)
        if mart_version == current_version:
            return latest_rows
        if table == "mart_user_portfolio_summary" and latest_rows:
            return self._withheld_summary(user_id, latest_rows, current_version)
        return []

    def _withheld_summary(self, user_id: Any, stale_rows: list[dict[str, Any]],
                          current_version: int) -> list[dict[str, Any]]:
        positions = list(self.operational.positions(user_id))
        stale_by_currency = {str(row.get("currency") or "TWD"): row for row in stale_rows}
        currencies = sorted(set(stale_by_currency) | {str(row.get("currency") or "TWD") for row in positions})
        result = []
        for currency in currencies:
            currency_positions = [row for row in positions if str(row.get("currency") or "TWD") == currency]
            stale = stale_by_currency.get(currency, {})
            symbols = sorted({str(row.get("symbol")) for row in currency_positions if row.get("symbol")})
            cost_basis = sum((Decimal(str(row.get("cost_basis") or 0)) for row in currency_positions), Decimal("0"))
            result.append({
                "user_id": str(user_id), "currency": currency,
                "market_value": None, "cost_basis": cost_basis, "unrealized_pnl": None,
                "unrealized_return": None, "aggregate_status": "withheld",
                "affected_symbol_count": len(symbols), "affected_symbols": symbols,
                "missing_price_count": len(symbols), "stale_price_count": 0,
                "valuation_status": "partial", "cash_safety_status": "insufficient_data",
                "cash_ratio": None, "minimum_cash_ratio": stale.get("minimum_cash_ratio"),
                "ledger_version": current_version,
                "valuation_date": stale.get("valuation_date") or self._today(),
            })
        return result

    @staticmethod
    def _today() -> date:
        from .private_pipeline import TAIPEI
        return datetime.now(TAIPEI).date()

    def rows(self, table: str, user_id: Any, limit: int | None = 200,
             filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        identifier = f"{self.namespace}.{table}"
        if not self.catalog.table_exists(identifier): return []
        if table in self.TRANSACTION_DERIVED_MARTS | self.VALUATION_MARTS and limit is not None:
            snapshot = self.catalog.load_table(identifier).current_snapshot()
            if snapshot is None: return []
            return deepcopy(self._snapshot_rows(identifier, snapshot.snapshot_id, str(user_id),
                                                min(limit, 200), tuple(sorted((filters or {}).items()))))
        return self._scan_rows(identifier, user_id, limit, filters or {})

    @lru_cache(maxsize=32)
    def _snapshot_rows(self, identifier: str, snapshot_id: int, user_id: str,
                       limit: int, filters: tuple) -> list[dict[str, Any]]:
        return self._scan_rows(identifier, user_id, limit, dict(filters), snapshot_id=snapshot_id)

    def _scan_rows(self, identifier: str, user_id: Any, limit: int | None,
                   filters: dict[str, Any], *, snapshot_id: int | None = None) -> list[dict[str, Any]]:
        from pyiceberg.expressions import And, EqualTo
        row_filter=EqualTo("user_id",str(user_id))
        for key,value in (filters or {}).items():
            row_filter=And(row_filter,EqualTo(key,value))
        scan_kwargs={"row_filter":row_filter, "snapshot_id":snapshot_id}
        if limit is not None: scan_kwargs["limit"]=min(limit,200)
        scan=self.catalog.load_table(identifier).scan(**scan_kwargs)
        return scan.to_arrow().to_pylist()

    def upsert(self, table_name: str, rows: list[dict[str, Any]]) -> int | None:
        if not rows: return None
        import pyarrow as pa

        identifier = f"{self.namespace}.{table_name}"
        normalized = [{key:self._value(value) for key,value in row.items()} for row in rows]
        inferred=pa.Table.from_pylist(normalized)
        incoming=pa.Table.from_pylist(normalized,schema=pa.schema([
            pa.field(field.name,pa.string() if pa.types.is_null(field.type) else field.type,nullable=True) for field in inferred.schema]))
        if not self.catalog.table_exists(identifier):
            table = self.catalog.create_table(identifier, incoming.schema,
                location=f"{self.warehouse}/{table_name}", properties={"format-version":"2"})
            with table.update_spec() as spec:
                spec.add_field("user_id", "bucket[32]")
        table = self.catalog.load_table(identifier)
        allowed=self.ADDITIVE_FIELDS.get(table_name,frozenset())
        existing={field.name for field in table.schema().fields}
        additions=[field for field in incoming.schema if field.name in allowed and field.name not in existing]
        schema_evolved=bool(additions)
        if schema_evolved:
            with table.update_schema() as update:
                update.union_by_name(pa.schema(additions))
            table=self.catalog.load_table(identifier)
        schema = table.schema().as_arrow()
        string_fields = {field.name for field in schema
                         if pa.types.is_string(field.type) or pa.types.is_large_string(field.type)}
        for row in normalized:
            for field in string_fields & row.keys():
                if isinstance(row[field], float):
                    row[field] = str(row[field])
        incoming = pa.Table.from_pylist(normalized, schema=schema)
        if schema_evolved:
            from functools import reduce
            from pyiceberg.expressions import And, EqualTo, Or
            predicates=[reduce(And,(EqualTo(key,row[key]) for key in self.TABLE_KEYS[table_name])) for row in normalized]
            overwrite_filter=reduce(Or,predicates) if len(predicates)>1 else predicates[0]
            table.overwrite(incoming, overwrite_filter=overwrite_filter)
        else:
            table.upsert(incoming, join_cols=list(self.TABLE_KEYS[table_name]))
        snapshot = self.catalog.load_table(identifier).current_snapshot()
        return snapshot.snapshot_id if snapshot else None

    def delete_user(self, user_id: Any) -> None:
        from pyiceberg.expressions import EqualTo
        for table_name in (*self.TABLE_KEYS, "context_snapshots", "assistant_events", "assistant_skill_revisions"):
            identifier=f"{self.namespace}.{table_name}"
            if self.catalog.table_exists(identifier):
                self.catalog.load_table(identifier).delete(EqualTo("user_id",str(user_id)))

    @staticmethod
    def _value(value: Any) -> Any:
        if isinstance(value, (UUID, Enum)): return str(value)
        if isinstance(value, Decimal): return str(value)
        if isinstance(value, datetime) and value.tzinfo is not None: return value.astimezone(timezone.utc)
        if isinstance(value, date) and not isinstance(value, datetime): return value.isoformat()
        return value
