"""Read-only Core query and safe Admin application services."""

from .core import CoreQueryService, QueryValidationError

__all__ = ["CoreQueryService", "QueryValidationError"]
