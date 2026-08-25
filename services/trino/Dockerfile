ARG TRINO_VERSION=474
FROM trinodb/trino:${TRINO_VERSION}

LABEL org.opencontainers.image.title="Janus Trino" \
      org.opencontainers.image.description="Trino query service for Janus OmniForge" \
      org.opencontainers.image.source="https://github.com/tommylin15/janus-omniforge"

# Connector configuration and catalog files will be added with the Trino WBS.
# Keep the base image non-root and use the upstream entrypoint.
