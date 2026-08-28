"""Bounded in-process DuckDB operations used by jobs and query consumers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from threading import Timer
from typing import Any, Iterable, Sequence


class DuckDBQueryError(RuntimeError):
    """Safe DuckDB query failure that does not expose SQL or credentials."""


@dataclass(frozen=True)
class MergeResult:
    rows: tuple[dict[str, Any], ...]
    changed_rows: tuple[dict[str, Any], ...]
    inserted: int
    updated: int
    reused: int


class DuckDBEngine:
    """One bounded DuckDB connection; callers must not share it across threads."""

    METADATA_FIELDS = frozenset({"execution_id", "provenance_id", "source_id", "content_hash"})

    def __init__(self, *, memory_limit: str = "384MB", threads: int = 1,
                 temp_directory: str = "/tmp/janus-duckdb", max_rows: int = 10_000,
                 query_timeout_seconds: int = 60) -> None:
        if threads != 1:
            raise ValueError("DuckDB runtime is limited to one thread")
        if not 1 <= max_rows <= 100_000:
            raise ValueError("max_rows must be between 1 and 100000")
        if not 1 <= query_timeout_seconds <= 300:
            raise ValueError("query_timeout_seconds must be between 1 and 300")
        if not re.fullmatch(r"[1-9][0-9]*(?:KB|MB|GB)", memory_limit.upper()):
            raise ValueError("memory_limit must be a positive KB, MB, or GB value")
        try:
            import duckdb
        except ImportError as error:
            raise RuntimeError("DuckDB runtime dependency is unavailable") from error
        Path(temp_directory).mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(":memory:")
        escaped_temp = temp_directory.replace("'", "''")
        self.connection.execute("SET threads = 1")
        self.connection.execute(f"SET memory_limit = '{memory_limit.upper()}'")
        self.connection.execute(f"SET temp_directory = '{escaped_temp}'")
        self.connection.execute("SET max_temp_directory_size = '1GB'")
        self.max_rows = max_rows
        self.query_timeout_seconds = query_timeout_seconds

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "DuckDBEngine":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def query(self, sql: str, parameters: Sequence[Any] = ()) -> tuple[dict[str, Any], ...]:
        statement = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
        if statement not in {"SELECT", "WITH", "EXPLAIN", "DESCRIBE", "SHOW"}:
            raise ValueError("DuckDB query must be read-only")
        try:
            timer = Timer(self.query_timeout_seconds, self.connection.interrupt)
            timer.daemon = True
            timer.start()
            result = self.connection.execute(sql, parameters)
            columns = tuple(item[0] for item in result.description or ())
            rows = result.fetchmany(self.max_rows + 1)
        except Exception as error:
            raise DuckDBQueryError("DuckDB query failed") from error
        finally:
            timer.cancel()
        if len(rows) > self.max_rows:
            raise DuckDBQueryError("DuckDB query exceeded the row limit")
        return tuple(dict(zip(columns, row, strict=True)) for row in rows)

    def merge(self, existing: Iterable[dict[str, Any]], incoming: Iterable[dict[str, Any]],
              identifiers: Sequence[str]) -> MergeResult:
        """Merge by natural key in DuckDB while preserving existing non-null values."""
        keys = tuple(identifiers)
        if not keys:
            raise ValueError("at least one identifier is required")
        existing_rows = [dict(row) for row in existing]
        incoming_rows = [dict(row) for row in incoming]
        for row in incoming_rows:
            missing = [key for key in keys if row.get(key) in {None, ""}]
            if missing:
                raise ValueError(f"missing Core identifier fields: {','.join(missing)}")
        if not incoming_rows:
            return MergeResult(tuple(existing_rows), (), 0, 0, 0)

        columns = tuple(sorted(set().union(*(row.keys() for row in existing_rows + incoming_rows))))
        normalized_existing = self._normalize(existing_rows, columns)
        normalized_incoming = self._normalize(incoming_rows, columns)
        existing_registered = incoming_registered = False
        try:
            import pyarrow as pa
            combined = pa.Table.from_pylist(normalized_existing + normalized_incoming)
            existing_arrow = combined.slice(0, len(normalized_existing))
            incoming_arrow = combined.slice(len(normalized_existing), len(normalized_incoming)).append_column(
                "__ordinal", pa.array(range(len(normalized_incoming)), type=pa.int64())
            )
            self.connection.register("existing_input", existing_arrow)
            existing_registered = True
            self.connection.register("incoming_input", incoming_arrow)
            incoming_registered = True
            quoted_keys = ",".join(self._identifier(key) for key in keys)
            self.connection.execute(
                f"CREATE OR REPLACE TEMP TABLE incoming_dedup AS "
                f"SELECT * EXCLUDE (__ordinal, __rn) FROM ("
                f"SELECT *, row_number() OVER (PARTITION BY {quoted_keys} ORDER BY __ordinal DESC) AS __rn "
                f"FROM incoming_input) WHERE __rn=1"
            )
            select_columns = []
            for column in columns:
                name = self._identifier(column)
                if column in keys:
                    select_columns.append(f"coalesce(i.{name}, e.{name}) AS {name}")
                else:
                    select_columns.append(f"coalesce(i.{name}, e.{name}) AS {name}")
            conditions = " AND ".join(
                f"i.{self._identifier(key)} IS NOT DISTINCT FROM e.{self._identifier(key)}" for key in keys
            )
            cursor = self.connection.execute(
                f"SELECT {','.join(select_columns)} FROM existing_input e FULL OUTER JOIN incoming_dedup i ON {conditions}"
            )
            merged_rows = [dict(zip((item[0] for item in cursor.description), row, strict=True))
                           for row in cursor.fetchall()]
        except Exception as error:
            raise DuckDBQueryError("DuckDB incremental merge failed") from error
        finally:
            if existing_registered:
                self.connection.unregister("existing_input")
            if incoming_registered:
                self.connection.unregister("incoming_input")

        existing_by_key = {self._key(row, keys): row for row in existing_rows}
        incoming_keys = {self._key(row, keys) for row in incoming_rows}
        inserted = updated = reused = 0
        changed: list[dict[str, Any]] = []
        final_rows: list[dict[str, Any]] = []
        for row in merged_rows:
            key = self._key(row, keys)
            prior = existing_by_key.get(key)
            row["content_hash"] = self.content_hash(row)
            if key not in incoming_keys:
                final_rows.append(prior or row)
            elif prior is None:
                inserted += 1
                changed.append(row)
                final_rows.append(row)
            elif prior.get("content_hash") == row["content_hash"] or self.content_hash(prior) == row["content_hash"]:
                reused += 1
                final_rows.append(prior)
            else:
                updated += 1
                changed.append(row)
                final_rows.append(row)
        final_rows.sort(key=lambda row: self._key(row, keys))
        return MergeResult(tuple(final_rows), tuple(changed), inserted, updated, reused)

    @classmethod
    def content_hash(cls, row: dict[str, Any]) -> str:
        logical = {key: cls._json_value(value) for key, value in row.items() if key not in cls.METADATA_FIELDS}
        payload = json.dumps(logical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _normalize(rows: list[dict[str, Any]], columns: Sequence[str], *, ordinal: bool = False) -> list[dict[str, Any]]:
        result = []
        for index, row in enumerate(rows):
            item = {column: row.get(column) for column in columns}
            if ordinal:
                item["__ordinal"] = index
            result.append(item)
        return result

    @staticmethod
    def _key(row: dict[str, Any], identifiers: Sequence[str]) -> tuple[str, ...]:
        return tuple(str(row.get(field)) for field in identifiers)

    @staticmethod
    def _identifier(value: str) -> str:
        if not value or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in value):
            raise ValueError("unsafe DuckDB identifier")
        return f'"{value}"'

    @staticmethod
    def _json_value(value: Any) -> Any:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value
