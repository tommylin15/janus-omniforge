FROM node:22-bookworm-slim AS codex-cli
RUN npm install -g @openai/codex@0.159.2 --omit=dev

FROM python:3.12.8-slim-bookworm

# Dev deployment controller: .github/workflows/deploy-dev.yml via scripts/gcp/deploy-dev.sh.
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    PYTHONPATH=/app:/app/jobs/intelligence-mart:/app/jobs/ingestion-core \
    PORT=8080

# Codex CLI is pinned and copied from a build-only Node stage. The runtime still
# receives account auth only at execution time from approved secret storage.
COPY --from=codex-cli /usr/local/bin/node /usr/local/bin/node
COPY --from=codex-cli /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex \
    && codex --version | grep -F '0.159.2'

COPY jobs/intelligence-mart/requirements.lock ./requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN if [ -s requirements.lock ] && ! grep -q '^# No Python dependencies' requirements.lock; then \
      pip install --no-cache-dir --require-hashes -r requirements.lock; \
    fi
COPY . .

EXPOSE 8080
CMD ["python", "-m", "intelligence_mart.provider_main"]
