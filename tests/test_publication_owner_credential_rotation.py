from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_publication_owner_rotation_is_bounded_and_forward_repairable():
    workflow = (ROOT / ".github/workflows/publication-owner-credential-rotation-dev.yml").read_text(encoding="utf-8")
    build = (ROOT / "scripts/gcp/cloudbuild-publication-owner-credential-rotation.yaml").read_text(encoding="utf-8")
    script = (ROOT / "scripts/gcp/rotate-publication-owner-credential-dev.sh").read_text(encoding="utf-8")
    hba = (ROOT / "infra/postgres/pg_hba.conf").read_text(encoding="utf-8")

    assert "ops/publication-owner-credential-rotation" in workflow
    assert "gcloud builds submit" in workflow
    assert "gcloud builds describe" in workflow
    assert "steps.id,steps.status" in workflow
    assert "yaml.safe_load" in workflow
    assert "add-iam-policy-binding" not in workflow
    assert "add-iam-policy-binding" not in build

    assert "verify-publication-owner-iap-tunnel" in build
    assert "start-iap-tunnel" in build
    assert "prepare-publication-owner-secret" in build
    assert "install-publication-owner-rotation-script" in build
    assert "rotate-publication-owner-database" in build
    assert "finalize-publication-owner-secret" in build
    assert "RUNTIME_BUNDLE" in build
    assert '"$${RUNTIME_BUNDLE}"' in build
    assert "publication_password" in build
    assert "gcloud secrets versions add janus-runtime-bundle" in build
    assert "gcloud secrets versions disable" in build
    assert "sudo tee /tmp/rotate-publication-owner-credential-dev.sh" in build
    assert "cat \"$${work}/password\" | gcloud compute ssh" in build
    assert "--filter='state=ENABLED'" in build

    assert "ALTER ROLE janus_publication PASSWORD" in script
    assert "SET log_min_duration_statement = -1" in script
    assert "PGPASSFILE" in script
    assert "localhost:5432:janus_control:janus_publication" in script
    assert "chown postgres:postgres" in script
    assert "-h 127.0.0.1" not in script
    assert "has_schema_privilege(current_user,'publication','CREATE')" in script
    assert "set -x" not in script

    hba_rules = {
        " ".join(line.split())
        for line in hba.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "local all all scram-sha-256" in hba_rules


def test_rotation_does_not_reuse_other_runtime_identity_passwords():
    build = (ROOT / "scripts/gcp/cloudbuild-publication-owner-credential-rotation.yaml").read_text(encoding="utf-8")
    for forbidden in ("mart_publication_password", "web_publication_password"):
        assert forbidden not in build
