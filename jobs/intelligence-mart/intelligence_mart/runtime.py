"""Bounded PostgreSQL connectivity checks for the Mart Cloud Run Job."""

from __future__ import annotations

from ipaddress import ip_interface
import os
from typing import Any, Callable


_DATABASES = {
    "catalog": ("CATALOG_DB", "catalog", "catalog.iceberg_tables"),
    "publication": ("PUBLICATION_DB", "publication", None),
}


def _settings(prefix: str) -> dict[str, str]:
    names = ("HOST", "NAME", "USER", "PASSWORD")
    values = {name.lower(): os.environ.get(f"{prefix}_{name}", "").strip() for name in names}
    missing = [f"{prefix}_{name}" for name in names if not values[name.lower()]]
    if missing:
        raise ValueError(f"missing database settings: {','.join(missing)}")
    return values


def _is_private(address: str) -> bool:
    parsed = ip_interface(address).ip
    return parsed.is_private and not (parsed.is_loopback or parsed.is_link_local)


def postgres_smoke(connect: Callable[..., Any] | None = None) -> dict[str, object]:
    """Verify both Mart identities reach PostgreSQL privately with bounded grants."""
    if connect is None:
        import psycopg

        connect = psycopg.connect

    results: dict[str, object] = {}
    for label, (prefix, schema, writable_table) in _DATABASES.items():
        settings = _settings(prefix)
        with connect(
            host=settings["host"],
            dbname=settings["name"],
            user=settings["user"],
            password=settings["password"],
            sslmode=os.environ.get(f"{prefix}_SSLMODE", "require"),
            connect_timeout=5,
            options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=15000",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_user, inet_server_addr()::text, "
                    "has_schema_privilege(current_user, %s, 'USAGE')",
                    (schema,),
                )
                role, server_address, schema_usage = cursor.fetchone()
                writable = True
                if writable_table:
                    cursor.execute(
                        "SELECT has_table_privilege(current_user, %s, 'SELECT,INSERT,UPDATE,DELETE')",
                        (writable_table,),
                    )
                    writable = bool(cursor.fetchone()[0])

        if role != settings["user"]:
            raise RuntimeError(f"{label} role mismatch")
        if not _is_private(server_address):
            raise RuntimeError(f"{label} database did not resolve to a private server address")
        if not schema_usage or not writable:
            raise RuntimeError(f"{label} role is missing its bounded schema privileges")
        results[label] = {"role": role, "server_address": server_address, "private": True, "privileges": "ok"}

    return {"component": "intelligence-mart", "status": "ok", "databases": results}
