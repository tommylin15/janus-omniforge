"""GHCR private-boundary smoke must target the current approved 0% request."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_boundary_probe_tracks_approved_sha_not_a_stale_hardcoded_candidate():
    text = (ROOT / ".github/workflows/ghcr-candidate-auth-boundary.yml").read_text()
    assert "ops/ghcr-candidate-request.json" in text
    assert 'EXPECTED_SHA="$(jq -r .sha ops/ghcr-candidate-request.json)"' in text
    assert 'CANDIDATE_TAG="ghcr-${EXPECTED_SHA:0:12}"' in text
    assert 'git merge-base --is-ancestor "$EXPECTED_SHA" HEAD' in text
    assert "EXPECTED_SHA: 0b93d99d42aa" not in text
    assert "CANDIDATE_TAG: ghcr-0b93d99d42aa" not in text


def test_boundary_is_read_only_no_owner_tokens_or_release_claim():
    text = (ROOT / ".github/workflows/ghcr-candidate-auth-boundary.yml").read_text()
    assert "0% canonical traffic" in text
    assert "Not verified:" in text
    assert '"/api/v1/me/journal/pnl",' in text
    assert '"/mcp",payload' in text
    assert "/.well-known/oauth-protected-resource" in text
    assert "python -m pytest" in text
    for dangerous in (
        "gcloud run deploy", "gcloud run services update-traffic",
        "gcloud run jobs update", "gcloud run jobs execute",
        "gcloud builds submit", "ghcr_release_lease.py release",
        "secrets.GOOGLE", "secrets.OWNER",
    ):
        assert dangerous not in text


def test_boundary_runs_after_explicit_readonly_request_and_accepts_prior_ghcr_traffic():
    text = (ROOT / ".github/workflows/ghcr-candidate-auth-boundary.yml").read_text()
    assert "ops/ghcr-candidate-boundary-request.json" in text
    assert "janus-dev-runtime-writers" in text
    assert 'test "$EXPECTED_SHA" = "$(jq -r .sha ops/ghcr-candidate-boundary-request.json)"' in text
    assert '"janus-api-g53d655ccb108-config"' not in text
    assert '.no_gcp_mutation == true' in text
    assert "update-traffic" not in text
