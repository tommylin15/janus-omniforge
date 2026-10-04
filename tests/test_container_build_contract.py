from pathlib import Path


ROOT = Path(__file__).parents[1]
API_DOCKERFILE = (ROOT / "services" / "api" / "Dockerfile").read_text(encoding="utf-8")
MART_DOCKERFILE = (ROOT / "jobs" / "intelligence-mart" / "Dockerfile").read_text(encoding="utf-8")
CLOUDBUILD = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(encoding="utf-8")


def test_api_and_private_pipeline_share_python_base_but_not_flutter_output():
    base = "FROM python:3.12.8-slim-bookworm AS api-python-base"
    private = "FROM api-python-base AS private-pipeline"
    flutter = "FROM ghcr.io/cirruslabs/flutter:stable AS flutter"
    api = "FROM api-python-base AS api"
    assert base in API_DOCKERFILE
    assert private in API_DOCKERFILE
    assert flutter in API_DOCKERFILE
    assert api in API_DOCKERFILE
    assert API_DOCKERFILE.index(private) < API_DOCKERFILE.index(flutter) < API_DOCKERFILE.index(api)
    private_block = API_DOCKERFILE.split(private, 1)[1].split(flutter, 1)[0]
    assert "COPY --from=flutter" not in private_block
    assert 'CMD ["python", "-m", "services.api.private_pipeline_runtime"]' in private_block
    api_block = API_DOCKERFILE.split(api, 1)[1]
    assert "COPY --from=flutter /app/apps/user_app/build/web /app/apps/user_app/build/web" in api_block


def test_cloud_build_uses_api_family_cache_and_targeted_images():
    assert "selected-image-exists" in CLOUDBUILD
    assert "api-peer-image-exists" in CLOUDBUILD
    assert "built-api-peer" in CLOUDBUILD
    assert 'services/api/Dockerfile:private-pipeline) target="private-pipeline"' in CLOUDBUILD
    assert 'services/api/Dockerfile:api) target="api"' in CLOUDBUILD
    assert 'build_image "api" "${api_peer}"' in CLOUDBUILD
    assert 'jobs/intelligence-mart/Dockerfile:*) target="mart-specialist"' in CLOUDBUILD
    assert "images:" not in CLOUDBUILD  # reuse-only builds need no local image at build end


def test_mart_specialist_target_stops_before_codex_and_ceo_provider_keeps_it():
    specialist = "FROM mart-python-base AS mart-specialist"
    node = "FROM node:22-bookworm-slim AS codex-cli"
    ceo = "FROM mart-python-base AS mart-ceo-provider"
    assert specialist in MART_DOCKERFILE
    assert node in MART_DOCKERFILE
    assert ceo in MART_DOCKERFILE
    assert MART_DOCKERFILE.index(specialist) < MART_DOCKERFILE.index(node) < MART_DOCKERFILE.index(ceo)
    specialist_block = MART_DOCKERFILE.split(specialist, 1)[1].split(node, 1)[0]
    assert "@openai/codex" not in specialist_block
    assert "/usr/local/bin/node" not in specialist_block
    ceo_block = MART_DOCKERFILE.split(ceo, 1)[1]
    assert "COPY --from=codex-cli /usr/local/bin/node /usr/local/bin/node" in ceo_block
    assert "codex --version | grep -F '0.159.2'" in ceo_block


def test_shared_api_backend_changes_serialize_api_after_private_pipeline():
    api_job = WORKFLOW.split("  deploy-api:\n", 1)[1]
    assert "needs: [detect, test-api, deploy-private-pipeline]" in api_job
    assert "needs.deploy-private-pipeline.result == 'success'" in api_job
    assert "needs.deploy-private-pipeline.result == 'skipped'" in api_job
