"""Explicit CEO Job operation and validated baseline serving projection."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from uuid import UUID, uuid4

from packages.analysis_product import baseline_projection, content_hash, freshness, numeric_facts, validate_ceo_output


def persist_screening(connection, artifact):
    from .specialists import digest
    if artifact['output_hash'] != digest({k: v for k, v in artifact.items() if k != 'output_hash'}):
        raise ValueError('screening product hash mismatch')
    identity = artifact['identity']
    with connection.transaction(), connection.cursor() as cursor:
        for row in artifact['rows']:
            payload = {'analysis_as_of': identity['analysis_as_of'], 'core_snapshot_id': identity['core_snapshot_id'],
                       'source_artifact_hash': artifact['output_hash'],
                       'membership_version': identity['membership']['membership_version'],
                       'cohort_size': len(identity['membership']['symbols']),
                       'metrics': row['metrics'], 'cross_sectional_rank': row['cross_sectional_rank'],
                       'candidate_rank': row['candidate_rank'], 'symbol': row['symbol'],
                       'latest_trade_date': row['latest_trade_date'], 'status': row['status'],
                       'model_quality': 'NOT_VERIFIED'}
            hashed = content_hash(payload)
            cursor.execute('''INSERT INTO private.market_screening_product
                (analysis_as_of,core_snapshot_id,symbol,content_hash,payload_json)
                VALUES (%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING''',
                (identity['analysis_as_of'], identity['core_snapshot_id'], row['symbol'], hashed, json.dumps(payload)))
            cursor.execute('''SELECT content_hash FROM private.market_screening_product
                WHERE analysis_as_of=%s AND core_snapshot_id=%s AND symbol=%s''',
                (identity['analysis_as_of'], identity['core_snapshot_id'], row['symbol']))
            if cursor.fetchone()[0] != hashed:
                raise ValueError('immutable screening product conflict')


def persist_products(connection, manifest, store, bucket):
    from hashlib import sha256
    from packages.change_analysis import observations, RULE_VERSION
    change_facts = None
    if manifest.get('change_facts'):
        ref = manifest['change_facts']
        prefix = f'gs://{bucket}/executions/{manifest["execution_id"]}/'
        if not ref['artifact_uri'].startswith(prefix):
            raise ValueError('change facts outside execution prefix')
        raw = store.read(ref['artifact_uri'][len(f'gs://{bucket}/'):])
        if 'sha256:' + sha256(raw).hexdigest() != ref['artifact_hash']:
            raise ValueError('change facts byte hash mismatch')
        change_facts = json.loads(raw)
    analyst_rows = {}
    if manifest.get("analyst_inputs"):
        ref = manifest["analyst_inputs"]
        expected = f'gs://{bucket}/executions/{manifest["execution_id"]}/analyst-inputs.json'
        if ref["artifact_uri"] != expected:
            raise ValueError("analyst input outside execution")
        raw = store.read(expected[len(f"gs://{bucket}/"):])
        if "sha256:" + sha256(raw).hexdigest() != ref["artifact_hash"]:
            raise ValueError("analyst input hash mismatch")
        document = json.loads(raw)
        if (document.get("analysis_as_of") != manifest["analysis_as_of"]
                or document.get("core_snapshot_id") != manifest["core_snapshot_id"]):
            raise ValueError("analyst input identity mismatch")
        for item in document["rows"]:
            if item["symbol"] in analyst_rows:
                raise ValueError("duplicate analyst symbol")
            analyst_rows[item["symbol"]] = item
    risk_rows = {}
    if manifest.get("risk_active"):
        from .risk_active import validate_risk_active_artifact
        ref = manifest["risk_active"]
        prefix = f"gs://{bucket}/risk-active/"
        if not ref["artifact_uri"].startswith(prefix):
            raise ValueError("Risk ACTIVE artifact outside immutable prefix")
        raw = store.read(ref["artifact_uri"][len(f"gs://{bucket}/"):])
        if "sha256:" + sha256(raw).hexdigest() != ref["artifact_hash"]:
            raise ValueError("Risk ACTIVE prediction byte hash mismatch")
        risk_rows = validate_risk_active_artifact(json.loads(raw), manifest)

    for symbol in sorted({r["symbol"] for r in manifest["specialists"]}):
        artifacts = []
        for ref in manifest["specialists"]:
            if ref["symbol"] != symbol:
                continue
            prefix = f"gs://{bucket}/specialists/"
            if not ref["artifact_uri"].startswith(prefix):
                raise ValueError("product artifact outside Mart specialist prefix")
            raw = store.read(ref["artifact_uri"][len(f"gs://{bucket}/"):])
            if "sha256:" + sha256(raw).hexdigest() != ref["artifact_hash"]:
                raise ValueError("product artifact byte hash mismatch")
            artifacts.append(json.loads(raw))
        payload = baseline_projection(manifest, artifacts)
        if symbol in risk_rows:
            # Persist original deterministic baseline and the candidate
            # separately. The API dynamically gates exposure against the
            # current append-only PG activation state, so rollback is instant
            # and never requires rewriting immutable prior analysis.
            payload["risk_first_release_candidate"] = risk_rows[symbol]
            payload["content_hash"] = content_hash(
                {k: v for k, v in payload.items() if k != "content_hash"})
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute('''SELECT payload_json FROM private.specialist_product
                WHERE execution_id=%s AND symbol=%s''', (manifest['execution_id'], symbol))
            existing = cursor.fetchone()
            if existing:
                saved = existing[0]
                if (saved['source_manifest_hash'] != manifest['output_hash'] or
                        saved['content_hash'] != content_hash({k: v for k, v in saved.items() if k != 'content_hash'})):
                    raise ValueError('immutable product projection conflict')
                continue
            if change_facts is not None:
                payload['change_analysis'] = {}
                for session, view in change_facts['views'].items():
                    cursor.execute('''SELECT payload_json FROM private.specialist_product
                        WHERE symbol=%s AND analysis_as_of<=%s
                        AND (payload_json->'change_analysis'->%s->>'cutoff_at')::timestamptz<=%s
                        ORDER BY analysis_as_of DESC,created_at DESC LIMIT 1''',
                        (symbol, manifest['analysis_as_of'], session, view['cutoff_at']))
                    prior = cursor.fetchone()
                    previous = prior[0] if prior else {}
                    if previous and previous['content_hash'] != content_hash(
                            {k: v for k, v in previous.items() if k != 'content_hash'}):
                        raise ValueError('previous observation hash mismatch')
                    payload['change_analysis'][session] = {'rule_version': RULE_VERSION,
                        'cutoff_at': view['cutoff_at'],
                        'observations': observations(view['symbols'][symbol],
                            previous.get('change_analysis', {}).get(session, {}).get('observations', []),
                            symbol=symbol, cutoff_at=view['cutoff_at'])}
                payload['content_hash'] = content_hash({k: v for k, v in payload.items() if k != 'content_hash'})
            if symbol in analyst_rows:
                cursor.execute("""SELECT payload_json FROM private.specialist_product
                    WHERE symbol=%s AND analysis_as_of<=%s AND execution_id<>%s
                    ORDER BY analysis_as_of DESC,created_at DESC LIMIT 1""",
                    (symbol, manifest["analysis_as_of"], manifest["execution_id"]))
                prior = cursor.fetchone()
                previous = prior[0] if prior else None
                if previous and previous["content_hash"] != content_hash(
                        {k: v for k, v in previous.items() if k != "content_hash"}):
                    raise ValueError("previous analyst product hash mismatch")
                payload["analyst_inputs"] = analyst_rows[symbol]
                reference = analyst_rows[symbol].get("valuation_reference")
                if reference is not None:
                    from packages.valuation_reference import validate_published_card
                    payload["valuation_reference"] = validate_published_card(
                        reference, symbol=symbol, as_of=manifest["analysis_as_of"],
                        core_snapshot_id=str(manifest["core_snapshot_id"]))
                from packages.stock_report_policy import attach_stock_report
                attach_stock_report(payload, analyst_rows[symbol], previous)
                payload["content_hash"] = content_hash({k: v for k, v in payload.items() if k != "content_hash"})
            cursor.execute("""INSERT INTO private.specialist_product
                (execution_id,symbol,analysis_as_of,content_hash,payload_json)
                VALUES (%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING""",
                (manifest["execution_id"], symbol, manifest["analysis_as_of"], payload["content_hash"],
                 json.dumps(payload, ensure_ascii=False)))
            cursor.execute("SELECT content_hash FROM private.specialist_product WHERE execution_id=%s AND symbol=%s",
                           (manifest["execution_id"], symbol))
            if cursor.fetchone()[0] != payload["content_hash"]:
                raise ValueError("immutable product projection conflict")


def execute_ceo(request, router, *, should_stop=None):
    """No fitting, scraping, canonical write or model promotion in this path."""
    baseline = request["baseline_json"]
    if (baseline["content_hash"] != request["baseline_hash"] or
            content_hash({k: v for k, v in baseline.items() if k != "content_hash"}) != request["baseline_hash"]):
        raise ValueError("CEO immutable input mismatch")
    inputs = {"fact_pack": baseline, "validated_specialists": baseline["specialists"],
        "validated_role_artifact_hashes": [a["output_hash"] for a in baseline["specialists"]],
        "canonical_numbers_are_read_only": True}
    inputs['previous_analysis'] = request.get('previous_report')
    inputs['numeric_facts'] = numeric_facts(baseline)
    inputs['numeric_claim_policy'] = ('Prefer narrative prose without numbers. Any number in claim text or missing_information '
        'must appear as an exact numeric_facts key=value binding. Do not repeat numeric dates, horizons or stock codes '
        'outside a binding. The canonical UI already displays formatted numbers.')
    result = router.invoke("ceo", inputs, **({"should_stop": should_stop} if should_stop else {}))
    # Never publish raw provider payload, stderr, credentials or arbitrary metadata.
    keys = {"provider", "transport", "model", "attempt", "duration_ms", "status", "reason", "usage",
            "actual_cost_usd", "billing_mode", "role", "invalid_fields"}
    audit = {"attempts": [{k: v for k, v in a.items() if k in keys} for a in result.attempts],
             "route_hash": result.routing["routing_hash"],
             "route": result.routing.get("execution_providers", result.routing["providers"]),
             "execution_policy": result.routing.get("execution_policy", "profile_route"),
             "provider": result.provider, "model": result.model, "publication_authority": False}
    if result.status != "succeeded" or result.output is None:
        allowed = {"invalid_structured_output", "quota", "auth_required", "free_tier_not_confirmed",
                   "provider_unavailable", "transport_error", "timeout",
                    "gateway_identity_unavailable", "gateway_prompt_too_large",
                    "gateway_contract_mismatch", "gateway_endpoint_unapproved",
                    "gateway_context_missing", "gateway_route_disabled"}
        return "BLOCKED", None, audit, result.reason if result.reason in allowed else "provider_unavailable"
    try:
        output = validate_ceo_output(result.output, baseline, has_previous=bool(request.get('previous_report')))
    except ValueError:
        return "BLOCKED", None, audit, "output_validation_failed"
    report = {"schema_version": "ceo-report.v1", "execution_id": str(request["request_id"]),
        "symbol": request["symbol"], "analysis_as_of": baseline["analysis_as_of"],
        "baseline_hash": request["baseline_hash"], "profile_id": request["profile_id"],
        "profile_version": request["profile_version"], "output": output,
        "publication_authority": False}
    return "PARTIAL" if output["missing_information"] else "SUCCEEDED", report, audit, None


def run_ceo_request():
    from packages.postgres_bundle import load_postgres_bundle
    from .runtime import _settings
    from .provider_routing import ProviderRouter
    import psycopg
    from psycopg.rows import dict_row
    request_id = UUID(os.environ["CEO_REQUEST_ID"])
    load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
        "PUBLICATION_DB_PASSWORD": ("mart_publication_password", "publication_password")})
    settings = _settings("PUBLICATION_DB")
    lease = uuid4()
    @contextmanager
    def connect():
        with psycopg.connect(host=settings["host"], dbname=settings["name"], user=settings["user"],
            password=settings["password"], sslmode="require", connect_timeout=5, row_factory=dict_row,
            options="-c statement_timeout=15000") as connection:
            yield connection
    with connect() as connection:
        # Claim this exact manual request once. An unknown/failed invocation is
        # never retried by this worker; retry means a new explicit request.
        row = connection.execute("""UPDATE private.ceo_requests SET status='RUNNING',lease_token=%s,
            started_at=now(),worker_execution=%s WHERE request_id=%s AND status='QUEUED'
            RETURNING *""", (lease, os.getenv("CLOUD_RUN_EXECUTION"), request_id)).fetchone()
    if not row:
        return {"operation": "ceo-request", "status": "not_claimed"}
    request = dict(row)
    state, report, audit, reason = "FAILED", None, {}, "worker_failed"
    try:
        with connect() as connection:
            cap = connection.execute("""SELECT enabled,daily_quota FROM private.ceo_capability_revisions
                WHERE user_id=%s ORDER BY version DESC LIMIT 1""", (request["user_id"],)).fetchone()
            profile = connection.execute("""SELECT approved FROM private.ceo_profile_revisions
                WHERE profile_id=%s ORDER BY version DESC LIMIT 1""", (request["profile_id"],)).fetchone()
            previous = connection.execute('''SELECT report_json,report_hash FROM private.ceo_requests
                WHERE user_id=%s AND symbol=%s AND requested_at<%s AND report_json IS NOT NULL
                AND status IN ('SUCCEEDED','PARTIAL') ORDER BY requested_at DESC LIMIT 1''',
                (request['user_id'], request['symbol'], request['requested_at'])).fetchone()
            if previous:
                if content_hash(previous['report_json']) != previous['report_hash']:
                    raise ValueError('previous CEO report hash mismatch')
                request['previous_report'] = previous['report_json']
        from datetime import datetime
        from zoneinfo import ZoneInfo
        if freshness(request['baseline_json'], datetime.now(ZoneInfo('Asia/Taipei')).date()) != 'current':
            state, reason = 'BLOCKED', 'baseline_expired'
        elif not cap or not cap["enabled"] or cap["daily_quota"] <= 0 or not profile or not profile["approved"]:
            state, reason = "BLOCKED", "authorization_revoked"
        else:
            # Cancellation is checked before each provider/fallback. An in-flight
            # remote call ends at its bounded timeout; its result is discarded.
            def should_stop():
                with connect() as connection:
                    row = connection.execute("SELECT status FROM private.ceo_requests WHERE request_id=%s AND lease_token=%s",
                        (request_id, lease)).fetchone()
                    return not row or row["status"] != "RUNNING"
            from contextlib import nullcontext
            from .codex_auth import auth_session
            session = (auth_session() if os.getenv('MART_CODEX_AUTH_SECRET') and
                       os.getenv('MART_CEO_GEMINI_ONLY', '').lower() != 'true' else nullcontext(None))
            with session as auth:
                router = ProviderRouter.from_environment({'ai_provider_routing': request['route_json']}, bounded_manual=True)
                # Bind the authenticated Janus owner and immutable request outside the Gemini prompt.
                gateway = router.providers['gemini']
                if hasattr(gateway, 'bind_context'):
                    gateway.bind_context(owner_id=str(request['user_id']), request_id=str(request_id))
                if auth is not None:
                    router.providers['codex_cli'].auth_error = auth.reason
                    router.providers['codex_cli'].auth_checkpoint = auth.checkpoint
                    router = ProviderRouter(router.providers, router.routing)
                state, report, audit, reason = execute_ceo(request, router, should_stop=should_stop)
                if auth is not None:
                    audit['codex_auth'] = auth.metadata()
            if report is not None and not should_stop():
                from ingestion_core.stage import GcsObjectStore
                from .runtime import _write_immutable_json
                completed_state, completed_report = state, report
                state, report, reason = 'FAILED', None, 'report_persist_failed'
                bucket = os.environ['MART_BUCKET']
                store = GcsObjectStore(bucket)
                name = f'ceo/{request_id}/report.json'
                _write_immutable_json(store, bucket, name, completed_report)
                if json.loads(store.read(name)) != completed_report:
                    raise ValueError('CEO immutable artifact readback mismatch')
                state, report, reason = completed_state, completed_report, None
    finally:
        with connect() as connection:
            current = connection.execute("""SELECT status FROM private.ceo_requests
                WHERE request_id=%s AND lease_token=%s FOR UPDATE""", (request_id, lease)).fetchone()
            if current and current["status"] in {"RUNNING", "CANCEL_REQUESTED"}:
                if current["status"] == "CANCEL_REQUESTED":
                    state, report, reason = "CANCELLED", None, "cancelled"
                connection.execute("""UPDATE private.ceo_requests SET status=%s,finished_at=now(),
                    report_json=%s::jsonb,report_hash=%s,audit_json=%s::jsonb,safe_reason=%s
                    WHERE request_id=%s AND lease_token=%s""",
                    (state, json.dumps(report, ensure_ascii=False) if report else None,
                     content_hash(report) if report else None, json.dumps(audit), reason, request_id, lease))
    return {"operation": "ceo-request", "request_id": str(request_id), "status": state}
