FROM node:22.20.0-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
COPY services/mcp-fixture ./services/mcp-fixture
RUN npm ci && npx tsc -p services/mcp-fixture/tsconfig.json && npm prune --omit=dev

FROM node:22.20.0-bookworm-slim
WORKDIR /app
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/services/mcp-fixture/dist ./services/mcp-fixture/dist
ENV NODE_ENV=production PORT=8080
USER node
EXPOSE 8080
CMD ["node", "services/mcp-fixture/dist/server.js"]
