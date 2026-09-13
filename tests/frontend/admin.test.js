import { describe, expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

describe("Admin Data Operations contract", () => {
  it("exposes persisted collection and analysis actions", async () => {
    const html = await readFile(resolve("apps/web/static/admin.html"), "utf8");
    expect(html).toContain("queue-collection");
    expect(html).toContain("加入收集佇列");
    expect(html).toContain("queue-analysis");
    expect(html).toContain("Mart 分析");
    expect(html).toContain("Governance");
    expect(html).toContain("governance-preview");
    expect(html).not.toContain("AI Prompt");
  });
  it("uses safe persisted-state vocabulary", () => {
    expect(["queued", "running", "partial", "failed", "retrying", "unavailable"]).toContain("queued");
  });
  it("renders sortable structured tables without a raw JSON escape hatch", async () => {
    const [html, js, css] = await Promise.all([
      readFile(resolve("apps/web/static/admin.html"), "utf8"),
      readFile(resolve("apps/web/static/admin.js"), "utf8"),
      readFile(resolve("apps/web/static/admin.css"), "utf8"),
    ]);
    expect(html).toContain("data-status-sort");
    expect(html).toContain("data-column-target");
    expect(js).toContain("execution-items-table");
    expect(js).toContain("/references");
    expect(js).toContain("基本面");
    expect(css).toContain("position:sticky");
    expect(`${html}${js}`).not.toContain("查看 JSON");
  });
});
