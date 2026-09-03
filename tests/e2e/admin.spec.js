import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";

let server;

test.beforeAll(async () => {
  const [html, css, js] = await Promise.all([
    readFile(new URL("../../apps/web/static/admin.html", import.meta.url)),
    readFile(new URL("../../apps/web/static/admin.css", import.meta.url)),
    readFile(new URL("../../apps/web/static/admin.js", import.meta.url)),
  ]);
  server = createServer((request, response) => {
    const path = new URL(request.url, "http://127.0.0.1").pathname;
    const asset = path === "/assets/admin.css" ? [css, "text/css"] : path === "/assets/admin.js" ? [js, "text/javascript"] : [html, "text/html"];
    response.writeHead(200, { "Content-Type": `${asset[1]}; charset=utf-8` });
    response.end(asset[0]);
  });
  await new Promise((resolve, reject) => { server.once("error", reject); server.listen(8080, "127.0.0.1", resolve); });
});

test.afterAll(async () => {
  server.closeAllConnections();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
});

const execution = {
  execution_id: "00000000-0000-0000-0000-000000000001", trace_id: "trace-1",
  status: "queued", trigger_type: "collection", config_id: "ohlcv", retry_count: 0,
  requested_at: "2026-08-31T08:00:00+00:00", finished_at: null, items: [],
};

async function mockAdmin(page, { candidate = false } = {}) {
  await page.route("**/health", (route) => route.fulfill({ json: { status: "ok", revision: "janus-web-test" } }));
  await page.route("**/api/v1/admin/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/v1/admin/stocks") return route.fulfill({ json: { items: [{ symbol: "2330", name: "台積電", market: "TWSE", enabled: true, listing_status: "listed", effective_from: "2026-08-31T00:00:00Z" }], limit: 10, next_cursor: null } });
    if (path === "/api/v1/admin/stocks/2330/status") return route.fulfill({ json: { symbol: "2330", items: [{ dataset_id: "ohlcv", latest_date: "2026-08-31", row_count: 2, received_symbols: 1, requested_symbols: 1, coverage_ratio: 1, null_count: 1, null_profile: [{ field: "close", count: 1, ratio: 0.5 }], quality_flags: ["warning"], dq_warning_count: 1, source_ids: ["twse"], snapshot_ids: ["42"], quarantine_count: 1, quarantine_state: "available" }] } });
    if (path === "/api/v1/admin/executions") return route.fulfill({ json: { items: [execution], limit: 10, next_cursor: null } });
    if (path === `/api/v1/admin/executions/${execution.execution_id}`) return route.fulfill({ json: execution });
    if (path === "/api/v1/admin/source-catalog") return route.fulfill({ json: { items: candidate ? [{ config_id: "anue-news", dataset_id: "news", source_ids: ["anue"], cadence: "intraday", coverage_tier: "core_focus", authorization_status: "candidate" }] : [] } });
    if (path === "/api/v1/admin/memberships/core_focus") return route.fulfill({ json: { items: [{ symbol: "2330" }], version: 2, effective_from: "2026-09-03T08:40:00Z" } });
    if (path === "/api/v1/admin/source-reviews/anue" && route.request().method() === "GET") return route.fulfill({ json: { adapter_id: "anue", value: null, version: 2 } });
    return route.fulfill({ status: 404, json: { error: "not found" } });
  });
}

test("tab deep link, keyboard, ARIA and responsive shell", async ({ page }) => {
  await mockAdmin(page);
  await page.goto("/admin/stocks?tab=executions");
  await expect(page.locator("#build-version")).toHaveText("janus-web-test");
  const executionsTab = page.getByRole("tab", { name: /最近執行/ });
  await expect(executionsTab).toHaveAttribute("aria-selected", "true");
  await expect(executionsTab).toHaveAttribute("aria-controls", "executions");
  await expect(page.getByRole("tabpanel", { name: /最近執行/ })).toBeVisible();
  await executionsTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /資料源健康/ })).toHaveAttribute("aria-selected", "true");
  await expect(page).toHaveURL(/tab=sources/);
  await expect(page.getByRole("button", { name: /加入 Analysis/ })).toHaveCount(0);
  await expect(page.getByRole("tab", { name: /Mart 分析/ })).toHaveCount(0);
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: /資料源設定/ })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Home");
  await expect(page.getByRole("tab", { name: /股票管理/ })).toHaveAttribute("aria-selected", "true");
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1280, height: 800 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByRole("heading", { name: "資料營運中心" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("stock dialog cancellation does not write and restores focus", async ({ page }) => {
  let writes = 0;
  await mockAdmin(page);
  await page.route("**/api/v1/admin/stocks", async (route) => {
    if (route.request().method() !== "GET") { writes += 1; return route.fulfill({ json: {} }); }
    return route.fulfill({ json: { items: [{ symbol: "2330", name: "台積電", market: "TWSE", enabled: true, listing_status: "listed", effective_from: "2026-08-31T00:00:00Z" }], limit: 10, next_cursor: null } });
  });
  await page.goto("/admin/stocks");
  const edit = page.getByRole("button", { name: "編輯" });
  await edit.click();
  await expect(page.getByRole("dialog", { name: /編輯 2330/ })).toHaveAttribute("aria-modal", "true");
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page.getByRole("dialog", { name: /編輯 2330/ })).not.toBeVisible();
  await expect(edit).toBeFocused();
  expect(writes).toBe(0);
});

test("core membership saves effective version without spoofable actor", async ({ page }) => {
  let saved;
  await mockAdmin(page);
  await page.route("**/api/v1/admin/memberships/core_focus", async (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { items: [{ symbol: "2330" }], version: 2, effective_from: "2026-09-03T08:40:00Z" } });
    saved = route.request().postDataJSON(); return route.fulfill({ json: { items: saved.symbols.map((symbol) => ({ symbol })), version: 3 } });
  });
  await page.goto("/admin/stocks?tab=membership");
  await expect(page.locator("#membership-count")).toHaveText("1 / 50 · v2");
  await expect(page.locator("#membership-effective")).toHaveAttribute("min", "2026-09-03T16:41");
  await page.locator("#membership-symbols").fill("2330, 2317");
  await page.locator("#membership-reason").fill("季度調整");
  await page.getByRole("button", { name: "儲存不可變更版本" }).click();
  expect(saved.expected_version).toBe(2);
  expect(saved.owner).toBeUndefined();
});

test("stock status renders Core coverage, null profile and quarantine", async ({ page }) => {
  await mockAdmin(page);
  await page.goto("/admin/stocks?tab=status");
  await page.locator("#status-symbol").fill("2330");
  await page.getByRole("button", { name: "查詢" }).click();
  const row = page.locator("#status-rows tr");
  await expect(row).toContainText("2026");
  await expect(row).toContainText("1/1 (100%)");
  await expect(row).toContainText("close 1 (50%)");
  await expect(row).toContainText("1 筆");
});

test("execution row opens details by keyboard and restores focus", async ({ page }) => {
  await mockAdmin(page);
  await page.goto("/admin/stocks?tab=executions");
  const row = page.getByRole("button", { name: `查看 execution ${execution.execution_id}` });
  await row.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "執行明細" })).toBeVisible();
  await page.getByRole("button", { name: "關閉明細" }).click();
  await expect(row).toBeFocused();
  await row.click();
  await expect(page.getByRole("dialog", { name: "執行明細" })).toBeVisible();
});

test("candidate adapter review submits full checklist and optimistic version", async ({ page }) => {
  let saved;
  await mockAdmin(page, { candidate: true });
  await page.route("**/api/v1/admin/source-reviews/anue", async (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { adapter_id: "anue", value: null, version: 2 } });
    saved = route.request().postDataJSON();
    return route.fulfill({ json: { adapter_id: "anue", version: 3, value: { ...saved.value, reviewer: saved.actor, decided_at: "2026-08-31T09:00:00Z" } } });
  });
  await page.goto("/admin/stocks?tab=catalog");
  await expect(page.getByRole("button", { name: "啟用", exact: true })).toHaveCount(0);
  await page.getByLabel("審查決策").selectOption("approved_fallback");
  for (const checkbox of await page.locator('[name="review-check"]').all()) await checkbox.check();
  await page.getByLabel(/證據 URL/).fill("https://example.com/anue-review");
  await page.getByLabel("Reviewer").fill("reviewer@example.com");
  await page.getByLabel("決策理由").fill("條款與安全檢查完成");
  await page.getByRole("button", { name: "儲存審查" }).click();
  await expect(page.locator("#review-version")).toHaveValue("3");
  expect(saved.expected_version).toBe(2);
  expect(Object.values(saved.value.checks).every(Boolean)).toBe(true);
  expect(Object.keys(saved.value.checks)).toHaveLength(11);
});

test("source config editor saves typed values and blocks candidate enablement", async ({ page }) => {
  const config = { config_id: "first-batch", dataset_id: "ohlcv", source_ids: ["twse"], expected_fields: ["symbol"], market: "TWSE", enabled: true, collection_enabled: true, analysis_enabled: false, lookback_days: 30, overlap_days: 2, full_refresh_interval_days: 0, batch_scope: "market", coverage_tier: "market_wide", cadence: "daily", scope: "market", authorization_status: "official", retention_class: "core_standard", contains_pii: false, republish_allowed: false, max_symbols: 50 };
  let saved;
  await mockAdmin(page);
  await page.route("**/api/v1/admin/source-catalog", async (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { items: [config] } });
    saved = route.request().postDataJSON(); return route.fulfill({ json: saved });
  });
  await page.goto("/admin/stocks?tab=catalog");
  await page.getByRole("button", { name: "編輯" }).click();
  await page.getByLabel("頻率").selectOption("weekly");
  await page.getByLabel("Authorization").selectOption("candidate");
  await expect(page.getByLabel("啟用設定")).toBeDisabled();
  await page.locator("#config-actor").fill("operator@example.com");
  await page.getByRole("button", { name: "儲存資料源設定" }).click();
  expect(saved.cadence).toBe("weekly");
  expect(saved.enabled).toBe(false);
  expect(saved.analysis_enabled).toBe(false);
});

test("logout clears the Admin session and returns to login", async ({ page, context }) => {
  await mockAdmin(page);
  await context.addCookies([{ name: "janus_session", value: "signed", url: "http://127.0.0.1:8080" }]);
  await page.route("**/logout", (route) => route.fulfill({ status: 200, headers: { "Set-Cookie": "janus_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax" }, body: "" }));
  await page.goto("/admin/stocks");
  await page.getByRole("button", { name: "登出" }).click();
  await page.waitForURL("**/login");
  expect((await context.cookies()).some((cookie) => cookie.name === "janus_session")).toBe(false);
});
