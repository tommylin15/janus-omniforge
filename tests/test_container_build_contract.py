from pathlib import Path


ROOT = Path(__file__).parents[1]
API_DOCKERFILE = (ROOT / "services" / "api" / "Dockerfile").read_text(encoding="utf-8")
MART_DOCKERFILE = (ROOT / "jobs" / "intelligence-mart" / "Dockerfile").read_text(encoding="utf-8")
CLOUDBUILD = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(encoding="utf-8")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8")
DOCKERIGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8")
LEGACY_CLOUDBUILD_BUCKET = "gen-lang-client-0593591102_cloudbuild"


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


def test_api_build_produces_distinct_admin_pwa_shell_without_second_user_app():
    assert "cp web/admin-manifest.json build/web/admin-manifest.json" in API_DOCKERFILE
    assert "cp build/web/index.html build/web/admin-index.html" in API_DOCKERFILE
    assert 'href="/app/admin-manifest.json"' in API_DOCKERFILE
    assert '\"id\": \"/app/admin\"' in API_DOCKERFILE
    assert '\"start_url\": \"/app/admin\"' in API_DOCKERFILE
    assert "flutter build web --release -t lib/final_visual.dart --base-href /app/" in API_DOCKERFILE
    assert API_DOCKERFILE.count("flutter build web") == 1


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
    needs = next(line.strip() for line in api_job.splitlines() if line.strip().startswith("needs: ["))
    dependencies = {part.strip() for part in needs.removeprefix("needs: [").removesuffix("]").split(",")}
    assert {"detect", "test-api", "deploy-private-pipeline", "migrate-operations",
            "migrate-quotes", "migrate-private-operations", "migrate-private-recalc",
            "migrate-latest-price", "migrate-latest-price-route",
            "migrate-holdings-reference"} <= dependencies
    assert "needs.migrate-holdings-reference.result == 'success'" in api_job
    assert "needs.detect.outputs.holdings_reference_schema != 'true'" in api_job
    assert "needs.migrate-quotes.result == 'success'" in api_job
    assert "needs.migrate-operations.result == 'success'" in api_job
    assert "needs.migrate-private-operations.result == 'success'" in api_job
    assert "needs.migrate-private-recalc.result == 'success'" in api_job
    assert "needs.detect.outputs.private_recalc_schema != 'true'" in api_job
    assert "needs.detect.outputs.operations_schema != 'true'" in api_job
    assert "needs.detect.outputs.private_ops_schema != 'true'" in api_job
    assert "needs.deploy-private-pipeline.result == 'success'" in api_job
    assert "needs.deploy-private-pipeline.result == 'skipped'" in api_job


def test_generated_and_orphaned_build_artifacts_stay_removed():
    assert "/tmp*/" in GITIGNORE
    assert ".flutter-plugins-dependencies" in GITIGNORE
    assert "tmp*/" in DOCKERIGNORE
    assert "**/.flutter-plugins-dependencies" in DOCKERIGNORE
    assert not (ROOT / "tmp4i2lk6d7").exists()
    assert not (ROOT / "apps" / "user_app" / ".flutter-plugins-dependencies").exists()
    assert not (ROOT / "scripts" / "gcp" / "cloudbuild-token-savior-verify.yaml").exists()
    assert not (ROOT / "token-savior").exists()
    assert not (ROOT / ".cicd-v2-work").exists()


def _cloud_build_submit_segments(text: str):
    marker = "gcloud builds submit"
    start = 0
    while True:
        index = text.find(marker, start)
        if index < 0:
            return
        next_gcloud = text.find("gcloud ", index + len(marker))
        yield text[index : next_gcloud if next_gcloud >= 0 else len(text)]
        start = index + len(marker)


def test_source_cloud_build_submits_are_regional_and_use_existing_staging_bucket():
    roots = (
        ROOT / ".github" / "workflows",
        ROOT / "scripts" / "gcp",
    )
    inspected = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".yml", ".yaml", ".sh"}:
                continue
            text = path.read_text(encoding="utf-8")
            for segment in _cloud_build_submit_segments(text):
                inspected.append((path, segment))
                if "--no-source" in segment:
                    continue
                assert "--region=" in segment, f"{path} submits a source build without an explicit region"
                assert "--gcs-source-staging-dir=" in segment, (
                    f"{path} submits source without the existing regional staging bucket"
                )
                assert "-cloudbuild-regional/source" in segment, (
                    f"{path} must stage source in the approved regional Cloud Build bucket"
                )

    assert inspected, "expected at least one Cloud Build submission in workflow/scripts"


def test_research_cloud_build_polling_uses_the_same_region_as_submit():
    for path in (ROOT / ".github" / "workflows").glob("research-cloud-cohort-500*.yml"):
        text = path.read_text(encoding="utf-8")
        if "gcloud builds submit research/cloud-cohort-500" not in text:
            continue
        assert '--region="${GCP_REGION}"' in text
        assert (
            'gcloud builds describe "${build_id}" --project="${GCP_PROJECT_ID}" '
            '--region="${GCP_REGION}"'
        ) in text


def test_legacy_cloud_build_bucket_is_not_reintroduced_in_active_build_paths():
    active_paths = [ROOT / "cloudbuild.yaml"]
    for root in (ROOT / ".github" / "workflows", ROOT / "scripts" / "gcp"):
        active_paths.extend(path for path in root.rglob("*") if path.is_file())
    offenders = []
    for path in active_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if LEGACY_CLOUDBUILD_BUCKET in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        "legacy Cloud Build bucket must stay deleted and must not be referenced by active build paths: "
        + ", ".join(offenders)
    )
