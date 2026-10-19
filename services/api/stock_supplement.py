"""Best-effort wake after the stock outbox transaction has committed."""
import logging
import os

LOGGER = logging.getLogger(__name__)


def wake_stock_supplement(repository, pipeline=None):
    if os.getenv('JANUS_STOCK_SUPPLEMENT_ENABLED','true').lower() != 'true':
        return
    try:
        if repository.reserve_supplement_dispatch():
            if pipeline is None:
                from .public_runtime import build_pipeline_service
                pipeline = build_pipeline_service()
            pipeline.supplement()
    except Exception as error:
        # A timeout can mean accepted. Keep the reservation; daily reconciliation retries.
        LOGGER.warning('stock supplement wake failed: %s',type(error).__name__)
