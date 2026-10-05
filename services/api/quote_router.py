"""DB-first operational quotes. Public prices contain no owner/holding data."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import logging

from .intraday_quotes import TAIPEI

LOGGER = logging.getLogger(__name__)
ROUTE_VERSION = "quote-router.v1"


class QuoteRouter:
    def __init__(self, repository, source):
        self.repository, self.source = repository, source

    def read(self, identities):
        return self.repository.last_quotes(identities)

    def refresh(self, identities):
        # Source performs its existing authorization gate and bounded batching.
        # No portfolio/user identifier crosses the market-source boundary.
        try:
            rows = self.source.prices(identities)
            received = datetime.now(TAIPEI)
            successful = {}
            for symbol, row in rows.items():
                if symbol not in identities:
                    continue
                try:
                    price = Decimal(str(row['price']))
                    at = datetime.fromisoformat(row['quote_at'])
                    source_received = datetime.fromisoformat(row.get('received_at', received.isoformat()))
                    if (not price.is_finite() or price <= 0 or at.tzinfo is None or
                            source_received.tzinfo is None or at > source_received or source_received > received):
                        continue
                except (KeyError, ValueError, TypeError, InvalidOperation):
                    continue
                successful[symbol] = {**row, 'received_at': source_received.isoformat(),
                                      'session': 'regular' if 540 <= at.astimezone(TAIPEI).hour * 60 + at.astimezone(TAIPEI).minute < 810 else 'off_session',
                                      'source': 'twse_mis', 'route_version': ROUTE_VERSION}
            if successful:
                self.repository.save_last_quotes(successful)
        except Exception as error:
            # Failure never clears the last success and never leaks upstream data.
            LOGGER.warning('quote refresh unavailable: %s', type(error).__name__)
