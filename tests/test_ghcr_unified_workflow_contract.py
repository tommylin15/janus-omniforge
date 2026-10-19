"""Validate current consolidated GHCR workflows; older per-file contracts live in archive."""
from pathlib import Path

ROOT = Path(__file__).parents[1]
GHCR = (ROOT / ".github/workflows/ghcr-dev.yml").read_text()
ARCHIVED_AUTO = (ROOT / ".github/workflows/archive/auto-release-obsolete-2026-10-19.yml").read_text()


def test_consolidated_workflows_share_global_runtime_writer_group():
    for source in (GHCR,):
        assert "janus-dev-runtime-writers" in source
        assert "cancel-in-progress: false" in source
        assert "id-token: write" in source


def test_lease_check_shares_writer_group_without_cloud_identity_or_rollout():
    import yaml
    job = yaml.safe_load(GHCR)['jobs']['lease-check']
    assert job['if'] == "needs.detect.outputs.operation == 'lease-check'"
    assert job['permissions'] == {'contents': 'write'}
    setup = next(step for step in job['steps'] if step.get('uses') == './.github/actions/setup-janus')
    assert setup['with']['gcp-auth'] == 'false'
    script = '\n'.join(step.get('run', '') for step in job['steps'])
    assert 'ghcr_release_lease.py acquire' in script
    assert 'ghcr_release_lease.py assert' in script
    assert 'ghcr_release_lease.py release --safe-to-release' in script
    assert 'gcloud' not in script and 'ghcr_jobs_rollout.py' not in script


def test_active_ghcr_release_is_exact_sha_tested_before_immutable_public_publish():
    assert "workflow_dispatch:" in GHCR and "branches: [main]" in GHCR
    assert "'ops/ghcr-release-request.json'" in GHCR
    assert "needs: [detect, release-tests, release-flutter]" in GHCR
    assert "needs.release-tests.result == 'success' && needs.release-flutter.result == 'success'" in GHCR
    assert "flutter test" in GHCR and "python -m pytest -q tests" in GHCR
    assert "docker buildx build" in GHCR
    assert 'sha-${GITHUB_SHA}' in GHCR
    assert "skopeo inspect --no-creds" in GHCR


def test_active_ghcr_operations_keep_canonical_and_jobs_fail_closed():
    assert 'gcloud run deploy "$SERVICE"' in GHCR and '--no-traffic' in GHCR
    assert 'ghcr_candidate_lease_guard.py' in GHCR
    assert 'scripts/gcp/cicd-v2-candidate.py' not in GHCR
    assert 'scripts/gcp/ghcr_candidate_auth_boundary.py' not in GHCR
    assert 'Probe OAuth metadata, private read boundaries and MCP auth challenge' in GHCR
    assert "python scripts/gcp/ghcr_preview_publish.py" in GHCR
    assert "python scripts/gcp/ghcr_jobs_rollout.py --release-run" in GHCR
    assert "python scripts/gcp/ghcr_jobs_rollout.py --recover" in GHCR
    assert "if: failure() || cancelled()" in GHCR
    assert "gh run download \"$JOBS_RUN\" -n ghcr-jobs-rollout-receipt" in GHCR
    assert "python scripts/gcp/ghcr_api_promote.py --release-run" in GHCR


def test_obsolete_auto_release_is_archived_and_not_executable():
    assert not (ROOT / ".github/workflows/auto-release.yml").exists()
    assert "build-receipt.json" in ARCHIVED_AUTO
    assert "scripts/gcp/cicd-v2-candidate.py" in ARCHIVED_AUTO
    assert "scripts/gcp/cicd-v2-candidate.py" not in GHCR
    assert "scripts/gcp/ghcr_candidate_auth_boundary.py" not in GHCR


def test_verify_runs_full_suites_without_publishing_or_changing_runtime():
    import yaml
    workflow = yaml.safe_load(GHCR)
    jobs = workflow['jobs']
    assert workflow['concurrency']['group'] == "${{ github.event.inputs.operation == 'verify' && 'janus-dev-verification' || 'janus-dev-runtime-writers' }}"
    for name in ('release-tests', 'release-flutter'):
        assert "needs.detect.outputs.operation == 'verify'" in jobs[name]['if']
    for name in ('release-publish', 'candidate', 'preview', 'auth-boundary', 'jobs-rollout', 'promote'):
        assert "needs.detect.outputs.operation == '" in jobs[name]['if']
        assert "'verify'" not in jobs[name]['if']
    assert "needs.detect.outputs.operation == 'release'" in jobs['release-publish']['if']
    assert jobs['release-verify']['needs'] == ['detect', 'release-publish']


def test_candidate_and_boundary_keep_source_lease_and_negative_auth_guards():
    import ast
    import re
    import yaml
    workflow = yaml.safe_load(GHCR)
    permissions = next(value for key, value in yaml.compose(GHCR).value if key.value == 'permissions')
    permission_names = [key.value for key, _ in permissions.value]
    assert len(permission_names) == len(set(permission_names))
    assert workflow['permissions']['actions'] == 'read'
    jobs = workflow['jobs']
    candidate = '\n'.join(step.get('run', '') for step in jobs['candidate']['steps'])
    boundary = '\n'.join(step.get('run', '') for step in jobs['auth-boundary']['steps'])
    for guard in ('skopeo inspect --no-creds', 'git merge-base --is-ancestor',
                  'ghcr_release_lease.py acquire', 'ghcr_release_lease.py assert',
                  'ghcr_candidate_lease_guard.py', '--no-traffic',
                  'candidate_full_release_not_verified'):
        assert guard in candidate
    for guard in ('S256', 'refresh_token', 'WWW-Authenticate', 'build-id.txt',
                  '/api/v1/me/journal/pnl', 'no_gcp_mutation == true'):
        assert guard in boundary
    assert 'gcloud run deploy' not in boundary
    for script in (candidate, boundary):
        for embedded in re.findall(r"python(?:3)? - <<'PY'\n(.*?)\nPY", script, re.S):
            ast.parse(embedded)
