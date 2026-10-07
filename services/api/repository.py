"""Bounded PostgreSQL operations for the private workspace."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import json
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

    def user_id_for_email(self, email: str) -> UUID:
        normalized = email.strip().lower()
        if not normalized:
            raise NotFoundError("user email is required")
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT user_id FROM private.users
                   WHERE lower(display_email)=%s
                   ORDER BY user_id
                   LIMIT 2""",
                (normalized,),
            ).fetchall()
        if len(rows) != 1:
            raise NotFoundError("user email does not resolve uniquely")
        return rows[0]["user_id"]

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
            connection.execute("SELECT private.refresh_current_positions(%s)", (user_id,))
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
            connection.execute("SELECT private.refresh_current_positions(%s)", (user_id,))
            return dict(row)

    def reverse_ledger(self, user_id: UUID, event_id: UUID, expected: int, key: str) -> dict[str, Any]:
        """Void one effective ledger event by appending a reversal-only event."""
        with self._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(str(event_id),))
            repeated=connection.execute(
                "SELECT * FROM private.ledger_events WHERE user_id=%s AND idempotency_key=%s",
                (user_id,key),
            ).fetchone()
            if repeated:
                if repeated["event_action"]=="REVERSAL" and repeated["reverses_event_id"]==event_id:
                    return dict(repeated)
                raise ConflictError("ledger reversal idempotency key was reused")
            original=connection.execute(
                "SELECT * FROM private.ledger_events WHERE user_id=%s AND event_id=%s",
                (user_id,event_id),
            ).fetchone()
            if not original:
                raise NotFoundError("ledger event not found")
            if original["event_action"]=="REVERSAL":
                raise ConflictError("ledger reversal cannot be reversed")
            if original["record_version"]!=expected:
                raise ConflictError("ledger event version changed")
            if connection.execute(
                "SELECT 1 FROM private.ledger_events WHERE user_id=%s AND reverses_event_id=%s",
                (user_id,event_id),
            ).fetchone():
                raise ConflictError("ledger event was already reversed")

            if original["event_type"] in (LedgerType.BUY,LedgerType.STOCK_DIV):
                active=connection.execute(
                    """SELECT e.event_type,e.shares
                       FROM private.ledger_events e
                       WHERE e.user_id=%s AND e.symbol=%s AND e.event_id<>%s
                         AND e.event_action<>'REVERSAL'
                         AND NOT EXISTS (
                           SELECT 1 FROM private.ledger_events r
                           WHERE r.user_id=e.user_id
                             AND r.event_action='REVERSAL'
                             AND r.reverses_event_id=e.event_id
                         )
                       ORDER BY e.trade_date,e.ledger_version""",
                    (user_id,original["symbol"],event_id),
                ).fetchall()
                running=Decimal("0")
                for row in active:
                    if row["event_type"] in (LedgerType.BUY,LedgerType.STOCK_DIV):
                        running+=Decimal(str(row["shares"] or 0))
                    elif row["event_type"]==LedgerType.SELL:
                        running-=Decimal(str(row["shares"] or 0))
                    if running<0:
                        raise OversellError("reversal would leave a sell without enough shares")

            reversal_version=self._next_version(connection,user_id)
            reversal_id=uuid4()
            row=connection.execute(
                """INSERT INTO private.ledger_events
                   (event_id,user_id,ledger_version,event_action,event_type,trade_date,symbol,shares,price,cash_amount,fee,tax,currency,memo,idempotency_key,reverses_event_id)
                   VALUES (%s,%s,%s,'REVERSAL',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (reversal_id,user_id,reversal_version,original["event_type"],original["trade_date"],original["symbol"],
                 original["shares"],original["price"],original["cash_amount"],original["fee"],original["tax"],
                 original["currency"],original["memo"],key,event_id),
            ).fetchone()
            self._change(connection,user_id,self._next_change_version(connection,user_id),"ledger",reversal_id,None)
            connection.execute("SELECT private.refresh_current_positions(%s)",(user_id,))
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
            row=connection.execute("SELECT * FROM private.note_index WHERE user_id=%s AND note_id=%s FOR UPDATE",(user_id,note_id)).fetchone()
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
            return [dict(row) for row in connection.execute(
                """SELECT w.*,s.name AS stock_name,
                   price.payload_json->>'close' AS market_price,
                   price.payload_json->>'trade_date' AS price_date,
                   CASE WHEN price.payload_json IS NULL THEN 'missing' ELSE 'persisted' END AS price_status,
                   EXISTS(SELECT 1 FROM private.current_positions p
                          WHERE p.user_id=w.user_id AND p.symbol=w.symbol AND p.shares>0) AS held,
                   (SELECT count(*) FROM private.note_index n
                    WHERE n.user_id=w.user_id AND n.symbol=w.symbol AND n.needs_follow_up) AS pending_note_count,
                   EXISTS(
                     SELECT 1 FROM control.liquid_500_members m
                     WHERE m.symbol=w.symbol AND s.market='TWSE' AND m.version=(
                       SELECT version FROM control.liquid_500_versions
                       WHERE effective_from<=now() ORDER BY effective_from DESC LIMIT 1)
                   ) AS in_market_500
                   FROM private.watchlist w LEFT JOIN control.stock_master s ON s.symbol=w.symbol
                   LEFT JOIN publication.stock_latest price ON price.symbol=w.symbol AND price.dataset_id='ohlcv'
                   WHERE w.user_id=%s AND w.active
                   ORDER BY w.sort_order,w.symbol""",
                (user_id,),
            ).fetchall()]

    def search_watchlist_stocks(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT s.symbol,s.name AS stock_name FROM control.stock_master s
                   JOIN control.liquid_500_members m ON m.symbol=s.symbol
                   WHERE s.market='TWSE' AND s.enabled AND m.version=(
                     SELECT version FROM control.liquid_500_versions
                     WHERE effective_from<=now() ORDER BY effective_from DESC LIMIT 1)
                   AND (strpos(lower(s.symbol),lower(%s))>0 OR strpos(s.name,%s)>0)
                   ORDER BY s.symbol LIMIT %s""", (query, query, min(limit, 20)),
            ).fetchall()]

    def investment_profile(self, user_id: UUID) -> dict[str, Any]:
        with self._connection() as connection:
            row=connection.execute("""SELECT risk_tolerance,investment_horizon,primary_goal,minimum_cash_ratio,
                                      ai_context_opt_in,version,updated_at
                                      FROM private.investment_profiles WHERE user_id=%s""",(user_id,)).fetchone()
            return dict(row) if row else {"risk_tolerance":None,"investment_horizon":None,"primary_goal":None,
                "minimum_cash_ratio":None,"ai_context_opt_in":False,"version":0,"updated_at":None}

    def last_quotes(self, identities) -> dict[str, dict[str, Any]]:
        if not identities:
            return {}
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM control.operational_last_quotes WHERE symbol=ANY(%s)",
                (sorted(identities),)).fetchall()
            return {row['symbol']: {**dict(row), 'price': str(row['price']),
                    'quote_at': row['quote_at'].isoformat(),
                    'received_at': row['received_at'].isoformat()} for row in rows}

    def eod_quotes(self, identities) -> dict[str, dict[str, Any]]:
        if not identities:
            return {}
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT symbol,sort_at,payload_json
                   FROM publication.stock_latest
                   WHERE dataset_id='ohlcv' AND symbol=ANY(%s)""",
                (sorted(identities),),
            ).fetchall()
        result = {}
        for row in rows:
            payload = row["payload_json"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            close = payload.get("close") if isinstance(payload, dict) else None
            trade_date = payload.get("trade_date") if isinstance(payload, dict) else None
            if close in (None, "") or trade_date in (None, ""):
                continue
            result[str(row["symbol"])] = {
                "price": str(close),
                "price_date": str(trade_date)[:10],
                "quote_at": None,
                "received_at": row["sort_at"].isoformat() if row.get("sort_at") else None,
                "session": "eod",
                "source": "core_ohlcv",
                "route_version": "latest-price.v2",
                "is_final": True,
            }
        return result

    def save_last_quotes(self, quotes) -> None:
        with self._connection() as connection:
            for symbol, row in sorted(quotes.items()):
                connection.execute("""INSERT INTO control.operational_last_quotes
                    (symbol,price,quote_at,received_at,session,source,route_version)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(symbol) DO UPDATE SET price=EXCLUDED.price,
                    quote_at=EXCLUDED.quote_at,received_at=EXCLUDED.received_at,
                    session=EXCLUDED.session,source=EXCLUDED.source,route_version=EXCLUDED.route_version
                    WHERE EXCLUDED.quote_at >= operational_last_quotes.quote_at""",
                    (symbol,row['price'],row['quote_at'],row['received_at'],row['session'],row['source'],row['route_version']))

    def broker_profile(self, user_id: UUID) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("""SELECT * FROM private.broker_profile_revisions
                WHERE user_id=%s ORDER BY version DESC LIMIT 1""", (user_id,)).fetchone()
            return dict(row) if row else {'version': 0, 'declared_cash': None,
                'cash_as_of': None, 'currency': 'TWD', 'rule_version': 'broker-profile.v1'}

    def broker_profile_history(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute("""SELECT * FROM private.broker_profile_revisions
                WHERE user_id=%s ORDER BY version""", (user_id,)).fetchall()]

    def save_broker_profile(self, user_id: UUID, value, key: str) -> dict[str, Any]:
        with self._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f'broker-profile:{user_id}',))
            if not connection.execute("SELECT user_id FROM private.users WHERE user_id=%s FOR UPDATE", (user_id,)).fetchone():
                raise NotFoundError('private user not found')
            replay = connection.execute("""SELECT * FROM private.broker_profile_revisions
                WHERE user_id=%s AND idempotency_key=%s""", (user_id,key)).fetchone()
            if replay:
                return dict(replay)
            current = connection.execute("""SELECT COALESCE(MAX(version),0) AS version
                FROM private.broker_profile_revisions WHERE user_id=%s""", (user_id,)).fetchone()
            if current['version'] != value.expected_version:
                raise ConflictError('broker profile version changed')
            row = connection.execute("""INSERT INTO private.broker_profile_revisions
                (user_id,version,fee_discount_multiplier,minimum_fee,cash_strategy,declared_cash,cash_as_of,idempotency_key)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (user_id,value.expected_version+1,value.fee_discount_multiplier,value.minimum_fee,
                 value.cash_strategy,value.declared_cash,value.cash_as_of,key)).fetchone()
            self._change(connection,user_id,self._next_change_version(connection,user_id),'broker-profile',user_id,None)
            return dict(row)

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
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('private-watchlist-symbol-limit'))")
            replay=self._mutation(connection,user_id,key)
            if replay:
                row=connection.execute("SELECT * FROM private.watchlist WHERE user_id=%s AND symbol=%s",(user_id,replay["entity_id"])).fetchone()
                if row: return dict(row)
            count = connection.execute("SELECT count(*) AS count FROM private.watchlist WHERE user_id=%s AND active",(user_id,)).fetchone()["count"]
            existing = connection.execute("SELECT * FROM private.watchlist WHERE user_id=%s AND symbol=%s FOR UPDATE",(user_id,value.symbol)).fetchone()
            if existing and existing["idempotency_key"]==key: return dict(existing)
            if not existing or not existing["active"]:
                eligible = connection.execute(
                    """SELECT 1 FROM control.liquid_500_members m
                       JOIN control.stock_master s ON s.symbol=m.symbol
                       WHERE m.symbol=%s AND s.market='TWSE' AND m.version=(
                         SELECT version FROM control.liquid_500_versions
                         WHERE effective_from<=now() ORDER BY effective_from DESC LIMIT 1)""",
                    (value.symbol,),
                ).fetchone()
                if not eligible: raise ConflictError("stock is not in the current market 500")
            if count >= 50 and not (existing and existing["active"]): raise ConflictError("watchlist limit reached")
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

    @staticmethod
    def _reap_stale_recalculations(connection: Any) -> None:
        connection.execute(
            """UPDATE private.recalculation_requests
               SET status=CASE WHEN status='CANCEL_REQUESTED' THEN 'CANCELLED' ELSE 'FAILED' END,
                   error_code=CASE WHEN status='CANCEL_REQUESTED' THEN 'ADMIN_CANCELLED' ELSE 'WORKER_TIMEOUT' END,
                   safe_message=CASE
                     WHEN status='CANCEL_REQUESTED' THEN COALESCE(safe_message,'管理員已中止本次重算')
                     ELSE '損益重算 worker 中斷或逾時，已停止等待，可重新嘗試'
                   END,
                   finished_at=now(),updated_at=now()
               WHERE status IN ('RUNNING','CANCEL_REQUESTED')
                 AND updated_at < now() - interval '35 minutes'"""
        )
        dispatch = connection.execute(
            "SELECT active,updated_at FROM private.recalculation_dispatch WHERE singleton=true FOR UPDATE"
        ).fetchone()
        if dispatch and dispatch["active"]:
            running = connection.execute(
                """SELECT 1 FROM private.recalculation_requests
                   WHERE status IN ('RUNNING','CANCEL_REQUESTED') LIMIT 1"""
            ).fetchone()
            connection.execute(
                """UPDATE private.recalculation_requests
                   SET status='FAILED',error_code='DISPATCH_TIMEOUT',
                       safe_message='損益重算 worker 未能啟動，已停止等待，可重新嘗試',
                       finished_at=now(),updated_at=now()
                   WHERE status='QUEUED'
                     AND %s < now() - interval '5 minutes'
                     AND %s = false""",
                (dispatch["updated_at"], bool(running)),
            )
        connection.execute(
            """UPDATE private.recalculation_dispatch
               SET active=false,updated_at=now()
               WHERE singleton=true
                 AND NOT EXISTS (
                   SELECT 1 FROM private.recalculation_requests
                   WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')
                 )"""
        )

    def enqueue_recalculation(self, user_id: UUID, trigger_source: str) -> dict[str, Any]:
        if trigger_source not in {"mutation", "manual"}:
            raise ValueError("recalculation trigger source is invalid")
        with self._connection() as connection:
            self._reap_stale_recalculations(connection)
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"private-recalc:{user_id}",))
            latest = connection.execute(
                "SELECT ledger_version FROM private.users WHERE user_id=%s",
                (user_id,),
            ).fetchone()
            if not latest:
                raise NotFoundError("user not found")
            active = connection.execute(
                """SELECT * FROM private.recalculation_requests
                   WHERE user_id=%s AND status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')
                   ORDER BY requested_at DESC LIMIT 1""",
                (user_id,),
            ).fetchone()
            if active:
                refreshed = connection.execute(
                    """UPDATE private.recalculation_requests
                       SET requested_ledger_version=GREATEST(requested_ledger_version,%s),updated_at=now()
                       WHERE request_id=%s RETURNING *""",
                    (int(latest["ledger_version"]), active["request_id"]),
                ).fetchone()
                result = dict(refreshed)
                result["should_dispatch"] = False
                result["already_active"] = True
                return result
            request_id = uuid4()
            row = connection.execute(
                """INSERT INTO private.recalculation_requests(
                       request_id,user_id,requested_ledger_version,status,trigger_source
                   ) VALUES(%s,%s,%s,'QUEUED',%s)
                   RETURNING *""",
                (request_id, user_id, int(latest["ledger_version"]), trigger_source),
            ).fetchone()
            dispatch = connection.execute(
                "SELECT active,generation FROM private.recalculation_dispatch WHERE singleton=true FOR UPDATE"
            ).fetchone()
            if not dispatch:
                raise RuntimeError("recalculation dispatch state is unavailable")
            should_dispatch = not bool(dispatch["active"])
            if should_dispatch:
                connection.execute(
                    """UPDATE private.recalculation_dispatch
                       SET active=true,generation=generation+1,updated_at=now()
                       WHERE singleton=true"""
                )
            result = dict(row)
            result["should_dispatch"] = should_dispatch
            result["already_active"] = False
            return result

    def recalculation_status(self, user_id: UUID) -> dict[str, Any] | None:
        with self._connection() as connection:
            self._reap_stale_recalculations(connection)
            row = connection.execute(
                """SELECT request_id,requested_ledger_version,status,trigger_source,error_code,safe_message,
                          requested_at,started_at,finished_at,updated_at
                   FROM private.recalculation_requests
                   WHERE user_id=%s
                   ORDER BY requested_at DESC LIMIT 1""",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def fail_recalculation_dispatch(self, request_id: UUID, code: str, message: str) -> None:
        safe_code = str(code or "TRIGGER_FAILED")[:80]
        safe_message = str(message or "重算服務啟動失敗")[:300]
        with self._connection() as connection:
            connection.execute(
                """UPDATE private.recalculation_requests
                   SET status='FAILED',error_code=%s,safe_message=%s,finished_at=now(),updated_at=now()
                   WHERE request_id=%s AND status='QUEUED'""",
                (safe_code, safe_message, request_id),
            )
            connection.execute(
                """UPDATE private.recalculation_dispatch d
                   SET active=false,updated_at=now()
                   WHERE d.singleton=true
                     AND NOT EXISTS (
                       SELECT 1 FROM private.recalculation_requests
                       WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')
                     )"""
            )

    def claim_recalculation(self, execution_name: str | None, task_index: int) -> dict[str, Any] | None:
        if task_index < 0:
            raise ValueError("worker task index is invalid")
        with self._connection() as connection:
            self._reap_stale_recalculations(connection)
            row = connection.execute(
                """SELECT * FROM private.recalculation_requests
                   WHERE status='QUEUED'
                   ORDER BY requested_at,request_id
                   FOR UPDATE SKIP LOCKED
                   LIMIT 1"""
            ).fetchone()
            if not row:
                return None
            lease = uuid4()
            claimed = connection.execute(
                """UPDATE private.recalculation_requests
                   SET status='RUNNING',lease_token=%s,worker_execution=%s,worker_task_index=%s,
                       attempt_count=attempt_count+1,started_at=COALESCE(started_at,now()),updated_at=now(),
                       error_code=NULL,safe_message=NULL
                   WHERE request_id=%s
                   RETURNING *""",
                (lease, (execution_name or "")[:300] or None, task_index, row["request_id"]),
            ).fetchone()
            connection.execute(
                "UPDATE private.recalculation_dispatch SET updated_at=now() WHERE singleton=true AND active"
            )
            return dict(claimed)

    def heartbeat_recalculation(self, request_id: UUID, lease_token: UUID) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE private.recalculation_requests
                   SET updated_at=now()
                   WHERE request_id=%s AND lease_token=%s AND status='RUNNING'""",
                (request_id, lease_token),
            )
            connection.execute(
                "UPDATE private.recalculation_dispatch SET updated_at=now() WHERE singleton=true AND active"
            )

    def recalculation_should_stop(self, request_id: UUID, lease_token: UUID) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT status,lease_token FROM private.recalculation_requests
                   WHERE request_id=%s""",
                (request_id,),
            ).fetchone()
            return (
                not row
                or row["lease_token"] != lease_token
                or row["status"] != "RUNNING"
            )

    def finish_recalculation(
        self,
        request_id: UUID,
        lease_token: UUID,
        *,
        succeeded: bool,
        processed_ledger_version: int | None = None,
        error_code: str | None = None,
        safe_message: str | None = None,
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
            current = connection.execute(
                """SELECT status FROM private.recalculation_requests
                   WHERE request_id=%s AND lease_token=%s FOR UPDATE""",
                (request_id, lease_token),
            ).fetchone()
            if not current:
                return None
            if current["status"] == "CANCEL_REQUESTED":
                status_value, code, message = "CANCELLED", "ADMIN_CANCELLED", safe_message or "管理員已中止本次重算"
            elif current["status"] != "RUNNING":
                return None
            elif succeeded:
                if processed_ledger_version is None:
                    raise ValueError("processed ledger version is required for success")
                version = connection.execute(
                    """SELECT requested_ledger_version FROM private.recalculation_requests
                       WHERE request_id=%s AND lease_token=%s""",
                    (request_id, lease_token),
                ).fetchone()
                if version and int(version["requested_ledger_version"]) > int(processed_ledger_version):
                    row = connection.execute(
                        """UPDATE private.recalculation_requests
                           SET status='QUEUED',lease_token=NULL,worker_execution=NULL,worker_task_index=NULL,
                               error_code=NULL,safe_message='交易版本已更新，重新排隊計算',updated_at=now()
                           WHERE request_id=%s AND lease_token=%s
                           RETURNING *""",
                        (request_id, lease_token),
                    ).fetchone()
                    return dict(row) if row else None
                status_value, code, message = "SUCCEEDED", None, None
            else:
                status_value = "FAILED"
                code = str(error_code or "RECALCULATION_FAILED")[:80]
                message = str(safe_message or "損益重算失敗，可重新嘗試")[:300]
            row = connection.execute(
                """UPDATE private.recalculation_requests
                   SET status=%s,error_code=%s,safe_message=%s,finished_at=now(),updated_at=now()
                   WHERE request_id=%s AND lease_token=%s
                   RETURNING *""",
                (status_value, code, message, request_id, lease_token),
            ).fetchone()
            return dict(row) if row else None

    def release_recalculation_dispatch_if_idle(self) -> bool:
        with self._connection() as connection:
            dispatch = connection.execute(
                "SELECT active FROM private.recalculation_dispatch WHERE singleton=true FOR UPDATE"
            ).fetchone()
            if not dispatch:
                return False
            active = connection.execute(
                """SELECT 1 FROM private.recalculation_requests
                   WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED') LIMIT 1"""
            ).fetchone()
            if active:
                return False
            connection.execute(
                "UPDATE private.recalculation_dispatch SET active=false,updated_at=now() WHERE singleton=true"
            )
            return True

    @contextmanager
    def private_mart_write_lock(self) -> Iterator[None]:
        import psycopg
        with psycopg.connect(self.dsn, connect_timeout=5, sslmode="require", autocommit=True) as connection:
            connection.execute("SELECT pg_advisory_lock(1835102836,3)")
            try:
                yield
            finally:
                connection.execute("SELECT pg_advisory_unlock(1835102836,3)")

    def admin_recalculations(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded = min(max(int(limit), 1), 100)
        with self._connection() as connection:
            self._reap_stale_recalculations(connection)
            return [dict(row) for row in connection.execute(
                """SELECT request_id,left(user_id::text,8) AS owner_ref,requested_ledger_version,
                          status,trigger_source,worker_execution,worker_task_index,attempt_count,
                          error_code,safe_message,requested_at,started_at,finished_at,updated_at
                   FROM private.recalculation_requests
                   ORDER BY requested_at DESC LIMIT %s""",
                (bounded,),
            ).fetchall()]

    def admin_cancel_recalculation(self, request_id: UUID, message: str, actor: str) -> dict[str, Any]:
        safe_message = str(message or "管理員要求中止")[:300]
        safe_actor = str(actor or "").strip()[:254]
        if not safe_actor:
            raise ValueError("admin actor is required")
        with self._connection() as connection:
            row = connection.execute(
                """SELECT status FROM private.recalculation_requests
                   WHERE request_id=%s FOR UPDATE""",
                (request_id,),
            ).fetchone()
            if not row:
                raise NotFoundError("recalculation request not found")
            if row["status"] == "QUEUED":
                status_value = "CANCELLED"
                finished = True
            elif row["status"] == "RUNNING":
                status_value = "CANCEL_REQUESTED"
                finished = False
            elif row["status"] == "CANCEL_REQUESTED":
                status_value = "CANCEL_REQUESTED"
                finished = False
            else:
                return dict(connection.execute(
                    "SELECT * FROM private.recalculation_requests WHERE request_id=%s",
                    (request_id,),
                ).fetchone())
            updated = connection.execute(
                """UPDATE private.recalculation_requests
                   SET status=%s,error_code='ADMIN_CANCELLED',safe_message=%s,
                       admin_actor=%s,admin_action='cancel',
                       finished_at=CASE WHEN %s THEN now() ELSE finished_at END,updated_at=now()
                   WHERE request_id=%s RETURNING *""",
                (status_value, safe_message, safe_actor, finished, request_id),
            ).fetchone()
            connection.execute(
                """UPDATE private.recalculation_dispatch
                   SET active=false,updated_at=now()
                   WHERE singleton=true
                     AND NOT EXISTS (
                       SELECT 1 FROM private.recalculation_requests
                       WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')
                     )"""
            )
            return dict(updated)

    def admin_fail_recalculation(self, request_id: UUID, message: str, actor: str) -> dict[str, Any]:
        safe_message = str(message or "").strip()
        safe_actor = str(actor or "").strip()[:254]
        if not safe_actor:
            raise ValueError("admin actor is required")
        if not safe_message:
            raise ValueError("failure reason is required")
        if len(safe_message) > 300:
            raise ValueError("failure reason is too long")
        with self._connection() as connection:
            row = connection.execute(
                """UPDATE private.recalculation_requests
                   SET status='FAILED',error_code='ADMIN_FORCED_FAILED',safe_message=%s,
                       admin_actor=%s,admin_action='force_failed',
                       finished_at=now(),updated_at=now()
                   WHERE request_id=%s AND status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')
                   RETURNING *""",
                (safe_message, safe_actor, request_id),
            ).fetchone()
            if row:
                connection.execute(
                    """UPDATE private.recalculation_dispatch
                       SET active=false,updated_at=now()
                       WHERE singleton=true
                         AND NOT EXISTS (
                           SELECT 1 FROM private.recalculation_requests
                           WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')
                         )"""
                )
                return dict(row)
            existing = connection.execute(
                "SELECT * FROM private.recalculation_requests WHERE request_id=%s",
                (request_id,),
            ).fetchone()
            if not existing:
                raise NotFoundError("recalculation request not found")
            return dict(existing)

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

    def record_pipeline_status(
        self,
        *,
        valuation_date: date | None,
        result: str,
        execution_name: str | None = None,
        name: str = "private-core",
    ) -> dict[str, Any]:
        if result not in {"running", "succeeded", "failed"}:
            raise ValueError("private pipeline result is invalid")
        execution = (execution_name or "").strip() or None
        if execution is not None:
            execution = execution[:300]
        with self._connection() as connection:
            metrics = connection.execute(
                """WITH checkpoint AS (
                       SELECT COALESCE((
                           SELECT change_id FROM private.pipeline_checkpoints
                           WHERE pipeline_name=%s
                       ), 0) AS value
                   )
                   SELECT
                     checkpoint.value AS checkpoint_change_id,
                     GREATEST(
                       checkpoint.value,
                       COALESCE((SELECT MAX(change_id) FROM private.change_log), 0)
                     ) AS latest_change_id,
                     (SELECT COUNT(*) FROM private.change_log
                       WHERE change_id > checkpoint.value) AS pending_changes,
                     COALESCE((SELECT MAX(ledger_version) FROM private.ledger_events), 0)
                       AS latest_ledger_version
                   FROM checkpoint""",
                (name,),
            ).fetchone()
            row = connection.execute(
                """INSERT INTO control.private_pipeline_status(
                       pipeline_name,checkpoint_change_id,latest_change_id,pending_changes,
                       latest_ledger_version,valuation_date,last_result,execution_name,updated_at
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,now())
                   ON CONFLICT(pipeline_name) DO UPDATE SET
                       checkpoint_change_id=EXCLUDED.checkpoint_change_id,
                       latest_change_id=EXCLUDED.latest_change_id,
                       pending_changes=EXCLUDED.pending_changes,
                       latest_ledger_version=EXCLUDED.latest_ledger_version,
                       valuation_date=COALESCE(
                           EXCLUDED.valuation_date,
                           control.private_pipeline_status.valuation_date
                       ),
                       last_result=EXCLUDED.last_result,
                       execution_name=EXCLUDED.execution_name,
                       updated_at=now()
                   RETURNING pipeline_name,checkpoint_change_id,latest_change_id,pending_changes,
                             latest_ledger_version,valuation_date,last_result,execution_name,updated_at""",
                (
                    name,
                    metrics["checkpoint_change_id"],
                    metrics["latest_change_id"],
                    metrics["pending_changes"],
                    metrics["latest_ledger_version"],
                    valuation_date,
                    result,
                    execution,
                ),
            ).fetchone()
            return dict(row)

    def portfolio_user_ids_for_pipeline(self, limit: int = 500) -> list[UUID]:
        bounded_limit = min(max(int(limit), 1), 500)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT user_id FROM private.ledger_events ORDER BY user_id LIMIT %s",
                (bounded_limit,),
            ).fetchall()
            return [row["user_id"] for row in rows]

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
            # Serialize with profile creation before deleting its revisions.
            connection.execute("SELECT user_id FROM private.users WHERE user_id=%s FOR UPDATE", (user_id,))
            connection.execute("DELETE FROM private.assistant_threads WHERE user_id=%s",(user_id,))
            connection.execute("DELETE FROM private.assistant_skill_state WHERE user_id=%s",(user_id,))
            connection.execute("DELETE FROM private.assistant_skill_revisions WHERE user_id=%s",(user_id,))
            for table in ("analysis_feedback","change_log","mutation_keys","note_index","watchlist","mcp_servers","mcp_oauth_refresh_tokens","mcp_oauth_codes","broker_profile_revisions","investment_profiles","current_positions","ledger_events","users"):
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
    def _position(connection: Any,user_id: UUID,symbol:str,exclude: UUID | None=None) -> Decimal:
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
