"""Bounded PostgreSQL operations for the private workspace."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import os
from typing import Any, Iterator
from uuid import UUID, uuid4

from .models import AnalysisFeedbackIn, InvestmentProfileIn, LedgerEventIn, LedgerType, NoteIn, WatchlistIn


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

        with psycopg.connect(self.dsn, connect_timeout=5, sslmode="require", row_factory=dict_row) as connection:
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

    def create_mcp_oauth_code(self, code_hash: str, value: dict[str, Any], expires_at: int) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO private.mcp_oauth_codes
                   (code_hash,user_id,client_id,redirect_uri,resource,scope,code_challenge,expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,to_timestamp(%s))""",
                (code_hash, value["user_id"], value["client_id"], value["redirect_uri"], value["resource"],
                 value["scope"], value["challenge"], expires_at),
            )

    def consume_mcp_oauth_code(self, code_hash: str, now: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """UPDATE private.mcp_oauth_codes
                   SET consumed_at=now()
                   WHERE code_hash=%s AND consumed_at IS NULL AND expires_at > to_timestamp(%s)
                   RETURNING user_id,client_id,redirect_uri,resource,scope,code_challenge""",
                (code_hash, now),
            ).fetchone()
            return dict(row) if row else None

    def create_mcp_oauth_refresh_token(self, token_hash: str, value: dict[str, Any], expires_at: int) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO private.mcp_oauth_refresh_tokens
                   (token_hash,user_id,client_id,resource,scope,expires_at)
                   VALUES (%s,%s,%s,%s,%s,to_timestamp(%s))""",
                (token_hash, value["user_id"], value["client_id"], value["resource"], value["scope"], expires_at),
            )

    def rotate_mcp_oauth_refresh_token(self, old_hash: str, new_hash: str, client_id: str,
                                      resource: str, now: int, expires_at: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """UPDATE private.mcp_oauth_refresh_tokens
                   SET token_hash=%s,issued_at=to_timestamp(%s),expires_at=to_timestamp(%s)
                   WHERE token_hash=%s AND client_id=%s AND resource=%s
                     AND revoked_at IS NULL AND expires_at > to_timestamp(%s)
                   RETURNING user_id,client_id,resource,scope""",
                (new_hash, now, expires_at, old_hash, client_id, resource, now),
            ).fetchone()
            return dict(row) if row else None

    def revoke_mcp_oauth_refresh_token(self, token_hash: str, client_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE private.mcp_oauth_refresh_tokens SET revoked_at=now()
                   WHERE token_hash=%s AND client_id=%s AND revoked_at IS NULL""",
                (token_hash, client_id),
            )

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

    def stock_identities(self, symbols: set[str]) -> dict[str, dict[str, Any]]:
        requested=sorted({str(symbol).upper() for symbol in symbols if str(symbol).strip()})
        if not requested: return {}
        with self._connection() as connection:
            rows=connection.execute(
                """SELECT symbol,name,market,enabled FROM control.stock_master
                   WHERE symbol = ANY(%s) ORDER BY symbol""",
                (requested,),
            ).fetchall()
        return {str(row["symbol"]):dict(row) for row in rows}

    def latest_ledger_version(self, user_id: UUID) -> int:
        with self._connection() as connection:
            return connection.execute(
                "SELECT COALESCE(MAX(ledger_version),0) AS version FROM private.ledger_events WHERE user_id=%s",
                (user_id,),
            ).fetchone()["version"]

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

    def analysis_feedback(self, user_id: UUID, execution_id: UUID, scope_type: str, scope_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row=connection.execute(
                """SELECT analysis_execution_id,scope_type,scope_id,feedback,reason,version,updated_at
                   FROM private.analysis_feedback
                   WHERE user_id=%s AND analysis_execution_id=%s AND scope_type=%s AND scope_id=%s""",
                (user_id,execution_id,scope_type,scope_id),
            ).fetchone()
            return dict(row) if row else None

    def analysis_feedback_export(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT analysis_execution_id,scope_type,scope_id,feedback,reason,version,updated_at
                   FROM private.analysis_feedback WHERE user_id=%s ORDER BY updated_at,feedback_id""",
                (user_id,),
            ).fetchall()]

    def save_analysis_feedback(self, user_id: UUID, value: AnalysisFeedbackIn, key: str) -> dict[str, Any]:
        with self._connection() as connection:
            target=connection.execute(
                """SELECT deterministic_hash FROM publication.feedback_analysis_targets
                   WHERE execution_id=%s AND scope_type=%s AND scope_id=%s""",
                (value.analysis_execution_id,value.scope_type,value.scope_id),
            ).fetchone()
            if not target: raise NotFoundError("analysis result not found")
            repeated=connection.execute(
                "SELECT * FROM private.analysis_feedback WHERE user_id=%s AND idempotency_key=%s",
                (user_id,key),
            ).fetchone()
            if repeated:
                if (repeated["analysis_execution_id"],repeated["scope_type"],repeated["scope_id"],
                    repeated["feedback"],repeated["reason"]) != (
                    value.analysis_execution_id,value.scope_type,value.scope_id,value.feedback,value.reason):
                    raise ConflictError("feedback idempotency key was reused")
                return dict(repeated)
            row=connection.execute(
                """INSERT INTO private.analysis_feedback(
                       feedback_id,user_id,analysis_execution_id,scope_type,scope_id,analysis_hash,
                       feedback,reason,idempotency_key)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(user_id,analysis_execution_id,scope_type,scope_id) DO UPDATE
                     SET feedback=EXCLUDED.feedback,reason=EXCLUDED.reason,
                         analysis_hash=EXCLUDED.analysis_hash,idempotency_key=EXCLUDED.idempotency_key,
                         version=private.analysis_feedback.version+1,updated_at=now()
                   RETURNING *""",
                (uuid4(),user_id,value.analysis_execution_id,value.scope_type,value.scope_id,
                 target["deterministic_hash"],value.feedback,value.reason,key),
            ).fetchone()
            return dict(row)

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
            return [dict(row) for row in connection.execute("SELECT * FROM private.watchlist WHERE user_id=%s AND active ORDER BY sort_order,symbol",(user_id,)).fetchall()]

    def investment_profile(self, user_id: UUID) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute("""SELECT risk_tolerance,investment_horizon,primary_goal,minimum_cash_ratio,
                                      ai_context_opt_in,version,updated_at
                                      FROM private.investment_profiles WHERE user_id=%s""",(user_id,)).fetchone()
            return dict(row) if row else {"risk_tolerance":None,"investment_horizon":None,"primary_goal":None,
                "minimum_cash_ratio":None,"ai_context_opt_in":False,"version":0,"updated_at":None}

    def save_investment_profile(self, user_id: UUID, value: InvestmentProfileIn, key: str) -> dict[str, Any]:
        with self._connection() as connection:
            replay=self._mutation(connection,user_id,key)
            if replay:
                row=connection.execute("""SELECT risk_tolerance,investment_horizon,primary_goal,minimum_cash_ratio,
                                          ai_context_opt_in,version,updated_at
                                          FROM private.investment_profiles WHERE user_id=%s""",(user_id,)).fetchone()
                if row: return dict(row)
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(f"investment-profile:{user_id}",))
            current=connection.execute("SELECT version FROM private.investment_profiles WHERE user_id=%s FOR UPDATE",(user_id,)).fetchone()
            version=int(current["version"]) if current else 0
            if version != value.expected_version: raise ConflictError("investment profile version changed")
            row=connection.execute(
                """INSERT INTO private.investment_profiles
                   (user_id,risk_tolerance,investment_horizon,primary_goal,minimum_cash_ratio,ai_context_opt_in,version,idempotency_key)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(user_id) DO UPDATE SET risk_tolerance=EXCLUDED.risk_tolerance,
                   investment_horizon=EXCLUDED.investment_horizon,primary_goal=EXCLUDED.primary_goal,
                   minimum_cash_ratio=EXCLUDED.minimum_cash_ratio,ai_context_opt_in=EXCLUDED.ai_context_opt_in,
                   version=EXCLUDED.version,idempotency_key=EXCLUDED.idempotency_key,updated_at=now()
                   RETURNING risk_tolerance,investment_horizon,primary_goal,minimum_cash_ratio,
                             ai_context_opt_in,version,updated_at""",
                (user_id,value.risk_tolerance,value.investment_horizon,value.primary_goal,value.minimum_cash_ratio,
                 value.ai_context_opt_in,version+1,key),).fetchone()
            change_version=self._next_change_version(connection,user_id)
            self._change(connection,user_id,change_version,"investment-profile",user_id,None)
            self._record_mutation(connection,user_id,key,"investment-profile",user_id)
            return dict(row)

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
            connection.execute("SELECT control.record_deep_tracking_demand(%s)", (value.symbol,))
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
            connection.execute("SELECT control.record_deep_tracking_demand(%s)", (symbol,))

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
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM private.watchlist WHERE user_id=%s ORDER BY updated_at,symbol", (user_id,)
            ).fetchall()]

    def investment_profile_for_pipeline(self, user_id: UUID) -> dict[str, Any] | None:
        with self._connection() as connection:
            row=connection.execute("""SELECT user_id,risk_tolerance,investment_horizon,primary_goal,
                                      minimum_cash_ratio,ai_context_opt_in,version,updated_at
                                      FROM private.investment_profiles WHERE user_id=%s""",(user_id,)).fetchone()
            return dict(row) if row else None

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

    def pending_deletions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM private.deletion_requests WHERE status IN ('QUEUED','CLEANUP_PENDING') ORDER BY requested_at LIMIT %s",(min(limit,20),)
            ).fetchall()]

    def complete_deletion(self, request_id: UUID, user_id: UUID) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM private.assistant_threads WHERE user_id=%s",(user_id,))
            connection.execute("DELETE FROM private.assistant_skill_state WHERE user_id=%s",(user_id,))
            connection.execute("DELETE FROM private.assistant_skill_revisions WHERE user_id=%s",(user_id,))
            for table in ("analysis_feedback","change_log","mutation_keys","note_index","watchlist","mcp_servers","mcp_oauth_refresh_tokens","mcp_oauth_codes","investment_profiles","ledger_events","users"):
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
