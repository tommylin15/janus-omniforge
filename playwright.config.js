import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: "http://127.0.0.1:8080", headless: true },
  webServer: { command: "python -m apps.web.server", url: "http://127.0.0.1:8080/admin/stocks", reuseExistingServer: true, timeout: 30000 }
});
