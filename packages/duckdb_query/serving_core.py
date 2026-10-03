"""Core writer with a fail-open, rebuildable stock serving projection."""
from __future__ import annotations

import logging
from typing import Any

from .iceberg import DuckDBIcebergCore as _CanonicalDuckDBIcebergCore


LOGGER = logging.getLogger(__name__)


class ServingDuckDBIcebergCore(_CanonicalDuckDBIcebergCore):
    """Preserve Iceberg as canonical while materializing recent UI read models.

    Projection failures never roll back an already successful canonical Core
    commit. Public API routes retain an Iceberg fallback until the projection is
    rebuilt by a later ingestion/backfill run.
    """

    def write(self, *, dataset_id: str, rows: list[dict[str, Any]], execution_id: str,
              provenance_id: str, source_id: str, partition_date: Any):
        result = super().write(
            dataset_id=dataset_id, rows=rows, execution_id=execution_id,
            provenance_id=provenance_id, source_id=source_id, partition_date=partition_date,
        )
        if dataset_id not in {"ohlcv", "valuation", "events"}:
            return result
        try:
            projection = getattr(self, "_stock_serving_projection", None)
            if projection is None:
                from ingestion_core.serving_projection import StockServingProjection
                projection = StockServingProjection.from_env()
                self._stock_serving_projection = projection
            projection.publish(
                dataset_id, rows, execution_id=execution_id, provenance_id=provenance_id,
                source_id=source_id, core_snapshot_id=result.snapshot_id,
            )
        except Exception as error:  # Rebuildable serving data must not poison canonical ingestion.
            LOGGER.warning("stock serving projection unavailable dataset=%s error=%s",
                           dataset_id, type(error).__name__)
        return result
