"""Public GHCR manifest inspection is anonymous, bounded and fail-closed."""
import hashlib
import json

import pytest

from scripts.gcp.ghcr_public_inspect import inspect_public_image


def test_public_oci_manifest_digest_and_source_label_are_verified():
    source = "a" * 40
    registry = "tommylin15/janus-api"
    labels = {
        "org.opencontainers.image.source": "https://github.com/tommylin15/janus-omniforge",
        "org.opencontainers.image.revision": source,
    }
    cfg = json.dumps({"config": {"Labels": labels}}, sort_keys=True).encode()
    cfg_sha = "sha256:" + hashlib.sha256(cfg).hexdigest()
    manifest = json.dumps({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
                           "config": {"digest": cfg_sha}}, sort_keys=True).encode()
    manifest_sha = "sha256:" + hashlib.sha256(manifest).hexdigest()
    calls = []

    class Response:
        def __init__(self, payload, digest=None):
            self.payload = payload
            self.headers = {"Docker-Content-Digest": digest} if digest else {}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, limit):
            assert limit <= 3_000_000
            return self.payload

    def opener(request, timeout):
        assert timeout <= 30
        url = request.full_url
        calls.append(url)
        if url.startswith("https://ghcr.io/token?"):
            assert "repository%3Atommylin15%2Fjanus-api%3Apull" in url
            return Response(b'{"token":"fake-anonymous-test-token"}')
        assert request.headers.get("Authorization") == "Bearer fake-anonymous-test-token"
        if url.endswith("/manifests/sha-" + source):
            return Response(manifest, manifest_sha)
        if url.endswith("/manifests/" + manifest_sha):
            return Response(manifest, manifest_sha)
        if url.endswith("/blobs/" + cfg_sha):
            return Response(cfg)
        raise AssertionError("unexpected registry URL")

    tag = f"ghcr.io/{registry}:sha-{source}"
    result = inspect_public_image(tag, opener=opener)
    assert result["Digest"] == manifest_sha
    assert result["Labels"] == labels
    exact = inspect_public_image(f"ghcr.io/{registry}@{manifest_sha}", opener=opener)
    assert exact["Digest"] == manifest_sha
    assert len(calls) == 6


def test_rejects_mutable_tag_and_other_namespace():
    for name in ("ghcr.io/tommylin15/janus-api:latest",
                 "ghcr.io/unknown/janus-api:sha-" + "a" * 40,
                 "https://example.com/not-a-janus-image"):
        with pytest.raises(ValueError, match="immutable_janus_image_required"):
            inspect_public_image(name, opener=lambda *_args, **_kwargs: None)
