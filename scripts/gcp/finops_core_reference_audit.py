"""Read-only bounded registry reconnaissance for Core execution-manifest retention.

This NEVER publishes a deletion fence: a GCS scan alone cannot certify all
PostgreSQL publication or ad-hoc model/research references.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
from pathlib import Path
import json
import re
import subprocess
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

PROJECT = "gen-lang-client-0593591102"
CORE = PROJECT + "-dev-core"
MART = PROJECT + "-dev-mart"
RESEARCH = PROJECT + "-dev-research-big-move-500"
PRIVATE = PROJECT + "-dev-private"
HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
LIMIT_PAGES = 25
LIMIT_DOCS = 3000
# Measured research JSON alone is 97,381,536 bytes; keep one complete pass bounded.
LIMIT_BYTES = 128 * 1024 * 1024

def access_token():
    return subprocess.check_output(["gcloud","auth","print-access-token"],
                                   text=True,stderr=subprocess.DEVNULL,timeout=30).strip()

def get_json(url, token, max_bytes=3 * 1024 * 1024):
    req=Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json"})
    with urlopen(req,timeout=35) as response:
        data=response.read(max_bytes+1)
    if len(data)>max_bytes:
        raise RuntimeError("GCS_METADATA_DOCUMENT_OVERSIZE")
    return json.loads(data)

def objects(bucket,token):
    base="https://storage.googleapis.com/storage/v1/b/"+quote(bucket,safe="")+"/o"
    token_page=""
    found=[]
    pages=0
    for _ in range(LIMIT_PAGES):
        params={"maxResults":"1000","fields":"items(name,size,updated,generation),nextPageToken"}
        if token_page: params["pageToken"]=token_page
        result=get_json(base+"?"+urlencode(params),token)
        found.extend(result.get("items",[]))
        pages+=1
        token_page=result.get("nextPageToken","")
        if not token_page:
            return found, pages
    raise RuntimeError("GCS_REFERENCE_INVENTORY_PAGINATION_TRUNCATED")

def read_doc(bucket,name,token, *, generation, max_bytes):
    url=("https://storage.googleapis.com/storage/v1/b/"+quote(bucket,safe="")+
         "/o/"+quote(name,safe="")+"?"+urlencode({"alt":"media","generation":generation}))
    return get_json(url,token,max_bytes=max_bytes)

def references(document):
    """Only accept known Core *identity* keys; ignore arbitrary artifact hashes."""
    refs=set()
    def visit(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key in ("core_snapshot_id","core_snapshot_ids","source_core_snapshot_id"):
                    values=child if isinstance(child,list) else [child]
                    for candidate in values:
                        if isinstance(candidate,str) and HASH.fullmatch(candidate):
                            refs.add(candidate)
                        elif candidate is not None:
                            raise ValueError("INVALID_CORE_REFERENCE_CONTRACT")
                else:
                    visit(child)
        elif isinstance(value,list):
            for v in value: visit(v)
    visit(document)
    return refs

def relevant_mart(name):
    return (name.endswith(("/specialist-manifest.json","/screening-manifest.json",
                            "/monthly-reconciliation.json","/oos-evaluation.json"))
            or name.startswith("maintenance/specialists/retained-") and name.endswith(".json")
            or name.startswith("ml-oos-data/") and name.endswith("/manifest.json")
            or name.startswith("acceptance/") and name.endswith(".json"))

def audit(token):
    listings={}
    pages={}
    for label,bucket in (("core",CORE),("mart",MART),("research",RESEARCH),("private",PRIVATE)):
        entries,p=objects(bucket,token)
        listings[label]=entries
        pages[label]=p
    cores=[o for o in listings["core"] if o["name"].startswith("executions/")
           and o["name"].endswith("/core-snapshot.json")]
    indexed={}
    read=0
    total_bytes=0
    for item in cores:
        if read>=LIMIT_DOCS: raise RuntimeError("CORE_DOCUMENT_SCAN_LIMIT")
        size=int(item["size"])
        if size > LIMIT_BYTES-total_bytes: raise RuntimeError("REFERENCE_DOCUMENT_BYTE_BUDGET_EXCEEDED")
        doc=read_doc(CORE,item["name"],token,generation=item["generation"],max_bytes=size)
        read+=1
        total_bytes+=int(item.get("size") or 0)
        if not isinstance(doc,dict) or not isinstance(doc.get("snapshot_id"),str) or not HASH.fullmatch(doc["snapshot_id"]):
            raise ValueError("INVALID_CORE_EXECUTION_IDENTITY")
        if item["name"] != "executions/"+str(doc.get("execution_id"))+"/core-snapshot.json":
            raise ValueError("CORE_EXECUTION_MANIFEST_PATH_MISMATCH")
        indexed[item["name"]]=(doc["snapshot_id"],item["updated"])
    protected=set()
    source_counts={}
    provenance={}
    for label,bucket,predicate in (
        ("mart",MART,relevant_mart),
        ("research",RESEARCH,lambda name:name.endswith(".json")),
        ("private",PRIVATE,lambda name:name.endswith(".json"))):
        matched=[x for x in listings[label] if predicate(x["name"])]
        if len(matched)+read>LIMIT_DOCS:
            raise RuntimeError("EXTERNAL_REFERENCE_SCAN_LIMIT")
        count=0
        skipped_oversized=0
        unavailable=0
        for obj in matched:
            size=int(obj.get("size") or 0)
            # Read large JSON within the existing total budget. Never turn a
            # budget omission into evidence that a document has no references.
            if size > LIMIT_BYTES-total_bytes:
                skipped_oversized+=1
                continue
            total_bytes+=size
            if total_bytes>LIMIT_BYTES: raise RuntimeError("REFERENCE_DOCUMENT_BYTE_BUDGET_EXCEEDED")
            try:
                doc=read_doc(bucket,obj["name"],token,generation=obj["generation"],max_bytes=size)
            except HTTPError:
                unavailable+=1
                continue
            refs=references(doc)
            protected.update(refs)
            for core_id in refs:
                provenance.setdefault(core_id,[]).append({
                    "bucket":bucket,"path_sha256":"sha256:"+sha256(obj["name"].encode()).hexdigest(),
                    "generation":obj.get("generation"),
                    "updated":obj.get("updated")})
            count+=1
            read+=1
        source_counts[label]={"documents_checked":count,
                              "documents_skipped_oversized":skipped_oversized,
                              "documents_unavailable":unavailable,
                              "matched_bytes":sum(int(x["size"]) for x in matched),
                              "largest_document_bytes":max((int(x["size"]) for x in matched),default=0),
                              "listed_objects":len(listings[label])}
    # JSON references alone cannot certify private Parquet/model schemas,
    # PostgreSQL publication or external research; this remains a candidate.
    known={identity for identity,_ in indexed.values()}
    cutoff=(datetime.now(timezone.utc)-timedelta(days=90))
    mature=[name for name,(identity,updated) in indexed.items()
            if datetime.fromisoformat(updated.replace("Z","+00:00"))<cutoff]
    unreferenced_mature=sum(indexed[name][0] not in protected for name in mature)
    return {"_candidate_reference_provenance":provenance,
            "component":"core-reference-discovery","status":"PARTIAL_REFERENCE_COVERAGE",
            "mode":"read-only","gcp_writes":0,"deletion_fence_published":False,
            "object_inventory_counts":{k:len(v) for k,v in listings.items()},
            "pages":pages,"core_manifest_count":len(indexed),
            "mature_90_day_core_manifests":len(mature),
            "externally_referenced_core_identities":len(protected),
            "external_references_not_in_current_core_manifest_inventory":len(protected-known),
            "mature_manifest_candidate_upper_bound":unreferenced_mature,
            "model_research_sources":source_counts,
            "private_json_payloads_scanned":source_counts["private"]["documents_checked"],
            "private_reference_completeness":"NOT_PROVEN",
            "postgres_publication_index_scanned":False,
            "research_json_coverage":"COMPLETE" if not (
                source_counts["research"]["documents_skipped_oversized"] or source_counts["research"]["documents_unavailable"]) else "INCOMPLETE",
            "research_reference_completeness":"NOT_PROVEN",
            "reason":"PostgreSQL publication and owner-private or external model references not independently inventoried; do not configure deletion fence or delete historical manifests"}

if __name__ == "__main__":
    result=audit(access_token())
    sources=result.pop("_candidate_reference_provenance")
    location=os.environ.get("FINOPS_REFERENCE_CANDIDATE_PATH","")
    if location:
        document={"schema_version":"finops-core-reference-candidates-v1",
                  "coverage_status":"PARTIAL_NOT_AUTHORIZED_FOR_DELETION",
                  "protected_core_snapshot_ids":sorted(sources),
                  "source_provenance":sources,
                  "audit_summary":result}
        payload=json.dumps(document,sort_keys=True,indent=2).encode()
        path=Path(location)
        path.write_bytes(payload)
        result["candidate_artifact_sha256"]="sha256:"+sha256(payload).hexdigest()
    print(json.dumps(result,sort_keys=True))
