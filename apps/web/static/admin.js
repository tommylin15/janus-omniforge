"use strict";

const state = {
  limit: 10, stocks: [], selected: new Set(), loadedTabs: new Set(), activeTab: "stocks",
  stockPage: 0, stockCursors: [null], stockNext: null,
  statusItems: [], statusPage: 0, statusSort: "dataset_id", statusDirection: 1, expandedStatus: new Set(),
  executions: [], executionPage: 0, executionCursors: [null], executionNext: null,
  executionSort: "requested_at", executionDirection: -1,
  sourcePage: 0, sourceCursors: [null], sourceNext: null,
  catalogPage: 0, catalogCursors: [null], catalogNext: null,
  editingConfig: null, governanceVersion: 0,
};
const byId = (id) => document.getElementById(id);
const dialogOpeners = new WeakMap();

const tabLoaders = {
  stocks: loadStocks, status: () => Promise.resolve(), executions: loadExecutions,
  sources: loadSources, settings: loadSettings,
  catalog: loadCatalog, mart: loadMart, backfill: () => Promise.resolve(), governance: loadGovernance,
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

const statusLabels = {
  succeeded: "成功", unavailable: "無法使用", enabled: "已啟用", disabled: "已停用",
  partial: "部分可用", success: "成功", fallback: "備援", failed: "失敗",
  schema_drift: "結構變更", queued: "排隊中", running: "執行中", retrying: "重試中",
  blocked: "已阻擋", publishable: "可發布", published: "已發布", superseded: "已取代",
  draft: "草稿", complete: "完整", invalid: "無效", review_required: "需要審查",
  risk_blocked: "風險阻擋", insufficient_data: "資料不足", candidate: "候選", approved: "已核准",
  approved_fallback: "核准備援", pending: "待處理", development_default: "開發預設",
  "development-default": "開發預設", official: "官方", collection: "資料收集", analysis: "分析",
  market: "市場", industry: "產業", symbol: "個股", fundamental: "基本面", valuation: "估值",
  positioning: "籌碼與定位", quant: "量化", event_risk: "事件風險", intraday: "盤中", daily: "每日",
  weekly: "每週", quarterly: "每季", on_demand: "按需", market_wide: "全市場", core_focus: "核心聚焦",
  market_macro: "市場總體", raw_short: "原始資料短期", core_standard: "Core 標準",
  deep_research: "深度研究", audit: "稽核", available: "可用", suspended: "暫停交易",
  delisted: "下市", unknown: "未知",
};

function displayStatus(value) {
  return statusLabels[value] || value || "無法使用";
}

function statusBadge(value) {
  return node("span", displayStatus(value), `state ${value || "unavailable"}`);
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "—" : new Intl.DateTimeFormat("zh-TW", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function formatRatio(value) {
  return typeof value === "number" ? `${Math.round(value * 1000) / 10}%` : "—";
}

function formatNullProfile(item) {
  if (!item.null_profile?.length) return item.row_count ? "0（無缺值）" : "—";
  return `${item.null_count} · ${item.null_profile.map((field) => `${field.field} ${field.count} (${formatRatio(field.ratio)})`).join("；")}`;
}

function compareValues(left, right) {
  if (left === right) return 0;
  if (left === null || left === undefined) return 1;
  if (right === null || right === undefined) return -1;
  return typeof left === "number" && typeof right === "number"
    ? left - right
    : String(left).localeCompare(String(right), "zh-Hant", { numeric: true });
}

function sorted(items, key, direction) {
  return [...items].sort((left, right) => compareValues(left[key], right[key]) * direction);
}

function updateSort(selector, key, direction) {
  document.querySelectorAll(selector).forEach((button) => {
    button.parentElement.setAttribute("aria-sort", button.dataset.statusSort === key || button.dataset.executionSort === key
      ? (direction === 1 ? "ascending" : "descending") : "none");
  });
}

function toggleColumn(input) {
  const table = byId(input.dataset.columnTarget);
  const index = Number(input.value) + 1;
  table.querySelectorAll(`tr > :nth-child(${index})`).forEach((cell) => { cell.hidden = !input.checked; });
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
    enabled.append(statusBadge(stock.enabled ? "enabled" : "disabled"));
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
  const labels = { collection_config: "收集設定", execution: "執行紀錄", market: "市場資料", report: "研報", fundamental: "基本面" };
  try {
    const summary = await request(`/api/v1/admin/stocks/${encodeURIComponent(stock.symbol)}/references`);
    const detail = Object.entries(labels).map(([key, label]) => `${label} ${summary.references[key] || 0}`).join("、");
    if (!summary.can_delete) return showNotice(`無法刪除 ${stock.symbol}：${detail}。請先解除所有引用。`, true);
    if (!window.confirm(`${stock.symbol} 引用檢查：${detail}。確定刪除？`)) return;
    await request(`/api/v1/admin/stocks/${encodeURIComponent(stock.symbol)}`, { method: "DELETE" }); showNotice(`${stock.symbol} 已刪除`); await loadStocks();
  }
  catch (error) { showNotice(error.message, true); }
}

async function openStatus(stock) {
  const symbol = typeof stock === "string" ? stock.trim().toUpperCase() : stock.symbol;
  if (!symbol) return showNotice("請輸入股票代號", true);
  try {
    const data = await request(`/api/v1/admin/stocks/${encodeURIComponent(symbol)}/status`);
    state.statusItems = data.items;
    state.statusPage = 0;
    state.expandedStatus.clear();
    byId("status-symbol").value = symbol;
    renderStatus();
    state.loadedTabs.add("status");
    await activateTab("status");
  }
  catch (error) { showNotice(error.message, true); }
}

function renderStatus() {
  const filter = byId("status-filter").value.trim().toLocaleLowerCase("zh-Hant");
  const matching = state.statusItems.filter((item) => !filter || item.dataset_id.toLocaleLowerCase("zh-Hant").includes(filter));
  const start = state.statusPage * state.limit;
  const page = sorted(matching, state.statusSort, state.statusDirection).slice(start, start + state.limit);
  const body = byId("status-rows"); body.replaceChildren();
  if (!page.length) body.append(rowMessage(matching.length ? "此頁沒有資料" : "目前沒有符合條件的 Core 資料", 12));
  page.forEach((item) => {
    const key = item.dataset_id;
    const expanded = state.expandedStatus.has(key);
    const detail = node("button", expanded ? "收合" : "查看", "button quiet");
    detail.type = "button"; detail.setAttribute("aria-expanded", String(expanded));
    detail.addEventListener("click", () => { expanded ? state.expandedStatus.delete(key) : state.expandedStatus.add(key); renderStatus(); });
    const detailCell = document.createElement("td"); detailCell.append(detail);
    const dq = document.createElement("td"); dq.append(statusBadge(item.dq_warning_count ? "partial" : "success")); dq.append(` ${item.dq_warning_count || 0}`);
    const tr = document.createElement("tr");
    tr.append(detailCell, node("td", item.dataset_id), node("td", formatDate(item.latest_date)), node("td", item.row_count ?? "—", "numeric"),
      node("td", `${item.received_symbols ?? "—"}/${item.requested_symbols ?? "—"} (${formatRatio(item.coverage_ratio)})`, "numeric"),
      node("td", formatNullProfile(item)), dq, node("td", item.source_ids?.join(", ") || "—"),
      node("td", item.snapshot_ids?.join(", ") || "—"), node("td", item.freshness ?? "—"), node("td", formatDate(item.updated_at)),
      node("td", item.quarantine_state === "available" ? `${item.quarantine_count} 筆` : "—", "numeric"));
    body.append(tr);
    if (expanded) {
      const nested = document.createElement("table");
      nested.innerHTML = "<thead><tr><th>缺值欄位</th><th class=\"numeric\">筆數</th><th class=\"numeric\">比例</th><th>品質標記</th><th>執行紀錄</th><th>來源追溯</th></tr></thead>";
      const nestedBody = document.createElement("tbody");
      const profiles = item.null_profile?.length ? item.null_profile : [{ field: "—", count: 0, ratio: null }];
      profiles.forEach((field, index) => {
        const row = document.createElement("tr");
        row.append(node("td", field.field || "—"), node("td", field.count ?? "—", "numeric"), node("td", formatRatio(field.ratio), "numeric"),
          node("td", index ? "—" : item.quality_flags?.join(", ") || "—"), node("td", index ? "—" : item.execution_ids?.join(", ") || "—"),
          node("td", index ? "—" : item.provenance_ids?.join(", ") || "—"));
        nestedBody.append(row);
      });
      nested.append(nestedBody);
      const detailRow = document.createElement("tr"); const cell = document.createElement("td");
      detailRow.className = "detail-row"; cell.colSpan = 12; cell.append(nested); detailRow.append(cell); body.append(detailRow);
    }
  });
  byId("status-page-label").textContent = `第 ${state.statusPage + 1} 頁 · ${matching.length} 筆`;
  byId("prev-status-page").disabled = state.statusPage === 0;
  byId("next-status-page").disabled = start + state.limit >= matching.length;
  updateSort("[data-status-sort]", state.statusSort, state.statusDirection);
  document.querySelectorAll('[data-column-target="status-table"]').forEach(toggleColumn);
}

async function enqueueCollection() {
  const configId = byId("config-id").value.trim();
  if (!configId) return showNotice("請輸入設定 ID", true);
  if (!state.selected.size) return showNotice("請先選取至少一檔股票", true);
  try {
    const payload = { config_id: configId, symbols: [...state.selected] };
    payload.options = {
      start_date: byId("backfill-start").value, end_date: byId("backfill-end").value,
      source_ids: byId("backfill-sources").value.split(/[\s,]+/).filter(Boolean),
    };
    const execution = await request("/api/v1/admin/executions/collection", { method: "POST", body: JSON.stringify(payload) });
    showNotice(`資料收集已加入佇列：${execution.execution_id}`);
    state.selected.clear();
    selectionChanged();
    await activateTab("executions", { reload: true });
  } catch (error) { showNotice(error.message, true); }
}

async function enqueueAnalysis() {
  const configId = byId("config-id").value.trim();
  if (!configId) return showNotice("請輸入設定 ID", true);
  if (!state.selected.size) return showNotice("請先選取至少一檔股票", true);
  try {
    const execution = await request("/api/v1/admin/executions/analysis", {
      method: "POST", body: JSON.stringify({ config_id: configId, symbols: [...state.selected] }),
    });
    showNotice(`分析已加入已保存佇列：${execution.execution_id}`);
    state.selected.clear(); selectionChanged();
    await activateTab("executions", { reload: true });
  } catch (error) { showNotice(error.message, true); }
}

async function loadMart() {
  const params = new URLSearchParams({ limit: "100" });
  [["analysis_as_of", "mart-date"], ["scope_type", "mart-scope"], ["scope_id", "mart-scope-id"],
    ["role", "mart-role"], ["prompt_version", "mart-prompt"], ["analysis_outcome", "mart-outcome"],
    ["publication_status", "mart-publication"]].forEach(([name, id]) => {
    const value = byId(id).value.trim(); if (value) params.set(name, value);
  });
  const body = byId("mart-rows");
  try {
    const data = await request(`/api/v1/admin/mart-reports?${params}`);
    body.replaceChildren();
    if (!data.items.length) body.append(rowMessage("此條件沒有已保存的 Mart 成果物", 9));
    data.items.forEach((report) => {
      const artifact = node("a", report.selected_role ? `成果物 · ${displayStatus(report.selected_role)}` : "成果物");
      artifact.href = report.artifact_console_url; artifact.target = "_blank"; artifact.rel = "noopener noreferrer";
      artifact.title = `${report.table_identifier} @ snapshot ${report.iceberg_snapshot_id}`;
      const artifactCell = document.createElement("td"); artifactCell.append(artifact);
      const outcome = document.createElement("td"); outcome.append(statusBadge(report.analysis_outcome));
      const publication = document.createElement("td"); publication.append(statusBadge(report.publication_status));
      const reviewCell = document.createElement("td");
      if (["publishable", "published", "blocked"].includes(report.publication_status) && report.analysis_outcome === "complete") {
        const action = report.publication_status === "blocked" ? "unblock" : "block";
        const button = node("button", action === "block" ? "封鎖" : "解除封鎖");
        button.className = "button quiet"; button.type = "button";
        button.addEventListener("click", async () => {
          const reason = window.prompt("請輸入發布審查理由");
          if (!reason || !reason.trim()) return;
          try {
            await request(`/api/v1/admin/mart-reports/${encodeURIComponent(report.execution_id)}/${encodeURIComponent(report.scope_type)}/${encodeURIComponent(report.scope_id)}/publication`, {
              method: "PATCH", body: JSON.stringify({ action, reason: reason.trim() }),
            });
            showNotice(`發布狀態已${action === "block" ? "封鎖" : "解除封鎖"}`); await loadMart();
          } catch (error) { showNotice(error.message, true); }
        });
        reviewCell.append(button);
      } else reviewCell.append(node("span", "—"));
      const row = document.createElement("tr");
      row.append(node("td", report.analysis_as_of), node("td", report.scope_type), node("td", report.scope_id),
        outcome, publication, node("td", report.prompt_version), node("td", formatRatio(report.completeness)), artifactCell, reviewCell);
      body.append(row);
    });
  } catch (error) { body.replaceChildren(rowMessage("Mart index 目前無法使用", 8)); showNotice(error.message, true); }
}

async function loadExecutions() {
  const body = byId("execution-rows");
  try {
    const params = new URLSearchParams({ limit: state.limit });
    const cursor = state.executionCursors[state.executionPage];
    if (cursor) params.set("cursor", cursor);
    const data = await request(`/api/v1/admin/executions?${params}`);
    state.executions = data.items;
    state.executionNext = data.next_cursor;
    renderExecutions();
  } catch (error) {
    body.replaceChildren(rowMessage("執行紀錄目前無法使用", 6));
    showNotice(error.message, true);
  }
}

function renderExecutions() {
  const filter = byId("execution-filter").value.trim().toLocaleLowerCase("zh-Hant");
  const items = sorted(state.executions.filter((item) => !filter || [item.status, item.trigger_type, item.config_id].some((value) => String(value || "").toLocaleLowerCase("zh-Hant").includes(filter))), state.executionSort, state.executionDirection);
  const body = byId("execution-rows"); body.replaceChildren();
  if (!items.length) body.append(rowMessage(filter ? "本頁沒有符合條件的執行紀錄" : "尚無已保存的執行紀錄", 6));
  items.forEach((execution) => {
    const tr = document.createElement("tr");
    const status = document.createElement("td"); status.append(statusBadge(execution.status));
    const detailCell = document.createElement("td"); detailCell.className = "align-right";
    const detail = node("button", "查看", "button quiet"); detail.type = "button";
    detail.addEventListener("click", (event) => { event.stopPropagation(); openExecution(execution.execution_id, detail); });
    detailCell.append(detail);
    tr.append(status, node("td", displayStatus(execution.trigger_type)), node("td", execution.config_id || "—"), node("td", formatDate(execution.requested_at)), node("td", execution.retry_count ?? "—", "numeric"), detailCell);
    tr.tabIndex = 0; tr.setAttribute("role", "button"); tr.setAttribute("aria-label", `查看執行紀錄 ${execution.execution_id}`);
    tr.addEventListener("click", () => openExecution(execution.execution_id, tr));
    tr.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); openExecution(execution.execution_id, tr); } });
    body.append(tr);
  });
  byId("execution-count").textContent = state.executions.length;
  byId("active-count").textContent = state.executions.filter((item) => ["queued", "running", "retrying"].includes(item.status)).length;
  byId("execution-page-label").textContent = `第 ${state.executionPage + 1} 頁`;
  byId("prev-execution-page").disabled = state.executionPage === 0;
  byId("next-execution-page").disabled = !state.executionNext;
  updateSort("[data-execution-sort]", state.executionSort, state.executionDirection);
  document.querySelectorAll('[data-column-target="execution-table"]').forEach(toggleColumn);
}

async function openExecution(id, opener) {
  try {
    const execution = await request(`/api/v1/admin/executions/${encodeURIComponent(id)}`);
    const content = byId("dialog-content"); content.replaceChildren();
    const list = document.createElement("dl"); list.className = "detail-grid";
    [["執行紀錄 ID", execution.execution_id], ["追蹤 ID", execution.trace_id], ["狀態", displayStatus(execution.status)], ["類型", displayStatus(execution.trigger_type)], ["設定", execution.config_id], ["要求時間", formatDate(execution.requested_at)], ["完成時間", formatDate(execution.finished_at)]].forEach(([term, value]) => { const wrap = document.createElement("div"); wrap.append(node("dt", term), node("dd", value)); list.append(wrap); });
    content.append(list, node("h3", "工作項目"));
    const wrap = node("div", null, "table-wrap"); const table = document.createElement("table"); table.id = "execution-items-table";
    table.innerHTML = "<thead><tr><th>來源</th><th>資料集</th><th>狀態</th><th class=\"numeric\">已處理</th><th class=\"numeric\">成功</th><th class=\"numeric\">失敗</th><th class=\"numeric\">重試</th><th>階段</th><th>Core 提交</th><th>安全訊息</th></tr></thead>";
    const body = document.createElement("tbody"); body.id = "execution-item-rows";
    (execution.items || []).forEach((item) => {
      const good = ["success", "fallback"].includes(item.state);
      const failed = ["failed", "unavailable", "schema_drift"].includes(item.state);
      const row = document.createElement("tr"); const status = document.createElement("td"); status.append(statusBadge(item.state));
      row.append(node("td", item.source_id || "—"), node("td", item.dataset_id || "—"), status,
        node("td", item.rows_received ?? "—", "numeric"), node("td", good ? item.rows_received ?? 0 : 0, "numeric"),
        node("td", failed ? 1 : 0, "numeric"), node("td", item.retry_count ?? 0, "numeric"),
        node("td", item.cache_hit ? "已命中快取" : "—"), node("td", item.core_committed === true ? "已提交" : "—"), node("td", item.safe_message || "—"));
      body.append(row);
    });
    if (!execution.items?.length) body.append(rowMessage("尚無工作項目", 10));
    table.append(body); wrap.append(table); content.append(wrap);
    const lineage = execution.lineage || { executions: [], reports: [] };
    content.append(node("h3", "執行鏈"));
    const chain = document.createElement("ul");
    (lineage.executions || []).forEach((item) => chain.append(node("li", `${displayStatus(item.trigger_type)} · ${item.execution_id} · ${displayStatus(item.status)}`)));
    if (!chain.children.length) chain.append(node("li", "尚無關聯執行紀錄"));
    content.append(chain, node("h3", "Mart 報告"));
    const reports = document.createElement("ul");
    (lineage.reports || []).forEach((item) => reports.append(node("li", `${displayStatus(item.scope_type)}:${item.scope_id} · Core ${item.core_snapshot_id} · ${displayStatus(item.publication_status)}`)));
    if (!reports.children.length) reports.append(node("li", "尚無 Mart 報告"));
    content.append(reports);
    const dialog = byId("execution-dialog"); dialogOpeners.set(dialog, opener); dialog.showModal(); byId("close-dialog").focus();
  } catch (error) { showNotice(error.message, true); }
}

async function loadSources() {
  const body = byId("source-list");
  try {
    const params = new URLSearchParams({ limit: state.limit });
    const cursor = state.sourceCursors[state.sourcePage]; if (cursor) params.set("cursor", cursor);
    const data = await request(`/api/v1/admin/source-health?${params}`);
    state.sourceNext = data.next_cursor;
    body.replaceChildren();
    if (!data.items.length) body.append(rowMessage("尚無已保存的監測資料", 11));
    let healthy = 0;
    data.items.forEach((source) => {
      const rate = typeof source.success_rate === "number" ? Math.round(source.success_rate * 100) : null;
      if (["success", "fallback", "partial"].includes(source.last_state)) healthy += 1;
      const status = document.createElement("td"); status.append(statusBadge(source.last_state));
      const expected = Number(source.expected_symbols || 0); const received = Number(source.received_symbols || 0);
      const gap = source.coverage_tier === "core_focus" ? Math.max(0, expected - received) : 0;
      const row = document.createElement("tr"); row.append(node("td", source.source_id || "—"), node("td", source.dataset_id || "—"), status,
        node("td", rate === null ? "—" : `${rate}%`, "numeric"), node("td", `${expected}/${received}`, "numeric"),
        node("td", gap, "numeric"), node("td", formatDate(source.last_fetched_at)), node("td", formatDate(source.latest_observation_at)),
        node("td", source.cache_age_seconds == null ? "—" : `${Math.round(source.cache_age_seconds)}s`, "numeric"),
      node("td", source.schema_drift_count ?? 0, "numeric"), node("td", displayStatus(source.coverage_tier))); body.append(row);
    });
    byId("source-summary").textContent = data.items.length ? `${healthy}/${data.items.length}` : "—";
    byId("source-page-label").textContent = `第 ${state.sourcePage + 1} 頁`;
    byId("prev-source-page").disabled = state.sourcePage === 0;
    byId("next-source-page").disabled = !state.sourceNext;
  } catch (error) { body.replaceChildren(rowMessage("來源健康目前無法使用", 6)); showNotice(error.message, true); }
}

async function loadCatalog() {
  const list = byId("catalog-list");
  try {
    const params = new URLSearchParams({ limit: state.limit });
    const cursor = state.catalogCursors[state.catalogPage]; if (cursor) params.set("cursor", cursor);
    const data = await request(`/api/v1/admin/source-catalog?${params}`);
    state.catalogNext = data.next_cursor;
    list.replaceChildren();
    if (!data.items.length) list.append(node("p", "尚無資料源設定", "empty"));
    const candidates = new Set();
    data.items.forEach((config) => {
      const card = node("article", null, "source-card");
      card.append(node("strong", `${config.config_id} · ${config.dataset_id}`), node("p", `來源 ${config.source_ids.join(", ")} · ${displayStatus(config.cadence)} · ${displayStatus(config.coverage_tier)}`), statusBadge(config.authorization_status));
      const edit = node("button", "編輯", "button quiet"); edit.type = "button"; edit.addEventListener("click", () => openConfig(config, edit)); card.append(edit);
      list.append(card);
      if (["candidate", "blocked"].includes(config.authorization_status)) config.source_ids.forEach((source) => candidates.add(source));
    });
    const select = byId("review-adapter");
    const previous = select.value;
    select.replaceChildren(...[...candidates].sort().map((adapter) => { const option = node("option", adapter); option.value = adapter; return option; }));
    if (candidates.has(previous)) select.value = previous;
    byId("review-form").hidden = candidates.size === 0;
    if (candidates.size) await loadReview();
    byId("catalog-page-label").textContent = `第 ${state.catalogPage + 1} 頁`;
    byId("prev-catalog-page").disabled = state.catalogPage === 0;
    byId("next-catalog-page").disabled = !state.catalogNext;
  }
  catch (error) { list.replaceChildren(node("p", "資料源設定目前無法使用", "empty")); showNotice(error.message, true); }
}

function updateConfigAuthorization() {
  const blocked = ["candidate", "blocked"].includes(byId("config-authorization").value);
  byId("config-enabled").disabled = blocked;
  if (blocked) byId("config-enabled").checked = false;
}

function openConfig(config, opener) {
  state.editingConfig = config;
  byId("config-edit-id").value = config.config_id;
  byId("config-dataset").value = config.dataset_id;
  byId("config-sources").value = config.source_ids.join(", ");
  byId("config-cadence").value = config.cadence;
  byId("config-coverage").value = config.coverage_tier;
  byId("config-scope").value = config.scope;
  byId("config-authorization").value = config.authorization_status;
  byId("config-retention").value = config.retention_class;
  byId("config-max-symbols").value = config.max_symbols;
  byId("config-enabled").checked = config.enabled;
  byId("config-collection-enabled").checked = config.collection_enabled;
  updateConfigAuthorization();
  const dialog = byId("config-dialog"); dialogOpeners.set(dialog, opener); dialog.showModal(); byId("config-sources").focus();
}

async function saveConfig(event) {
  event.preventDefault();
  const payload = {
    ...state.editingConfig,
    actor: byId("config-actor").value.trim(),
    source_ids: byId("config-sources").value.split(/[\s,]+/).filter(Boolean),
    cadence: byId("config-cadence").value, coverage_tier: byId("config-coverage").value,
    scope: byId("config-scope").value.trim(), authorization_status: byId("config-authorization").value,
    retention_class: byId("config-retention").value, max_symbols: Number(byId("config-max-symbols").value),
    enabled: byId("config-enabled").checked, collection_enabled: byId("config-collection-enabled").checked,
  };
  try {
    await request("/api/v1/admin/source-catalog", { method: "PUT", body: JSON.stringify(payload) });
    byId("config-dialog").close(); showNotice("資料源設定已儲存並寫入稽核紀錄"); await loadCatalog();
  } catch (error) { showNotice(error.message, true); }
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
    showNotice("候選資料介面審查已儲存並寫入稽核紀錄");
  } catch (error) { showNotice(error.message, true); }
}

function governanceValue() {
  return {
    version: byId("governance-policy-version").value.trim(),
    developmentCompletenessGate: Number(byId("governance-gate").value),
    roleWeights: Object.fromEntries(["fundamental", "valuation", "positioning", "quant", "event_risk"].map((role) => [role, Number(byId(`governance-weight-${role}`).value)])),
    blocking: { manualReviewRequired: byId("governance-manual-review").checked, criticalQualityFlag: byId("governance-critical-quality").checked, highRiskScoreAtLeast: Number(byId("governance-high-risk").value) },
    deterministicConstants: { status: byId("governance-constant-status").value, approved: byId("governance-approved").checked, values: { highRiskScoreThreshold: Number(byId("governance-constant-risk").value), largeMovePercent: Number(byId("governance-constant-move").value), completenessGatePercent: Number(byId("governance-constant-gate").value) } },
  };
}

function fillGovernance(value) {
  byId("governance-policy-version").value = value.version;
  byId("governance-gate").value = value.developmentCompletenessGate;
  Object.entries(value.roleWeights).forEach(([role, weight]) => { byId(`governance-weight-${role}`).value = weight; });
  byId("governance-manual-review").checked = value.blocking.manualReviewRequired;
  byId("governance-critical-quality").checked = value.blocking.criticalQualityFlag;
  byId("governance-high-risk").value = value.blocking.highRiskScoreAtLeast;
  byId("governance-constant-status").value = value.deterministicConstants.status;
  byId("governance-approved").checked = value.deterministicConstants.approved;
  byId("governance-constant-risk").value = value.deterministicConstants.values.highRiskScoreThreshold;
  byId("governance-constant-move").value = value.deterministicConstants.values.largeMovePercent;
  byId("governance-constant-gate").value = value.deterministicConstants.values.completenessGatePercent;
}

function renderGovernanceHistory(items) {
  const body = byId("governance-history"); body.replaceChildren();
  if (!items.length) return body.append(node("p", "尚無已提交版本", "empty"));
  items.forEach((item) => {
    const card = document.createElement("article"); card.className = "card";
    card.append(node("strong", `v${item.detail?.version ?? "?"} · ${displayStatus(item.detail?.status || "pending")}`), node("small", `${item.actor} · ${formatDate(item.created_at)}`));
    card.append(node("p", item.detail?.reason || "—"));
    const changes = item.detail?.changes || [];
    card.append(node("small", `${changes.length} 項變更`));
    body.append(card);
  });
}

async function loadGovernance() {
  try {
    const [current, history] = await Promise.all([request("/api/v1/admin/governance/policy"), request("/api/v1/admin/governance/policy/history")]);
    state.governanceVersion = current.version; fillGovernance(current);
    byId("governance-status").value = current.status;
    byId("governance-version").value = current.version;
    byId("governance-state").textContent = `${displayStatus(current.status)} · v${current.version}`;
    renderGovernanceHistory(history.items);
  } catch (error) { showNotice(error.message, true); }
}

async function previewGovernance() {
  try {
    const diff = await request("/api/v1/admin/governance/policy/diff", { method: "POST", body: JSON.stringify({ value: governanceValue() }) });
    byId("governance-diff").textContent = diff.changes.length
      ? diff.changes.map((change) => `${change.path}: ${JSON.stringify(change.before)} → ${JSON.stringify(change.after)}`).join("\n")
      : "沒有變更";
  } catch (error) { showNotice(error.message, true); }
}

async function saveGovernance(event) {
  event.preventDefault();
  try {
    const saved = await request("/api/v1/admin/governance/policy", { method: "PUT", body: JSON.stringify({ value: governanceValue(), status: byId("governance-status").value, reason: byId("governance-reason").value.trim(), expected_version: state.governanceVersion }) });
    state.governanceVersion = saved.version; byId("governance-version").value = saved.version;
    byId("governance-state").textContent = `${displayStatus(saved.status)} · v${saved.version}`;
    byId("governance-reason").value = ""; byId("governance-diff").textContent = "已儲存新版本";
    showNotice(`治理設定 v${saved.version} 已儲存`); await loadGovernance();
  } catch (error) { showNotice(error.message, true); }
}

async function runBackfill(event) {
  event.preventDefault();
  const start = byId("bf-start").value;
  const end = byId("bf-end").value;
  if (!start || !end) return showNotice("請填寫起訖日期", true);
  const result = byId("backfill-result");
  result.textContent = "送出中…";
  try {
    const data = await request("/api/v1/admin/pipeline/backfill", {
      method: "POST",
      body: JSON.stringify({ start_date: start, end_date: end, trigger_mart: byId("bf-trigger-mart").checked }),
    });
    result.textContent = JSON.stringify(data, null, 2);
    showNotice(`補跑已送出：${data.execution_name || data.status}`);
  } catch (error) {
    result.textContent = error.message;
    showNotice(error.message, true);
  }
}

async function loadSettings() {
  try {
    const schedule = await request("/api/v1/admin/settings/schedule"); const retention = await request("/api/v1/admin/settings/retention");
    if (schedule.value) { byId("schedule-time").value = schedule.value.time || "08:00"; byId("schedule-enabled").checked = schedule.value.enabled !== false; byId("holiday-overrides").value = (schedule.value.holiday_overrides || []).join(", "); byId("settings-form").dataset.scheduleVersion = schedule.version; }
    if (retention.value) { byId("retention-days").value = retention.value.days || 30; byId("cleanup-enabled").checked = retention.value.cleanup_enabled !== false; byId("settings-form").dataset.retentionVersion = retention.version; }
  } catch (error) { showNotice(error.message, true); }
}

async function saveSettings(event) {
  event.preventDefault(); const actor = byId("settings-actor").value.trim(); if (!actor) return showNotice("請填寫操作者", true);
  const form = byId("settings-form");
  try {
    const holidays = byId("holiday-overrides").value.split(/[\s,]+/).filter(Boolean);
    const schedule = await request("/api/v1/admin/settings/schedule", { method: "PUT", body: JSON.stringify({ actor, expected_version: Number(form.dataset.scheduleVersion || 0), value: { time: byId("schedule-time").value, enabled: byId("schedule-enabled").checked, holiday_overrides: holidays } }) });
    const retention = await request("/api/v1/admin/settings/retention", { method: "PUT", body: JSON.stringify({ actor, expected_version: Number(form.dataset.retentionVersion || 0), value: { days: Number(byId("retention-days").value), cleanup_enabled: byId("cleanup-enabled").checked } }) });
    form.dataset.scheduleVersion = schedule.version; form.dataset.retentionVersion = retention.version; showNotice("設定已儲存，Cloud Scheduler 已同步");
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
  const resetStockPage = () => { state.stockPage = 0; state.stockCursors = [null]; state.stockNext = null; };
  byId("stock-search").addEventListener("submit", (event) => { event.preventDefault(); resetStockPage(); loadStocks(); });
  byId("enabled-filter").addEventListener("change", () => { resetStockPage(); loadStocks(); });
  byId("prev-page").addEventListener("click", () => { if (state.stockPage > 0) { state.stockPage -= 1; loadStocks(); } });
  byId("next-page").addEventListener("click", () => { if (state.stockNext) { state.stockPage += 1; state.stockCursors[state.stockPage] = state.stockNext; loadStocks(); } });
  byId("select-page").addEventListener("change", (event) => { state.stocks.forEach((stock) => event.target.checked ? state.selected.add(stock.symbol) : state.selected.delete(stock.symbol)); selectionChanged(); renderStocks(); });
  byId("clear-selection").addEventListener("click", () => { state.selected.clear(); renderStocks(); });
  byId("queue-collection").addEventListener("click", enqueueCollection);
  byId("queue-analysis").addEventListener("click", enqueueAnalysis);
  byId("refresh-executions").addEventListener("click", loadExecutions);
  byId("prev-execution-page").addEventListener("click", () => { if (state.executionPage > 0) { state.executionPage -= 1; loadExecutions(); } });
  byId("next-execution-page").addEventListener("click", () => { if (state.executionNext) { state.executionPage += 1; state.executionCursors[state.executionPage] = state.executionNext; loadExecutions(); } });
  byId("execution-filter").addEventListener("input", renderExecutions);
  document.querySelectorAll("[data-execution-sort]").forEach((button) => button.addEventListener("click", () => {
    const key = button.dataset.executionSort; state.executionDirection = state.executionSort === key ? -state.executionDirection : 1; state.executionSort = key; renderExecutions();
  }));
  byId("status-filter").addEventListener("input", () => { state.statusPage = 0; renderStatus(); });
  byId("prev-status-page").addEventListener("click", () => { if (state.statusPage > 0) { state.statusPage -= 1; renderStatus(); } });
  byId("next-status-page").addEventListener("click", () => { state.statusPage += 1; renderStatus(); });
  document.querySelectorAll("[data-status-sort]").forEach((button) => button.addEventListener("click", () => {
    const key = button.dataset.statusSort; state.statusDirection = state.statusSort === key ? -state.statusDirection : 1; state.statusSort = key; state.statusPage = 0; renderStatus();
  }));
  document.querySelectorAll("[data-column-target]").forEach((input) => input.addEventListener("change", () => toggleColumn(input)));
  byId("prev-source-page").addEventListener("click", () => { if (state.sourcePage > 0) { state.sourcePage -= 1; loadSources(); } });
  byId("next-source-page").addEventListener("click", () => { if (state.sourceNext) { state.sourcePage += 1; state.sourceCursors[state.sourcePage] = state.sourceNext; loadSources(); } });
  byId("prev-catalog-page").addEventListener("click", () => { if (state.catalogPage > 0) { state.catalogPage -= 1; loadCatalog(); } });
  byId("next-catalog-page").addEventListener("click", () => { if (state.catalogNext) { state.catalogPage += 1; state.catalogCursors[state.catalogPage] = state.catalogNext; loadCatalog(); } });
  byId("refresh-all").addEventListener("click", refreshAll);
  byId("logout").addEventListener("click", logout);
  byId("status-search").addEventListener("submit", (event) => { event.preventDefault(); openStatus(byId("status-symbol").value); });
  byId("governance-preview").addEventListener("click", previewGovernance);
  byId("governance-form").addEventListener("submit", saveGovernance);
  byId("mart-filter").addEventListener("submit", (event) => { event.preventDefault(); loadMart(); });
  byId("add-stock").addEventListener("click", () => openStock());
  byId("stock-form").addEventListener("submit", async (event) => { event.preventDefault(); const dialog = byId("stock-dialog"); try { await request("/api/v1/admin/stocks", { method: "PUT", body: JSON.stringify({ symbol: byId("stock-symbol").value, name: byId("stock-name").value, market: byId("stock-market").value, listing_status: byId("stock-listing").value, enabled: byId("stock-enabled").checked }) }); dialog.close(); showNotice("股票資料已儲存"); await loadStocks(); } catch (error) { showNotice(error.message, true); } });
  byId("backfill-form").addEventListener("submit", runBackfill);
  byId("settings-form").addEventListener("submit", saveSettings);
  byId("review-adapter").addEventListener("change", loadReview);
  byId("review-form").addEventListener("submit", saveReview);
  byId("config-authorization").addEventListener("change", updateConfigAuthorization);
  byId("config-form").addEventListener("submit", saveConfig);
  byId("close-dialog").addEventListener("click", () => byId("execution-dialog").close());
  byId("cancel-stock").addEventListener("click", () => byId("stock-dialog").close());
  byId("cancel-config").addEventListener("click", () => byId("config-dialog").close());
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", restoreDialogFocus);
  });
  try { const health = await request("/health"); document.querySelector(".pulse").className = "pulse ok"; byId("runtime-label").textContent = "控制面服務正常"; byId("build-version").textContent = health.revision || "unknown"; } catch { document.querySelector(".pulse").className = "pulse error"; byId("runtime-label").textContent = "控制面服務無法使用"; byId("build-version").textContent = "unknown"; }
  const initial = new URL(window.location.href).searchParams.get("tab") || "stocks";
  await activateTab(initial);
});
