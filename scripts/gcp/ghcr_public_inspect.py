#!/usr/bin/env python3
"""Bounded anonymous GHCR OCI manifest and source-label verification.

No GitHub secrets, package manager, image layer downloads or mutable deployment.
Supported references are Janus immutable source tags and SHA256 digests only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_IMAGE = re.compile(
    r"ghcr[.]io/(?P<repository>tommylin15/janus-"
    r"(?:api|ingestion-core|intelligence-mart|private-pipeline))"
    r"(?P<reference>:sha-[0-9a-f]{40}|@sha256:[0-9a-f]{64})\Z"
)
_ACCEPT = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def inspect_public_image(image: str, *, opener=urlopen) -> dict:
    match = _IMAGE.fullmatch(image)
    if match is None:
        raise ValueError("immutable_janus_image_required")
    repository = match["repository"]
    reference = match["reference"][1:]
    if reference.startswith("sha256:") and not _DIGEST.fullmatch(reference):
        raise ValueError("invalid_sha256_digest")

    query = urlencode({
        "service": "ghcr.io",
        "scope": f"repository:{repository}:pull",
    })
    token_request = Request(
        "https://ghcr.io/token?" + query,
        headers={"Accept": "application/json"},
    )
    with opener(token_request, timeout=25) as response:
        token_json = json.loads(response.read(100_000))
    token = token_json.get("token") or token_json.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("public_ghcr_token_unavailable")

    def fetch(path: str, accept: str) -> tuple[bytes, str | None]:
        request = Request(
            f"https://ghcr.io/v2/{repository}/{path}",
            headers={"Authorization": "Bearer " + token, "Accept": accept},
        )
        with opener(request, timeout=30) as response:
            return response.read(3_000_000), response.headers.get("Docker-Content-Digest")

    def manifest(ref: str) -> tuple[dict, str]:
        content, header_digest = fetch("manifests/" + ref, _ACCEPT)
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        if header_digest and header_digest != digest:
            raise ValueError("public_ghcr_manifest_digest_mismatch")
        if ref.startswith("sha256:") and ref != digest:
            raise ValueError("public_ghcr_immutable_digest_mismatch")
        return json.loads(content), digest

    top, digest = manifest(reference)
    if "manifests" in top:
        candidates = [
            part for part in top["manifests"]
            if part.get("platform", {}).get("os") == "linux"
            and part.get("platform", {}).get("architecture") == "amd64"
        ]
        if len(candidates) != 1:
            raise ValueError("public_ghcr_amd64_manifest_required")
        item = candidates[0]
        resolved, _ = manifest(item["digest"])
    else:
        resolved = top
    config = resolved.get("config") or {}
    config_digest = config.get("digest", "")
    if not isinstance(config_digest, str) or not _DIGEST.fullmatch(config_digest):
        raise ValueError("public_ghcr_config_digest_required")
    body, _ = fetch("blobs/" + config_digest, "application/octet-stream")
    if "sha256:" + hashlib.sha256(body).hexdigest() != config_digest:
        raise ValueError("public_ghcr_config_hash_mismatch")
    config_json = json.loads(body)
    labels = (config_json.get("config") or {}).get("Labels") or {}
    if labels.get("org.opencontainers.image.source") != "https://github.com/tommylin15/janus-omniforge":
        raise ValueError("public_ghcr_source_label_mismatch")
    source_sha = labels.get("org.opencontainers.image.revision")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("public_ghcr_source_revision_required")
    if reference.startswith("sha-") and reference[4:] != source_sha:
        raise ValueError("public_ghcr_source_sha_mismatch")
    return {
        "Digest": digest,
        "Labels": labels,
        "Name": "ghcr.io/" + repository,
        "Tag": reference,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    print(json.dumps(inspect_public_image(args.image), sort_keys=True))


if __name__ == "__main__":
    main()
