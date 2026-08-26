FROM postgres:16.15-bookworm@sha256:bb3e1a57e5407e0a5280b4211980a5e537f4abd234a87014ac979849a78dd825

LABEL org.opencontainers.image.title="Janus PostgreSQL control plane" \
      org.opencontainers.image.version="16.15" \
      org.opencontainers.image.source="https://github.com/tommylin15/janus-omniforge"

COPY postgresql.conf /opt/janus/postgresql.conf
COPY pg_hba.conf /opt/janus/pg_hba.conf
COPY migrations /opt/janus/migrations
COPY readiness.sql /opt/janus/readiness.sql
