from __future__ import annotations

import csv, hashlib, io, json, os, re, tempfile, zipfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from google.cloud import storage

CURRENT = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
NEW = "https://openapi.twse.com.tw/v1/company/newlisting"
DELIST = "https://openapi.twse.com.tw/v1/company/suspendListingCsvAndHtml"
MI = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
UA = "janus-research-cloud-cohort-500/1.1 (+research-only)"


def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def sha(b: bytes): return hashlib.sha256(b).hexdigest()
def file_sha(p: Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def d(v: Any) -> date | None:
    if v is None: return None
    s = str(v).strip().replace("年", "/").replace("月", "/").replace("日", "").replace(".", "/").replace("-", "/")
    if not s or s.lower() in {"nan", "nat", "none"}: return None
    try:
        p = [x for x in s.split("/") if x]
        if len(p) == 3:
            y,m,dd = map(int,p); y = y + 1911 if y < 1911 else y
            return date(y,m,dd)
        x = re.sub(r"\D", "", s)
        if len(x) == 8 and int(x[:4]) >= 1900: return date(int(x[:4]),int(x[4:6]),int(x[6:8]))
        if len(x) == 7: return date(int(x[:3])+1911,int(x[3:5]),int(x[5:7]))
    except ValueError: pass
    return None

def b(v: Any): return str(v).strip().lower() in {"1","true","yes","y"}
def iso(v: date | None): return v.isoformat() if v else ""

def get(url: str):
    r = requests.get(url, timeout=60, headers={"User-Agent":UA,"Accept":"application/json"})
    r.raise_for_status(); raw = r.content
    return r.json(), raw, {"url":url,"fetched_at":now(),"size_bytes":len(raw),"sha256":sha(raw)}

def current(rows):
    out={}
    for r in rows:
        sid=str(r.get("公司代號",r.get("Code",""))).strip()
        if re.fullmatch(r"\d{4}",sid): out[sid]={"start":d(r.get("上市日期",r.get("ListingDate"))),"name":str(r.get("公司簡稱",r.get("Company",""))).strip()}
    return out

def new(rows):
    out={}
    for r in rows:
        sid=str(r.get("Code","")).strip()
        if re.fullmatch(r"\d{4}",sid): out[sid]={"start":d(r.get("ApprovedListingDate")) or d(r.get("ListingDate")),"note":str(r.get("Note","")).strip()}
    return out

def delist(rows):
    out={}
    for r in rows:
        sid=str(r.get("Code","")).strip(); x=d(r.get("DelistingDate"))
        if re.fullmatch(r"\d{4}",sid) and x: out[sid]=x
    return out

def mi_members(j):
    if str(j.get("stat","")).upper() != "OK": raise RuntimeError(f"MI_INDEX stat={j.get('stat')!r}")
    for t in j.get("tables",[]):
        f=[str(x).strip() for x in t.get("fields",[])]
        if "證券代號" in f and any(x in f for x in ("成交股數","收盤價","證券名稱")):
            k=f.index("證券代號"); s={str(r[k]).strip() for r in t.get("data",[]) if len(r)>k and re.fullmatch(r"\d{4}",str(r[k]).strip())}
            if s: return s
    raise RuntimeError("MI_INDEX securities table missing")

def calendar(z, base, start, end):
    for name in (base+"metadata/taiwan_stock_trading_date.parquet", base+"benchmark/taiex_total_return_index.parquet"):
        if name not in z.namelist(): continue
        try:
            q=pd.read_parquet(io.BytesIO(z.read(name)))
            c=next((x for x in ("date","trade_date","trading_date","Date") if x in q.columns),None) or next(x for x in q.columns if "date" in x.lower())
            vals=sorted({x for x in (d(v) for v in q[c]) if x and start<=x<=end})
            if len(vals)>=100: return vals,{"artifact":name,"date_column":c,"rows":len(q),"unique_dates":len(vals)}
        except Exception: pass
    raise RuntimeError("materialized trading calendar unreadable")

def usable(z, base, sid, start, end):
    n=base+f"ohlcv/symbol={sid}.parquet"
    if n not in z.namelist(): return 0,0,0,True
    q=pd.read_parquet(io.BytesIO(z.read(n)),columns=["trade_date","open","high","low","close"])
    q["trade_date"]=pd.to_datetime(q["trade_date"],errors="coerce").dt.date
    q=q[(q.trade_date>=start)&(q.trade_date<end)].copy()
    dup=q.duplicated("trade_date",keep=False); dupn=int(q.loc[dup,"trade_date"].nunique()); q=q[~dup]
    for c in ["open","high","low","close"]: q[c]=pd.to_numeric(q[c],errors="coerce")
    good=q[["open","high","low","close"]].notna().all(axis=1)&(q[["open","high","low","close"]]>0).all(axis=1)&(q.high>=q[["open","low","close"]].max(axis=1))&(q.low<=q[["open","high","close"]].min(axis=1))
    return int(good.sum()),dupn,int((~good).sum()),False

def csv_bytes(rows, fields):
    s=io.StringIO(newline=""); w=csv.DictWriter(s,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows); return s.getvalue().encode("utf-8-sig")

def run(request: dict[str,Any], bucket: str, prefix: str, run_id: str):
    start=d(request.get("research_start")) or date(2015,1,1); end=d(request.get("research_end")) or date(2026,9,16)
    mincov=float(request.get("usable_ohlcv_coverage_min",.9)); target=int(request.get("cohort_size",500)); rev=str(request.get("materialized_revision","20260917T025906Z"))
    obj=str(request.get("source_gcs_object","")).strip(); expected_sha=str(request.get("source_sha256","")).lower(); expected_size=int(request.get("source_size_bytes",0))
    if not obj or not re.fullmatch(r"[0-9a-f]{64}",expected_sha) or expected_size<=0: raise RuntimeError("immutable source identity missing")
    client=storage.Client(); buck=client.bucket(bucket); root=f"{prefix}/revisions/{run_id}"; base=f"janus_step2a_materialized/{rev}/"
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"source.zip"; buck.blob(obj).download_to_filename(p)
        if p.stat().st_size!=expected_size or file_sha(p)!=expected_sha: raise RuntimeError("staged source identity mismatch")
        with zipfile.ZipFile(p) as z:
            cal,calmeta=calendar(z,base,start,end); first=cal[0]
            sources=[]
            C,cr,cm=get(CURRENT); sources.append(("twse_current_basic",cr,cm))
            N,nr,nm=get(NEW); sources.append(("twse_newlisting",nr,nm))
            D,dr,dm=get(DELIST); sources.append(("twse_delisting",dr,dm))
            miurl=MI+"?response=json&date="+first.strftime("%Y%m%d")+"&type=ALL"; M,mr,mm=get(miurl); sources.append(("twse_research_start_membership",mr,mm))
            C,N,D,M=current(C),new(N),delist(D),mi_members(M)
            master=pd.read_csv(io.BytesIO(z.read(base+"metadata/symbol_master.csv")),dtype=str).fillna("")
            cand=master[master.stock_id.str.fullmatch(r"\d{4}") & master.fetch_candidate.map(b) & ~master.known_non_common.map(b) & master.market_hints.str.lower().str.split("|").map(lambda x:"twse" in x)].to_dict("records")
            life=[]; resolved={}
            for r in cand:
                sid=r["stock_id"]; a=C.get(sid,{}).get("start"); n=N.get(sid,{}).get("start"); e=D.get(sid); active=sid in C; at_start=sid in M; conflict=[]
                if a and n and a!=n: conflict.append(f"listing_date_conflict:{a}:{n}")
                official=a or n
                if active and e: conflict.append("active_and_delisted_conflict")
                if official and e and official>=e: conflict.append("start_not_before_end")
                eff=None; status="unresolved"; reason=""
                if conflict: status="conflict"; reason="|".join(conflict)
                elif e and e<=start: status="out_of_window"; reason="delisted_on_or_before_research_start"
                else:
                    eff=max(start,official) if official else (start if at_start else None)
                    if not eff: reason="no_official_twse_start_evidence"
                    elif e is None and not active: reason="no_official_active_or_delisting_end_evidence"
                    elif e and eff>=e: status="out_of_window"; reason="effective_start_not_before_end"
                    else: status="resolved"
                ev=[]
                if a: ev.append("twse_current_basic_listing_date")
                if n: ev.append("twse_newlisting_listing_date")
                if at_start: ev.append(f"twse_mi_index_membership_{first}")
                if e: ev.append("twse_delisting_date")
                if active: ev.append("twse_current_basic_active")
                x={"stock_id":sid,"stock_name":r.get("stock_name",""),"market":"TWSE","security_type":"common_equity","effective_start":iso(eff),"effective_end_exclusive":iso(e),"lifecycle_status":status,"reason":reason,"official_listing_date":iso(official),"official_delisting_date":iso(e),"research_start_membership":at_start,"active_current_basic":active,"market_transition":"tpex_to_twse" if "櫃轉市" in N.get(sid,{}).get("note","") else "","evidence":"|".join(ev)}
                life.append(x)
                if status=="resolved": resolved[sid]=x
            rows=[]; endx=end+timedelta(days=1)
            for sid,x in sorted(resolved.items()):
                s=d(x["effective_start"]); ex=min(d(x["effective_end_exclusive"]) or endx,endx)
                exp=sum(s<=v<ex for v in cal); u,dups,inv,missing=usable(z,base,sid,s,ex); cov=u/exp if exp else 0
                rows.append({"stock_id":sid,"stock_name":x["stock_name"],"effective_start":x["effective_start"],"effective_end_exclusive":x["effective_end_exclusive"],"expected_trading_days":exp,"usable_ohlcv_days":u,"coverage":cov,"duplicate_dates":dups,"invalid_ohlc_days":inv,"missing_price_file":missing,"qualified":cov>=mincov and not missing,"selected":False,"rank_rule":"qualified_then_stock_id_ascending"})
            qual=sorted([r for r in rows if r["qualified"]],key=lambda r:int(r["stock_id"])); chosen={r["stock_id"] for r in qual[:target]}
            for r in rows: r["selected"]=r["stock_id"] in chosen
            if len(chosen)<target: raise RuntimeError(f"cohort gate failed: qualified={len(chosen)} need={target}")
            lf=["stock_id","stock_name","market","security_type","effective_start","effective_end_exclusive","lifecycle_status","reason","official_listing_date","official_delisting_date","research_start_membership","active_current_basic","market_transition","evidence"]
            cf=["stock_id","stock_name","effective_start","effective_end_exclusive","expected_trading_days","usable_ohlcv_days","coverage","duplicate_dates","invalid_ohlc_days","missing_price_file","qualified","selected","rank_rule"]
            counts=Counter(x["lifecycle_status"] for x in life); summary={"schema_version":"janus.research.cloud-cohort-500.cohort-build.v1","status":"ok","run_id":run_id,"generated_at":now(),"research_period":{"start":iso(start),"end":iso(end)},"source":{"gcs_object":obj,"sha256":expected_sha,"size_bytes":expected_size,"materialized_revision":rev},"calendar":calmeta|{"first_trade_date":iso(first),"last_trade_date":iso(cal[-1])},"candidate_rule":"Step2A fetch_candidate=true, known_non_common=false, 4-digit numeric, market_hints contains twse; official TWSE evidence governs lifecycle","lifecycle":{"candidate_symbols":len(cand),"status_counts":dict(counts),"research_start_membership_count":len(M),"current_basic_count":len(C),"newlisting_count":len(N),"delisting_count":len(D),"conflict_count":counts.get("conflict",0)},"cohort":{"coverage_min":mincov,"qualified_symbols":len(qual),"selected_symbols":len(chosen),"selection_rule":"qualified then ascending numeric stock_id; independent of MFE/outcomes","selected_stock_ids":sorted(chosen,key=int)},"isolation":{"postgresql_used":False,"database_used":False,"existing_janus_iceberg_catalog_used":False,"janus_core_written":False,"janus_mart_written":False,"janus_private_mart_written":False,"runtime_secret_used":False,"official_public_twse_http_used":True},"official_sources":{n:m for n,_,m in sources},"next_gate":"preflight_dq_then_mfe20_mfe60"}
            outputs=[(f"{root}/lifecycle/twse_pit_lifecycle.csv",csv_bytes(life,lf),"text/csv"),(f"{root}/cohort/cohort_manifest.csv",csv_bytes(sorted(rows,key=lambda r:int(r['stock_id'])),cf),"text/csv"),(f"{root}/cohort/cohort_build_result.json",(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode(),"application/json")]
            for o,body,ct in outputs: buck.blob(o).upload_from_string(body,content_type=ct)
            for n,raw,m in sources: buck.blob(f"{root}/lifecycle/raw/{n}-{m['sha256']}.json").upload_from_string(raw,content_type="application/json")
            return summary


def self_test():
    assert d("115/09/22")==date(2026,9,22) and d("1150922")==date(2026,9,22) and d("20260922")==date(2026,9,22)
    assert current([{"公司代號":"2330","上市日期":"0830905"}])["2330"]["start"]==date(1994,9,5)
    assert new([{"Code":"5236","ApprovedListingDate":"1150716"}])["5236"]["start"]==date(2026,7,16)
    assert delist([{"Code":"2867","DelistingDate":"115/09/01"}])["2867"]==date(2026,9,1)
    assert mi_members({"stat":"OK","tables":[{"fields":["證券代號","成交股數"],"data":[["1101","1"],["2330","1"]]}]})=={"1101","2330"}
