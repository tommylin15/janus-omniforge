FROM node:22.20.0-bookworm-slim AS build

WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
COPY services/agent-gateway ./services/agent-gateway
COPY services/mcp-fixture ./services/mcp-fixture
RUN npm ci && npm run build:agent-gateway && npm run build:mcp-fixture && npm prune --omit=dev

FROM node:22.20.0-bookworm-slim

WORKDIR /app
ENV NODE_ENV=production PORT=8080 SANDBOX_ROOT=/var/run/janus \
    CODEX_BIN=/app/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex \
    CODEX_CA_CERTIFICATE=/etc/ssl/certs/ca-certificates.crt
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/services/agent-gateway/dist ./services/agent-gateway/dist
COPY --from=build /app/services/mcp-fixture/dist ./services/mcp-fixture/dist
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/run/janus \
    && chown node:node /var/run/janus
USER node
EXPOSE 8080
CMD ["node", "services/agent-gateway/dist/server.js"]
