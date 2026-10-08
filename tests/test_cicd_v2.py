import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cicd_v2", ROOT / "scripts/gcp/cicd-v2.py")
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


@pytest.mark.parametrize("paths,expected", [
    (["doc/status.md", "README.md"], []),
    (["jobs/ingestion-core/ingestion_core/sources.py"], ["ingestion-core"]),
    (["jobs/intelligence-mart/intelligence_mart/specialists.py"], ["intelligence-mart"]),
    (["services/api/private_recalc_queue.py"], ["private-pipeline", "api"]),
    (["apps/user_app/lib/main.dart"], ["api"]),
    (["packages/postgres_bundle.py"], list(v2.COMPONENTS)),
    (["infra/postgres/migrations/050_holdings_previous_close_read.sql"], list(v2.COMPONENTS)),
    (["jobs/ingestion-core/ingestion_core/retention.py"], ["ingestion-core", "intelligence-mart"]),
])
def test_selection(paths, expected):
    assert v2.select_components(paths) == expected


def test_digest_fence_includes_nested_revisions_and_executions():
    image = "registry/image@sha256:" + "a" * 64
    assert v2.image_references({"spec": {"containers": [{"image": image}]}}) == {image}
    with pytest.raises(ValueError):
        v2.image_references({"image": "registry/image:latest"})


def test_cleanup_fail_closed_on_inventory_failure(monkeypatch):
    def denied(*args):
        raise RuntimeError("permission denied")
    monkeypatch.setattr(v2, "gcloud", denied)
    with pytest.raises(RuntimeError):
        v2.cleanup_plan([])


def test_cleanup_preserves_candidates_and_job_execution_images(monkeypatch):
    prefix = f"{v2.REGION}-docker.pkg.dev/{v2.PROJECT}/janusai-poc/api"
    images = [prefix + "@sha256:" + char * 64 for char in "abc"]
    def inventory(*args):
        if args[:3] == ("run", "jobs", "executions"):
            return [{"containers": [{"image": images[1]}]}]
        if args[:2] == ("run", "jobs"):
            return [{"metadata": {"name": "janus-api-worker"}}]
        if args[0] == "run":
            return []
        return [{"package": "api", "version": "sha256:" + char * 64, "imageSizeBytes": "10"} for char in "abc"]
    monkeypatch.setattr(v2, "gcloud", inventory)
    plan = v2.cleanup_plan([images[0]])
    assert plan["inventory_bytes"] == 30
    assert plan["unreferenced"] == [{"image": images[2], "bytes": 10}]
    assert plan["delete_allowed"] is False


def test_no_tag_based_cleanup_in_legacy_build():
    build = (ROOT / 'cloudbuild.yaml').read_text()
    assert 'cleanup-untagged-images' not in build
    assert 'gcloud artifacts docker images delete' not in build


def test_shadow_pipeline_is_fail_closed_and_logs_regional_only():
    build = (ROOT / 'cloudbuild-v2.yaml').read_text()
    script = (ROOT / 'scripts/gcp/cicd-v2-build.sh').read_text()
    assert build.index('tests-and-security') < build.index('build-and-push-candidates')
    assert '_MODE: "shadow"' in build
    assert 'CLOUD_LOGGING_ONLY' in build
    assert 'gcloud builds submit' not in script
    assert '--if-generation-match=0' in script
    assert 'tests-pass' in script
    assert 'apt-get install -y --no-install-recommends libgomp1' in script


def test_ci_selects_only_affected_tests_and_controller_dependencies():
    assert v2.ci_matrix(["doc/status.md"])["include"] == []
    matrix = v2.ci_matrix(["jobs/intelligence-mart/intelligence_mart/specialists.py"])
    assert [row["group"] for row in matrix["include"]] == ["mart"]
    controller = v2.ci_matrix(["cloudbuild-v2.yaml"])["include"][0]
    assert controller["requirements"] == ["requirements-ci.txt"]
    assert v2.ci_matrix(["tests/test_cicd_v2.py"])["include"][0]["tests"] == ["tests/test_cicd_v2.py"]


def test_push_has_no_canonical_runtime_deployment():
    for name in ("deploy-dev.yml", "b3-live-acceptance.yml", "b5-live-acceptance.yml", "portfolio-live-acceptance.yml"):
        workflow = (ROOT / ".github/workflows" / name).read_text()
        assert "  push:" not in workflow
    for name in ("b3-live-acceptance.yml", "b5-live-acceptance.yml", "portfolio-live-acceptance.yml"):
        assert "bash scripts/gcp/deploy-dev.sh" not in (ROOT / ".github/workflows" / name).read_text()
    assert "  push:" in (ROOT / ".github/workflows/ci-v2.yml").read_text()


def test_manual_release_and_acceptance_fail_closed():
    import json
    trigger = json.loads((ROOT / "infra/gcp/cicd-v2-trigger.json").read_text())
    assert "repositoryEventConfig" not in trigger
    assert trigger["sourceToBuild"]["repository"].endswith("tommylin15-janus-omniforge")
    candidate_spec = importlib.util.spec_from_file_location("candidate", ROOT / "scripts/gcp/cicd-v2-candidate.py")
    candidate = importlib.util.module_from_spec(candidate_spec)
    candidate_spec.loader.exec_module(candidate)
    receipt = {"sha": "a" * 40, "images": {"api": "image@sha256:" + "b" * 64}}
    with pytest.raises(ValueError):
        candidate.validate_acceptance({"sha": "c" * 40}, receipt)
    with pytest.raises(RuntimeError):
        candidate.validate_acceptance({**receipt, "gates": {}}, receipt)
    source = (ROOT / "scripts/gcp/cicd-v2-candidate.py").read_text()
    assert "for component in v2.COMPONENTS[:-1] if release else []" in source
    assert "for schedule in schedules if release else []" in source
