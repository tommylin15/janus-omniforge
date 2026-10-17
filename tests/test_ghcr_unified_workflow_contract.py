"""Validate current consolidated GHCR workflows; older per-file contracts live in archive."""
from pathlib import Path

ROOT = Path(__file__).parents[1]
GHCR = (ROOT / ".github/workflows/ghcr-dev.yml").read_text()
AUTO = (ROOT / ".github/workflows/auto-release.yml").read_text()


def test_consolidated_workflows_share_global_runtime_writer_group():
    for source in (GHCR, AUTO):
        assert "group: janus-dev-runtime-writers" in source
        assert "cancel-in-progress: false" in source
        assert "id-token: write" in source


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
    assert "python scripts/gcp/cicd-v2-candidate.py" in GHCR
    assert "python scripts/gcp/ghcr_candidate_auth_boundary.py" in GHCR
    assert "python scripts/gcp/ghcr_preview_publish.py" in GHCR
    assert "python scripts/gcp/ghcr_jobs_rollout.py --release-run" in GHCR
    assert "python scripts/gcp/ghcr_jobs_rollout.py --recover" in GHCR
    assert "if: failure() || cancelled()" in GHCR
    assert "gh run download \"$JOBS_RUN\" -n ghcr-jobs-rollout-receipt" in GHCR
    assert "python scripts/gcp/ghcr_api_promote.py --release-run" in GHCR


def test_auto_release_cannot_publish_with_skipped_python_or_flutter_gates():
    assert "ops/auto-release-request.json" in AUTO
    assert '.approved == true' in AUTO
    assert "needs.python-tests.result == 'success'" in AUTO
    assert "needs.flutter-tests.result == 'success'" in AUTO
    assert "skip-tests" not in AUTO
    assert "needs.jobs-rollout.result == 'success'" in AUTO
    assert "needs.validate.outputs.skip-api-promote != 'true'" in AUTO


def test_verify_runs_full_suites_without_publishing_or_changing_runtime():
    import yaml
    workflow = yaml.safe_load(GHCR)
    jobs = workflow['jobs']
    for name in ('release-tests', 'release-flutter'):
        assert "needs.detect.outputs.operation == 'verify'" in jobs[name]['if']
    for name in ('release-publish', 'candidate', 'preview', 'auth-boundary', 'jobs-rollout', 'promote'):
        assert "needs.detect.outputs.operation == '" in jobs[name]['if']
        assert "'verify'" not in jobs[name]['if']
    assert "needs.detect.outputs.operation == 'release'" in jobs['release-publish']['if']
    assert jobs['release-verify']['needs'] == ['detect', 'release-publish']
