import { describe, expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

describe("Admin Data Operations contract", () => {
  it("only exposes the collection queue action", async () => {
    const html = await readFile(resolve("apps/web/static/admin.html"), "utf8");
    expect(html).toContain("queue-collection");
    expect(html).not.toContain("queue-analysis");
    expect(html).not.toContain("Mart 分析");
    expect(html).not.toContain("AI Prompt");
  });
  it("uses safe persisted-state vocabulary", () => {
    expect(["queued", "running", "partial", "failed", "retrying", "unavailable"]).toContain("queued");
  });
});
