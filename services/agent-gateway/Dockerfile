FROM node:22.20.0-bookworm-slim AS build

WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
COPY services/agent-gateway ./services/agent-gateway
RUN npm ci && npm run build:agent-gateway && npm prune --omit=dev

FROM node:22.20.0-bookworm-slim

WORKDIR /app
ENV NODE_ENV=production PORT=8080 SANDBOX_ROOT=/var/run/janus \
    CODEX_BIN=/app/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/services/agent-gateway/dist ./services/agent-gateway/dist
RUN mkdir -p /var/run/janus && chown node:node /var/run/janus
USER node
EXPOSE 8080
CMD ["node", "services/agent-gateway/dist/server.js"]
