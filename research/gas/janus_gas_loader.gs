/**
 * Janus GAS Loader v1 — manually authorized Drive -> Apps Script project sync.
 *
 * Script Properties (only in this standalone Loader project):
 * JANUS_LOADER_FOLDER_ID: Drive folder ID of private janusChatGPT/GAS 程式
 * JANUS_LOADER_TARGETS_JSON: JSON array of approved {key,sourceFileId,scriptId,
 *   destinationName,approvedSha256} entries (sha256 of normalized UTF-8 code).
 * JANUS_LOADER_SELECTED_KEY: target key selected for this manual operation.
 * JANUS_LOADER_CONFIRM_CODE: paste the one-time code from Preview, then Apply.
 *
 * No dynamic-code evaluation, auto-triggers, collector execution, or default deployment.
 * Target Apps Script API overwrites the whole project: ALL untouched files and
 * appsscript.json are round-tripped, never reconstructed from just the .gs file.
 */
const JANUS_GAS_LOADER = Object.freeze({
  baseUrl: 'https://script.googleapis.com/v1/projects/',
  pendingKey: 'JANUS_LOADER_PENDING',
  confirmKey: 'JANUS_LOADER_CONFIRM_CODE',
  pendingMillis: 10 * 60 * 1000,
  maxSourceBytes: 64 * 1024,
  maxProjectFiles: 150
});

/** Choose JANUS_LOADER_SELECTED_KEY in Script Properties, then run from editor. */
function janusGasLoaderPreview() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) throw new Error('another loader operation is in progress');
  try {
    const props = PropertiesService.getScriptProperties();
    props.deleteProperty(JANUS_GAS_LOADER.pendingKey);
    props.deleteProperty(JANUS_GAS_LOADER.confirmKey);
    const target = janusLoaderTarget_(props);
    const source = janusLoaderSource_(props, target);
    if (source.sha256 !== target.approvedSha256) {
      return {status: 'SOURCE_HASH_NOT_APPROVED', key: target.key,
        observedSha256: source.sha256, approvedSha256: target.approvedSha256,
        message: 'Review Drive source against trusted GitHub, then update approvedSha256'};
    }
    const head = janusLoaderGetContent_(target.scriptId);
    const proposed = janusLoaderProposed_(head.files, target.destinationName, source.content);
    const beforeHash = janusLoaderProjectHash_(head.files);
    const afterHash = janusLoaderProjectHash_(proposed);
    const current = head.files.find(f => f.name === target.destinationName);
    if (beforeHash === afterHash) return {status: 'NO_CHANGE', key: target.key,
      sourceSha256: source.sha256, destination: target.destinationName,
      targetScriptId: target.scriptId};
    const confirmationCode = Utilities.getUuid().replace(/-/g, '').slice(0, 12).toUpperCase();
    props.setProperty(JANUS_GAS_LOADER.pendingKey, JSON.stringify({
      key: target.key, scriptId: target.scriptId, sourceFileId: target.sourceFileId,
      destinationName: target.destinationName, sourceSha256: source.sha256,
      beforeHash: beforeHash, afterHash: afterHash,
      confirmationCode: confirmationCode,
      expiresAt: Date.now() + JANUS_GAS_LOADER.pendingMillis
    }));
    return {status: 'REVIEW_REQUIRED', key: target.key,
      change: current ? 'UPDATE_ONE_FILE' : 'ADD_ONE_FILE',
      targetScriptId: target.scriptId, destination: target.destinationName,
      sourceSha256: source.sha256,
      existingFileCount: head.files.length, proposedFileCount: proposed.length,
      unchangedFileCount: head.files.length - (current ? 1 : 0),
      confirmationCode: confirmationCode, validForMinutes: 10,
      message: 'Manually set JANUS_LOADER_CONFIRM_CODE and run janusGasLoaderApply()'};
  } finally { lock.releaseLock(); }
}

/** Requires manual one-time code from Preview, pinned SHA, and unchanged HEAD. */
function janusGasLoaderApply() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) throw new Error('another loader operation is in progress');
  try {
    const props = PropertiesService.getScriptProperties();
    const raw = props.getProperty(JANUS_GAS_LOADER.pendingKey);
    const submitted = props.getProperty(JANUS_GAS_LOADER.confirmKey) || '';
    if (!raw) throw new Error('no pending preview; run Preview first');
    const pending = JSON.parse(raw);
    if (Date.now() > pending.expiresAt || !submitted ||
        submitted !== pending.confirmationCode) {
      throw new Error('confirmation code missing, incorrect or expired');
    }
    // Consume before ANY remote write, so retries require new Preview.
    props.deleteProperty(JANUS_GAS_LOADER.pendingKey);
    props.deleteProperty(JANUS_GAS_LOADER.confirmKey);
    const target = janusLoaderTarget_(props);
    if (target.key !== pending.key || target.scriptId !== pending.scriptId ||
        target.sourceFileId !== pending.sourceFileId ||
        target.destinationName !== pending.destinationName) {
      throw new Error('target configuration changed; preview again');
    }
    const source = janusLoaderSource_(props, target);
    if (source.sha256 !== target.approvedSha256 || source.sha256 !== pending.sourceSha256) {
      throw new Error('source changed or approval hash mismatched; preview again');
    }
    const head = janusLoaderGetContent_(target.scriptId);
    if (janusLoaderProjectHash_(head.files) !== pending.beforeHash) {
      throw new Error('target changed since preview; preview again');
    }
    const proposed = janusLoaderProposed_(head.files, target.destinationName, source.content);
    if (janusLoaderProjectHash_(proposed) !== pending.afterHash) {
      throw new Error('proposed project changed since preview');
    }
    // Immutable HEAD snapshot is required before any potentially destructive PUT.
    const backup = janusLoaderApi_('post', target.scriptId + '/versions', {
      description: 'Janus Loader pre-sync ' + target.key + ' ' + source.sha256.slice(0, 12)
    });
    if (!Number.isInteger(backup.versionNumber) || backup.versionNumber < 1) {
      throw new Error('backup version was not confirmed; update cancelled');
    }
    const versionHash = janusLoaderProjectHash_(
      janusLoaderGetContent_(target.scriptId, backup.versionNumber).files);
    if (versionHash !== pending.beforeHash) {
      throw new Error('backup version differs from preview; update cancelled');
    }
    if (janusLoaderProjectHash_(janusLoaderGetContent_(target.scriptId).files) !== pending.beforeHash) {
      throw new Error('target changed before update; update cancelled');
    }
    try {
      janusLoaderApi_('put', target.scriptId + '/content', {files: proposed});
      const verified = janusLoaderGetContent_(target.scriptId);
      if (janusLoaderProjectHash_(verified.files) !== pending.afterHash) {
        throw new Error('post-sync HEAD verification failed');
      }
      return {status: 'SYNCED_VERIFIED', key: target.key,
        targetScriptId: target.scriptId, destination: target.destinationName,
        sourceSha256: source.sha256, backupVersion: backup.versionNumber,
        fileCount: verified.files.length, collectorExecuted: false};
    } catch (failure) {
      // Recover only our known immutable version; never restore unknown content.
      let recovered = false;
      try {
        const oldFiles = janusLoaderFiles_(janusLoaderGetContent_(target.scriptId, backup.versionNumber).files);
        if (janusLoaderProjectHash_(oldFiles) !== pending.beforeHash) {
          throw new Error('snapshot hash differs');
        }
        janusLoaderApi_('put', target.scriptId + '/content', {files: oldFiles});
        recovered = janusLoaderProjectHash_(janusLoaderGetContent_(target.scriptId).files) === pending.beforeHash;
      } catch (_rollbackFailure) { recovered = false; }
      throw new Error(recovered ? 'sync failed; prior version restored and verified' :
        'sync failed; rollback NOT VERIFIED — inspect target and saved version ' + backup.versionNumber);
    }
  } finally { lock.releaseLock(); }
}

function janusLoaderTarget_(props) {
  let targets;
  try { targets = JSON.parse(props.getProperty('JANUS_LOADER_TARGETS_JSON') || 'null'); }
  catch (_e) { throw new Error('invalid targets JSON'); }
  if (!Array.isArray(targets) || !targets.length || targets.length > 20) {
    throw new Error('targets must be a nonempty JSON array of <=20 entries');
  }
  const keys = targets.map(t => t && t.key);
  if (keys.length !== new Set(keys).size) throw new Error('duplicate target keys');
  const selected = props.getProperty('JANUS_LOADER_SELECTED_KEY') || '';
  const t = targets.find(x => x && x.key === selected);
  if (!t || !/^[a-z][a-z0-9_-]{1,40}$/.test(t.key) ||
      !/^[A-Za-z0-9_-]{15,}$/.test(t.sourceFileId || '') ||
      !/^[A-Za-z0-9_-]{15,}$/.test(t.scriptId || '') ||
      !/^[A-Za-z][A-Za-z0-9_]{0,80}$/.test(t.destinationName || '') ||
      t.destinationName === 'appsscript' ||
      !/^[a-f0-9]{64}$/.test(t.approvedSha256 || '')) {
    throw new Error('selected target is missing or has unsafe configuration');
  }
  return t;
}

function janusLoaderSource_(props, target) {
  const folderId = props.getProperty('JANUS_LOADER_FOLDER_ID');
  if (!/^[A-Za-z0-9_-]{15,}$/.test(folderId || '')) throw new Error('invalid source folder ID');
  const folder = DriveApp.getFolderById(folderId);
  if (folder.getName() !== 'GAS 程式' || folder.getSharingAccess() !== DriveApp.Access.PRIVATE) {
    throw new Error('source folder must be private GAS 程式');
  }
  const parents = folder.getParents();
  if (!parents.hasNext() || parents.next().getName() !== 'janusChatGPT') {
    throw new Error('source folder must be directly inside janusChatGPT');
  }
  const file = DriveApp.getFileById(target.sourceFileId);
  if (file.getName() !== target.destinationName + '.gs' || file.getSize() > JANUS_GAS_LOADER.maxSourceBytes ||
      file.getSize() <= 0 || file.getSharingAccess() !== DriveApp.Access.PRIVATE) {
    throw new Error('source filename, size or privacy validation failed');
  }
  const fileParents = file.getParents();
  if (!fileParents.hasNext() || fileParents.next().getId() !== folderId) {
    throw new Error('source file is outside approved GAS folder');
  }
  const content = janusLoaderNormalize_(file.getBlob().getDataAsString('UTF-8'));
  if (content.length === 0 || content.length > JANUS_GAS_LOADER.maxSourceBytes) {
    throw new Error('source content size invalid');
  }
  return {content: content, sha256: janusLoaderSha_(content)};
}

function janusLoaderNormalize_(source) {
  return String(source).replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').replace(/\n*$/, '\n');
}

function janusLoaderSha_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8)
    .map(b => ('0' + ((b + 256) % 256).toString(16)).slice(-2)).join('');
}

function janusLoaderFiles_(files) {
  if (!Array.isArray(files) || files.length < 1 || files.length > JANUS_GAS_LOADER.maxProjectFiles) {
    throw new Error('unexpected project file count');
  }
  const out = files.map(f => {
    if (!f || !/^[A-Za-z][A-Za-z0-9_]*$/.test(f.name || '') ||
        !['SERVER_JS', 'HTML', 'JSON'].includes(f.type) || typeof f.source !== 'string') {
      throw new Error('unsupported or malformed project file');
    }
    return {name:f.name, type:f.type, source:f.source};
  });
  if (new Set(out.map(f=>f.name)).size !== out.length ||
      out.filter(f=>f.name==='appsscript' && f.type==='JSON').length !== 1) {
    throw new Error('duplicate names or missing appsscript.json');
  }
  return out;
}

function janusLoaderProposed_(files, destinationName, content) {
  const before = janusLoaderFiles_(files);
  const old = before.find(f=>f.name===destinationName);
  if (old && old.type !== 'SERVER_JS') throw new Error('destination exists with another type');
  return old ? before.map(f=>f.name===destinationName ? {name:destinationName,type:'SERVER_JS',source:content} : f) :
    before.concat([{name:destinationName,type:'SERVER_JS',source:content}]);
}

function janusLoaderProjectHash_(files) {
  // Order-independent; unchanged contents and manifest must be round-tripped exactly.
  const normalized = janusLoaderFiles_(files).sort((a,b)=>a.name.localeCompare(b.name));
  return janusLoaderSha_(JSON.stringify(normalized));
}

function janusLoaderGetContent_(scriptId, versionNumber) {
  const suffix = versionNumber ? ('?versionNumber=' + versionNumber) : '';
  const response = janusLoaderApi_('get', scriptId + '/content' + suffix);
  janusLoaderFiles_(response.files);
  if (response.scriptId && response.scriptId !== scriptId) throw new Error('project identity mismatch');
  return response;
}

function janusLoaderApi_(method, path, payload) {
  const options = {method:method, muteHttpExceptions:true, followRedirects:false,
    headers:{Authorization:'Bearer ' + ScriptApp.getOAuthToken()}};
  if (payload !== undefined) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(payload);
  }
  const resp = UrlFetchApp.fetch(JANUS_GAS_LOADER.baseUrl + path, options);
  const http = resp.getResponseCode();
  if (http < 200 || http >= 300) {
    // Never print response body or bearer credentials into Apps Script logs.
    throw new Error('Apps Script API ' + method.toUpperCase() + ' failed, HTTP ' + http);
  }
  let parsed;
  try { parsed = JSON.parse(resp.getContentText()); }
  catch (_e) { throw new Error('Apps Script API response JSON invalid'); }
  return parsed;
}