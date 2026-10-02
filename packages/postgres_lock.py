"""Shared Core/Mart mutation fence on the existing PostgreSQL database."""
from contextlib import contextmanager


@contextmanager
def public_data_lock(settings=None):
    if settings is None:
        yield  # Local SQLite catalog fixtures have no cloud writers.
        return
    import psycopg
    # ponytail: one public-data lock; split by table only if contention matters.
    with psycopg.connect(**settings, autocommit=True) as connection:
        if not connection.execute("SELECT pg_try_advisory_lock(1835102836,2)").fetchone()[0]:
            raise RuntimeError("public data mutation lock is busy")
        try:
            yield
        finally:
            connection.execute("SELECT pg_advisory_unlock(1835102836,2)")
