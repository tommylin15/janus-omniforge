// Targeted offline contract tests for GAS Loader. No Google API/network needed.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');

const code = fs.readFileSync(__dirname + '/janus_gas_loader.gs', 'utf8');
const folderId = 'CCCCCCCCCCCCCCCCCCCCCCCC';
const sourceId = 'BBBBBBBBBBBBBBBBBBBBBBBB';
const scriptId = 'AAAAAAAAAAAAAAAAAAAAAAAA';
const original = [
  {name:'appsscript', type:'JSON', source:JSON.stringify({timeZone:'Asia/Taipei',runtimeVersion:'V8'})},
  {name:'Code', type:'SERVER_JS', source:'function existing(){return 3;}\n'},
  {name:'Dashboard', type:'HTML', source:'<h1>hello</h1>'}
];
const clone=x=>JSON.parse(JSON.stringify(x));
const hash=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');

function harness(opts={}) {
  const sourceCode=opts.sourceCode ?? 'function janusRiskPilotCollect(){return 42;}\n';
  const cleaned=sourceCode.replace(/^\uFEFF/, '').replace(/\r\n?/g,'\n').replace(/\n*$/, '\n');
  const props=new Map([
    ['JANUS_LOADER_FOLDER_ID',folderId],
    ['JANUS_LOADER_TARGETS_JSON',JSON.stringify([{key:'risk_pilot',sourceFileId:sourceId,scriptId,destinationName:'risk_monthly_pilot',approvedSha256:opts.approvedSha ?? hash(cleaned)}])],
    ['JANUS_LOADER_SELECTED_KEY','risk_pilot']
  ]);
  const io={gets:0, puts:0, versions:0, updates:[],rollbackVerifications:0};
  const state={files:clone(opts.original||original), versions:new Map(), sourceCode, filePrivacy:opts.filePrivacy??'PRIVATE',
    parentId:opts.parentId??folderId, folderPrivacy:opts.folderPrivacy??'PRIVATE', failVerification:opts.failVerification??false};
  const api=(url, request)=>{
    const u=new URL(url);
    const path=u.pathname;
    const method=request.method;
    if(path.endsWith('/content') && method==='get'){
      io.gets++;
      const version=u.searchParams.get('versionNumber');
      const files=version ? state.versions.get(Number(version)) : state.files;
      if(!files) return {getResponseCode:()=>404,getContentText:()=>''};
      // Mimic response with read-only metadata field.
      return {getResponseCode:()=>200,getContentText:()=>JSON.stringify({scriptId,files:clone(files).map(f=>({...f,functionSet:{test:true}}))})};
    }
    if(path.endsWith('/versions') && method==='post'){
      io.versions++;
      state.versions.set(io.versions,clone(state.files));
      return {getResponseCode:()=>200,getContentText:()=>JSON.stringify({versionNumber:io.versions})};
    }
    if(path.endsWith('/content') && method==='put'){
      io.puts++;
      const incoming=JSON.parse(request.payload).files;
      io.updates.push(clone(incoming));
      if(state.failVerification && io.puts===1){
        state.files=clone(incoming);
        state.files.find(f=>f.name==='Dashboard').source='CORRUPTED';
      }else state.files=clone(incoming);
      return {getResponseCode:()=>200,getContentText:()=>JSON.stringify({scriptId,files:clone(state.files)})};
    }
    throw new Error('Unexpected request '+method+' '+url);
  };
  const iterator=v=>({hasNext:()=>true,next:()=>v});
  const sandbox={
    URL,
    LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{}})},
    PropertiesService:{getScriptProperties:()=>({
      getProperty:k=>props.get(k)||null,
      setProperty:(k,v)=>props.set(k,v),
      deleteProperty:k=>props.delete(k)
    })},
    DriveApp:{Access:{PRIVATE:'PRIVATE'},getFolderById:id=>{
      assert.equal(id,folderId);
      return {getName:()=> 'GAS 程式',getSharingAccess:()=>state.folderPrivacy,
        getParents:()=>iterator({getName:()=> 'janusChatGPT'})};
    },getFileById:id=>{
      assert.equal(id,sourceId);
      return {getName:()=> 'risk_monthly_pilot.gs',getSize:()=>state.sourceCode.length,
        getSharingAccess:()=>state.filePrivacy,getParents:()=>iterator({getId:()=>state.parentId}),
        getBlob:()=>({getDataAsString:()=>state.sourceCode})};
    }},
    Utilities:{DigestAlgorithm:{SHA_256:'SHA_256'},Charset:{UTF_8:'UTF_8'},
      computeDigest:(_a,t)=>Array.from(crypto.createHash('sha256').update(t,'utf8').digest()).map(v=>v>127?v-256:v),
      getUuid:()=> '12345678-1234-5678-9000-111122223333'},
    ScriptApp:{getOAuthToken:()=> 'FAKE_TOKEN',getScriptId:()=> opts.loaderScriptId || 'LOADER_SCRIPT_12345678901234567890'},
    UrlFetchApp:{fetch:api}
  };
  vm.createContext(sandbox);
  vm.runInContext(code,sandbox,{filename:'janus_gas_loader.gs'});
  return {sandbox,props,state,io,preview:()=>sandbox.janusGasLoaderPreview(),apply:()=>sandbox.janusGasLoaderApply()};
}

test('loader source parses and has no eval or implicit triggers',()=>{
  assert.doesNotThrow(()=>new vm.Script(code));
  assert.doesNotMatch(code, /\beval\s*\(/);
  assert.doesNotMatch(code, /\bnewTrigger\s*\(/);
});

test('source normalizes UTF-8 BOM/Windows line endings and pins digest',()=>{
  const h=harness({sourceCode:'\uFEFFfunction janusRiskPilotCollect(){return 42;}\r\n\r\n'});
  const result=h.preview();
  assert.equal(result.status,'REVIEW_REQUIRED');
  assert.equal(result.sourceSha256,hash('function janusRiskPilotCollect(){return 42;}\n'));
});

test('SHA mismatch shows observed hash but does not stage update',()=>{
  const h=harness({approvedSha:'f'.repeat(64)});
  assert.equal(h.preview().status,'SOURCE_HASH_NOT_APPROVED');
  assert.equal(h.io.versions,0); assert.equal(h.io.puts,0);
  assert.equal(h.props.has('JANUS_LOADER_PENDING'),false);
});

test('preview/apply preserves all existing project files, manifest and creates version',()=>{
  const h=harness();
  const p=h.preview();
  assert.equal(p.status,'REVIEW_REQUIRED');
  assert.equal(p.change,'ADD_ONE_FILE');
  assert.equal(h.io.puts,0);
  h.props.set('JANUS_LOADER_CONFIRM_CODE',p.confirmationCode);
  const result=h.apply();
  assert.equal(result.status,'SYNCED_VERIFIED');
  assert.equal(result.backupVersion,1);
  assert.equal(result.collectorExecuted,false);
  assert.equal(h.io.puts,1);
  assert.deepEqual(h.state.files.filter(x=>x.name!=='risk_monthly_pilot'),original);
  assert.equal(h.state.files.find(x=>x.name==='risk_monthly_pilot').type,'SERVER_JS');
  assert.equal(h.state.files.find(x=>x.name==='risk_monthly_pilot').source,'function janusRiskPilotCollect(){return 42;}\n');
  assert.equal(h.props.has('JANUS_LOADER_PENDING'),false);
  assert.equal(h.props.has('JANUS_LOADER_CONFIRM_CODE'),false);
  assert.equal(h.preview().status,'NO_CHANGE');
});

test('wrong code refuses remote writes and consumes no version',()=>{
  const h=harness();h.preview();h.props.set('JANUS_LOADER_CONFIRM_CODE','INVALID');
  assert.throws(()=>h.apply(),/incorrect or expired/);
  assert.equal(h.io.puts,0);assert.equal(h.io.versions,0);
});

test('after preview target HEAD change refuses sync',()=>{
  const h=harness();const p=h.preview();
  h.state.files.find(x=>x.name==='Code').source='someone else edited';
  h.props.set('JANUS_LOADER_CONFIRM_CODE',p.confirmationCode);
  assert.throws(()=>h.apply(),/target changed since preview/);
  assert.equal(h.io.puts,0);assert.equal(h.io.versions,0);
});

test('after preview changed Drive code refuses sync',()=>{
  const h=harness();const p=h.preview();h.state.sourceCode='unreviewed()';
  h.props.set('JANUS_LOADER_CONFIRM_CODE',p.confirmationCode);
  assert.throws(()=>h.apply(),/source changed or approval hash/);
  assert.equal(h.io.puts,0);assert.equal(h.io.versions,0);
});

test('suspicious folder permissions or wrong parent are refused',()=>{
  const shared=harness({folderPrivacy:'ANYONE'});
  assert.throws(()=>shared.preview(),/source folder must be private/);
  const wrong=harness({parentId:'INVALID_PARENT'});
  assert.throws(()=>wrong.preview(),/outside approved GAS folder/);
});

test('missing manifest aborts before any PUT',()=>{
  const h=harness({original:[{name:'Code',type:'SERVER_JS',source:'ok'}]});
  assert.throws(()=>h.preview(),/appsscript.json/);
  assert.equal(h.io.puts,0);
});

test('readback mismatch triggers pre-sync version rollback and verification',()=>{
  const h=harness({failVerification:true});const p=h.preview();
  h.props.set('JANUS_LOADER_CONFIRM_CODE',p.confirmationCode);
  assert.throws(()=>h.apply(),/prior version restored and verified/);
  assert.equal(h.io.versions,1);assert.equal(h.io.puts,2);
  assert.deepEqual(h.state.files,original);
});

test('one-time confirmation cannot be replayed',()=>{
  const h=harness();const p=h.preview();
  h.props.set('JANUS_LOADER_CONFIRM_CODE',p.confirmationCode);h.apply();
  h.props.set('JANUS_LOADER_CONFIRM_CODE',p.confirmationCode);
  assert.throws(()=>h.apply(),/no pending preview/);
});
test('target equal to Loader project refuses self-overwrite',()=>{
  const h=harness({loaderScriptId:scriptId});
  assert.throws(()=>h.preview(),/Loader cannot sync itself/);
  assert.equal(h.io.puts,0);
});

test('Apps Script editor wrappers report preview and apply outcomes',()=>{
  const h=harness();
  let printed=[];h.sandbox.console={log:x=>printed.push(x)};
  const p=h.sandbox.janusGasLoaderPreviewFromEditor();
  assert.equal(JSON.parse(printed[0]).confirmationCode,p.confirmationCode);
  h.props.set('JANUS_LOADER_CONFIRM_CODE',p.confirmationCode);
  const out=h.sandbox.janusGasLoaderApplyFromEditor();
  assert.equal(out.status,'SYNCED_VERIFIED');
  assert.equal(JSON.parse(printed[1]).status,'SYNCED_VERIFIED');
});
