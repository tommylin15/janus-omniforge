"""Bounded PostgreSQL operations for the private workspace."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import os
from typing import Any, Iterator
from uuid import UUID, uuid4

from .models import LedgerEventIn, LedgerType, McpServerIn, NoteIn, WatchlistIn


class ConflictError(ValueError): pass
class NotFoundError(ValueError): pass
class OversellError(ValueError): pass


class PostgresWorkspaceRepository:
    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PRIVATE_DATABASE_URL is required")
        self.dsn = dsn

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.dsn, connect_timeout=5, row_factory=dict_row) as connection:
            with connection.transaction():
                yield connection

    def resolve_user(self, google_sub: str, email: str) -> UUID:
        with self._connection() as connection:
            row = connection.execute(
                """INSERT INTO private.users(user_id, google_sub, display_email)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (google_sub) DO UPDATE SET display_email=EXCLUDED.display_email, updated_at=now()
                   RETURNING user_id""",
                (uuid4(), google_sub, email),
            ).fetchone()
            return row["user_id"]

    def require_owned_trade(self, user_id: UUID, event_id: UUID | None) -> None:
        with self._connection() as connection: self._require_owned_trade(connection,user_id,event_id)

    def add_ledger(self, user_id: UUID, value: LedgerEventIn, key: str) -> dict[str, Any]:
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT * FROM private.ledger_events WHERE user_id=%s AND idempotency_key=%s", (user_id, key)
            ).fetchone()
            if existing:
                return dict(existing)
            if value.event_type == LedgerType.SELL:
                available = self._position(connection, user_id, value.symbol)
                if available < (value.shares or 0):
                    raise OversellError("sell exceeds available shares")
            version = self._next_version(connection, user_id)
            row = connection.execute(
                """INSERT INTO private.ledger_events
                   (event_id,user_id,ledger_version,event_action,event_type,trade_date,symbol,shares,price,cash_amount,fee,tax,currency,memo,idempotency_key)
                   VALUES (%s,%s,%s,'ORIGINAL',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (uuid4(), user_id, version, value.event_type, value.trade_date, value.symbol, value.shares,
                 value.price, value.cash_amount, value.fee, value.tax, value.currency, value.memo, key),
            ).fetchone()
            self._change(connection, user_id, self._next_change_version(connection,user_id), "ledger", row["event_id"], None)
            return dict(row)

    def correct_ledger(self, user_id: UUID, event_id: UUID, expected: int, value: LedgerEventIn, key: str) -> dict[str, Any]:
        with self._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(str(event_id),))
            repeated=connection.execute("SELECT * FROM private.ledger_events WHERE user_id=%s AND idempotency_key=%s",(user_id,key)).fetchone()
            if repeated: return dict(repeated)
            original = connection.execute(
                "SELECT * FROM private.ledger_events WHERE user_id=%s AND event_id=%s", (user_id, event_id)
            ).fetchone()
            if not original:
                raise NotFoundError("ledger event not found")
            if original["record_version"] != expected:
                raise ConflictError("ledger event version changed")
            if connection.execute("SELECT 1 FROM private.ledger_events WHERE user_id=%s AND reverses_event_id=%s", (user_id, event_id)).fetchone():
                raise ConflictError("ledger event was already corrected")
            if value.event_type == LedgerType.SELL:
                available = self._position(connection, user_id, value.symbol, exclude=event_id)
                if available < (value.shares or 0):
                    raise OversellError("sell exceeds available shares")
            reversal_version = self._next_version(connection, user_id)
            reversal_id = uuid4()
            connection.execute(
                """INSERT INTO private.ledger_events
                   (event_id,user_id,ledger_version,event_action,event_type,trade_date,symbol,shares,price,cash_amount,fee,tax,currency,memo,idempotency_key,reverses_event_id)
                   VALUES (%s,%s,%s,'REVERSAL',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (reversal_id,user_id,reversal_version,original["event_type"],original["trade_date"],original["symbol"],original["shares"],
                 original["price"],original["cash_amount"],original["fee"],original["tax"],original["currency"],original["memo"],f"reversal:{uuid4()}",event_id),
            )
            version = self._next_version(connection, user_id)
            row = connection.execute(
                """INSERT INTO private.ledger_events
                   (event_id,user_id,ledger_version,event_action,event_type,trade_date,symbol,shares,price,cash_amount,fee,tax,currency,memo,idempotency_key,replaces_event_id)
                   VALUES (%s,%s,%s,'REPLACEMENT',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (uuid4(),user_id,version,value.event_type,value.trade_date,value.symbol,value.shares,value.price,value.cash_amount,
                 value.fee,value.tax,value.currency,value.memo,key,event_id),
            ).fetchone()
            self._change(connection, user_id, self._next_change_version(connection,user_id), "ledger", reversal_id, None)
            self._change(connection, user_id, self._next_change_version(connection,user_id), "ledger", row["event_id"], None)
            return dict(row)

    def ledger_history(self, user_id: UUID, symbol: str | None, year: int | None, limit: int = 200) -> list[dict[str, Any]]:
        clauses, values = ["user_id=%s"], [user_id]
        if symbol:
            clauses.append("symbol=%s"); values.append(symbol)
        if year:
            clauses.append("trade_date >= %s AND trade_date < %s"); values.extend((date(year, 1, 1), date(year + 1, 1, 1)))
        values.append(min(limit, 200))
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                f"SELECT * FROM private.ledger_events WHERE {' AND '.join(clauses)} ORDER BY ledger_version DESC LIMIT %s", values
            ).fetchall()]

    def positions(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM private.current_positions WHERE user_id=%s ORDER BY symbol", (user_id,)
            ).fetchall()]

    def annual_pnl(self, user_id: UUID, year: int) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM private.annual_pnl WHERE user_id=%s AND year=%s ORDER BY currency", (user_id, year)
            ).fetchall()]

    def add_note(self, user_id: UUID, value: NoteIn, key: str, artifact_ref: str, note_id: UUID | None = None) -> dict[str, Any]:
        with self._connection() as connection:
            replay=self._mutation(connection,user_id,key)
            existing = connection.execute("SELECT * FROM private.note_index WHERE user_id=%s AND note_id=%s", (user_id,replay["entity_id"])).fetchone() if replay else None
            if existing: return dict(existing)
            self._require_owned_trade(connection,user_id,value.trade_event_id)
            note_id, version = note_id or uuid4(), 1
            row = connection.execute(
                """INSERT INTO private.note_index(note_id,user_id,current_version,symbol,trade_event_id,needs_follow_up,artifact_ref,idempotency_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (note_id,user_id,version,value.symbol,value.trade_event_id,value.needs_follow_up,artifact_ref,key),
            ).fetchone()
            change_version = self._next_change_version(connection, user_id)
            self._change(connection,user_id,change_version,"note",note_id,artifact_ref)
            self._record_mutation(connection,user_id,key,"note",note_id)
            return dict(row)

    def revise_note(self, user_id: UUID, note_id: UUID, expected: int, value: NoteIn, key: str, artifact_ref: str) -> dict[str, Any]:
        with self._connection() as connection:
            replay=self._mutation(connection,user_id,key)
            repeated=connection.execute("SELECT * FROM private.note_index WHERE user_id=%s AND note_id=%s",(user_id,replay["entity_id"])).fetchone() if replay else None
            if repeated: return dict(repeated)
            self._require_owned_trade(connection,user_id,value.trade_event_id)
            row = connection.execute("SELECT * FROM private.note_index WHERE user_id=%s AND note_id=%s FOR UPDATE",(user_id,note_id)).fetchone()
            if not row: raise NotFoundError("note not found")
            if row["current_version"] != expected: raise ConflictError("note version changed")
            updated = connection.execute(
                """UPDATE private.note_index SET current_version=current_version+1,symbol=%s,trade_event_id=%s,needs_follow_up=%s,
                   artifact_ref=%s,idempotency_key=%s,updated_at=now() WHERE user_id=%s AND note_id=%s RETURNING *""",
                (value.symbol,value.trade_event_id,value.needs_follow_up,artifact_ref,key,user_id,note_id),
            ).fetchone()
            change_version = self._next_change_version(connection,user_id)
            self._change(connection,user_id,change_version,"note",note_id,artifact_ref)
            self._record_mutation(connection,user_id,key,"note",note_id)
            return dict(updated)

    def notes(self, user_id: UUID, symbol: str | None = None) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM private.note_index WHERE user_id=%s AND (%s::text IS NULL OR symbol=%s) ORDER BY updated_at DESC LIMIT 200",
                (user_id,symbol,symbol),
            ).fetchall()
            return [dict(row) for row in rows]

    def watchlist(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM private.watchlist WHERE user_id=%s ORDER BY sort_order,symbol",(user_id,)).fetchall()]

    def follow(self, user_id: UUID, value: WatchlistIn, key: str) -> dict[str, Any]:
        with self._connection() as connection:
            replay=self._mutation(connection,user_id,key)
            if replay:
                row=connection.execute("SELECT * FROM private.watchlist WHERE user_id=%s AND symbol=%s",(user_id,replay["entity_id"])).fetchone()
                if row: return dict(row)
            count = connection.execute("SELECT count(*) AS count FROM private.watchlist WHERE user_id=%s AND active",(user_id,)).fetchone()["count"]
            existing = connection.execute("SELECT * FROM private.watchlist WHERE user_id=%s AND symbol=%s FOR UPDATE",(user_id,value.symbol)).fetchone()
            if existing and existing["idempotency_key"]==key: return dict(existing)
            if count >= 50 and not existing: raise ConflictError("watchlist limit reached")
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('private-watchlist-symbol-limit'))")
            globally_known=connection.execute("SELECT 1 FROM private.watchlist WHERE symbol=%s AND active LIMIT 1",(value.symbol,)).fetchone()
            global_count=connection.execute("SELECT count(DISTINCT symbol) AS count FROM private.watchlist WHERE active").fetchone()["count"]
            if not globally_known and global_count>=50: raise ConflictError("deep-tracking symbol limit reached")
            version = (existing["version"] + 1) if existing else 1
            row = connection.execute(
                """INSERT INTO private.watchlist(user_id,symbol,target_price,sort_order,active,version,idempotency_key)
                   VALUES (%s,%s,%s,%s,true,%s,%s) ON CONFLICT(user_id,symbol) DO UPDATE SET target_price=EXCLUDED.target_price,
                   active=true,version=EXCLUDED.version,idempotency_key=EXCLUDED.idempotency_key,updated_at=now() RETURNING *""",
                (user_id,value.symbol,value.target_price,count,version,key),
            ).fetchone()
            change_version=self._next_change_version(connection,user_id); self._change(connection,user_id,change_version,"watchlist",value.symbol,None)
            self._record_mutation(connection,user_id,key,"watchlist",value.symbol)
            return dict(row)

    def unfollow(self, user_id: UUID, symbol: str, key: str) -> None:
        with self._connection() as connection:
            if self._mutation(connection,user_id,key): return
            existing=connection.execute("SELECT active,idempotency_key FROM private.watchlist WHERE user_id=%s AND symbol=%s FOR UPDATE",(user_id,symbol)).fetchone()
            if existing and not existing["active"] and existing["idempotency_key"]==key: return
            row=connection.execute("UPDATE private.watchlist SET active=false,version=version+1,idempotency_key=%s,updated_at=now() WHERE user_id=%s AND symbol=%s AND active RETURNING symbol",(key,user_id,symbol)).fetchone()
            if not row: raise NotFoundError("watchlist item not found")
            version=self._next_change_version(connection,user_id); self._change(connection,user_id,version,"watchlist",symbol,None)
            self._record_mutation(connection,user_id,key,"watchlist",symbol)

    def reorder(self, user_id: UUID, symbols: list[str], expected: int, key: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            if self._mutation(connection,user_id,key): return self.watchlist(user_id)
            current=connection.execute("SELECT symbol,version,idempotency_key FROM private.watchlist WHERE user_id=%s AND active FOR UPDATE",(user_id,)).fetchall()
            if set(symbols)!={row["symbol"] for row in current}: raise ConflictError("order must contain the active watchlist")
            if current and all(row["idempotency_key"]==key for row in current): return self.watchlist(user_id)
            if max((row["version"] for row in current),default=0)!=expected: raise ConflictError("watchlist version changed")
            for order,symbol in enumerate(symbols):
                connection.execute("UPDATE private.watchlist SET sort_order=%s,version=version+1,idempotency_key=%s,updated_at=now() WHERE user_id=%s AND symbol=%s",(order,key,user_id,symbol))
            version=self._next_change_version(connection,user_id); self._change(connection,user_id,version,"watchlist-order",str(uuid4()),None)
            self._record_mutation(connection,user_id,key,"watchlist-order",str(uuid4()))
        return self.watchlist(user_id)

    def pipeline_batch(self, checkpoint: int, limit: int = 500) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM private.change_log WHERE change_id>%s ORDER BY change_id LIMIT %s",(checkpoint,min(limit,500))
            ).fetchall()]

    def pipeline_checkpoint(self, name: str = "private-core") -> int:
        with self._connection() as connection:
            row=connection.execute("SELECT change_id FROM private.pipeline_checkpoints WHERE pipeline_name=%s",(name,)).fetchone()
            return row["change_id"] if row else 0

    def advance_pipeline_checkpoint(self, change_id: int, name: str = "private-core") -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO private.pipeline_checkpoints(pipeline_name,change_id,updated_at) VALUES(%s,%s,now())
                   ON CONFLICT(pipeline_name) DO UPDATE SET change_id=GREATEST(private.pipeline_checkpoints.change_id,EXCLUDED.change_id),updated_at=now()""",
                (name,change_id),
            )

    def ledger_for_pipeline(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM private.ledger_events WHERE user_id=%s ORDER BY trade_date,ledger_version",(user_id,)
            ).fetchall()]

    def watchlist_for_pipeline(self, user_id: UUID) -> list[dict[str, Any]]:
        return self.watchlist(user_id)

    def request_deletion(self, user_id: UUID, key: str) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute(
                """INSERT INTO private.deletion_requests(request_id,user_id,idempotency_key) VALUES(%s,%s,%s)
                   ON CONFLICT(user_id,idempotency_key) DO NOTHING RETURNING *""",
                (uuid4(),user_id,key),
            ).fetchone()
            if not row:
                row=connection.execute("SELECT * FROM private.deletion_requests WHERE user_id=%s AND idempotency_key=%s",(user_id,key)).fetchone()
            return dict(row)

    def deletion_request(self, user_id: UUID, request_id: UUID) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM private.deletion_requests WHERE user_id=%s AND request_id=%s",
                (user_id, request_id),
            ).fetchone()
            if not row: raise NotFoundError("deletion request not found")
            return dict(row)

    def mcp_servers(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT server_id,config_ref,enabled,tool_grants,updated_at FROM private.mcp_servers WHERE user_id=%s ORDER BY server_id",
                (user_id,),
            ).fetchall()]

    def replace_mcp_servers(self, user_id: UUID, items: list[McpServerIn]) -> list[dict[str, Any]]:
        with self._connection() as connection:
            connection.execute("SELECT 1 FROM private.users WHERE user_id=%s FOR UPDATE",(user_id,))
            connection.execute("DELETE FROM private.mcp_servers WHERE user_id=%s",(user_id,))
            for item in items:
                connection.execute(
                    "INSERT INTO private.mcp_servers(user_id,server_id,config_ref,enabled,tool_grants) VALUES(%s,%s,%s,%s,%s)",
                    (user_id,item.server_id,item.config_ref,item.enabled,item.tool_grants),
                )
        return self.mcp_servers(user_id)

    def create_assistant_thread(self, user_id: UUID, thread_id: str, binding: Any,
                                *, parent_thread_id: str | None = None) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute(
                """INSERT INTO private.assistant_threads
                   (user_id,thread_id,runtime,model,assistant_profile,skill_profile,parent_thread_id)
                   VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(user_id,thread_id) DO NOTHING RETURNING *""",
                (user_id,thread_id,binding.runtime.value,binding.model,binding.assistant_profile,
                 binding.skill_profile,parent_thread_id),
            ).fetchone()
            if not row:
                row=connection.execute(
                    "SELECT * FROM private.assistant_threads WHERE user_id=%s AND thread_id=%s",
                    (user_id,thread_id),
                ).fetchone()
            if (row["runtime"],row["model"]) != (binding.runtime.value,binding.model):
                raise ConflictError("thread runtime and model are immutable")
            return dict(row)

    def assistant_threads(self, user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM private.assistant_threads WHERE user_id=%s ORDER BY updated_at DESC LIMIT %s",
                (user_id, min(limit, 100)),
            ).fetchall()]

    def assistant_thread(self, user_id: UUID, thread_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM private.assistant_threads WHERE user_id=%s AND thread_id=%s",
                (user_id, thread_id),
            ).fetchone()
            if not row: raise NotFoundError("assistant thread not found")
            return dict(row)

    def assistant_turn(self, user_id: UUID, thread_id: str, turn_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM private.assistant_turns WHERE user_id=%s AND thread_id=%s AND turn_id=%s",
                (user_id, thread_id, turn_id),
            ).fetchone()
            if not row: raise NotFoundError("assistant turn not found")
            return dict(row)

    def next_assistant_seq(self, user_id: UUID, thread_id: str) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 AS next_seq FROM private.assistant_event_index WHERE user_id=%s AND thread_id=%s",
                (user_id, thread_id),
            ).fetchone()
            return int(row["next_seq"])

    def assistant_event_for_key(self, user_id: UUID, thread_id: str, key: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM private.assistant_event_index WHERE user_id=%s AND thread_id=%s AND idempotency_key=%s",
                (user_id, thread_id, key),
            ).fetchone()
            return dict(row) if row else None

    def latest_assistant_continuation(self, user_id: UUID, thread_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT continuation FROM private.assistant_turns
                   WHERE user_id=%s AND thread_id=%s AND continuation <> '{}'::jsonb
                   ORDER BY started_at DESC LIMIT 1""", (user_id, thread_id),
            ).fetchone()
            return dict(row["continuation"]) if row and row["continuation"] else {}

    def start_assistant_turn(self, user_id: UUID, thread_id: str, turn_id: str, key: str,
                             *, context_artifact_ref: str | None = None, skill_id: str | None = None,
                             skill_revision: int | None = None, continuation: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute(
                """INSERT INTO private.assistant_turns
                   (user_id,thread_id,turn_id,idempotency_key,context_artifact_ref,skill_id,skill_revision,continuation)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(user_id,thread_id,idempotency_key) DO NOTHING RETURNING *""",
                (user_id,thread_id,turn_id,key,context_artifact_ref,skill_id,skill_revision,continuation or {}),
            ).fetchone()
            if not row:
                row=connection.execute(
                    "SELECT * FROM private.assistant_turns WHERE user_id=%s AND thread_id=%s AND idempotency_key=%s",
                    (user_id,thread_id,key),
                ).fetchone()
            if row["turn_id"] != turn_id:
                raise ConflictError("turn idempotency key was already used")
            return dict(row)

    def finish_assistant_turn(self, user_id: UUID, thread_id: str, turn_id: str,
                              status: str, continuation: dict[str, Any] | None = None) -> dict[str, Any]:
        if status not in {"COMPLETED","CANCELLED","ERROR"}:
            raise ValueError("turn terminal status is invalid")
        with self._connection() as connection:
            row=connection.execute(
                """UPDATE private.assistant_turns SET status=%s,completed_at=now(),
                   continuation=COALESCE(%s, continuation)
                   WHERE user_id=%s AND thread_id=%s AND turn_id=%s AND status='RUNNING' RETURNING *""",
                (status, continuation, user_id, thread_id, turn_id),
            ).fetchone()
            if not row:
                row=connection.execute(
                    """SELECT * FROM private.assistant_turns
                       WHERE user_id=%s AND thread_id=%s AND turn_id=%s""", (user_id,thread_id,turn_id),
                ).fetchone()
            if not row: raise NotFoundError("assistant turn not found")
            if row["status"] != status: raise ConflictError("assistant turn already reached another terminal status")
            return dict(row)

    def update_assistant_turn_continuation(self, user_id: UUID, thread_id: str, turn_id: str,
                                           continuation: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                """UPDATE private.assistant_turns SET continuation=%s
                   WHERE user_id=%s AND thread_id=%s AND turn_id=%s AND status='RUNNING'
                   RETURNING *""", (continuation, user_id, thread_id, turn_id),
            ).fetchone()
            if not row: raise NotFoundError("running assistant turn not found")
            return dict(row)

    def active_assistant_turns(self, user_id: UUID, thread_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT * FROM private.assistant_turns
                   WHERE user_id=%s AND thread_id=%s AND status='RUNNING'
                     AND continuation->>'turnHandle' IS NOT NULL
                   ORDER BY started_at""", (user_id, thread_id),
            ).fetchall()]

    def reserve_assistant_event(self, user_id: UUID, event: Any, key: str,
                                payload_digest: str) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute(
                """INSERT INTO private.assistant_event_index
                   (user_id,thread_id,turn_id,event_id,seq,event_type,payload_digest,idempotency_key)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(user_id,thread_id,idempotency_key) DO NOTHING RETURNING *""",
                (user_id,event.thread_id,event.turn_id,event.event_id,event.seq,event.event_type.value,
                 payload_digest,key),
            ).fetchone()
            if not row:
                row=connection.execute(
                    "SELECT * FROM private.assistant_event_index WHERE user_id=%s AND thread_id=%s AND idempotency_key=%s",
                    (user_id,event.thread_id,key),
                ).fetchone()
            expected=(event.event_id,event.turn_id,event.seq,event.event_type.value,payload_digest)
            actual=(row["event_id"],row["turn_id"],row["seq"],row["event_type"],row["payload_digest"])
            if actual != expected:
                raise ConflictError("event idempotency key was already used")
            return dict(row)

    def complete_assistant_event(self, user_id: UUID, thread_id: str, event_id: str,
                                 artifact_ref: str) -> None:
        with self._connection() as connection:
            row=connection.execute(
                """UPDATE private.assistant_event_index SET status='PERSISTED',artifact_ref=%s,persisted_at=now()
                   WHERE user_id=%s AND thread_id=%s AND event_id=%s RETURNING seq""",
                (artifact_ref,user_id,thread_id,event_id),
            ).fetchone()
            if not row: raise NotFoundError("assistant event not found")
            connection.execute(
                "UPDATE private.assistant_threads SET updated_at=now() WHERE user_id=%s AND thread_id=%s",
                (user_id,thread_id),
            )

    def assistant_events_after(self, user_id: UUID, thread_id: str, cursor: int,
                               limit: int = 200) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT event_id,turn_id,seq,event_type,artifact_ref,created_at FROM private.assistant_event_index
                   WHERE user_id=%s AND thread_id=%s AND status='PERSISTED' AND seq>%s
                   ORDER BY seq LIMIT %s""", (user_id,thread_id,cursor,min(limit,200)),
            ).fetchall()]

    def reserve_skill_revision(self, user_id: UUID, skill_id: str, revision: int, key: str,
                               content_digest: str) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute(
                """INSERT INTO private.assistant_skill_revisions
                   (user_id,skill_id,revision,content_digest,idempotency_key) VALUES(%s,%s,%s,%s,%s)
                   ON CONFLICT(user_id,idempotency_key) DO NOTHING RETURNING *""",
                (user_id,skill_id,revision,content_digest,key),
            ).fetchone()
            if not row:
                row=connection.execute(
                    "SELECT * FROM private.assistant_skill_revisions WHERE user_id=%s AND idempotency_key=%s",
                    (user_id,key),
                ).fetchone()
            if (row["skill_id"],row["revision"],row["content_digest"]) != (skill_id,revision,content_digest):
                raise ConflictError("skill revision idempotency key was already used")
            return dict(row)

    def complete_skill_revision(self, user_id: UUID, skill_id: str, revision: int,
                                artifact_ref: str) -> None:
        with self._connection() as connection:
            row=connection.execute(
                """UPDATE private.assistant_skill_revisions SET status='PERSISTED',artifact_ref=%s
                   WHERE user_id=%s AND skill_id=%s AND revision=%s RETURNING revision""",
                (artifact_ref,user_id,skill_id,revision),
            ).fetchone()
            if not row: raise NotFoundError("skill revision not found")
            connection.execute(
                """INSERT INTO private.assistant_skill_state(user_id,skill_id,current_revision)
                   VALUES(%s,%s,%s) ON CONFLICT(user_id,skill_id) DO UPDATE SET
                   current_revision=EXCLUDED.current_revision,updated_at=now()""",
                (user_id,skill_id,revision),
            )

    def skill_revision(self, user_id: UUID, skill_id: str, revision: int) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT r.*, COALESCE(s.enabled, false) AS enabled,
                          (s.current_revision = r.revision) AS active
                   FROM private.assistant_skill_revisions r
                   LEFT JOIN private.assistant_skill_state s
                     ON s.user_id=r.user_id AND s.skill_id=r.skill_id
                   WHERE r.user_id=%s AND r.skill_id=%s AND r.revision=%s""",
                (user_id, skill_id, revision),
            ).fetchone()
            if not row: raise NotFoundError("skill revision not found")
            return dict(row)

    def skill_revisions(self, user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT r.*, COALESCE(s.enabled, false) AS enabled,
                          (s.current_revision = r.revision) AS active
                   FROM private.assistant_skill_revisions r
                   LEFT JOIN private.assistant_skill_state s
                     ON s.user_id=r.user_id AND s.skill_id=r.skill_id
                   WHERE r.user_id=%s ORDER BY r.skill_id, r.revision DESC LIMIT %s""",
                (user_id, min(limit, 100)),
            ).fetchall()]

    def set_skill_state(self, user_id: UUID, skill_id: str, *, enabled: bool,
                        revision: int | None = None) -> dict[str, Any]:
        with self._connection() as connection:
            if revision is None:
                row = connection.execute(
                    """SELECT current_revision FROM private.assistant_skill_state
                       WHERE user_id=%s AND skill_id=%s""", (user_id, skill_id),
                ).fetchone()
                if not row: raise NotFoundError("skill not found")
                revision = row["current_revision"]
            revision_row = connection.execute(
                """SELECT 1 FROM private.assistant_skill_revisions
                   WHERE user_id=%s AND skill_id=%s AND revision=%s AND status='PERSISTED'""",
                (user_id, skill_id, revision),
            ).fetchone()
            if not revision_row: raise NotFoundError("skill revision not found")
            row = connection.execute(
                """INSERT INTO private.assistant_skill_state(user_id,skill_id,current_revision,enabled)
                   VALUES(%s,%s,%s,%s)
                   ON CONFLICT(user_id,skill_id) DO UPDATE SET current_revision=EXCLUDED.current_revision,
                   enabled=EXCLUDED.enabled,updated_at=now() RETURNING *""",
                (user_id, skill_id, revision, enabled),
            ).fetchone()
            return dict(row)

    def save_approval(self, request: Any, artifact_ref: str) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute(
                """INSERT INTO private.assistant_approvals
                   (user_id,thread_id,turn_id,request_id,operation,scope,params_digest,artifact_ref,expires_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(user_id,thread_id,turn_id,request_id) DO NOTHING RETURNING *""",
                (request.owner_id,request.thread_id,request.turn_id,request.request_id,request.operation,
                 request.scope,request.params_digest,artifact_ref,request.expires_at),
            ).fetchone()
            if not row:
                row=connection.execute(
                    """SELECT * FROM private.assistant_approvals
                       WHERE user_id=%s AND thread_id=%s AND turn_id=%s AND request_id=%s""",
                    (request.owner_id,request.thread_id,request.turn_id,request.request_id),
                ).fetchone()
            if row["params_digest"] != request.params_digest:
                raise ConflictError("approval request binding changed")
            return dict(row)

    def approval(self, user_id: UUID | str, thread_id: str, turn_id: str,
                 request_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute(
                """SELECT * FROM private.assistant_approvals
                   WHERE user_id=%s AND thread_id=%s AND turn_id=%s AND request_id=%s""",
                (user_id,thread_id,turn_id,request_id),
            ).fetchone()
            if not row: raise NotFoundError("approval request not found")
            return dict(row)

    def resolve_approval(self, decision: Any, status: str, resolved_at: Any) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute(
                """UPDATE private.assistant_approvals SET status=%s,resolved_at=%s
                   WHERE user_id=%s AND thread_id=%s AND turn_id=%s AND request_id=%s
                     AND params_digest=%s AND status='PENDING' RETURNING *""",
                (status,resolved_at,decision.owner_id,decision.thread_id,decision.turn_id,
                 decision.request_id,decision.params_digest),
            ).fetchone()
            if not row: raise ConflictError("approval was already resolved or binding changed")
            return dict(row)

    def pending_deletions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM private.deletion_requests WHERE status IN ('QUEUED','CLEANUP_PENDING') ORDER BY requested_at LIMIT %s",(min(limit,20),)
            ).fetchall()]

    def assistant_cleanup_required(self, user_id: UUID) -> bool:
        with self._connection() as connection:
            return connection.execute(
                "SELECT 1 FROM private.assistant_threads WHERE user_id=%s AND runtime='codex' LIMIT 1",
                (user_id,),
            ).fetchone() is not None

    def mark_deletion_cleanup_pending(self, request_id: UUID, user_id: UUID) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE private.deletion_requests SET status='CLEANUP_PENDING',cleanup_pending=ARRAY['codex_auth_state']
                   WHERE request_id=%s AND user_id=%s""", (request_id,user_id),
            )

    def complete_deletion(self, request_id: UUID, user_id: UUID) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM private.assistant_threads WHERE user_id=%s",(user_id,))
            connection.execute("DELETE FROM private.assistant_skill_state WHERE user_id=%s",(user_id,))
            connection.execute("DELETE FROM private.assistant_skill_revisions WHERE user_id=%s",(user_id,))
            for table in ("change_log","mutation_keys","note_index","watchlist","mcp_servers","ledger_events","users"):
                connection.execute(f"DELETE FROM private.{table} WHERE user_id=%s",(user_id,))
            connection.execute("""UPDATE private.deletion_requests SET status='COMPLETED',cleanup_pending='{}',completed_at=now()
                                WHERE request_id=%s AND user_id=%s""",(request_id,user_id))

    @staticmethod
    def _next_version(connection: Any, user_id: UUID) -> int:
        return connection.execute("UPDATE private.users SET ledger_version=ledger_version+1 WHERE user_id=%s RETURNING ledger_version",(user_id,)).fetchone()["ledger_version"]

    @staticmethod
    def _next_change_version(connection: Any, user_id: UUID) -> int:
        return connection.execute("UPDATE private.users SET change_version=change_version+1 WHERE user_id=%s RETURNING change_version",(user_id,)).fetchone()["change_version"]

    @staticmethod
    def _change(connection: Any,user_id: UUID,version: int,kind: str,entity: Any,artifact: str | None) -> None:
        connection.execute("INSERT INTO private.change_log(user_id,change_version,kind,entity_id,artifact_ref) VALUES (%s,%s,%s,%s,%s)",(user_id,version,kind,str(entity),artifact))

    @staticmethod
    def _mutation(connection: Any,user_id: UUID,key: str) -> Any:
        return connection.execute("SELECT kind,entity_id FROM private.mutation_keys WHERE user_id=%s AND idempotency_key=%s",(user_id,key)).fetchone()

    @staticmethod
    def _record_mutation(connection: Any,user_id: UUID,key: str,kind: str,entity: Any) -> None:
        connection.execute("INSERT INTO private.mutation_keys(user_id,idempotency_key,kind,entity_id) VALUES(%s,%s,%s,%s)",(user_id,key,kind,str(entity)))

    @staticmethod
    def _position(connection: Any,user_id: UUID,symbol: str,exclude: UUID | None=None) -> Decimal:
        clause=" AND event_id<>%s" if exclude else ""
        row=connection.execute(
            """SELECT COALESCE(sum(CASE WHEN event_action='REVERSAL' THEN -1 ELSE 1 END *
                   CASE WHEN event_type IN ('BUY','STOCK_DIV') THEN shares WHEN event_type='SELL' THEN -shares ELSE 0 END),0) AS shares
               FROM private.ledger_events WHERE user_id=%s AND symbol=%s"""+clause,(user_id,symbol,*([exclude] if exclude else []))
        ).fetchone()
        return row["shares"]

    @staticmethod
    def _require_owned_trade(connection: Any,user_id: UUID,event_id: UUID | None) -> None:
        if event_id and not connection.execute("SELECT 1 FROM private.ledger_events WHERE user_id=%s AND event_id=%s",(user_id,event_id)).fetchone():
            raise NotFoundError("trade event not found")


def repository_from_env() -> PostgresWorkspaceRepository:
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "PRIVATE_DATABASE_URL": "database_url",
        "PRIVATE_CATALOG_PASSWORD": "catalog_password",
        "CORE_CATALOG_PASSWORD": "core_catalog_password",
    })
    return PostgresWorkspaceRepository(os.getenv("PRIVATE_DATABASE_URL", ""))
