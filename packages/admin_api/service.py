"""Admin operations over the existing control-plane repository.

This layer contains request-level bounds and safe response mapping.  It does
not execute collection work inline; enqueue methods only persist a queued
execution for a worker to claim later.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any
from urllib.parse import urlsplit
from urllib.parse import quote
from uuid import UUID


class AdminValidationError(ValueError):
    """Safe validation failure suitable for an API 4xx response."""


class AdminService:
    FUNDAMENTAL_DATASETS = frozenset({"financials"})
    REPORT_DATASETS = frozenset({"report", "reports", "mart-report", "mart_scoped_analysis"})

    def __init__(self, control: Any, *, core: Any | None = None, schedule_sync: Any | None = None) -> None:
        self.control = control
        self.core = core
        self.schedule_sync = schedule_sync

    def stocks(self, query: str = "", *, enabled: bool | None = None, limit: int = 50,
               cursor: str | None = None) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 101:
            raise AdminValidationError("limit must be between 1 and 101")
        if cursor is not None and not re.fullmatch(r"[A-Z0-9_-]{1,20}", cursor):
            raise AdminValidationError("stock cursor is invalid")
        return tuple(self._stock(item) for item in self.control.search_stocks(query, enabled=enabled, limit=limit, after=cursor))

    def set_stock_enabled(self, symbol: str, enabled: bool) -> None:
        self.control.set_stock_enabled(symbol, enabled)

    def upsert_stock(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate and persist one stock master record in one transaction."""
        from ingestion_core.control import Stock

        symbol = payload.get("symbol")
        name = payload.get("name")
        market = payload.get("market", "TWSE")
        if not isinstance(symbol, str) or not isinstance(name, str):
            raise AdminValidationError("symbol and name are required")
        if market not in {"TWSE", "TPEX"}:
            raise AdminValidationError("market is invalid")
        if not isinstance(payload.get("enabled", True), bool):
            raise AdminValidationError("enabled must be a boolean")
        listing_status = payload.get("listing_status", "unknown")
        if listing_status not in {"listed", "suspended", "delisted", "unknown"}:
            raise AdminValidationError("listing_status is invalid")
        stock = self.control.upsert_stock(Stock(
            symbol=symbol.strip().upper(), name=name.strip(), market=market,
            enabled=payload.get("enabled", True), listing_status=listing_status,
        ))
        return self._stock(stock)

    def stock_references(self, symbol: str) -> dict[str, Any]:
        references = self.control.stock_references(symbol)
        external = self._data_references(symbol)
        for key, value in external.items():
            references[key] += value
        return {"symbol": symbol.strip().upper(), "can_delete": not any(references.values()), "references": references}

    def delete_stock(self, symbol: str) -> None:
        # Control references are rechecked inside the delete transaction; Core
        # references are immutable and cannot appear without an execution ref.
        self.control.delete_stock(symbol, external_references=self._data_references(symbol))

    def _data_references(self, symbol: str) -> dict[str, int]:
        if self.core is None:
            raise RuntimeError("stock reference check unavailable")
        counts = {"market": 0, "report": 0, "fundamental": 0}
        for dataset_id, dataset in self.core.summary(symbol).get("datasets", {}).items():
            count = int(dataset.get("row_count", 0))
            if dataset_id in self.FUNDAMENTAL_DATASETS:
                counts["fundamental"] += count
            elif dataset_id in self.REPORT_DATASETS:
                counts["report"] += count
            else:
                counts["market"] += count
        return counts

    def executions(self, *, limit: int = 50, cursor: str | None = None) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 51:
            raise AdminValidationError("limit must be between 1 and 51")
        before = None
        if cursor is not None:
            try:
                requested_at, execution_id = cursor.rsplit(",", 1)
                point = datetime.fromisoformat(requested_at)
                UUID(execution_id)
                if point.tzinfo is None:
                    raise ValueError
                before = (point, execution_id)
            except (AttributeError, TypeError, ValueError) as error:
                raise AdminValidationError("execution cursor is invalid") from error
        return tuple(self._execution(item) for item in self.control.list_executions(limit=limit, before=before))

    def execution_details(self, execution_id: str) -> dict[str, Any]:
        execution = self.control.get_execution(execution_id)
        return {**self._execution(execution), "items": tuple(self._item(item) for item in self.control.list_items(execution_id))}

    def enqueue_collection(self, config_id: str, symbols: tuple[str, ...] | None = None, *, trace_id: str | None = None,
                           request_options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = self._collection_options(request_options or {})
        return self._execution(self.control.enqueue_collection(
            config_id, symbols, trace_id=trace_id, request_options=options,
        ))

    def enqueue_analysis(self, config_id: str, symbols: tuple[str, ...] | None = None, *, trace_id: str | None = None) -> dict[str, Any]:
        return self._execution(self.control.enqueue_analysis(config_id, symbols, trace_id=trace_id))

    def mart_reports(self, *, analysis_as_of: str = "", scope_type: str = "", scope_id: str = "",
                     role: str = "", prompt_version: str = "", analysis_outcome: str = "",
                     publication_status: str = "", limit: int = 50) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 100:
            raise AdminValidationError("limit must be between 1 and 100")
        if analysis_as_of and not self._iso_date(analysis_as_of):
            raise AdminValidationError("analysis_as_of must be an ISO date")
        allowed = {
            "scope_type": {"market", "industry", "symbol"},
            "role": {"fundamental", "valuation", "positioning", "quant", "event_risk"},
            "analysis_outcome": {"complete", "invalid", "review_required", "risk_blocked", "insufficient_data"},
            "publication_status": {"draft", "blocked", "publishable", "published", "superseded"},
        }
        for name, value in (("scope_type", scope_type), ("role", role), ("analysis_outcome", analysis_outcome),
                            ("publication_status", publication_status)):
            if value and value not in allowed[name]:
                raise AdminValidationError(f"{name} is invalid")
        if scope_id and not re.fullmatch(r"[\w.:-]{1,80}", scope_id):
            raise AdminValidationError("scope_id is invalid")
        if prompt_version and not re.fullmatch(r"[\w.:-]{1,80}", prompt_version):
            raise AdminValidationError("prompt_version is invalid")
        filters = {key: value for key, value in {
            "analysis_as_of": analysis_as_of, "scope_type": scope_type, "scope_id": scope_id,
            "prompt_version": prompt_version, "analysis_outcome": analysis_outcome,
            "publication_status": publication_status,
        }.items() if value}
        return tuple(self._report(item, role=role) for item in self.control.list_mart_reports(filters=filters, limit=limit))

    def membership(self, coverage_tier: str, *, as_of: datetime | None = None) -> tuple[dict[str, Any], ...]:
        return tuple({"coverage_tier": item.coverage_tier.value, "symbol": item.symbol, "effective_from": item.effective_from.isoformat(), "effective_to": item.effective_to.isoformat() if item.effective_to else None, "reason": item.reason, "owner": item.owner} for item in self.control.coverage_membership(coverage_tier, as_of=as_of))

    def membership_snapshot(self, coverage_tier: str) -> dict[str, Any]:
        version, effective_from = self.control.coverage_membership_revision(coverage_tier)
        return {"items": self.membership(coverage_tier), "version": version, "effective_from": effective_from.isoformat() if effective_from else None}

    def set_membership(self, coverage_tier: str, symbols: tuple[str, ...], *, effective_from: datetime, reason: str, owner: str,
                       expected_version: int | None = None) -> dict[str, Any]:
        self.control.set_coverage_membership(coverage_tier, symbols, effective_from=effective_from, reason=reason, owner=owner, expected_version=expected_version)
        return self.membership_snapshot(coverage_tier)

    def source_health(self, *, limit: int = 200, cursor: str | None = None) -> tuple[dict[str, Any], ...]:
        """Return persisted telemetry only; this method never calls an upstream source."""
        if not 1 <= limit <= 201:
            raise AdminValidationError("limit must be between 1 and 201")
        after = None
        if cursor is not None:
            try:
                after = tuple(cursor.rsplit(",", 1))
                if len(after) != 2 or any(not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", value) for value in after):
                    raise ValueError
            except (AttributeError, ValueError) as error:
                raise AdminValidationError("source health cursor is invalid") from error
        return tuple(self.control.source_health_summary(limit=limit, after=after))

    def collection_configs(self, *, limit: int = 200, cursor: str | None = None) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 201:
            raise AdminValidationError("limit must be between 1 and 201")
        if cursor is not None and not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", cursor):
            raise AdminValidationError("collection config cursor is invalid")
        return tuple(self._config(item) for item in self.control.list_collection_configs(limit=limit, after=cursor))

    def save_collection_config(self, payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
        from ingestion_core.control import CollectionConfig
        if not isinstance(actor, str) or not actor.strip():
            raise AdminValidationError("actor is required")
        required = ("config_id", "dataset_id", "source_ids")
        if any(not isinstance(payload.get(key), str if key != "source_ids" else list) for key in required):
            raise AdminValidationError("config_id, dataset_id and source_ids are required")
        try:
            config = CollectionConfig(
                payload["config_id"].strip(), payload["dataset_id"].strip(), tuple(payload["source_ids"]),
                frozenset(payload.get("expected_fields", [])), market=payload.get("market", "TWSE"),
                enabled=payload.get("enabled", True), collection_enabled=payload.get("collection_enabled", True),
                analysis_enabled=payload.get("analysis_enabled", True), lookback_days=payload.get("lookback_days", 30),
                overlap_days=payload.get("overlap_days", 2), full_refresh_interval_days=payload.get("full_refresh_interval_days", 0),
                batch_scope=payload.get("batch_scope", "market"), coverage_tier=payload.get("coverage_tier", "market_wide"),
                cadence=payload.get("cadence", "daily"), scope=payload.get("scope", "market"),
                authorization_status=payload.get("authorization_status", "official"), retention_class=payload.get("retention_class", "core_standard"),
                contains_pii=payload.get("contains_pii", False), republish_allowed=payload.get("republish_allowed", False), max_symbols=payload.get("max_symbols", 50),
            )
            if config.authorization_status in {"candidate", "blocked"} and config.enabled:
                raise AdminValidationError("candidate or blocked source cannot be enabled")
            if config.enabled and any(not self.control.source_is_approved(source_id) for source_id in config.source_ids):
                raise AdminValidationError("every enabled source requires an approved review")
            symbols = tuple(payload["symbols"]) if "symbols" in payload else None
            self.control.put_collection_config(config, symbols, actor=actor.strip())
            return self._config(config)
        except (TypeError, ValueError) as error:
            raise AdminValidationError(str(error)) from error

    def setting(self, key: str) -> dict[str, Any]:
        if not key or len(key) > 80:
            raise AdminValidationError("setting key is invalid")
        current = self.control.get_admin_setting(key)
        return {"key": key, "value": current[0] if current else None, "version": current[1] if current else 0}

    def save_setting(self, key: str, value: Any, *, actor: str, expected_version: int | None = None) -> dict[str, Any]:
        if not isinstance(actor, str) or not actor.strip():
            raise AdminValidationError("actor is required")
        if key.startswith("source_review:"):
            raise AdminValidationError("source reviews must use the review API")
        if key == "schedule" and (not isinstance(value, dict) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value.get("time", "")) or not isinstance(value.get("enabled", True), bool)):
            raise AdminValidationError("schedule requires time and enabled")
        if key == "schedule":
            holidays = value.get("holiday_overrides", [])
            if not isinstance(holidays, list) or len(holidays) > 100 or any(not self._iso_date(item) for item in holidays):
                raise AdminValidationError("holiday_overrides must contain at most 100 ISO dates")
        if key == "retention" and (not isinstance(value, dict) or not isinstance(value.get("cleanup_enabled"), bool) or not isinstance(value.get("days"), int) or not 1 <= value["days"] <= 3650):
            raise AdminValidationError("retention requires cleanup_enabled and days between 1 and 3650")
        if key == "source_config" and not isinstance(value, dict):
            raise AdminValidationError("source_config must be an object")
        current = self.control.get_admin_setting(key)
        scheduler = None
        if key == "schedule":
            if self.schedule_sync is None:
                raise AdminValidationError("Cloud Scheduler sync is unavailable")
            if current and expected_version is not None and current[1] != expected_version:
                raise AdminValidationError("setting has changed; reload before saving")
            scheduler = self.schedule_sync(value)
        try:
            version = self.control.put_admin_setting(key, value, actor=actor.strip(), expected_version=expected_version)
        except Exception:
            if key == "schedule" and current:
                self.schedule_sync(current[0])
            raise
        return {"key": key, "value": value, "version": version, **({"scheduler": scheduler} if scheduler else {})}

    def audit(self, *, limit: int = 50) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 50:
            raise AdminValidationError("limit must be between 1 and 50")
        return tuple(self.control.admin_audit(limit=limit))

    def source_review(self, adapter_id: str) -> dict[str, Any]:
        adapter = self._adapter_id(adapter_id)
        current = self.control.get_admin_setting(f"source_review:{adapter}")
        return {"adapter_id": adapter, "value": current[0] if current else None, "version": current[1] if current else 0}

    def save_source_review(self, adapter_id: str, payload: dict[str, Any], *, actor: str,
                           expected_version: int | None = None) -> dict[str, Any]:
        adapter = self._adapter_id(adapter_id)
        if not isinstance(payload, dict):
            raise AdminValidationError("review must be an object")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
            raise AdminValidationError("expected_version is required")
        status = payload.get("status", "candidate")
        if status not in {"candidate", "approved_fallback", "blocked"}:
            raise AdminValidationError("review status is invalid")
        checks = payload.get("checks")
        from ingestion_core.control import SOURCE_REVIEW_CHECKS
        required = SOURCE_REVIEW_CHECKS
        if not isinstance(checks, dict) or any(not isinstance(checks.get(key), bool) for key in required):
            raise AdminValidationError("review checks are incomplete")
        evidence_url = payload.get("evidence_url", "")
        reason = payload.get("reason", "")
        evidence = urlsplit(evidence_url) if isinstance(evidence_url, str) else None
        if not isinstance(evidence_url, str) or (evidence_url and (evidence.scheme != "https" or not evidence.hostname or evidence.username or evidence.password or evidence.query)):
            raise AdminValidationError("evidence_url must be a safe https URL without query parameters")
        if not isinstance(reason, str) or not reason.strip():
            raise AdminValidationError("review reason is required")
        if status == "approved_fallback" and (not all(checks[key] for key in required) or not evidence_url):
            raise AdminValidationError("all checks and evidence are required before approval")
        reviewer = actor.strip() if isinstance(actor, str) else ""
        if not reviewer:
            raise AdminValidationError("reviewer is required")
        value = {"adapter_id": adapter, "status": status, "checks": {key: checks[key] for key in required},
                 "evidence_url": evidence_url, "reviewer": reviewer, "reason": reason.strip(),
                 "decided_at": datetime.now(timezone.utc).isoformat()}
        version = self.control.put_admin_setting(f"source_review:{adapter}", value, actor=reviewer, expected_version=expected_version)
        return {"adapter_id": adapter, "value": value, "version": version}

    @staticmethod
    def _adapter_id(value: str) -> str:
        adapter = str(value).strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", adapter):
            raise AdminValidationError("adapter_id is invalid")
        return adapter

    @classmethod
    def _collection_options(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"date", "start_date", "end_date", "source_ids"}
        if not isinstance(value, dict) or set(value) - allowed:
            raise AdminValidationError("collection options are invalid")
        single, start, end = (value.get(key, "") for key in ("date", "start_date", "end_date"))
        if single and (start or end) or bool(start) != bool(end):
            raise AdminValidationError("use either date or a complete date range")
        if any(item and not cls._iso_date(item) for item in (single, start, end)):
            raise AdminValidationError("collection dates must be ISO dates")
        if start and (date.fromisoformat(end) - date.fromisoformat(start)).days not in range(367):
            raise AdminValidationError("backfill range must be ordered and at most 367 days")
        sources = value.get("source_ids", [])
        if not isinstance(sources, list) or len(sources) > 20 or any(not isinstance(item, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", item) for item in sources):
            raise AdminValidationError("source_ids are invalid")
        return {key: item for key, item in (("date", single), ("start_date", start), ("end_date", end), ("source_ids", sources)) if item}

    @staticmethod
    def _iso_date(value: Any) -> bool:
        try:
            date.fromisoformat(value)
            return isinstance(value, str)
        except (TypeError, ValueError):
            return False

    def stock_status(self, symbol: str) -> dict[str, Any]:
        if self.core is None:
            raise AdminValidationError("core status unavailable")
        summary = self.core.summary(symbol)
        items = []
        for dataset_id, dataset in summary.get("datasets", {}).items():
            null_profile = dataset.get("null_profile", {})
            row_count = int(dataset.get("row_count", 0))
            associations = dataset.get("associations", {})
            quality_flags = dataset.get("quality_flags", ())
            warning_count = dataset.get("warning_count", dataset.get("dq_warning_count", len(quality_flags)))
            quarantine_count = dataset.get("quarantined_count", dataset.get("quarantine_count"))
            coverage = dataset.get("coverage", {})
            received_symbols = int(coverage.get("received_symbols", 0))
            requested_symbols = int(coverage.get("requested_symbols", 1))
            freshness = dataset.get("freshness_state", dataset.get("freshness"))
            if not isinstance(freshness, (str, int, float, bool)):
                freshness = None
            items.append({
                "dataset_id": dataset_id,
                "latest_date": dataset.get("latest_date"),
                "row_count": row_count,
                "received_symbols": received_symbols,
                "requested_symbols": requested_symbols,
                "coverage_ratio": received_symbols / requested_symbols if requested_symbols else None,
                "null_count": sum(int(value) for value in null_profile.values()),
                "null_profile": tuple({
                    "field": field,
                    "count": int(count),
                    "ratio": int(count) / row_count if row_count else None,
                } for field, count in sorted(null_profile.items())),
                "quality_flags": tuple(quality_flags),
                "dq_warning_count": warning_count,
                "source_ids": tuple(associations.get("source_id", ())),
                "execution_ids": tuple(associations.get("execution_id", ())),
                "provenance_ids": tuple(associations.get("provenance_id", ())),
                "snapshot_ids": tuple(associations.get("snapshot_id", ())),
                "freshness": freshness,
                "updated_at": dataset.get("updated_at", dataset.get("materialized_at")),
                "quarantine_count": quarantine_count,
                "quarantine_state": "available" if quarantine_count is not None else "unavailable",
            })
        return {"symbol": summary.get("symbol", symbol), "items": tuple(sorted(items, key=lambda item: item["dataset_id"]))}

    @staticmethod
    def _config(config: Any) -> dict[str, Any]:
        result = {key: getattr(config, key) for key in (
            "config_id", "dataset_id", "source_ids", "expected_fields", "market", "enabled",
            "collection_enabled", "analysis_enabled", "lookback_days", "overlap_days",
            "full_refresh_interval_days", "batch_scope", "coverage_tier", "cadence", "scope",
            "authorization_status", "retention_class", "contains_pii", "republish_allowed", "max_symbols",
        )}
        result["expected_fields"] = tuple(sorted(result["expected_fields"]))
        return result

    @staticmethod
    def parse_datetime(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise AdminValidationError("effective_from must be an ISO-8601 datetime") from error
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _stock(stock: Any) -> dict[str, Any]:
        return {"symbol": stock.symbol, "name": stock.name, "market": stock.market, "enabled": stock.enabled, "listing_status": stock.listing_status, "updated_at": stock.updated_at.isoformat() if stock.updated_at else None, "effective_from": stock.effective_from.isoformat() if stock.effective_from else None}

    @staticmethod
    def _execution(execution: Any) -> dict[str, Any]:
        return {"execution_id": execution.execution_id, "trace_id": execution.trace_id, "config_id": execution.config_id, "trigger_type": execution.trigger_type.value, "status": execution.status.value, "requested_symbols": execution.requested_symbols, "request_options": execution.request_options, "requested_at": execution.requested_at.isoformat() if execution.requested_at else None, "started_at": execution.started_at.isoformat() if execution.started_at else None, "finished_at": execution.finished_at.isoformat() if execution.finished_at else None, "retry_count": execution.retry_count, "error_code": execution.error_code}

    @staticmethod
    def _report(report: dict[str, Any], *, role: str) -> dict[str, Any]:
        item = {key: value.isoformat() if isinstance(value, (date, datetime)) else value for key, value in report.items()}
        uri = urlsplit(str(item["artifact_uri"]))
        item["artifact_console_url"] = f"https://console.cloud.google.com/storage/browser/_details/{quote(uri.netloc)}/{quote(uri.path.lstrip('/'))}"
        item["selected_role"] = role or None
        return item

    @staticmethod
    def _item(item: Any) -> dict[str, Any]:
        return {"item_key": item.item_key, "source_id": item.source_id, "dataset_id": item.dataset_id, "state": item.state.value, "rows_received": item.rows_received, "retry_count": item.retry_count, "cache_hit": item.cache_hit, "is_fallback": item.is_fallback, "error_code": item.error_code, "safe_message": item.safe_message}
