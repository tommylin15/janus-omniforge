FROM python:3.12.8-slim-bookworm
WORKDIR /app
COPY scripts/gcp/mcp_host_acceptance.py ./mcp_host_acceptance.py
USER nobody
ENTRYPOINT ["python", "/app/mcp_host_acceptance.py"]
