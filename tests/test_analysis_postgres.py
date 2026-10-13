"""Real PostgreSQL security/concurrency gate; CI uses an isolated service DB."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

from packages.analysis_product import content_hash
from services.api.analysis import AnalysisService, CEOCapabilityIn, CEOProfileIn


@pytest.fixture(scope='module')
def database():
    dsn = os.getenv('ANALYSIS_TEST_DSN')
    if not dsn:
        pytest.skip('isolated PostgreSQL service unavailable locally; mandatory release CI gate')
    # Never initialize a production database. This gate has a dedicated CI DB.
    with psycopg.connect(dsn, autocommit=True) as connection:
        info = connection.info
        assert info.dbname == 'janus_analysis_test' and info.host in {'localhost', '127.0.0.1', 'postgres'}
        for role in ('janus_control', 'janus_private_api', 'janus_mart_publication', 'janus_public_api'):
            if not connection.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
                connection.execute(f'CREATE ROLE {role} NOLOGIN')
        connection.execute('CREATE SCHEMA IF NOT EXISTS control AUTHORIZATION janus_control')
        connection.execute('CREATE SCHEMA IF NOT EXISTS private AUTHORIZATION janus_control')
        connection.execute('REVOKE ALL ON SCHEMA private,control FROM PUBLIC')
        connection.execute('GRANT USAGE ON SCHEMA private TO janus_private_api')
        connection.execute('SET ROLE janus_control')
        connection.execute('CREATE TABLE IF NOT EXISTS control.schema_migrations(version text PRIMARY KEY)')
        connection.execute('CREATE TABLE IF NOT EXISTS private.ledger_events(event_id uuid PRIMARY KEY)')
        connection.execute('CREATE TABLE IF NOT EXISTS private.current_positions(user_id uuid)')
        connection.execute('RESET ROLE')
        sql = (Path(__file__).parents[1] / 'infra/postgres/migrations/051_analysis_product.sql').read_text()
        connection.execute('\n'.join(line for line in sql.splitlines() if not line.startswith('\\')))
        quota_sql = (Path(__file__).parents[1] / 'infra/postgres/migrations/052_ceo_daily_quota_50.sql').read_text()
        connection.execute('\n'.join(line for line in quota_sql.splitlines() if not line.startswith('\\')))
    return dsn


class Repository:
    def __init__(self, dsn, owner):
        self.dsn, self.owner = dsn, owner

    @contextmanager
    def _connection(self):
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            connection.execute('SET ROLE janus_private_api')
            yield connection

    def user_id_for_email(self, _email):
        return self.owner


@pytest.fixture
def service(database):
    owner = uuid4()
    service = AnalysisService(Repository(database, owner))
    value = {'symbol': '2330', 'execution_id': str(uuid4()),
             'analysis_as_of': str(datetime.now(ZoneInfo('Asia/Taipei')).date()),
             'specialists': [{'role': 'quant', 'status': 'partial', 'baseline_status': 'available',
                             'output_hash': 'sha256:' + '1'*64}]}
    value['content_hash'] = content_hash(value)
    with psycopg.connect(database) as connection:
        connection.execute('SET ROLE janus_control')
        connection.execute('''INSERT INTO private.specialist_product
            (execution_id,symbol,analysis_as_of,content_hash,payload_json) VALUES (%s,%s,%s,%s,%s::jsonb)''',
            (value['execution_id'], '2330', value['analysis_as_of'], value['content_hash'], json.dumps(value)))
    service.save_capability(CEOCapabilityIn(email='test@example.com', enabled=True, daily_quota=3,
        cooldown_seconds=60, expected_version=0, reason='CI security gate'), 'admin@example.com')
    with psycopg.connect(database) as connection:
        version = connection.execute("SELECT max(version) FROM private.ceo_profile_revisions WHERE profile_id='default'").fetchone()[0]
    service.save_profile('default', CEOProfileIn(approved=True, expected_version=version, reason='CI fixture'), 'admin@example.com')
    return service, owner


def test_ceo_quota_50_is_db_enforced_without_changing_prior_revision(database, service):
    api, owner = service
    old = api.capability(owner)['capability']
    assert old['daily_quota'] == 3
    api.save_capability(CEOCapabilityIn(email='test@example.com', enabled=True,
        daily_quota=50, cooldown_seconds=300, expected_version=old['version'],
        reason='approved owner quota'), 'admin@example.com')
    fresh = api.capability(owner)['capability']
    assert fresh['daily_quota'] == 50 and fresh['cooldown_seconds'] == 300
    with psycopg.connect(database) as connection:
        assert connection.execute(
            "SELECT 1 FROM control.schema_migrations WHERE version='052_ceo_daily_quota_50'"
        ).fetchone()
        connection.execute('SET ROLE janus_private_api')
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute("""INSERT INTO private.ceo_capability_revisions
                (user_id,version,enabled,daily_quota,cooldown_seconds,actor,reason)
                VALUES (%s,%s,true,51,300,'test','reject')""", (owner, old['version'] + 2))



def test_concurrent_idempotency_and_active_quota_are_database_enforced(service):
    api, owner = service
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: api.enqueue(owner, '2330', 'default', 'same-key'), range(4)))
    assert len({r['request_id'] for r in results}) == 1
    assert sum(not r.get('already_requested', False) for r in results) == 1
    with pytest.raises(HTTPException) as error:
        api.enqueue(owner, '2330', 'default', 'new-key')
    assert error.value.status_code == 429
    request_id = results[0]['request_id']
    from services.api.repository import NotFoundError
    with pytest.raises(NotFoundError):
        api.request_status(uuid4(), request_id)
    assert api.cancel(owner, request_id)['status'] == 'CANCELLED'
    assert api.request_status(owner, request_id)['finished_at'] is not None


def test_terminal_report_and_worker_private_boundary(database, service):
    api, owner = service
    request_id = api.enqueue(owner, '2330', 'default', 'terminal-test')['request_id']
    with psycopg.connect(database) as connection:
        connection.execute('SET ROLE janus_mart_publication')
        connection.execute("UPDATE private.ceo_requests SET status='SUCCEEDED',report_json='{}',report_hash=%s WHERE request_id=%s",
                           (content_hash({}), request_id))
    with psycopg.connect(database) as connection:
        connection.execute('SET ROLE janus_mart_publication')
        with pytest.raises(psycopg.errors.RaiseException, match='immutable'):
            connection.execute("UPDATE private.ceo_requests SET status='FAILED' WHERE request_id=%s", (request_id,))
    for role, statement in (
        ('janus_mart_publication', 'SELECT * FROM private.ledger_events'),
        ('janus_mart_publication', 'SELECT * FROM private.current_positions'),
        ('janus_private_api', "UPDATE private.ceo_requests SET report_json='{}'"),
        ('janus_public_api', 'SELECT * FROM private.ceo_requests'),
    ):
        with psycopg.connect(database) as connection:
            connection.execute(f'SET ROLE {role}')
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(statement)


def test_capability_version_revocation_and_profile_snapshot(service):
    api, owner = service
    request_id = api.enqueue(owner, '2330', 'default', 'frozen-profile')['request_id']
    before = api.request_status(owner, request_id)
    api.save_capability(CEOCapabilityIn(email='test@example.com', enabled=False, daily_quota=0,
        cooldown_seconds=60, expected_version=1, reason='revoke'), 'admin@example.com')
    assert api.capability(owner)['can_request'] is False
    assert api.request_status(owner, request_id)['profile_version'] == before['profile_version']
    assert api.enqueue(owner, '2330', 'default', 'frozen-profile')['already_requested'] is True
    from services.api.repository import ConflictError
    with pytest.raises(ConflictError):
        api.save_capability(CEOCapabilityIn(email='test@example.com', enabled=True, daily_quota=1,
            cooldown_seconds=60, expected_version=1, reason='stale editor'), 'admin@example.com')


def test_worker_recovery_requires_confirmed_cloud_terminal(database, service):
    api, owner = service
    request_id = api.enqueue(owner, '2330', 'default', 'crashed-worker')['request_id']
    with psycopg.connect(database) as connection:
        connection.execute('SET ROLE janus_mart_publication')
        connection.execute("UPDATE private.ceo_requests SET status='RUNNING',worker_execution='janus-ceo-analysis-test' WHERE request_id=%s", (request_id,))
    class Trigger:
        def terminal_execution(self, execution):
            assert execution == 'janus-ceo-analysis-test'
            return False
    api.trigger = Trigger()
    assert api.reconcile(owner, request_id)['status'] == 'RUNNING'
    api.trigger.terminal_execution = lambda _: True
    assert api.reconcile(owner, request_id)['status'] == 'FAILED'
    assert api.request_status(owner, request_id)['safe_reason'] == 'worker_terminal_without_report'


def test_p0v_five_role_synthetic_ceo_full_validator_to_isolated_postgres_to_owner_api(database, service):
    """Use an isolated CI PostgreSQL database, never the parallel-live owner DB.

    The Gateway real model receipt is a separate live acceptance gate. This
    checks that its structured result survives the production CEO guard,
    Mart-only immutable report write and owner-scoped API history/readback.
    """
    from copy import deepcopy
    from types import SimpleNamespace
    from services.api.repository import NotFoundError
    from intelligence_mart.product_runtime import execute_ceo
    from packages.analysis_product import validate_ceo_output

    api, owner = service
    roles = ("fundamental", "valuation", "quant", "risk", "event")
    output_hashes = ["sha256:" + str(i + 1) * 64 for i in range(5)]
    source = {
        "schema_version": "analysis-product.v1",
        "symbol": "P0VTEST",
        "execution_id": str(uuid4()),
        "analysis_as_of": str(datetime.now(ZoneInfo("Asia/Taipei")).date()),
        "core_snapshot_id": "synthetic-isolated",
        "model_quality": "NOT_VERIFIED",
        "publication_authority": False,
        "specialists": [
            {"role": role, "status": "partial", "baseline_status": "unavailable",
             "output_hash": output_hashes[index], "metrics": {},
             "missing_data": ["測試資料非真實五角色"], "evidence_ids": [],
             "provenance_ids": []}
            for index, role in enumerate(roles)
        ],
    }
    source["content_hash"] = content_hash(source)
    with psycopg.connect(database) as connection:
        connection.execute("SET ROLE janus_control")
        connection.execute("""INSERT INTO private.specialist_product
            (execution_id,symbol,analysis_as_of,content_hash,payload_json)
            VALUES (%s,%s,%s,%s,%s::jsonb)""",
            (source["execution_id"], source["symbol"], source["analysis_as_of"],
             source["content_hash"], json.dumps(source, ensure_ascii=False)))
    result = api.enqueue(owner, "P0VTEST", "default", str(uuid4()))
    assert result["status"] == "QUEUED"
    request_id = result["request_id"]
    with psycopg.connect(database, row_factory=dict_row) as connection:
        connection.execute("SET ROLE janus_mart_publication")
        request = connection.execute(
            "SELECT * FROM private.ceo_requests WHERE request_id=%s", (request_id,)).fetchone()
    assert len(request["baseline_json"]["specialists"]) == 5
    assert request["baseline_hash"] == request["baseline_json"]["content_hash"]
    output = {
        "schema_version": "1.0.0", "role": "ceo",
        "stance": "insufficient_data", "thesis": None, "confidence": 0.0,
        "missing_information": ["合成資料不能作為正式投資分析"],
        "evidence_ids": [], "supporting_roles": [], "opposing_roles": [],
        "contradictions": [], "bull_case": [], "bear_case": [],
        "principal_risks": [], "watch_items": [],
        "change_since_previous_analysis": [],
        "validated_role_artifact_hashes": output_hashes,
    }
    class Router:
        def __init__(self, value):
            self.value = value
        def invoke(self, role, inputs, *, should_stop=None):
            assert role == "ceo" and len(inputs["validated_specialists"]) == 5
            assert inputs["validated_role_artifact_hashes"] == output_hashes
            assert inputs["canonical_numbers_are_read_only"] is True
            return SimpleNamespace(status="succeeded", output=self.value,
                attempts=[{"provider": "gemini", "transport": "omniagent_gateway",
                           "model": "gemini-3.5-flash-lite", "status": "succeeded",
                           "raw_text": "never-publish-me"}],
                routing={"routing_hash":"synthetic-p0v", "providers":["gemini"],
                         "execution_policy":"omniagent_gateway_gemini_lite_only"},
                provider="gemini", model="gemini-3.5-flash-lite")
    state, report, audit, reason = execute_ceo(request, Router(output))
    assert state == "PARTIAL" and reason is None
    assert report["publication_authority"] is False
    assert report["output"]["validated_role_artifact_hashes"] == output_hashes
    assert report["execution_id"] == str(request_id)
    assert "raw_text" not in str(audit) and "never-publish-me" not in str(audit)
    assert report["schema_version"] == "ceo-report.v1"

    for tamper in ("hash", "unknown_evidence", "fabricated_number", "hidden_missing"):
        changed = deepcopy(output)
        if tamper == "hash":
            changed["validated_role_artifact_hashes"][0] = "sha256:" + "f" * 64
        elif tamper == "unknown_evidence":
            changed["thesis"] = {
                "text": "合成方向主張", "evidence_ids": ["ev-" + "a"*24]}
        elif tamper == "fabricated_number":
            changed["missing_information"] = ["虛構 99999 目標價"]
        else:
            changed["missing_information"] = []
        blocked, discarded, _, invalid_reason = execute_ceo(request, Router(changed))
        assert blocked == "BLOCKED" and discarded is None
        assert invalid_reason == "output_validation_failed"
    with psycopg.connect(database) as connection:
        connection.execute("SET ROLE janus_mart_publication")
        lease = uuid4()
        row = connection.execute("""UPDATE private.ceo_requests
            SET status='RUNNING',lease_token=%s
            WHERE request_id=%s AND status='QUEUED'
            RETURNING request_id""", (lease, request_id)).fetchone()
        assert row
        connection.execute("""UPDATE private.ceo_requests
            SET status=%s,report_json=%s::jsonb,report_hash=%s,
                audit_json=%s::jsonb
            WHERE request_id=%s AND lease_token=%s""",
            (state,json.dumps(report,ensure_ascii=False),content_hash(report),
             json.dumps(audit),request_id,lease))
    served = api.request_status(owner, request_id)
    assert served["status"] == "PARTIAL"
    assert served["report_hash"] == content_hash(report)
    assert served["report_json"] == report
    assert api.history(owner,"P0VTEST")[0]["material_change"] is False
    with pytest.raises(NotFoundError):
        api.request_status(uuid4(),request_id)
    assert all(x["request_id"] != request_id for x in api.history(uuid4(), "P0VTEST"))
    with pytest.raises(HTTPException) as error:
        api._public_request({**served, "report_hash": "sha256:" + "0"*64})
    assert error.value.status_code == 503
    with psycopg.connect(database) as connection:
        connection.execute("SET ROLE janus_mart_publication")
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            connection.execute("UPDATE private.ceo_requests SET status='FAILED' WHERE request_id=%s",(request_id,))
