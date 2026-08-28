import { test, expect } from "@playwright/test";

test("Admin shell is responsive and safe", async ({ page }) => {
  await page.goto("/admin/stocks");
  await expect(page.getByRole("heading", { name: "資料營運中心" })).toBeVisible();
  await expect(page.getByRole("button", { name: "新增股票" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("raw payload");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toBeVisible();
});
