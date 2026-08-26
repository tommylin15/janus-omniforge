"""Small, dependency-free Trino client used by long-running jobs."""

from .client import QueryClient, QueryError, QueryHandle, QueryPage

__all__ = ["QueryClient", "QueryError", "QueryHandle", "QueryPage"]
