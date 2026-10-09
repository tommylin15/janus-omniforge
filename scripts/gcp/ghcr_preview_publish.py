#!/usr/bin/env python3
"""Promote only the validated 0%-traffic Janus candidate to the fixed preview tag.

Same Cloud Run service, existing Git-ref deployment lease, zero canonical traffic
writes, and owner-only release. Failure restores the original preview routing.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
import time

import ghcr_api_promote as api
import ghcr_jobs_rollout as jobs
from ghcr_mcp_route import BASE, LEASE, PROJECT, REGION, SERVICE, command, describe, probe

REQUEST=Path("ops/ghcr-preview-request.json")
EXPECTED_URL="https://preview---janus-api-2oo7qbkd5q-uc.a.run.app"
SHA=re.compile(r"^[0-9a-f]{40}$")
IMAGE=re.compile(r"^ghcr\.io/tommylin15/janus-api@sha256:[0-9a-f]{64}$")


def authorized():
    data=json.loads(REQUEST.read_text())
    source=data.get("source_sha")
    if (data.get("intent") != "publish-verified-ghcr-candidate-to-fixed-preview"
            or data.get("approved") is not True
            or data.get("scope") != "janus-api-preview-tag-only"
            or not isinstance(source,str) or not SHA.fullmatch(source)
            or not isinstance(data.get("api_image"),str) or not IMAGE.fullmatch(data["api_image"])
            or data.get("canonical_traffic_mutation") is not False
            or data.get("jobs_or_scheduler_mutation") is not False
            or data.get("other_tags_mutation") is not False
            or data.get("preview_url") != EXPECTED_URL + "/app/"
            or not all(isinstance(data.get(k),str) and data[k].isdigit()
                       for k in ("release_run","candidate_run","boundary_run"))):
        raise ValueError("preview_request_invalid")
    current=json.loads(Path("ops/ghcr-candidate-request.json").read_text())
    boundary=json.loads(Path("ops/ghcr-candidate-boundary-request.json").read_text())
    if current.get("sha")!=source or boundary.get("sha")!=source:
        raise ValueError("preview_candidate_sha_mismatch")
    return data


def provenance(req):
    specs=(("release_run","Janus GHCR full-test image publication"),
           ("candidate_run","Janus GHCR Cloud Run 0-percent candidate"),
           ("boundary_run","GHCR candidate OAuth and private-boundary probe"))
    for name, expected in specs:
        metadata=json.loads(command(["gh","run","view",req[name],
                                     "--json","headSha,status,conclusion,workflowName"]))
        if (metadata.get("status")!="completed"
                or metadata.get("conclusion")!="success"
                or metadata.get("workflowName")!=expected):
            raise ValueError("preview_provenance_workflow_incomplete")
        if name=="release_run" and metadata.get("headSha")!=req["source_sha"]:
            raise ValueError("preview_source_not_full_release")
    command(["git","merge-base","--is-ancestor",req["source_sha"],"HEAD"])


def routes(state):
    rows=state.get("status",{}).get("traffic",[])
    if not isinstance(rows,list):
        raise ValueError("preview_traffic_unknown")
    active=[(r.get("revisionName"),r.get("percent")) for r in rows if (r.get("percent") or 0)>0]
    tags={}
    for r in rows:
        if r.get("tag"):
            if r["tag"] in tags:
                raise ValueError("preview_duplicate_tag")
            tags[r["tag"]]=r.get("revisionName")
    if len(active)!=1 or active[0][1]!=100:
        raise ValueError("preview_baseline_split_traffic")
    return active, tags


def ready(state):
    cond=state.get("status",{}).get("conditions",[])
    return (isinstance(cond,list)
            and any(x.get("type")=="Ready" and x.get("status")=="True" for x in cond)
            and not any(x.get("type")=="RoutesReady" and x.get("status")!="True" for x in cond))


def assert_routes(before,after,target,restored=False):
    old_active,old_tags=routes(before)
    new_active,new_tags=routes(after)
    if new_active!=old_active:
        raise ValueError("preview_canonical_traffic_drift")
    expected=dict(old_tags)
    if restored:
        pass
    else:
        expected["preview"]=target
    if new_tags!=expected:
        raise ValueError("preview_other_tags_changed")
    if before.get("spec",{}).get("template")!=after.get("spec",{}).get("template"):
        raise ValueError("preview_service_runtime_config_changed")
    if not ready(after):
        raise ValueError("preview_service_not_ready")


def check_candidate(before,req):
    source=req["source_sha"]
    active,tags=routes(before)
    candidate=tags.get("ghcr-"+source[:12])
    if not ready(before) or not candidate or candidate==active[0][0]:
        raise ValueError("preview_valid_zero_percent_candidate_required")
    for item in before["status"]["traffic"]:
        if item.get("tag")=="ghcr-"+source[:12] and (item.get("percent") or 0)!=0:
            raise ValueError("preview_candidate_traffic_not_zero")
    revision=json.loads(command(["gcloud","run","revisions","describe",candidate,
                                 f"--project={PROJECT}",f"--region={REGION}","--format=json"]))
    if api.revision_image(revision)!=req["api_image"]:
        raise ValueError("preview_candidate_immutable_image_mismatch")
    if not any(x.get("type")=="Ready" and x.get("status")=="True"
               for x in revision.get("status",{}).get("conditions",[])):
        raise ValueError("preview_candidate_not_ready")
    base="https://ghcr-"+source[:12]+"---"+BASE.removeprefix("https://")
    probe(base,source)
    return candidate


def update_preview(target=None,remove=False):
    if remove:
        cmd=["gcloud","run","services","update-traffic",SERVICE,
             f"--project={PROJECT}",f"--region={REGION}",
             "--remove-tags=preview","--quiet"]
    else:
        cmd=["gcloud","run","services","update-traffic",SERVICE,
             f"--project={PROJECT}",f"--region={REGION}",
             "--update-tags=preview="+target,"--quiet"]
    command(cmd)


def reconciled(before,target,restored=False,attempts=8):
    for number in range(attempts):
        after=describe()
        try:
            assert_routes(before,after,target,restored=restored)
            return after
        except ValueError:
            if number==attempts-1:
                raise
            time.sleep(8)
    raise ValueError("preview_reconciliation_unverified")


def apply(receipt):
    evidence={"status":"BLOCKED","phase":"PREFLIGHT","canonical_traffic_write":False,
              "jobs_or_scheduler_write":False,"preview_tag_mutation_attempted":False,
              "lease_released":False,"restored_previous_preview":False}
    def save():
        receipt.write_text(json.dumps(evidence,sort_keys=True))
    save()
    before=None
    mutated=False
    try:
        req=authorized()
        provenance(req)
        jobs.legacy_writers()
        command(LEASE+["acquire"])
        before=describe()
        candidate=check_candidate(before,req)
        evidence.update(source_sha=req["source_sha"],candidate=candidate,
                        before_preview=routes(before)[1].get("preview"))
        save()
        command(LEASE+["assert"])
        evidence["phase"]="UPDATE_PREVIEW_TAG"
        evidence["preview_tag_mutation_attempted"]=True
        save()
        mutated=True
        update_preview(candidate)
        reconciled(before,candidate)
        probe(EXPECTED_URL,req["source_sha"])
        command(LEASE+["assert"])
        evidence["status"]="PASS"
        evidence["phase"]="VERIFIED_FIXED_PREVIEW"
        evidence["preview_revision"]=candidate
        save()
        command(LEASE+["release","--safe-to-release"])
        evidence["lease_released"]=True
        save()
        return 0
    except Exception as error:
        reason=str(error)
        evidence["reason"]=reason if re.fullmatch(r"[a-z][a-z0-9_]{3,100}",reason) else "control_failure"
        evidence["error_type"]=type(error).__name__
        save()
        if before is None:
            return 78
        try:
            command(LEASE+["assert"])
            if mutated:
                old=routes(before)[1].get("preview")
                update_preview(old,remove=old is None)
            reconciled(before,"",restored=True)
            evidence["restored_previous_preview"]=True
            evidence["phase"]="RESTORED_PREVIEW_OR_NO_MUTATION"
            save()
            command(LEASE+["release","--safe-to-release"])
            evidence["lease_released"]=True
            save()
        except Exception:
            evidence["phase"]="RECOVERY_BLOCKED_LEASE_RETAINED"
            save()
        return 78


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--receipt",type=Path,required=True)
    return apply(parser.parse_args().receipt)


if __name__=="__main__":
    sys.exit(main())
