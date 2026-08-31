"use strict";

const state = {
  limit: 10, stocks: [], selected: new Set(), loadedTabs: new Set(), activeTab: "stocks",
  stockPage: 0, stockCursors: [null], stockNext: null,
  executionPage: 0, executionCursors: [null], executionNext: null,
};
const byId = (id) => document.getElementById(id);
const dialogOpeners = new WeakMap();

const tabLoaders = {
  stocks: loadStocks, status: () => Promise.resolve(), executions: loadExecutions,
  sources: loadSources, membership: loadMembership, settings: loadSettings,
  catalog: loadCatalog, prompts: () => Promise.resolve(), mart: () => Promise.resolve(),
};

async function activateTab(name, { focus = false, reload = false } = {}) {
  if (!tabLoaders[name]) name = "stocks";
  state.activeTab = name;
  document.querySelectorAll('[role="tab"]').forEach((tab) => {
    const selected = tab.dataset.tab === name;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => { panel.hidden = panel.id !== (name === "status" ? "stock-status" : name); });
  const url = new URL(window.location.href); url.searchParams.set("tab", name); window.history.replaceState(null, "", url);
  if (reload || !state.loadedTabs.has(name)) {
    await tabLoaders[name]();
    state.loadedTabs.add(name);
  }
}

function showNotice(message, error = false) {
  const notice = byId("notice");
  notice.textContent = message;
  notice.classList.toggle("error", error);
  notice.hidden = false;
  window.clearTimeout(showNotice.timer);
  showNotice.timer = window.setTimeout(() => { notice.hidden = true; }, 5000);
}

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "服務暫時無法處理要求");
  return body;
}

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}

function statusBadge(value) {
  return node("span", value || "unavailable", `state ${value || "unavailable"}`);
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "—" : new Intl.DateTimeFormat("zh-TW", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function selectionChanged() {
  byId("selected-count").textContent = state.selected.size;
  byId("bulk-count").textContent = state.selected.size;
  const current = state.stocks.map((stock) => stock.symbol);
  byId("select-page").checked = current.length > 0 && current.every((symbol) => state.selected.has(symbol));
  byId("select-page").indeterminate = current.some((symbol) => state.selected.has(symbol)) && !byId("select-page").checked;
}

async function loadStocks() {
  const params = new URLSearchParams({ q: byId("stock-query").value.trim(), limit: state.limit });
  const cursor = state.stockCursors[state.stockPage];
  if (cursor) params.set("cursor", cursor);
  const enabled = byId("enabled-filter").value;
  if (enabled) params.set("enabled", enabled);
  try {
    const data = await request(`/api/v1/admin/stocks?${params}`);
    state.stocks = data.items;
    state.stockNext = data.next_cursor;
    renderStocks();
  } catch (error) {
    byId("stock-rows").replaceChildren(rowMessage("股票資料目前無法使用"));
    showNotice(error.message, true);
  }
}

function rowMessage(message, columns = 6) {
  const tr = document.createElement("tr");
  const td = node("td", message, "empty");
  td.colSpan = columns;
  tr.append(td);
  return tr;
}

function renderStocks() {
  const body = byId("stock-rows");
  body.replaceChildren();
  if (!state.stocks.length) body.append(rowMessage("此條件沒有股票"));
  state.stocks.forEach((stock) => {
    const tr = document.createElement("tr");
    const selectCell = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selected.has(stock.symbol);
    checkbox.setAttribute("aria-label", `選取 ${stock.symbol} ${stock.name}`);
    checkbox.addEventListener("change", () => { checkbox.checked ? state.selected.add(stock.symbol) : state.selected.delete(stock.symbol); selectionChanged(); });
    selectCell.append(checkbox);
    const identity = document.createElement("td");
    identity.append(node("strong", stock.symbol), node("small", stock.name));
    const enabled = document.createElement("td");
    enabled.append(statusBadge(stock.enabled ? "succeeded" : "unavailable"));
    enabled.lastChild.textContent = stock.enabled ? "enabled" : "disabled";
    const action = document.createElement("td");
    action.className = "align-right";
    const toggle = node("button", stock.enabled ? "停用" : "啟用", "button quiet");
    toggle.type = "button";
    toggle.addEventListener("click", () => setEnabled(stock, !stock.enabled));
    const edit = node("button", "編輯", "button quiet"); edit.type = "button"; edit.addEventListener("click", () => openStock(stock));
    const remove = node("button", "刪除", "button quiet"); remove.type = "button"; remove.addEventListener("click", () => deleteStock(stock));
    const status = node("button", "資料狀態", "button quiet"); status.type = "button"; status.addEventListener("click", () => openStatus(stock));
    action.append(edit, toggle, status, remove);
    tr.append(selectCell, identity, node("td", stock.market), enabled, node("td", formatDate(stock.effective_from)), action);
    body.append(tr);
  });
  byId("page-label").textContent = `第 ${state.stockPage + 1} 頁`;
  byId("prev-page").disabled = state.stockPage === 0;
  byId("next-page").disabled = !state.stockNext;
  selectionChanged();
}

async function setEnabled(stock, enabled) {
  try {
    await request(`/api/v1/admin/stocks/${encodeURIComponent(stock.symbol)}/enabled`, { method: "PATCH", body: JSON.stringify({ enabled }) });
    showNotice(`${stock.symbol} 已${enabled ? "啟用" : "停用"}`);
    await loadStocks();
  } catch (error) { showNotice(error.message, true); }
}

function openStock(stock = null) {
  byId("stock-dialog-title").textContent = stock ? `編輯 ${stock.symbol}` : "新增股票";
  byId("stock-symbol").value = stock?.symbol || ""; byId("stock-symbol").readOnly = Boolean(stock);
  byId("stock-name").value = stock?.name || ""; byId("stock-market").value = stock?.market || "TWSE";
  byId("stock-listing").value = stock?.listing_status || "unknown"; byId("stock-enabled").checked = stock?.enabled ?? true;
  const dialog = byId("stock-dialog"); dialog.dataset.editing = stock?.symbol || ""; dialogOpeners.set(dialog, document.activeElement); dialog.showModal(); byId("stock-name").focus();
}

async function deleteStock(stock) {
  if (!window.confirm(`${stock.symbol} 若仍被設定或 execution 使用將無法刪除。確定刪除？`)) return;
  try { await request(`/api/v1/admin/stocks/${encodeURIComponent(stock.symbol)}`, { method: "DELETE" }); showNotice(`${stock.symbol} 已刪除`); await loadStocks(); }
  catch (error) { showNotice(error.message, true); }
}

async function openStatus(stock) {
  const symbol = typeof stock === "string" ? stock.trim().toUpperCase() : stock.symbol;
  if (!symbol) return showNotice("請輸入股票代號", true);
  try {
    const data = await request(`/api/v1/admin/stocks/${encodeURIComponent(symbol)}/status`);
    const body = byId("status-rows"); body.replaceChildren();
    if (!data.items.length) body.append(rowMessage("目前沒有 Core 資料", 9));
    data.items.forEach((item) => {
      const tr = document.createElement("tr");
      tr.append(node("td", item.dataset_id), node("td", formatDate(item.latest_date)), node("td", item.row_count),
        node("td", `${item.received_symbols}/${item.requested_symbols}`), node("td", item.null_count),
        node("td", item.quality_flags.length ? item.quality_flags.join(", ") : "good"),
        node("td", item.source_ids.join(", ") || "—"), node("td", item.snapshot_ids.join(", ") || "—"),
        node("td", item.quarantine_count ?? "尚未提供"));
      body.append(tr);
    });
    byId("status-symbol").value = symbol;
    state.loadedTabs.add("status");
    await activateTab("status");
  }
  catch (error) { showNotice(error.message, true); }
}

async function enqueue(kind) {
  const configId = byId("config-id").value.trim();
  if (!configId) return showNotice("請輸入設定 ID", true);
  if (!state.selected.size) return showNotice("請先選取至少一檔股票", true);
  try {
    const execution = await request(`/api/v1/admin/executions/${kind}`, { method: "POST", body: JSON.stringify({ config_id: configId, symbols: [...state.selected] }) });
    showNotice(`${kind === "collection" ? "Collection" : "Analysis"} 已加入佇列：${execution.execution_id}`);
    await loadExecutions();
  } catch (error) { showNotice(error.message, true); }
}

async function loadExecutions() {
  const body = byId("execution-rows");
  try {
    const params = new URLSearchParams({ limit: state.limit });
    const cursor = state.executionCursors[state.executionPage];
    if (cursor) params.set("cursor", cursor);
    const data = await request(`/api/v1/admin/executions?${params}`);
    state.executionNext = data.next_cursor;
    body.replaceChildren();
    if (!data.items.length) body.append(rowMessage("尚無 persisted execution", 6));
    let active = 0;
    data.items.forEach((execution) => {
      if (["queued", "running", "retrying"].includes(execution.status)) active += 1;
      const tr = document.createElement("tr");
      const status = document.createElement("td"); status.append(statusBadge(execution.status));
      const detailCell = document.createElement("td"); detailCell.className = "align-right";
      const detail = node("button", "查看", "button quiet"); detail.type = "button";
      detail.addEventListener("click", (event) => { event.stopPropagation(); openExecution(execution.execution_id, detail); });
      detailCell.append(detail);
      tr.append(status, node("td", execution.trigger_type), node("td", execution.config_id), node("td", formatDate(execution.requested_at)), node("td", execution.retry_count), detailCell);
      tr.tabIndex = 0; tr.setAttribute("role", "button"); tr.setAttribute("aria-label", `查看 execution ${execution.execution_id}`);
      tr.addEventListener("click", () => openExecution(execution.execution_id, tr));
      tr.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); openExecution(execution.execution_id, tr); } });
      body.append(tr);
    });
    byId("execution-count").textContent = data.items.length;
    byId("active-count").textContent = active;
    byId("execution-page-label").textContent = `第 ${state.executionPage + 1} 頁`;
    byId("prev-execution-page").disabled = state.executionPage === 0;
    byId("next-execution-page").disabled = !state.executionNext;
  } catch (error) {
    body.replaceChildren(rowMessage("執行紀錄目前無法使用", 6));
    showNotice(error.message, true);
  }
}

async function openExecution(id, opener) {
  try {
    const execution = await request(`/api/v1/admin/executions/${encodeURIComponent(id)}`);
    const content = byId("dialog-content"); content.replaceChildren();
    const list = document.createElement("dl"); list.className = "detail-grid";
    [["Execution ID", execution.execution_id], ["狀態", execution.status], ["類型", execution.trigger_type], ["設定", execution.config_id], ["要求時間", formatDate(execution.requested_at)], ["完成時間", formatDate(execution.finished_at)]].forEach(([term, value]) => { const wrap = document.createElement("div"); wrap.append(node("dt", term), node("dd", value)); list.append(wrap); });
    content.append(list, node("h3", "工作項目"));
    const items = node("div", null, "item-list");
    (execution.items || []).forEach((item) => { const card = node("article", null, "item-card"); card.append(statusBadge(item.state), node("strong", ` ${item.dataset_id || "dataset"} · ${item.source_id || "source"}`), node("p", item.safe_message || `rows: ${item.rows_received ?? "—"}`)); items.append(card); });
    if (!execution.items?.length) items.append(node("p", "尚無工作項目", "empty"));
    content.append(items);
    const dialog = byId("execution-dialog"); dialogOpeners.set(dialog, opener); dialog.showModal(); byId("close-dialog").focus();
  } catch (error) { showNotice(error.message, true); }
}

async function loadSources() {
  const list = byId("source-list");
  try {
    const data = await request("/api/v1/admin/source-health");
    list.replaceChildren();
    if (!data.items.length) list.append(node("p", "尚無 persisted telemetry", "empty"));
    let healthy = 0;
    data.items.forEach((source) => {
      const rate = typeof source.success_rate === "number" ? Math.round(source.success_rate * 100) : null;
      if (["success", "fallback", "partial"].includes(source.last_state)) healthy += 1;
      const card = node("article", null, "source-card");
      card.append(node("strong", `${source.source_id} · ${source.dataset_id}`), node("p", `成功率 ${rate === null ? "—" : `${rate}%`} · 最後取得 ${formatDate(source.last_fetched_at)}`), statusBadge(source.last_state));
      list.append(card);
    });
    byId("source-summary").textContent = data.items.length ? `${healthy}/${data.items.length}` : "—";
  } catch (error) { list.replaceChildren(node("p", "來源健康目前無法使用", "empty")); showNotice(error.message, true); }
}

async function loadCatalog() {
  const list = byId("catalog-list");
  try {
    const data = await request("/api/v1/admin/source-catalog");
    list.replaceChildren();
    if (!data.items.length) list.append(node("p", "尚無資料源設定", "empty"));
    const candidates = new Set();
    data.items.forEach((config) => {
      const card = node("article", null, "source-card");
      card.append(node("strong", `${config.config_id} · ${config.dataset_id}`), node("p", `來源 ${config.source_ids.join(", ")} · ${config.cadence} · ${config.coverage_tier}`), statusBadge(config.authorization_status));
      list.append(card);
      if (["candidate", "blocked"].includes(config.authorization_status)) config.source_ids.forEach((source) => candidates.add(source));
    });
    const select = byId("review-adapter");
    const previous = select.value;
    select.replaceChildren(...[...candidates].sort().map((adapter) => { const option = node("option", adapter); option.value = adapter; return option; }));
    if (candidates.has(previous)) select.value = previous;
    byId("review-form").hidden = candidates.size === 0;
    if (candidates.size) await loadReview();
  }
  catch (error) { list.replaceChildren(node("p", "資料源設定目前無法使用", "empty")); showNotice(error.message, true); }
}

async function loadReview() {
  const adapter = byId("review-adapter").value;
  if (!adapter) return;
  try {
    const review = await request(`/api/v1/admin/source-reviews/${encodeURIComponent(adapter)}`);
    const value = review.value || {};
    byId("review-status").value = value.status || "candidate";
    document.querySelectorAll('[name="review-check"]').forEach((input) => { input.checked = value.checks?.[input.value] === true; });
    byId("review-evidence").value = value.evidence_url || "";
    byId("review-actor").value = value.reviewer || byId("review-actor").value;
    byId("review-reason").value = value.reason || "";
    byId("review-version").value = review.version;
    byId("review-decision-time").textContent = value.decided_at ? `決策時間：${formatDate(value.decided_at)}` : "尚未審查";
  } catch (error) { showNotice(error.message, true); }
}

async function saveReview(event) {
  event.preventDefault();
  const checks = Object.fromEntries([...document.querySelectorAll('[name="review-check"]')].map((input) => [input.value, input.checked]));
  const payload = {
    actor: byId("review-actor").value.trim(), expected_version: Number(byId("review-version").value),
    value: { status: byId("review-status").value, checks, evidence_url: byId("review-evidence").value.trim(), reason: byId("review-reason").value.trim() },
  };
  try {
    const saved = await request(`/api/v1/admin/source-reviews/${encodeURIComponent(byId("review-adapter").value)}`, { method: "PUT", body: JSON.stringify(payload) });
    byId("review-version").value = saved.version;
    byId("review-decision-time").textContent = `決策時間：${formatDate(saved.value.decided_at)}`;
    showNotice("候選 adapter 審查已儲存並寫入 audit");
  } catch (error) { showNotice(error.message, true); }
}

async function loadMembership() {
  try {
    const data = await request("/api/v1/admin/memberships/core_focus");
    const symbols = data.items.map((item) => item.symbol);
    byId("membership-symbols").value = symbols.join(", ");
    byId("membership-count").textContent = `${symbols.length} / 50`;
  } catch (error) { showNotice(error.message, true); }
}

async function loadSettings() {
  try {
    const schedule = await request("/api/v1/admin/settings/schedule"); const retention = await request("/api/v1/admin/settings/retention");
    if (schedule.value) { byId("schedule-time").value = schedule.value.time || "08:00"; byId("schedule-enabled").checked = schedule.value.enabled !== false; byId("settings-form").dataset.scheduleVersion = schedule.version; }
    if (retention.value) { byId("retention-days").value = retention.value.days || 30; byId("cleanup-enabled").checked = retention.value.cleanup_enabled !== false; byId("settings-form").dataset.retentionVersion = retention.version; }
  } catch (error) { showNotice(error.message, true); }
}

async function saveSettings(event) {
  event.preventDefault(); const actor = byId("settings-actor").value.trim(); if (!actor) return showNotice("請填寫操作者", true);
  const form = byId("settings-form");
  try {
    const schedule = await request("/api/v1/admin/settings/schedule", { method: "PUT", body: JSON.stringify({ actor, expected_version: Number(form.dataset.scheduleVersion || 0), value: { time: byId("schedule-time").value, enabled: byId("schedule-enabled").checked } }) });
    const retention = await request("/api/v1/admin/settings/retention", { method: "PUT", body: JSON.stringify({ actor, expected_version: Number(form.dataset.retentionVersion || 0), value: { days: Number(byId("retention-days").value), cleanup_enabled: byId("cleanup-enabled").checked } }) });
    form.dataset.scheduleVersion = schedule.version; form.dataset.retentionVersion = retention.version; showNotice("排程與保存設定已儲存");
  } catch (error) { showNotice(error.message, true); }
}

function membershipSymbols() {
  return [...new Set(byId("membership-symbols").value.split(/[\s,]+/).map((value) => value.trim().toUpperCase()).filter(Boolean))];
}

async function saveMembership(event) {
  event.preventDefault();
  const symbols = membershipSymbols();
  if (symbols.length > 50) return showNotice("核心名單不可超過 50 檔", true);
  const localTime = byId("membership-effective").value;
  if (!localTime) return showNotice("請設定生效時間", true);
  try {
    await request("/api/v1/admin/memberships/core_focus", { method: "PUT", body: JSON.stringify({ symbols, effective_from: new Date(localTime).toISOString(), reason: byId("membership-reason").value, owner: byId("membership-owner").value }) });
    showNotice("核心名單版本已儲存");
    await loadMembership();
  } catch (error) { showNotice(error.message, true); }
}

async function refreshAll() { await activateTab(state.activeTab, { reload: true }); }

async function logout() {
  try {
    const response = await fetch("/logout", { method: "POST", credentials: "same-origin" });
    if (!response.ok) throw new Error("登出失敗");
    window.location.assign("/login");
  } catch (error) { showNotice(error.message, true); }
}

function restoreDialogFocus(event) {
  const opener = dialogOpeners.get(event.target);
  if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
  dialogOpeners.delete(event.target);
}

function setupTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
    tab.addEventListener("keydown", (event) => {
      let target = null;
      if (["ArrowDown", "ArrowRight"].includes(event.key)) target = tabs[(index + 1) % tabs.length];
      if (["ArrowUp", "ArrowLeft"].includes(event.key)) target = tabs[(index - 1 + tabs.length) % tabs.length];
      if (event.key === "Home") target = tabs[0];
      if (event.key === "End") target = tabs[tabs.length - 1];
      if (target) { event.preventDefault(); activateTab(target.dataset.tab, { focus: true }); }
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset()); byId("membership-effective").value = now.toISOString().slice(0, 16);
  const resetStockPage = () => { state.stockPage = 0; state.stockCursors = [null]; state.stockNext = null; };
  byId("stock-search").addEventListener("submit", (event) => { event.preventDefault(); resetStockPage(); loadStocks(); });
  byId("enabled-filter").addEventListener("change", () => { resetStockPage(); loadStocks(); });
  byId("prev-page").addEventListener("click", () => { if (state.stockPage > 0) { state.stockPage -= 1; loadStocks(); } });
  byId("next-page").addEventListener("click", () => { if (state.stockNext) { state.stockPage += 1; state.stockCursors[state.stockPage] = state.stockNext; loadStocks(); } });
  byId("select-page").addEventListener("change", (event) => { state.stocks.forEach((stock) => event.target.checked ? state.selected.add(stock.symbol) : state.selected.delete(stock.symbol)); selectionChanged(); renderStocks(); });
  byId("clear-selection").addEventListener("click", () => { state.selected.clear(); renderStocks(); });
  byId("queue-collection").addEventListener("click", () => enqueue("collection"));
  byId("queue-analysis").addEventListener("click", () => enqueue("analysis"));
  byId("refresh-executions").addEventListener("click", loadExecutions);
  byId("prev-execution-page").addEventListener("click", () => { if (state.executionPage > 0) { state.executionPage -= 1; loadExecutions(); } });
  byId("next-execution-page").addEventListener("click", () => { if (state.executionNext) { state.executionPage += 1; state.executionCursors[state.executionPage] = state.executionNext; loadExecutions(); } });
  byId("refresh-all").addEventListener("click", refreshAll);
  byId("logout").addEventListener("click", logout);
  byId("status-search").addEventListener("submit", (event) => { event.preventDefault(); openStatus(byId("status-symbol").value); });
  byId("membership-form").addEventListener("submit", saveMembership);
  byId("add-stock").addEventListener("click", () => openStock());
  byId("stock-form").addEventListener("submit", async (event) => { event.preventDefault(); const dialog = byId("stock-dialog"); try { await request("/api/v1/admin/stocks", { method: "PUT", body: JSON.stringify({ symbol: byId("stock-symbol").value, name: byId("stock-name").value, market: byId("stock-market").value, listing_status: byId("stock-listing").value, enabled: byId("stock-enabled").checked }) }); dialog.close(); showNotice("股票資料已儲存"); await loadStocks(); } catch (error) { showNotice(error.message, true); } });
  byId("settings-form").addEventListener("submit", saveSettings);
  byId("review-adapter").addEventListener("change", loadReview);
  byId("review-form").addEventListener("submit", saveReview);
  byId("close-dialog").addEventListener("click", () => byId("execution-dialog").close());
  byId("cancel-stock").addEventListener("click", () => byId("stock-dialog").close());
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", restoreDialogFocus);
  });
  try { await request("/health"); document.querySelector(".pulse").className = "pulse ok"; byId("runtime-label").textContent = "控制面服務正常"; } catch { document.querySelector(".pulse").className = "pulse error"; byId("runtime-label").textContent = "控制面服務無法使用"; }
  const initial = new URL(window.location.href).searchParams.get("tab") || "stocks";
  await activateTab(initial);
});
