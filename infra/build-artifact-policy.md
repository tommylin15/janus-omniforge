# Build artifact policy

Build pipelines must publish images using the immutable commit SHA as the
primary tag, then resolve and record the resulting image digest. Deployments
must consume the digest (`@sha256:...`), never a mutable tag such as `latest`.

Each published image may produce an SPDX or CycloneDX SBOM locally during the
build. If produced, it is stored as an ordinary build artifact and references
the image digest by filename or metadata. This policy explicitly does not use
Artifact Analysis API, Container Scanning API, vulnerability scanning, or
occurrence APIs.

An immutable image digest is required. A vulnerability result is not a build
gate and must not be requested from a Google scanning API.

This policy is declarative until the component Dockerfiles and Cloud Build
pipeline are added. No build or deployment was run by this change.
