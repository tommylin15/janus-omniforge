ARG TRINO_VERSION=474
FROM trinodb/trino:${TRINO_VERSION}

LABEL org.opencontainers.image.title="Janus Trino" \
      org.opencontainers.image.description="Trino query service for Janus OmniForge" \
      org.opencontainers.image.source="https://github.com/tommylin15/janus-omniforge"

# Keep the base image non-root and use the upstream entrypoint.  Runtime
# credentials are injected by Cloud Run; no credential values belong in this
# image.
COPY services/trino/etc /etc/trino
COPY services/trino/catalog /etc/trino/catalog
