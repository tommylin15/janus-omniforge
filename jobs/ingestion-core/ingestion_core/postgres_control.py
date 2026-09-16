"""PostgreSQL control-plane adapter.

The adapter intentionally accepts an injected DB-API connection factory.  This
keeps imports and tests lightweight while allowing production to use psycopg3
or a small external pool.  One connection is held per repository instance;
callers should create bounded instances according to the connection budget.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Callable, Iterator
from uuid import NAMESPACE_URL, uuid4, uuid5

from .control import (
    AuthorizationStatus, CacheMetadata, CollectionConfig, ControlPlaneError, CoverageMembership, CoverageTier, Cursor, DataState,
    Execution, ExecutionItem, ExecutionStatus, InvalidTransitionError, SOURCE_AUTHORIZATION, SOURCE_REVIEW_CHECKS, Stock,
    StockInUseError, TriggerType, _analysis_options, _analysis_request, _iso, _parse_time, _symbol, utc_now,
)


class PostgreSQLControlPlane:
    """Transactional PostgreSQL repository for control metadata only."""

    def __init__(self, connection_factory: Callable[[], Any], *, statement_timeout_ms: int = 5000,
                 idle_in_transaction_timeout_ms: int = 10000) -> None:
        self.connection = connection_factory()
        self._closed = False
        if hasattr(self.connection, "autocommit"):
            self.connection.autocommit = True
        with self.connection.cursor() as cur:
            cur.execute("SELECT set_config('statement_timeout', %s, false)",
                        (f"{statement_timeout_ms}ms",))
            cur.execute("SELECT set_config('idle_in_transaction_session_timeout', %s, false)",
                        (f"{idle_in_transaction_timeout_ms}ms",))
        self.connection.commit()

    def close(self) -> None:
        if not self._closed:
            self.connection.close()
            self._closed = True

    @contextmanager
    def _tx(self) -> Iterator[Any]:
        transaction = getattr(self.connection, "transaction", None)
        if getattr(self.connection, "autocommit", False) and transaction is not None:
            with transaction(), self.connection.cursor() as cur:
                yield cur
            return
        try:
            with self.connection.cursor() as cur:
                yield cur
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def upsert_stock(self, stock: Stock) -> Stock:
        symbol = _symbol(stock.symbol)
        if not stock.name.strip() or stock.market not in {"TWSE", "TPEX"}:
            raise ValueError("stock name and market are invalid")
        if stock.listing_status not in {"listed", "suspended", "delisted", "unknown"}:
            raise ValueError("listing_status is invalid")
        timestamp = stock.updated_at or utc_now()
        effective_from = stock.effective_from or timestamp
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.stock_master(symbol,name,market,enabled,updated_at,listing_status,effective_from)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(symbol) DO UPDATE SET name=EXCLUDED.name,
                market=EXCLUDED.market,enabled=EXCLUDED.enabled,updated_at=EXCLUDED.updated_at,
                listing_status=EXCLUDED.listing_status,effective_from=EXCLUDED.effective_from""",
                (symbol, stock.name.strip(), stock.market, stock.enabled, timestamp, stock.listing_status, effective_from))
        return Stock(symbol, stock.name.strip(), stock.market, stock.enabled, timestamp, stock.listing_status, effective_from)

    def set_stock_enabled(self, symbol: str, enabled: bool) -> None:
        with self._tx() as cur:
            cur.execute("UPDATE control.stock_master SET enabled=%s,updated_at=now() WHERE symbol=%s", (enabled, _symbol(symbol)))
            if cur.rowcount != 1:
                raise KeyError("stock not found")

    def stock_references(self, symbol: str) -> dict[str, int]:
        symbol = _symbol(symbol)
        with self.connection.cursor() as cur:
            cur.execute("""SELECT
                (SELECT count(*) FROM control.collection_symbols WHERE symbol=%s),
                (SELECT count(*) FROM control.execution_symbols WHERE symbol=%s),
                (SELECT count(*) FROM control.coverage_memberships WHERE symbol=%s)""", (symbol, symbol, symbol))
            collection, execution, market = cur.fetchone()
        return {"collection_config": collection, "execution": execution, "market": market, "report": 0, "fundamental": 0}

    def delete_stock(self, symbol: str, *, external_references: dict[str, int] | None = None) -> None:
        symbol = _symbol(symbol)
        with self._tx() as cur:
            cur.execute("""SELECT
                (SELECT count(*) FROM control.collection_symbols WHERE symbol=%s),
                (SELECT count(*) FROM control.execution_symbols WHERE symbol=%s),
                (SELECT count(*) FROM control.coverage_memberships WHERE symbol=%s)""", (symbol, symbol, symbol))
            collection, execution, market = cur.fetchone()
            references = {"collection_config": collection, "execution": execution, "market": market, "report": 0, "fundamental": 0}
            for key, value in (external_references or {}).items():
                if key in references:
                    references[key] += int(value)
            if any(references.values()):
                raise StockInUseError(references)
            cur.execute("DELETE FROM control.stock_master WHERE symbol=%s", (symbol,))
            if cur.rowcount != 1:
                raise KeyError("stock not found")

    def search_stocks(self, query: str = "", *, enabled: bool | None = None, limit: int = 50,
                      after: str | None = None) -> tuple[Stock, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be 1..500")
        clauses = ["(symbol ILIKE %s OR name ILIKE %s)"]
        args: list[Any] = [f"%{query}%", f"%{query}%"]
        if enabled is not None:
            clauses.append("enabled=%s"); args.append(enabled)
        if after is not None:
            clauses.append("symbol>%s"); args.append(_symbol(after))
        args.append(limit)
        with self.connection.cursor() as cur:
            cur.execute(f"SELECT symbol,name,market,enabled,updated_at,listing_status,effective_from FROM control.stock_master WHERE {' AND '.join(clauses)} ORDER BY symbol LIMIT %s", args)
            return tuple(Stock(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in cur.fetchall())

    def put_collection_config(self, config: CollectionConfig, symbols: tuple[str, ...] | list[str] | None = None, *, actor: str | None = None) -> None:
        normalized_symbols = None if symbols is None else tuple(sorted({_symbol(value) for value in symbols}))
        if normalized_symbols is not None and config.coverage_tier == CoverageTier.CORE_FOCUS.value and len(normalized_symbols) > config.max_symbols:
            raise ControlPlaneError("core_focus collection exceeds max_symbols")
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.collection_configs(config_id,dataset_id,source_ids,expected_fields,market,enabled,collection_enabled,analysis_enabled,lookback_days,overlap_days,full_refresh_interval_days,batch_scope,coverage_tier,cadence,scope,authorization_status,retention_class,contains_pii,republish_allowed,max_symbols)
                VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(config_id) DO UPDATE SET dataset_id=EXCLUDED.dataset_id,source_ids=EXCLUDED.source_ids,expected_fields=EXCLUDED.expected_fields,market=EXCLUDED.market,enabled=EXCLUDED.enabled,collection_enabled=EXCLUDED.collection_enabled,analysis_enabled=EXCLUDED.analysis_enabled,lookback_days=EXCLUDED.lookback_days,overlap_days=EXCLUDED.overlap_days,full_refresh_interval_days=EXCLUDED.full_refresh_interval_days,batch_scope=EXCLUDED.batch_scope,coverage_tier=EXCLUDED.coverage_tier,cadence=EXCLUDED.cadence,scope=EXCLUDED.scope,authorization_status=EXCLUDED.authorization_status,retention_class=EXCLUDED.retention_class,contains_pii=EXCLUDED.contains_pii,republish_allowed=EXCLUDED.republish_allowed,max_symbols=EXCLUDED.max_symbols""",
                (config.config_id, config.dataset_id, json.dumps(config.source_ids), json.dumps(sorted(config.expected_fields)), config.market, config.enabled, config.collection_enabled, config.analysis_enabled, config.lookback_days, config.overlap_days, config.full_refresh_interval_days, config.batch_scope, config.coverage_tier, config.cadence, config.scope, config.authorization_status, config.retention_class, config.contains_pii, config.republish_allowed, config.max_symbols))
            if normalized_symbols is not None:
                cur.execute("DELETE FROM control.collection_symbols WHERE config_id=%s", (config.config_id,))
                for symbol in normalized_symbols:
                    cur.execute("INSERT INTO control.collection_symbols(config_id,symbol) VALUES (%s,%s)", (config.config_id, symbol))
            if actor:
                cur.execute("INSERT INTO control.admin_audit(action,resource,resource_key,actor,detail_json,created_at) VALUES ('update','collection_config',%s,%s,%s::jsonb,now())", (config.config_id, actor.strip(), json.dumps({"authorization_status": config.authorization_status, "enabled": config.enabled})))

    def get_collection_config(self, config_id: str) -> CollectionConfig:
        with self.connection.cursor() as cur:
            cur.execute("SELECT config_id,dataset_id,source_ids,expected_fields,market,enabled,collection_enabled,analysis_enabled,lookback_days,overlap_days,full_refresh_interval_days,batch_scope,coverage_tier,cadence,scope,authorization_status,retention_class,contains_pii,republish_allowed,max_symbols FROM control.collection_configs WHERE config_id=%s", (config_id,))
            r = cur.fetchone()
        if not r: raise KeyError("collection config not found")
        return CollectionConfig(r[0], r[1], tuple(r[2]), frozenset(r[3]), r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13], r[14], r[15], r[16], r[17], r[18], r[19])

    def list_collection_configs(self, *, limit: int = 200, after: str | None = None) -> tuple[CollectionConfig, ...]:
        if not 1 <= limit <= 201:
            raise ValueError("limit must be 1..201")
        with self.connection.cursor() as cur:
            clause = "WHERE config_id>%s" if after is not None else ""
            parameters = (after, limit) if after is not None else (limit,)
            cur.execute(f"SELECT config_id FROM control.collection_configs {clause} ORDER BY config_id LIMIT %s", parameters); ids = [r[0] for r in cur.fetchall()]
        return tuple(self.get_collection_config(item) for item in ids)

    def config_symbols(self, config_id: str, *, only_enabled: bool = True) -> tuple[str, ...]:
        config = self.get_collection_config(config_id)
        condition = " AND s.enabled" if only_enabled else ""
        with self.connection.cursor() as cur:
            if config.coverage_tier == CoverageTier.CORE_FOCUS.value:
                cur.execute("SELECT dm.symbol FROM control.active_deep_tracking_memberships dm JOIN control.stock_master s USING(symbol) WHERE true" + condition + " ORDER BY dm.symbol")
                rows = cur.fetchall()
            else:
                cur.execute(f"SELECT cs.symbol FROM control.collection_symbols cs JOIN control.stock_master s USING(symbol) WHERE cs.config_id=%s{condition} ORDER BY cs.symbol", (config_id,))
                rows = cur.fetchall()
            if not rows and config.coverage_tier == CoverageTier.MARKET_WIDE.value:
                cur.execute(f"SELECT s.symbol FROM control.stock_master s WHERE true{condition} ORDER BY s.symbol")
                rows = cur.fetchall()
            return tuple(r[0] for r in rows)

    def set_coverage_membership(self, coverage_tier: str, symbols: tuple[str, ...] | list[str], *, effective_from: datetime, reason: str, owner: str,
                                expected_version: int | None = None) -> tuple[CoverageMembership, ...]:
        if coverage_tier not in {item.value for item in CoverageTier}:
            raise ValueError("coverage_tier is invalid")
        if effective_from.tzinfo is None or not reason.strip() or not owner.strip():
            raise ValueError("effective_from, reason, and owner are required")
        normalized = tuple(sorted({_symbol(value) for value in symbols}))
        if coverage_tier == CoverageTier.CORE_FOCUS.value and len(normalized) > 50:
            raise ControlPlaneError("core_focus membership cannot exceed 50 symbols")
        with self._tx() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"coverage_membership:{coverage_tier}",))
            cur.execute("SELECT symbol FROM control.stock_master WHERE symbol=ANY(%s)", (list(normalized),))
            if {row[0] for row in cur.fetchall()} != set(normalized):
                raise KeyError("stock not found")
            cur.execute("SELECT COALESCE(MAX(version),0), MAX(effective_from) FROM control.coverage_membership_versions WHERE coverage_tier=%s", (coverage_tier,))
            version, current = cur.fetchone()
            if expected_version is not None and expected_version != version:
                raise ControlPlaneError("membership version conflict")
            if current is not None and effective_from <= current:
                raise ValueError("effective_from must be after the current membership")
            cur.execute("SELECT symbol FROM control.coverage_memberships WHERE coverage_tier=%s AND effective_to IS NULL", (coverage_tier,))
            previous = {row[0] for row in cur.fetchall()}
            version += 1
            cur.execute("UPDATE control.coverage_memberships SET effective_to=%s WHERE coverage_tier=%s AND effective_to IS NULL", (effective_from, coverage_tier))
            cur.executemany("INSERT INTO control.coverage_memberships(coverage_tier,symbol,effective_from,reason,owner) VALUES (%s,%s,%s,%s,%s)", [(coverage_tier, symbol, effective_from, reason.strip(), owner.strip()) for symbol in normalized])
            cur.execute("INSERT INTO control.coverage_membership_versions(coverage_tier,version,effective_from) VALUES (%s,%s,%s)", (coverage_tier, version, effective_from))
            detail = {"version": version, "effective_from": effective_from.isoformat(), "reason": reason.strip(), "added": sorted(set(normalized) - previous), "removed": sorted(previous - set(normalized))}
            cur.execute("INSERT INTO control.admin_audit(action,resource,resource_key,actor,detail_json,created_at) VALUES ('update','coverage_membership',%s,%s,%s::jsonb,now())", (coverage_tier, owner.strip(), json.dumps(detail)))
        return self.coverage_membership(coverage_tier, as_of=effective_from)

    def coverage_membership_revision(self, coverage_tier: str) -> tuple[int, datetime | None]:
        with self.connection.cursor() as cur:
            cur.execute("SELECT version,effective_from FROM control.coverage_membership_versions WHERE coverage_tier=%s ORDER BY version DESC LIMIT 1", (coverage_tier,))
            row = cur.fetchone()
            return (row[0], row[1]) if row else (0, None)

    def coverage_membership(self, coverage_tier: str, *, as_of: datetime | None = None) -> tuple[CoverageMembership, ...]:
        if coverage_tier not in {item.value for item in CoverageTier}:
            raise ValueError("coverage_tier is invalid")
        point = as_of or utc_now()
        if point.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        with self.connection.cursor() as cur:
            cur.execute("SELECT coverage_tier,symbol,effective_from,effective_to,reason,owner FROM control.coverage_memberships WHERE coverage_tier=%s AND effective_from<=%s AND (effective_to IS NULL OR effective_to>%s) ORDER BY symbol", (coverage_tier, point, point))
            return tuple(CoverageMembership(CoverageTier(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in cur.fetchall())

    def _enqueue(self, config_id: str, trigger: TriggerType, symbols: tuple[str, ...] | None,
                 trace_id: str | None, request_options: dict[str, Any] | None = None) -> Execution:
        config = self.get_collection_config(config_id)
        if not config.enabled or not getattr(config, f"{trigger.value}_enabled"):
            raise ControlPlaneError(f"{trigger.value} trigger is disabled")
        if config.authorization_status in {AuthorizationStatus.CANDIDATE.value, AuthorizationStatus.BLOCKED.value}:
            raise ControlPlaneError("collection source authorization is not approved")
        if any(not self.source_is_approved(source_id) for source_id in config.source_ids):
            raise ControlPlaneError("collection includes a candidate or blocked source")
        requested = tuple(sorted({_symbol(s) for s in (symbols if symbols is not None else self.config_symbols(config_id))}))
        if not requested: raise ControlPlaneError("no enabled stocks are selected")
        if config.coverage_tier == CoverageTier.CORE_FOCUS.value and len(requested) > config.max_symbols:
            raise ControlPlaneError("core_focus execution exceeds max_symbols")
        execution_id, correlation = uuid4(), trace_id or str(uuid4())
        with self._tx() as cur:
            cur.execute("SELECT symbol FROM control.stock_master WHERE symbol=ANY(%s)", (list(requested),))
            if {r[0] for r in cur.fetchall()} != set(requested): raise KeyError("stock not found")
            cur.execute("INSERT INTO control.executions(execution_id,trace_id,config_id,trigger_type,status,requested_symbols,request_options) VALUES (%s,%s,%s,%s,'queued',%s::jsonb,%s::jsonb)", (execution_id, correlation, config_id, trigger.value, json.dumps(requested), json.dumps(request_options or {})))
            cur.executemany("INSERT INTO control.execution_symbols(execution_id,symbol) VALUES (%s,%s)", [(execution_id, s) for s in requested])
        return self.get_execution(str(execution_id))

    def enqueue_collection(self, config_id: str, symbols: tuple[str, ...] | None = None, *, trace_id: str | None = None, request_options: dict[str, Any] | None = None) -> Execution: return self._enqueue(config_id, TriggerType.COLLECTION, symbols, trace_id, request_options)
    def enqueue_analysis(self, config_id: str, symbols: tuple[str, ...] | None = None, *, trace_id: str | None = None) -> Execution:
        with self.connection.cursor() as cur:
            cur.execute("SELECT payload FROM control.core_ready_events WHERE config_id=%s ORDER BY created_at DESC LIMIT 1", (config_id,))
            row = cur.fetchone()
        if row is None:
            raise ControlPlaneError("no successful Core snapshot is available for analysis")
        requested, options = _analysis_request(row[0], symbols)
        return self._enqueue(config_id, TriggerType.ANALYSIS, requested, trace_id, options)

    def source_is_approved(self, source_id: str) -> bool:
        baseline = SOURCE_AUTHORIZATION.get(source_id, AuthorizationStatus.BLOCKED)
        if baseline in {AuthorizationStatus.OFFICIAL, AuthorizationStatus.APPROVED_FALLBACK}:
            return True
        setting = self.get_admin_setting(f"source_review:{source_id}")
        if not setting or not isinstance(setting[0], dict):
            return False
        review = setting[0]
        checks = review.get("checks")
        return bool(
            review.get("status") == AuthorizationStatus.APPROVED_FALLBACK.value
            and isinstance(checks, dict) and all(checks.get(key) is True for key in SOURCE_REVIEW_CHECKS)
            and isinstance(review.get("evidence_url"), str) and review["evidence_url"].startswith("https://")
            and isinstance(review.get("reviewer"), str) and review["reviewer"].strip()
            and isinstance(review.get("reason"), str) and review["reason"].strip()
            and isinstance(review.get("decided_at"), str) and review["decided_at"]
        )

    def get_execution(self, execution_id: str) -> Execution:
        with self.connection.cursor() as cur:
            cur.execute("SELECT execution_id,trace_id,config_id,trigger_type,status,requested_symbols,requested_at,started_at,finished_at,retry_count,error_code,request_options FROM control.executions WHERE execution_id=%s", (execution_id,)); r = cur.fetchone()
        if not r: raise KeyError("execution not found")
        return self._execution(r)

    def list_executions(self, *, limit: int = 50,
                        before: tuple[datetime, str] | None = None) -> tuple[Execution, ...]:
        if not 1 <= limit <= 51: raise ValueError("limit must be 1..51")
        clause = ""
        parameters: tuple[Any, ...] = (limit,)
        if before is not None:
            clause = "WHERE (requested_at, execution_id) < (%s, %s::uuid)"
            parameters = (before[0], before[1], limit)
        with self.connection.cursor() as cur:
            cur.execute(f"SELECT execution_id,trace_id,config_id,trigger_type,status,requested_symbols,requested_at,started_at,finished_at,retry_count,error_code,request_options FROM control.executions {clause} ORDER BY requested_at DESC, execution_id DESC LIMIT %s", parameters)
            return tuple(self._execution(row) for row in cur.fetchall())

    def list_executions_by_trace(self, trace_id: str, *, limit: int = 20) -> tuple[Execution, ...]:
        if not trace_id.strip() or not 1 <= limit <= 50:
            raise ValueError("trace_id and limit 1..50 are required")
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT execution_id,trace_id,config_id,trigger_type,status,requested_symbols,requested_at,started_at,finished_at,retry_count,error_code,request_options FROM control.executions WHERE trace_id=%s ORDER BY requested_at,execution_id LIMIT %s",
                (trace_id, limit),
            )
            return tuple(self._execution(row) for row in cur.fetchall())

    @staticmethod
    def _execution(row: Any) -> Execution:
        return Execution(str(row[0]), str(row[1]), row[2], TriggerType(row[3]), ExecutionStatus(row[4]), tuple(row[5]), row[6], row[7], row[8], row[9], row[10], row[11])

    def cleanup_candidates(self, *, before: datetime, limit: int = 20) -> tuple[str, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        with self.connection.cursor() as cur:
            cur.execute("SELECT execution_id FROM control.executions WHERE status='succeeded' AND finished_at < %s ORDER BY finished_at LIMIT %s", (before, limit))
            return tuple(str(row[0]) for row in cur.fetchall())

    def list_mart_reports(self, *, filters: dict[str, str], limit: int = 50) -> tuple[dict[str, Any], ...]:
        fields = ("execution_id","analysis_as_of","scope_type","scope_id","core_snapshot_id","artifact_uri",
                  "artifact_hash","deterministic_hash","table_identifier","iceberg_snapshot_id","schema_version",
                  "feature_version","model_version","governance_snapshot_version","prompt_version","prompt_hash",
                  "completeness","confidence","data_quality","analysis_outcome","publication_status","created_at","ready_at")
        clauses, values = [], []
        for field, value in filters.items():
            if field not in {"execution_id","analysis_as_of","scope_type","scope_id","prompt_version","analysis_outcome","publication_status"}:
                raise ValueError("invalid Mart report filter")
            clauses.append(f"{field}=%s")
            values.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)
        with self.connection.cursor() as cur:
            cur.execute(
                f"SELECT {','.join(fields)} FROM publication.mart_report_index{where} ORDER BY analysis_as_of DESC,created_at DESC,execution_id DESC,scope_type,scope_id LIMIT %s",
                values,
            )
            return tuple(dict(zip(fields, row, strict=True)) for row in cur.fetchall())

    def review_mart_report(self, execution_id: str, scope_type: str, scope_id: str,
                           action: str, reason: str, actor: str) -> dict[str, Any]:
        if action not in {"block", "unblock"} or not reason.strip() or not actor.strip():
            raise ValueError("publication review action, reason and actor are required")
        with self._tx() as cur:
            cur.execute(
                "SELECT publication_status, updated_at FROM publication.review_mart_report(%s,%s,%s,%s)",
                (execution_id, scope_type, scope_id, action),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError("Mart report not found")
            cur.execute(
                "INSERT INTO control.admin_audit(action,resource,resource_key,actor,detail_json,created_at) "
                "VALUES (%s,%s,%s,%s,%s::jsonb,now())",
                (action, "mart_report_publication", f"{execution_id}:{scope_type}:{scope_id}", actor.strip(),
                 json.dumps({"reason": reason.strip(), "publication_status": row[0]}, ensure_ascii=False)),
            )
        return {"execution_id": execution_id, "scope_type": scope_type, "scope_id": scope_id,
                "publication_status": row[0], "reason": reason.strip(), "actor": actor.strip(),
                "updated_at": row[1]}

    def claim_execution(self, worker_id: str, *, trigger_type: TriggerType | None = None,
                        lease: timedelta = timedelta(minutes=5)) -> Execution | None:
        if not worker_id.strip() or lease <= timedelta(0):
            raise ValueError("worker_id and a positive lease are required")
        trigger_clause = " AND trigger_type=%s" if trigger_type is not None else ""
        parameters: tuple[Any, ...] = ((trigger_type.value,) if trigger_type is not None else ()) + (worker_id.strip(), f"{int(lease.total_seconds())} seconds")
        with self._tx() as cur:
            cur.execute(f"""WITH candidate AS (SELECT execution_id FROM control.executions WHERE status IN ('queued','retrying','running') AND (claimed_until IS NULL OR claimed_until < now()){trigger_clause} ORDER BY requested_at FOR UPDATE SKIP LOCKED LIMIT 1)
                UPDATE control.executions e SET status='running',claimed_by=%s,claimed_until=now()+%s::interval,started_at=COALESCE(started_at,now()) FROM candidate WHERE e.execution_id=candidate.execution_id RETURNING e.execution_id""", parameters)
            row = cur.fetchone()
        return self.get_execution(str(row[0])) if row else None

    def transition_execution(self, execution_id: str, status: ExecutionStatus, *, error_code: str | None = None, retry_count: int | None = None) -> Execution:
        current = self.get_execution(execution_id)
        allowed = {ExecutionStatus.QUEUED:{ExecutionStatus.RUNNING,ExecutionStatus.RETRYING,ExecutionStatus.FAILED},ExecutionStatus.RETRYING:{ExecutionStatus.RUNNING,ExecutionStatus.RETRYING,ExecutionStatus.FAILED},ExecutionStatus.RUNNING:{ExecutionStatus.SUCCEEDED,ExecutionStatus.PARTIAL,ExecutionStatus.FAILED,ExecutionStatus.RETRYING}}
        if status not in allowed.get(current.status, set()): raise InvalidTransitionError(f"cannot transition execution from {current.status} to {status}")
        with self._tx() as cur:
            cur.execute("UPDATE control.executions SET status=%s,started_at=COALESCE(started_at,CASE WHEN %s IN ('running','retrying') THEN now() END),finished_at=CASE WHEN %s IN ('succeeded','partial','failed') THEN now() END,retry_count=COALESCE(%s,retry_count),error_code=%s,claimed_by=NULL,claimed_until=NULL WHERE execution_id=%s", (status.value,status.value,status.value,retry_count,error_code,execution_id))
        return self.get_execution(execution_id)

    def complete_collection(self, execution_id: str, ready_event: dict[str, Any] | None = None) -> tuple[Execution, Execution | None]:
        """Atomically commit collection success and idempotently enqueue its Mart work."""
        analysis_id = uuid5(NAMESPACE_URL, f"janus:mart:{execution_id}") if ready_event else None
        with self._tx() as cur:
            cur.execute(
                "SELECT trace_id,config_id,status,requested_symbols FROM control.executions WHERE execution_id=%s FOR UPDATE",
                (execution_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError("execution not found")
            trace_id, config_id, status, requested = row
            if ready_event and (ready_event.get("executionId") != execution_id or ready_event.get("configId") != config_id):
                raise ControlPlaneError("Core ready event does not match its collection execution")
            options = _analysis_options(ready_event) if ready_event else None
            cur.execute("SELECT analysis_execution_id,payload FROM control.core_ready_events WHERE core_execution_id=%s", (execution_id,))
            existing = cur.fetchone()
            if status == "succeeded" and existing:
                if ready_event is not None and existing[1] != ready_event:
                    raise ControlPlaneError("immutable Core ready event conflict")
                analysis_id = existing[0]
            elif status != "running":
                raise InvalidTransitionError(f"cannot complete collection from {status}")
            else:
                cur.execute(
                    "UPDATE control.executions SET status='succeeded',finished_at=now(),claimed_by=NULL,claimed_until=NULL WHERE execution_id=%s",
                    (execution_id,),
                )
                if ready_event:
                    cur.execute("SELECT analysis_enabled FROM control.collection_configs WHERE config_id=%s", (config_id,))
                    if not cur.fetchone()[0]:
                        analysis_id = None
                    if analysis_id:
                        cur.execute(
                            "INSERT INTO control.executions(execution_id,trace_id,config_id,trigger_type,status,requested_symbols,request_options) VALUES(%s,%s,%s,'analysis','queued',%s::jsonb,%s::jsonb)",
                            (analysis_id, trace_id, config_id, json.dumps(requested), json.dumps(options)),
                        )
                        cur.executemany(
                            "INSERT INTO control.execution_symbols(execution_id,symbol) VALUES(%s,%s)",
                            [(analysis_id, symbol) for symbol in requested],
                        )
                    cur.execute(
                        "INSERT INTO control.core_ready_events(core_execution_id,analysis_execution_id,config_id,payload) VALUES(%s,%s,%s,%s::jsonb)",
                        (execution_id, analysis_id, config_id, json.dumps(ready_event, sort_keys=True, separators=(",", ":"))),
                    )
        return self.get_execution(execution_id), self.get_execution(str(analysis_id)) if analysis_id else None

    def save_item(self, item: ExecutionItem) -> None:
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.execution_items(execution_id,item_key,source_id,dataset_id,state,rows_received,retry_count,cache_hit,is_fallback,error_code,safe_message)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(execution_id,item_key) DO UPDATE SET source_id=EXCLUDED.source_id,dataset_id=EXCLUDED.dataset_id,state=EXCLUDED.state,rows_received=EXCLUDED.rows_received,retry_count=EXCLUDED.retry_count,cache_hit=EXCLUDED.cache_hit,is_fallback=EXCLUDED.is_fallback,error_code=EXCLUDED.error_code,safe_message=EXCLUDED.safe_message""",
                (item.execution_id,item.item_key,item.source_id,item.dataset_id,item.state.value,item.rows_received,item.retry_count,item.cache_hit,item.is_fallback,item.error_code,item.safe_message))

    def list_items(self, execution_id: str) -> tuple[ExecutionItem, ...]:
        with self.connection.cursor() as cur:
            cur.execute("SELECT execution_id,item_key,source_id,dataset_id,state,rows_received,retry_count,cache_hit,is_fallback,error_code,safe_message FROM control.execution_items WHERE execution_id=%s ORDER BY item_key", (execution_id,))
            return tuple(ExecutionItem(str(r[0]),r[1],r[2],r[3],DataState(r[4]),r[5],r[6],r[7],r[8],r[9],r[10]) for r in cur.fetchall())

    def source_health_summary(self, *, source_id: str | None = None, dataset_id: str | None = None,
                              limit: int = 200, after: tuple[str, str] | None = None) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 201:
            raise ValueError("limit must be 1..201")
        clauses, values = [], []
        if source_id is not None:
            clauses.append("source_id=%s"); values.append(source_id)
        if dataset_id is not None:
            clauses.append("dataset_id=%s"); values.append(dataset_id)
        if after is not None:
            clauses.append("(source_id, dataset_id) > (%s, %s)")
            values.extend(after)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)
        with self.connection.cursor() as cur:
            cur.execute(f"SELECT source_id,dataset_id,success_count,failure_count,total_latency_ms,last_fetched_at,latest_observation_at,last_state,expected_symbols,received_symbols,cache_hits,fallback_count,schema_drift_count,coverage_tier,last_cache_age_seconds FROM control.source_health{where} ORDER BY source_id,dataset_id LIMIT %s", values)
            rows = cur.fetchall()
        return tuple({"source_id": r[0], "dataset_id": r[1], "success_rate": r[2] / (r[2] + r[3]) if r[2] + r[3] else 0.0, "average_latency_ms": r[4] / (r[2] + r[3]) if r[2] + r[3] else 0.0, "last_fetched_at": r[5], "latest_observation_at": r[6], "last_state": r[7], "expected_symbols": r[8], "received_symbols": r[9], "missing_symbols": max(0,r[8]-r[9]), "cache_hits": r[10], "fallback_count": r[11], "schema_drift_count": r[12], "coverage_tier": r[13], "cache_age_seconds": r[14]} for r in rows)

    def get_cursor(self, cursor_key: str) -> Cursor:
        with self.connection.cursor() as cur:
            cur.execute("SELECT last_observed_at,last_success_at FROM control.collection_cursors WHERE cursor_key=%s", (cursor_key,)); r = cur.fetchone()
        return Cursor(cursor_key, r[0] if r else None, r[1] if r else None)

    def advance_cursor(self, cursor_key: str, observed_at: datetime, *, successful: bool) -> None:
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.collection_cursors(cursor_key,last_observed_at,last_success_at) VALUES (%s,%s,%s)
                ON CONFLICT(cursor_key) DO UPDATE SET last_observed_at=GREATEST(control.collection_cursors.last_observed_at,EXCLUDED.last_observed_at),last_success_at=CASE WHEN EXCLUDED.last_success_at IS NOT NULL THEN EXCLUDED.last_success_at ELSE control.collection_cursors.last_success_at END""", (cursor_key, observed_at, observed_at if successful else None))

    def record_health(self, source_id: str, dataset_id: str, *, state: DataState, latency_ms: float, fetched_at: datetime, latest_observation_at: datetime | None = None, expected_symbols: int = 0, received_symbols: int = 0, cache_hit: bool = False, coverage_tier: str = CoverageTier.MARKET_WIDE.value, cache_age_seconds: float | None = None) -> None:
        success = state in {DataState.SUCCESS, DataState.FALLBACK, DataState.PARTIAL}
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.source_health(source_id,dataset_id,success_count,failure_count,total_latency_ms,last_fetched_at,latest_observation_at,last_state,expected_symbols,received_symbols,cache_hits,fallback_count,schema_drift_count,coverage_tier,last_cache_age_seconds) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(source_id,dataset_id) DO UPDATE SET success_count=control.source_health.success_count+EXCLUDED.success_count,failure_count=control.source_health.failure_count+EXCLUDED.failure_count,total_latency_ms=control.source_health.total_latency_ms+EXCLUDED.total_latency_ms,last_fetched_at=EXCLUDED.last_fetched_at,latest_observation_at=COALESCE(EXCLUDED.latest_observation_at,control.source_health.latest_observation_at),last_state=EXCLUDED.last_state,expected_symbols=EXCLUDED.expected_symbols,received_symbols=EXCLUDED.received_symbols,cache_hits=control.source_health.cache_hits+EXCLUDED.cache_hits,fallback_count=control.source_health.fallback_count+EXCLUDED.fallback_count,schema_drift_count=control.source_health.schema_drift_count+EXCLUDED.schema_drift_count,coverage_tier=EXCLUDED.coverage_tier,last_cache_age_seconds=EXCLUDED.last_cache_age_seconds""", (source_id,dataset_id,int(success),int(not success),latency_ms,fetched_at,latest_observation_at,state.value,expected_symbols,received_symbols,int(cache_hit),int(state == DataState.FALLBACK),int(state == DataState.SCHEMA_DRIFT),coverage_tier,cache_age_seconds))

    def source_health(self, source_id: str, dataset_id: str) -> dict[str, Any] | None:
        with self.connection.cursor() as cur:
            cur.execute("SELECT success_count,failure_count,total_latency_ms,last_fetched_at,latest_observation_at,last_state,expected_symbols,received_symbols,cache_hits,fallback_count,schema_drift_count,coverage_tier,last_cache_age_seconds FROM control.source_health WHERE source_id=%s AND dataset_id=%s", (source_id,dataset_id)); r = cur.fetchone()
        if not r: return None
        total = r[0] + r[1]
        return {"source_id":source_id,"dataset_id":dataset_id,"success_rate":r[0]/total if total else 0.0,"average_latency_ms":r[2]/total if total else 0.0,"last_fetched_at":r[3],"latest_observation_at":r[4],"last_state":r[5],"expected_symbols":r[6],"received_symbols":r[7],"missing_symbols":max(0,r[6]-r[7]),"cache_hits":r[8],"fallback_count":r[9],"schema_drift_count":r[10],"coverage_tier":r[11],"cache_age_seconds":r[12]}

    def get_admin_setting(self, key: str) -> tuple[Any, int] | None:
        with self.connection.cursor() as cur:
            cur.execute("SELECT value_json,version FROM control.admin_settings WHERE setting_key=%s", (key,)); row = cur.fetchone()
        return (row[0], row[1]) if row else None

    def put_admin_setting(self, key: str, value: Any, *, actor: str, expected_version: int | None = None,
                          audit_resource: str = "admin_setting", audit_detail: dict[str, Any] | None = None) -> int:
        if expected_version is not None and (isinstance(expected_version, bool) or expected_version < 0):
            raise ControlPlaneError("expected version must be non-negative")
        detail = dict(audit_detail or {})
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO control.admin_settings(setting_key,value_json,version,updated_at,updated_by)
                   VALUES (%s,%s::jsonb,1,now(),%s)
                   ON CONFLICT(setting_key) DO UPDATE SET value_json=EXCLUDED.value_json,
                       version=control.admin_settings.version+1,updated_at=now(),updated_by=EXCLUDED.updated_by
                   WHERE %s IS NULL OR control.admin_settings.version=%s
                   RETURNING version""",
                (key, json.dumps(value, ensure_ascii=False), actor.strip(), expected_version, expected_version),
            )
            row = cur.fetchone()
            if not row:
                raise ControlPlaneError("setting has changed; reload before saving")
            version = row[0]
            detail["version"] = version
            cur.execute("INSERT INTO control.admin_audit(action,resource,resource_key,actor,detail_json,created_at) VALUES ('update',%s,%s,%s,%s::jsonb,now())", (audit_resource, key.removeprefix("governance:"), actor.strip(), json.dumps(detail, ensure_ascii=False)))
        return version

    def admin_audit(self, *, limit: int = 50) -> tuple[dict[str, Any], ...]:
        with self.connection.cursor() as cur:
            cur.execute("SELECT action,resource,resource_key,actor,detail_json,created_at FROM control.admin_audit ORDER BY created_at DESC,audit_id DESC LIMIT %s", (limit,)); rows = cur.fetchall()
        return tuple({"action": r[0], "resource": r[1], "resource_key": r[2], "actor": r[3], "detail": r[4], "created_at": r[5]} for r in rows)

    def governance_history(self, governance_key: str, *, limit: int = 50) -> tuple[dict[str, Any], ...]:
        with self.connection.cursor() as cur:
            cur.execute("SELECT action,resource,resource_key,actor,detail_json,created_at FROM control.admin_audit WHERE resource='governance' AND resource_key=%s ORDER BY created_at DESC,audit_id DESC LIMIT %s", (governance_key, limit)); rows = cur.fetchall()
        return tuple({"action": r[0], "resource": r[1], "resource_key": r[2], "actor": r[3], "detail": r[4], "created_at": r[5]} for r in rows)

    def put_cache(self, *_: Any, **__: Any) -> None:
        raise ControlPlaneError("PostgreSQL stores cache metadata only; write the response to GCS and call put_cache_metadata")

    def get_cache(self, *_: Any, **__: Any) -> None:
        raise ControlPlaneError("PostgreSQL stores cache metadata only; read the response from GCS using get_cache_metadata")

    def put_cache_metadata(self, metadata: CacheMetadata) -> None:
        if not metadata.payload_uri.startswith("gs://"): raise ValueError("payload_uri must be a gs:// URI")
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.response_cache(cache_key,source_id,dataset_id,payload_uri,content_hash,fetched_at,expires_at,observed_at,state) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(cache_key) DO UPDATE SET payload_uri=EXCLUDED.payload_uri,content_hash=EXCLUDED.content_hash,fetched_at=EXCLUDED.fetched_at,expires_at=EXCLUDED.expires_at,observed_at=EXCLUDED.observed_at,state=EXCLUDED.state""", (metadata.cache_key,metadata.source_id,metadata.dataset_id,metadata.payload_uri,metadata.content_hash,metadata.fetched_at,metadata.expires_at,metadata.observed_at,metadata.state.value))

    def get_cache_metadata(self, cache_key: str, *, now: datetime | None = None) -> CacheMetadata | None:
        with self.connection.cursor() as cur:
            cur.execute("SELECT cache_key,source_id,dataset_id,payload_uri,content_hash,fetched_at,expires_at,observed_at,state FROM control.response_cache WHERE cache_key=%s AND expires_at>%s", (cache_key, now or utc_now())); r = cur.fetchone()
        return CacheMetadata(*r[:7], r[7], DataState(r[8])) if r else None

    def prune(self, *, before: datetime, batch_size: int = 500) -> dict[str, int]:
        counts = {}
        with self._tx() as cur:
            for table, column in (("response_cache","expires_at"),("executions","requested_at"),("source_health","last_fetched_at")):
                cur.execute(f"DELETE FROM control.{table} WHERE {column} < %s", (before,)); counts[table] = cur.rowcount
        return counts

    def __enter__(self) -> "PostgreSQLControlPlane": return self
    def __exit__(self, *_: object) -> None: self.close()
