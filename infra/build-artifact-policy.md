# Build artifact policy

Build pipelines must publish images using the immutable commit SHA as the
primary tag, then resolve and record the resulting image digest. Deployments
must consume the digest (`@sha256:...`), never a mutable tag such as `latest`.

Each published image must also produce an SPDX or CycloneDX SBOM. The SBOM is
stored beside the image metadata in Artifact Registry and is linked to the
image digest. A build is incomplete if either the digest or SBOM is missing.

This policy is declarative until the component Dockerfiles and Cloud Build
pipeline are added. No build or deployment was run by this change.
