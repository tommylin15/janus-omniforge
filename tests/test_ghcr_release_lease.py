"""Fail-closed / atomic lease behavior without network or cloud resources."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "scripts/gcp/ghcr_release_lease.py"
spec = importlib.util.spec_from_file_location("ghcr_release_lease", MODULE)
lease = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = lease
spec.loader.exec_module(lease)

SHA_A = "a" * 40
SHA_B = "b" * 40
TAG_SHA_A = "c" * 40
TAG_SHA_B = "d" * 40
O1 = lease.Owner("tommylin15/janus-omniforge", 1234, 1, SHA_A)
O2 = lease.Owner("tommylin15/janus-omniforge", 1235, 1, SHA_B)


class FakeApi:
    def __init__(self):
        self.ref = None
        self.tags = {}
        self.next_tag_sha = TAG_SHA_A
        self.fail_get = False
        self.get_readbacks = 0
        self.trace = []

    def __call__(self, method, path, body=None):
        self.trace.append((method, path))
        if method == "GET" and "/git/ref/tags/" in path:
            self.get_readbacks += 1
            if self.fail_get:
                raise lease.ApiError(403)
            if self.ref is None:
                raise lease.ApiError(404)
            return {"object": {"type": "tag", "sha": self.ref}}
        if method == "GET" and "/git/tags/" in path:
            if path.split("/")[-1] not in self.tags:
                raise lease.ApiError(404)
            return self.tags[path.split("/")[-1]]
        if method == "POST" and path.endswith("/git/tags"):
            sha = self.next_tag_sha
            self.next_tag_sha = TAG_SHA_B
            self.tags[sha] = {"tag": body["tag"], "message": body["message"],
                              "object": {"type": "commit", "sha": body["object"]}}
            return {"sha": sha}
        if method == "POST" and path.endswith("/git/refs"):
            if self.ref is not None:
                raise lease.ApiError(422)
            self.ref = body["sha"]
            return {"object": {"sha": self.ref}}
        if method == "DELETE" and "/git/refs/tags/" in path:
            self.ref = None
            return None
        raise AssertionError((method, path))


def test_acquire_owner_readback_release():
    api = FakeApi()
    assert lease.acquire(api, O1) == TAG_SHA_A
    assert lease._validated_lease(api, O1) == TAG_SHA_A
    lease.release(api, O1)
    assert api.ref is None
    assert any(method == "POST" and path.endswith("/git/refs") for method, path in api.trace)


def test_concurrent_claim_rejected_not_overwritten():
    api = FakeApi()
    lease.acquire(api, O1)
    with pytest.raises(lease.LeaseBlocked, match="lease_busy"):
        lease.acquire(api, O2)
    assert lease._validated_lease(api, O1) == TAG_SHA_A


def test_atomic_race_conflict_rejects_claim():
    api = FakeApi()
    real = api.__call__
    def race(method, path, body=None):
        if method == "POST" and path.endswith("/git/refs"):
            api.ref = TAG_SHA_B
            raise lease.ApiError(422)
        return real(method, path, body)
    with pytest.raises(lease.LeaseBlocked, match="atomic_lease_claim_rejected"):
        lease.acquire(race, O1)
    assert api.ref == TAG_SHA_B


def test_unrelated_run_cannot_assert_or_release():
    api = FakeApi()
    lease.acquire(api, O1)
    with pytest.raises(lease.LeaseBlocked, match="lease_owned_by_other_run"):
        lease._validated_lease(api, O2)
    with pytest.raises(lease.LeaseBlocked, match="lease_owned_by_other_run"):
        lease.release(api, O2)
    assert api.ref == TAG_SHA_A


def test_ambiguous_permission_and_missing_ref_fail_closed():
    api = FakeApi()
    api.fail_get = True
    with pytest.raises(lease.LeaseBlocked, match="lease_ref_readback_failed"):
        lease.acquire(api, O1)
    api.fail_get = False
    with pytest.raises(lease.LeaseBlocked, match="lease_missing"):
        lease.release(api, O1)


def test_same_source_different_run_is_not_owner():
    api = FakeApi()
    lease.acquire(api, O1)
    other = lease.Owner(O1.repo, O1.run_id + 1, O1.run_attempt, O1.source_sha)
    with pytest.raises(lease.LeaseBlocked, match="lease_owned_by_other_run"):
        lease.release(api, other)
    assert api.ref == TAG_SHA_A


def test_invalid_identity_never_calls_api():
    api = FakeApi()
    with pytest.raises(lease.LeaseBlocked, match="invalid_restrictive_owner_identity"):
        lease.acquire(api, lease.Owner("invalid", 1234, 1, SHA_A))
    assert api.trace == []


def test_anomalous_tag_or_metadata_blocks_release():
    api = FakeApi()
    lease.acquire(api, O1)
    api.tags[TAG_SHA_A]["message"] = "unknown"
    with pytest.raises(lease.LeaseBlocked, match="invalid_lease_metadata"):
        lease.release(api, O1)
    assert api.ref == TAG_SHA_A


def test_no_cloud_mutation_commands_present():
    source = MODULE.read_text()
    assert "gcloud " not in source
    assert "force-unlock" in source
    assert '"--safe-to-release"' in source


def test_live_drill_has_no_gcp_and_contender_rejected():
    workflow = (MODULE.parents[2] / ".github/workflows/ghcr-release-lease-drill.yml").read_text()
    assert "github-only-global-lease-drill" in workflow
    assert 'allow_gcp_mutation==false' in workflow
    assert "independent-recovery:" in workflow
    assert 'python scripts/gcp/ghcr_release_lease.py acquire' in workflow
    assert 'python scripts/gcp/ghcr_release_lease.py release --safe-to-release' in workflow
    assert 'if python scripts/gcp/ghcr_release_lease.py acquire' in workflow
    assert 'if python scripts/gcp/ghcr_release_lease.py release' in workflow
    assert "gcloud " not in workflow
    assert "--force" not in workflow
