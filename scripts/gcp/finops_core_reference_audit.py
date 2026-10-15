"""Read-only bounded registry reconnaissance for Core execution-manifest retention.

This NEVER publishes a deletion fence: a GCS scan alone cannot certify all
PostgreSQL publication or ad-hoc model/research references.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
import re
import subprocess
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

PROJECT = "gen-lang-client-0593591102"
CORE = PROJECT + "-dev-core"
MART = PROJECT + "-dev-mart"
RESEARCH = PROJECT + "-dev-research-big-move-500"
PRIVATE = PROJECT + "-dev-private"
HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
LIMIT_PAGES = 25
LIMIT_DOCS = 3000
LIMIT_BYTES = 60 * 1024 * 1024

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

def read_doc(bucket,name,token):
    url=("https://storage.googleapis.com/storage/v1/b/"+quote(bucket,safe="")+
         "/o/"+quote(name,safe="")+"?alt=media")
    return get_json(url,token)

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
        doc=read_doc(CORE,item["name"],token)
        read+=1
        total_bytes+=int(item.get("size") or 0)
        if not isinstance(doc,dict) or not isinstance(doc.get("snapshot_id"),str) or not HASH.fullmatch(doc["snapshot_id"]):
            raise ValueError("INVALID_CORE_EXECUTION_IDENTITY")
        if item["name"] != "executions/"+str(doc.get("execution_id"))+"/core-snapshot.json":
            raise ValueError("CORE_EXECUTION_MANIFEST_PATH_MISMATCH")
        indexed[item["name"]]=(doc["snapshot_id"],item["updated"])
    protected=set()
    source_counts={}
    for label,bucket,predicate in (
        ("mart",MART,relevant_mart),
        ("research",RESEARCH,lambda name:name.endswith(".json"))):
        matched=[x for x in listings[label] if predicate(x["name"])]
        if len(matched)+read>LIMIT_DOCS:
            raise RuntimeError("EXTERNAL_REFERENCE_SCAN_LIMIT")
        count=0
        for obj in matched:
            total_bytes+=int(obj.get("size") or 0)
            if total_bytes>LIMIT_BYTES: raise RuntimeError("REFERENCE_DOCUMENT_BYTE_BUDGET_EXCEEDED")
            doc=read_doc(bucket,obj["name"],token)
            protected.update(references(doc))
            count+=1
            read+=1
        source_counts[label]={"documents_checked":count,"listed_objects":len(listings[label])}
    # Private object metadata are counted, but owner-private payloads and
    # PostgreSQL publication references are NOT inspected with CI identity.
    # Therefore no broad-delete approval is implied by this report.
    known={identity for identity,_ in indexed.values()}
    cutoff=(datetime.now(timezone.utc)-timedelta(days=90))
    mature=[name for name,(identity,updated) in indexed.items()
            if datetime.fromisoformat(updated.replace("Z","+00:00"))<cutoff]
    unreferenced_mature=sum(indexed[name][0] not in protected for name in mature)
    return {"component":"core-reference-discovery","status":"PARTIAL_REFERENCE_COVERAGE",
            "mode":"read-only","gcp_writes":0,"deletion_fence_published":False,
            "object_inventory_counts":{k:len(v) for k,v in listings.items()},
            "pages":pages,"core_manifest_count":len(indexed),
            "mature_90_day_core_manifests":len(mature),
            "externally_referenced_core_identities":len(protected),
            "external_references_not_in_current_core_manifest_inventory":len(protected-known),
            "mature_manifest_candidate_upper_bound":unreferenced_mature,
            "model_research_sources":source_counts,
            "private_payloads_scanned":False,
            "postgres_publication_index_scanned":False,
            "research_reference_completeness":"NOT_PROVEN",
            "reason":"PostgreSQL publication and owner-private or external model references not independently inventoried; do not configure deletion fence or delete historical manifests"}

if __name__ == "__main__":
    result=audit(access_token())
    print(json.dumps(result,sort_keys=True))
