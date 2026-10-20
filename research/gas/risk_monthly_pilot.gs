/**
 * D07-PRE Risk Analyst: manual, bounded GAS public-data collection pilot.
 * Research only. No GCP, Owner data, paid APIs, model publication, or triggers.
 *
 * Required Script Properties (do NOT hardcode secrets):
 * JANUS_RESEARCH_FOLDER_ID : private janusChatGPT/資料源 Drive folder ID
 * JANUS_FINMIND_LICENSE_ACK : true (operator checked account/source terms)
 * JANUS_RISK_START_MONTH : YYYY-MM, e.g. 2025-01
 * JANUS_RISK_END_MONTH   : YYYY-MM, e.g. 2026-09
 * JANUS_RISK_SYMBOLS     : 1-10 comma-delimited ordinary-stock codes
 * Optional: JANUS_FINMIND_TOKEN (never logged), JANUS_RISK_REVISION (r1...r999)
 *
 * Run janusRiskPilotCollect() repeatedly until status=PROBE_ARCHIVED.
 * Result ZIPs: janusChatGPT/資料源/_pilot_risk/<revision>/YYYY-MM.zip.
 * No 70% full-market certification; this deliberately avoids naming a
 * sampled file as the canonical research monthly archive.
 */
const JANUS_RISK_PILOT = Object.freeze({
  endpoint: 'https://api.finmindtrade.com/api/v4/data',
  maxSymbols: 10,
  maxRequestsPerRun: 8,
  throttleMs: 12500,
  throttleProperty: 'JANUS_RISK_FINMIND_NEXT_MS'
});

function janusRiskPilotCollect() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) throw new Error('risk pilot is already running');
  try {
    const properties = PropertiesService.getScriptProperties();
    if (properties.getProperty('JANUS_FINMIND_LICENSE_ACK') !== 'true') {
      throw new Error('FinMind license/plan confirmation missing');
    }
    const startMonth = properties.getProperty('JANUS_RISK_START_MONTH') || '';
    const endMonth = properties.getProperty('JANUS_RISK_END_MONTH') || '';
    if (!janusRiskMonthValid_(startMonth) || !janusRiskMonthValid_(endMonth) || startMonth > endMonth) {
      throw new Error('invalid or reversed research month range');
    }
    const revision = properties.getProperty('JANUS_RISK_REVISION') || 'r1';
    if (!/^r[1-9][0-9]{0,2}$/.test(revision)) throw new Error('invalid revision');
    const symbols = String(properties.getProperty('JANUS_RISK_SYMBOLS') || '').split(',')
      .map(s => s.trim()).filter(Boolean);
    if (!symbols.length || symbols.length > JANUS_RISK_PILOT.maxSymbols ||
        new Set(symbols).size !== symbols.length || symbols.some(s => !/^[1-9][0-9]{3}$/.test(s))) {
      throw new Error('set 1-10 unique four-digit ordinary-stock candidates');
    }
    const sourceFolder = DriveApp.getFolderById(properties.getProperty('JANUS_RESEARCH_FOLDER_ID'));
    if (sourceFolder.getName() !== '資料源' || sourceFolder.getSharingAccess() !== DriveApp.Access.PRIVATE) {
      throw new Error('destination must be the private 資料源 folder');
    }
    const parents = sourceFolder.getParents();
    if (!parents.hasNext() || parents.next().getName() !== 'janusChatGPT') {
      throw new Error('destination must be under janusChatGPT');
    }
    const stage = janusRiskChild_(sourceFolder, '_pilot_risk');
    const revisionFolder = janusRiskChild_(stage, revision);
    const shards = janusRiskChild_(revisionFolder, '_shards-' + startMonth + '-' + endMonth);
    const rosterFilename = 'roster.json';
    let requestCount = 0;
    let roster;
    let existing = janusRiskFile_(shards, rosterFilename);
    if (existing) {
      roster = JSON.parse(existing.getBlob().getDataAsString('UTF-8'));
    } else {
      janusRiskThrottle_(properties);
      roster = janusRiskFetch_(properties, {dataset: 'TaiwanStockInfo'});
      requestCount++;
      const newest = {};
      roster.forEach(item => {
        const id = String(item.stock_id || '');
        if (!symbols.includes(id)) return;
        const recorded = String(item.date || '');
        if (!newest[id] || String(newest[id].date || '') < recorded) newest[id] = item;
      });
      const approved = {};
      symbols.forEach(id => {
        const item = newest[id];
        const category = String(item && item.industry_category || '').toLowerCase();
        if (!item || !['twse', 'tpex'].includes(item.type) ||
            /(etf|etn|index|基金|債券|權證|大盤|所有證券|存託憑證|受益證券)/i.test(category)) {
          throw new Error('roster cannot verify an ordinary-share candidate: ' + id);
        }
        approved[id] = {symbol: id, market: item.type, industry: item.industry_category,
                        roster_date: item.date || null};
      });
      roster = approved;
      shards.createFile(rosterFilename, JSON.stringify(roster), MimeType.PLAIN_TEXT);
    }
    if (symbols.some(symbol => !roster[symbol])) {
      throw new Error('revision roster does not match the selected symbols');
    }
    const range = {start_date: startMonth + '-01', end_date: janusRiskEndOfMonth_(endMonth)};
    for (const symbol of symbols) {
      const filename = 'ohlcv-' + symbol + '.json';
      if (janusRiskFile_(shards, filename)) continue;
      if (requestCount >= JANUS_RISK_PILOT.maxRequestsPerRun) {
        return {status: 'PARTIAL', downloaded: symbols.filter(s => !!janusRiskFile_(shards, 'ohlcv-' + s + '.json')).length,
                total: symbols.length, monthly_zip_generated: false};
      }
      janusRiskThrottle_(properties);
      const rows = janusRiskFetch_(properties, Object.assign({dataset: 'TaiwanStockPrice', data_id: symbol}, range));
      requestCount++;
      const normalized = [];
      const observedAt = new Date().toISOString();
      rows.forEach(row => {
        if (String(row.stock_id || '') !== symbol ||
            String(row.date || '') < range.start_date || String(row.date || '') > range.end_date) return;
        const month = String(row.date).slice(0, 7);
        const values = [row.open, row.max, row.min, row.close, row.Trading_Volume, row.Trading_money];
        // Missing values remain null. They are not invented to make a usable bar.
        normalized.push({symbol: symbol, market: roster[symbol].market,
          trade_date: row.date, open: values[0], high: values[1], low: values[2],
          close: values[3], volume: values[4], turnover: values[5],
          source: 'FinMind:TaiwanStockPrice', source_month: month,
          observed_at: observedAt});
      });
      shards.createFile(filename, JSON.stringify(normalized), MimeType.PLAIN_TEXT);
    }
    const all = [];
    symbols.forEach(symbol => {
      const file = janusRiskFile_(shards, 'ohlcv-' + symbol + '.json');
      if (!file) throw new Error('missing symbol shard; rerun before sealing');
      JSON.parse(file.getBlob().getDataAsString('UTF-8')).forEach(row => all.push(row));
    });
    const months = janusRiskMonthRange_(startMonth, endMonth);
    for (const month of months) {
      const filename = month + '.zip';
      if (janusRiskFile_(revisionFolder, filename)) continue; // immutable completed output
      const bars = all.filter(row => row.source_month === month)
        .sort((a, b) => a.symbol.localeCompare(b.symbol) || a.trade_date.localeCompare(b.trade_date));
      const universeRows = symbols.map(symbol => roster[symbol]);
      const universeCsv = janusRiskCsv_(universeRows, ['symbol','market','industry','roster_date']);
      const barCsv = janusRiskCsv_(bars, ['symbol','market','trade_date','open','high','low','close',
                                        'volume','turnover','source','source_month','observed_at']);
      const monthCounts = {};
      ['twse','tpex'].forEach(market => {
        const chosen = universeRows.filter(row => row.market === market);
        const nonempty = new Set(bars.filter(row => row.market === market &&
          row.close !== null && row.close !== undefined && Number(row.close) > 0)
          .map(row => row.symbol));
        monthCounts[market] = {sample_symbols: chosen.length,
          symbols_with_valid_close: nonempty.size,
          observed_ratio: chosen.length ? nonempty.size / chosen.length : null};
      });
      const quality = {status:'PROBE', research_70pct_certified:false, month:month,
        market_counts:monthCounts, adjusted_close:'UNAVAILABLE',
        benchmark:'UNAVAILABLE', historical_pit:'NOT_VERIFIED',
        note:'Research pilot sample only; monthly market coverage is not certified'};
      const members = {
        'universe.csv':universeCsv, 'ohlcv.csv':barCsv,
        'valuation.csv':'', 'financials.csv':'', 'institutional.csv':'',
        'market_activity.csv':'', 'events.jsonl':'', 'benchmark.csv':'',
        'quality.json':JSON.stringify(quality)
      };
      const hashes = {};
      Object.keys(members).forEach(name => hashes[name] = janusRiskSha_(members[name]));
      const manifest = {schema_version:1, kind:'RISK_PROBE_ONLY',
        month:month, revision:revision, data_source:'FinMind',
        source_url:JANUS_RISK_PILOT.endpoint,
        source_datasets:['TaiwanStockInfo','TaiwanStockPrice'],
        collected_at:new Date().toISOString(), sha256:hashes,
        unavailable:['valuation','financials','institutional','market_activity','events','benchmark'],
        publication_allowed:false};
      members['manifest.json'] = JSON.stringify(manifest);
      const blobs = Object.keys(members).map(name =>
        Utilities.newBlob(members[name], 'text/plain', name));
      const zip = Utilities.zip(blobs, filename);
      revisionFolder.createFile(zip); // never overwrite or silently mutate
    }
    return {status:'PROBE_ARCHIVED', archived_months:months.length,
      selected_symbols:symbols.length, research_70pct_certified:false,
      drive_subfolder:'_pilot_risk/' + revision,
      message:'Manual Colab pilot ZIP inputs only; no model promotion'};
  } finally { lock.releaseLock(); }
}

function janusRiskMonthValid_(month) { return /^20\d{2}-(0[1-9]|1[0-2])$/.test(month); }
function janusRiskEndOfMonth_(month) {
  const p = month.split('-').map(Number);
  return Utilities.formatDate(new Date(Date.UTC(p[0], p[1], 0)), 'UTC', 'yyyy-MM-dd');
}
function janusRiskMonthRange_(start, end) {
  const out = [];
  let [year, month] = start.split('-').map(Number);
  while (year + '-' + ('0'+month).slice(-2) <= end) {
    out.push(year + '-' + ('0'+month).slice(-2));
    if (++month === 13) { year++; month=1; }
    if (out.length > 36) throw new Error('pilot range exceeds 36 months');
  }
  return out;
}
function janusRiskChild_(parent, name) {
  const items=parent.getFoldersByName(name);
  return items.hasNext() ? items.next() : parent.createFolder(name);
}
function janusRiskFile_(folder, name) {
  const files=folder.getFilesByName(name);
  return files.hasNext() ? files.next() : null;
}
function janusRiskSha_(body) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, body, Utilities.Charset.UTF_8)
    .map(x=>('0'+((x+256)%256).toString(16)).slice(-2)).join('');
}
function janusRiskCsv_(rows, names) {
  const quote=x=>'"'+String(x===null||x===undefined?'':x).replace(/"/g,'""')+'"';
  return [names.join(',')].concat(rows.map(row=>names.map(name=>quote(row[name])).join(','))).join('\n')+'\n';
}
function janusRiskThrottle_(props) {
  const next = Number(props.getProperty(JANUS_RISK_PILOT.throttleProperty)||0);
  if (next > Date.now()) Utilities.sleep(next - Date.now());
  props.setProperty(JANUS_RISK_PILOT.throttleProperty, String(Date.now() + JANUS_RISK_PILOT.throttleMs));
}
function janusRiskFetch_(props, query) {
  const token = props.getProperty('JANUS_FINMIND_TOKEN');
  const qs = Object.keys(query).map(k=>encodeURIComponent(k)+'='+encodeURIComponent(query[k])).join('&');
  const response = UrlFetchApp.fetch(JANUS_RISK_PILOT.endpoint+'?'+qs, {
    method:'get',followRedirects:false,muteHttpExceptions:true,
    headers: token ? {Authorization:'Bearer '+token} : {}
  });
  if (response.getResponseCode()!==200) throw new Error('FinMind request non-200; safely rerun missing shards');
  const payload=JSON.parse(response.getContentText());
  if (payload.status!==200 || !Array.isArray(payload.data)) throw new Error('invalid FinMind response');
  return payload.data;
}
