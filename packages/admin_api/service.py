"""Admin operations over the existing control-plane repository.

This layer contains request-level bounds and safe response mapping.  It does
not execute collection work inline; enqueue methods only persist a queued
execution for a worker to claim later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class AdminValidationError(ValueError):
    """Safe validation failure suitable for an API 4xx response."""


class AdminService:
    def __init__(self, control: Any, *, core: Any | None = None) -> None:
        self.control = control
        self.core = core

    def stocks(self, query: str = "", *, enabled: bool | None = None, limit: int = 50, offset: int = 0) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 500 or offset < 0:
            raise AdminValidationError("limit or offset is invalid")
        return tuple(self._stock(item) for item in self.control.search_stocks(query, enabled=enabled, limit=limit, offset=offset))

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

    def delete_stock(self, symbol: str) -> None:
        # The control-plane FK/reference guard is authoritative and deliberately
        # maps to a safe domain error at the HTTP boundary.
        self.control.delete_stock(symbol)

    def executions(self, *, limit: int = 50) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 50:
            raise AdminValidationError("limit must be between 1 and 50")
        return tuple(self._execution(item) for item in self.control.list_executions(limit=limit))

    def execution_details(self, execution_id: str) -> dict[str, Any]:
        execution = self.control.get_execution(execution_id)
        return {**self._execution(execution), "items": tuple(self._item(item) for item in self.control.list_items(execution_id))}

    def enqueue_collection(self, config_id: str, symbols: tuple[str, ...] | None = None, *, trace_id: str | None = None) -> dict[str, Any]:
        return self._execution(self.control.enqueue_collection(config_id, symbols, trace_id=trace_id))

    def enqueue_analysis(self, config_id: str, symbols: tuple[str, ...] | None = None, *, trace_id: str | None = None) -> dict[str, Any]:
        return self._execution(self.control.enqueue_analysis(config_id, symbols, trace_id=trace_id))

    def membership(self, coverage_tier: str, *, as_of: datetime | None = None) -> tuple[dict[str, Any], ...]:
        return tuple({"coverage_tier": item.coverage_tier.value, "symbol": item.symbol, "effective_from": item.effective_from.isoformat(), "effective_to": item.effective_to.isoformat() if item.effective_to else None, "reason": item.reason, "owner": item.owner} for item in self.control.coverage_membership(coverage_tier, as_of=as_of))

    def set_membership(self, coverage_tier: str, symbols: tuple[str, ...], *, effective_from: datetime, reason: str, owner: str) -> tuple[dict[str, Any], ...]:
        return tuple({"coverage_tier": item.coverage_tier.value, "symbol": item.symbol, "effective_from": item.effective_from.isoformat(), "effective_to": item.effective_to.isoformat() if item.effective_to else None, "reason": item.reason, "owner": item.owner} for item in self.control.set_coverage_membership(coverage_tier, symbols, effective_from=effective_from, reason=reason, owner=owner))

    def source_health(self) -> tuple[dict[str, Any], ...]:
        """Return persisted telemetry only; this method never calls an upstream source."""
        return tuple(self.control.source_health_summary())

    def collection_configs(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._config(item) for item in self.control.list_collection_configs())

    def save_collection_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        from ingestion_core.control import CollectionConfig
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
            symbols = tuple(payload.get("symbols", []))
            self.control.put_collection_config(config, symbols)
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
        if key == "schedule" and (not isinstance(value, dict) or not isinstance(value.get("time"), str) or not isinstance(value.get("enabled", True), bool)):
            raise AdminValidationError("schedule requires time and enabled")
        if key == "retention" and (not isinstance(value, dict) or not isinstance(value.get("cleanup_enabled"), bool) or not isinstance(value.get("days"), int) or not 1 <= value["days"] <= 3650):
            raise AdminValidationError("retention requires cleanup_enabled and days between 1 and 3650")
        if key == "source_config" and not isinstance(value, dict):
            raise AdminValidationError("source_config must be an object")
        version = self.control.put_admin_setting(key, value, actor=actor.strip(), expected_version=expected_version)
        return {"key": key, "value": value, "version": version}

    def audit(self, *, limit: int = 50) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 50:
            raise AdminValidationError("limit must be between 1 and 50")
        return tuple(self.control.admin_audit(limit=limit))

    def stock_status(self, symbol: str) -> dict[str, Any]:
        if self.core is None:
            raise AdminValidationError("core status unavailable")
        return {"symbol": symbol, "summary": self.core.summary(symbol)}

    @staticmethod
    def _config(config: Any) -> dict[str, Any]:
        return {"config_id": config.config_id, "dataset_id": config.dataset_id, "source_ids": config.source_ids, "enabled": config.enabled, "collection_enabled": config.collection_enabled, "analysis_enabled": config.analysis_enabled, "coverage_tier": config.coverage_tier, "cadence": config.cadence, "scope": config.scope, "authorization_status": config.authorization_status, "retention_class": config.retention_class, "max_symbols": config.max_symbols}

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
        return {"execution_id": execution.execution_id, "trace_id": execution.trace_id, "config_id": execution.config_id, "trigger_type": execution.trigger_type.value, "status": execution.status.value, "requested_symbols": execution.requested_symbols, "requested_at": execution.requested_at.isoformat() if execution.requested_at else None, "started_at": execution.started_at.isoformat() if execution.started_at else None, "finished_at": execution.finished_at.isoformat() if execution.finished_at else None, "retry_count": execution.retry_count, "error_code": execution.error_code}

    @staticmethod
    def _item(item: Any) -> dict[str, Any]:
        return {"item_key": item.item_key, "source_id": item.source_id, "dataset_id": item.dataset_id, "state": item.state.value, "rows_received": item.rows_received, "retry_count": item.retry_count, "cache_hit": item.cache_hit, "is_fallback": item.is_fallback, "error_code": item.error_code, "safe_message": item.safe_message}
