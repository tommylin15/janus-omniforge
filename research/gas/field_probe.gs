/**
 * Janus D07-PRE: public-field availability probe (NOT the full monthly collector).
 * Personal/non-commercial research only.  No Owner, trade, or cash records.
 * GAS Script Properties required:
 *   JANUS_RESEARCH_MONTH        YYYY-MM (completed or current probe month)
 *   JANUS_RESEARCH_SYMBOLS      comma-delimited public common-stock symbols, max 20
 *   JANUS_RESEARCH_FOLDER_ID    Drive ID of private janusChatGPT/資料源
 *   JANUS_FINMIND_LICENSE_ACK   true (operator reviewed source conditions)
 * Optional:
 *   JANUS_FINMIND_TOKEN         keep only in Script Properties, never logs
 *   JANUS_RESEARCH_REVISION     r1, r2, etc. (changing starts a new immutable probe)
 */
const JANUS_PROBE = Object.freeze({
  source: "FinMind",
  endpoint: "https://api.finmindtrade.com/api/v4/data",
  datasets: [
    "TaiwanStockPrice",
    "TaiwanStockPER",
    "TaiwanStockMonthRevenue",
    "TaiwanStockInstitutionalInvestorsBuySell"
  ],
  maxSymbols: 20,
  maxRequestsPerRun: 12,
  minimumIntervalMillis: 12500,
  checkpointKey: "JANUS_PUBLIC_PROBE_CURSOR"
});

function janusResearchProbe() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) throw new Error("another Janus research probe is running");
  try {
    const props = PropertiesService.getScriptProperties();
    if (props.getProperty("JANUS_FINMIND_LICENSE_ACK") !== "true") {
      throw new Error("FinMind source-use license has not been acknowledged");
    }
    const month = props.getProperty("JANUS_RESEARCH_MONTH");
    if (!/^20\\d{2}-(0[1-9]|1[0-2])$/.test(month || "")) throw new Error("invalid research month");
    const revision = props.getProperty("JANUS_RESEARCH_REVISION") || "r1";
    if (!/^r[1-9]\\d{0,3}$/.test(revision)) throw new Error("invalid immutable probe revision");
    const symbols = String(props.getProperty("JANUS_RESEARCH_SYMBOLS") || "")
      .split(",").map(s => s.trim()).filter(Boolean);
    if (!symbols.length || symbols.length > JANUS_PROBE.maxSymbols ||
        new Set(symbols).size !== symbols.length ||
        symbols.some(s => !/^[1-9]\\d{3}$/.test(s))) {
      throw new Error("set 1-20 unique four-digit ordinary-stock candidates");
    }
    const folderId = props.getProperty("JANUS_RESEARCH_FOLDER_ID");
    if (!folderId) throw new Error("missing private Drive folder ID");
    const destination = DriveApp.getFolderById(folderId);
    if (destination.getName() !== "資料源") throw new Error("unexpected Drive destination");
    const parents = destination.getParents();
    if (!parents.hasNext() || parents.next().getName() !== "janusChatGPT") {
      throw new Error("Drive destination must be inside janusChatGPT");
    }
    if (destination.getSharingAccess() !== DriveApp.Access.PRIVATE) {
      throw new Error("research Drive destination must not be publicly shared");
    }
    const folder = janusChildFolder_(janusChildFolder_(destination, "_field_probe"), month);
    const key = JSON.stringify({month: month, revision: revision, symbols: symbols,
                                datasets: JANUS_PROBE.datasets});
    const state = JSON.parse(props.getProperty(JANUS_PROBE.checkpointKey) || "null");
    if (state && state.key !== key) {
      throw new Error("probe checkpoint belongs to a different scope; archive and clear it manually");
    }
    let cursor = state ? state.cursor : 0;
    let fetched = 0;
    const [year, mon] = month.split("-").map(Number);
    const start = month + "-01";
    const end = Utilities.formatDate(new Date(Date.UTC(year, mon, 0)), "UTC", "yyyy-MM-dd");
    while (cursor < symbols.length * JANUS_PROBE.datasets.length &&
           fetched < JANUS_PROBE.maxRequestsPerRun) {
      const symbol = symbols[Math.floor(cursor / JANUS_PROBE.datasets.length)];
      const dataset = JANUS_PROBE.datasets[cursor % JANUS_PROBE.datasets.length];
      const prefix = revision + "-" + dataset + "-" + symbol + "-";
      const existing = folder.getFiles();
      let done = false;
      while (existing.hasNext()) {
        if (existing.next().getName().indexOf(prefix) === 0) { done = true; break; }
      }
      if (!done) {
        janusThrottle_(props);
        const options = {dataset: dataset, data_id: symbol, start_date: start, end_date: end};
        const query = Object.keys(options).map(k =>
          encodeURIComponent(k) + "=" + encodeURIComponent(options[k])).join("&");
        const token = props.getProperty("JANUS_FINMIND_TOKEN");
        const response = UrlFetchApp.fetch(JANUS_PROBE.endpoint + "?" + query, {
          method: "get", followRedirects: false, muteHttpExceptions: true,
          headers: token ? {Authorization: "Bearer " + token} : {}
        });
        if (response.getResponseCode() !== 200) {
          throw new Error("FinMind HTTP non-200; retry same checkpoint later");
        }
        const payload = JSON.parse(response.getContentText());
        if (payload.status !== 200 || !Array.isArray(payload.data)) {
          throw new Error("FinMind dataset response is not successful");
        }
        const rows = payload.data.filter(row => String(row.stock_id || "") === symbol);
        const fields = Array.from(new Set(rows.flatMap(row => Object.keys(row)))).sort();
        const nonempty = {};
        fields.forEach(field => nonempty[field] = rows.filter(row =>
          row[field] !== null && row[field] !== undefined && row[field] !== "").length);
        const entry = {
          schema_version: 1, kind: "PUBLIC_FIELD_AVAILABILITY_ONLY",
          source: JANUS_PROBE.source, source_dataset: dataset,
          source_url: JANUS_PROBE.endpoint, market: "UNKNOWN_UNVERIFIED",
          symbol: symbol, month: month, revision: revision,
          collected_at: new Date().toISOString(), rows: rows,
          field_names: fields, nonempty_counts: nonempty,
          status: rows.length ? "OBSERVED" : "EMPTY"
        };
        const bytes = JSON.stringify(entry);
        const sha = janusSha256_(bytes);
        folder.createFile(prefix + sha + ".json", bytes, MimeType.PLAIN_TEXT);
        fetched++;
      }
      cursor++;
      props.setProperty(JANUS_PROBE.checkpointKey, JSON.stringify({key: key, cursor: cursor}));
    }
    return {status: cursor === symbols.length * JANUS_PROBE.datasets.length
                     ? "FIELD_PROBE_COLLECTED" : "PARTIAL",
            observed_requests_this_run: fetched, cursor: cursor,
            total: symbols.length * JANUS_PROBE.datasets.length,
            monthly_zip_generated: false, research_70pct_certified: false,
            message: "Only public field availability was probed; no model training"};
  } finally { lock.releaseLock(); }
}

function janusChildFolder_(parent, name) {
  const folders = parent.getFoldersByName(name);
  return folders.hasNext() ? folders.next() : parent.createFolder(name);
}

function janusSha256_(body) {
  const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, body,
                                         Utilities.Charset.UTF_8);
  return digest.map(b => ("0" + ((b + 256) % 256).toString(16)).slice(-2)).join("");
}

function janusThrottle_(props) {
  const until = Number(props.getProperty("JANUS_FINMIND_NEXT_REQUEST_MS") || 0);
  const now = Date.now();
  if (until > now) Utilities.sleep(until - now);
  props.setProperty("JANUS_FINMIND_NEXT_REQUEST_MS",
                    String(Date.now() + JANUS_PROBE.minimumIntervalMillis));
}
