FROM python:3.12.8-slim-bookworm AS mart-python-base

# Dev deployment controller: .github/workflows/deploy-dev.yml via scripts/gcp/deploy-dev.sh.
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    PYTHONPATH=/app:/app/jobs/intelligence-mart:/app/jobs/ingestion-core \
    PORT=8080

COPY jobs/intelligence-mart/requirements.lock ./requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN if [ -s requirements.lock ] && ! grep -q '^# No Python dependencies' requirements.lock; then \
      pip install --no-cache-dir --require-hashes -r requirements.lock; \
    fi
COPY . .

# The production specialist path is deterministic Python/SQL/ML and must not
# carry the Codex/Node runtime. Keep this target before the Node stage so builds
# for the live Mart Job stop here.
FROM mart-python-base AS mart-specialist
EXPOSE 8080
CMD ["python", "-m", "intelligence_mart.provider_main"]

FROM node:22-bookworm-slim AS codex-cli
RUN npm install -g @openai/codex@0.159.2 --omit=dev

# Reserved build target for the later authorized On-demand CEO provider WBS.
# Creating this target does not create or deploy a new runtime by itself.
FROM mart-python-base AS mart-ceo-provider
COPY --from=codex-cli /usr/local/bin/node /usr/local/bin/node
COPY --from=codex-cli /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex \
    && codex --version | grep -F '0.159.2'
EXPOSE 8080
CMD ["python", "-m", "intelligence_mart.provider_main"]
