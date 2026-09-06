import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "jsdom", include: ["tests/frontend/**/*.test.js", "tests/agent_gateway.test.ts", "tests/gemini_provider.test.ts", "tests/openrouter_provider.test.ts"] }
});
