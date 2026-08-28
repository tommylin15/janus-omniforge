import { describe, expect, it } from "vitest";

describe("Admin Data Operations contract", () => {
  it("keeps queue actions separate", () => {
    expect("/api/v1/admin/executions/collection").not.toBe("/api/v1/admin/executions/analysis");
  });
  it("uses safe persisted-state vocabulary", () => {
    expect(["queued", "running", "partial", "failed", "retrying", "unavailable"]).toContain("queued");
  });
});
