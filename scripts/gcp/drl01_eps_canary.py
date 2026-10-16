#!/usr/bin/env python3
"""Run one approved official MOPS EPS history repair via existing Cloud Run Job."""
import json,re,sys,time
from pathlib import Path
from ghcr_jobs_rollout import cloud,job,terminal,ROOT

def main():
    req=json.loads(Path(sys.argv[1]).read_text())
    syms=req.get("symbols")
    if (req.get("intent")!="drl01-existing-mops-eps-history"
            or req.get("approved") is not True or req.get("no_new_provider") is not True
            or req.get("no_job_template_change") is not True
            or not isinstance(syms,list) or not 1<=len(syms)<=2
            or any(not re.fullmatch(r"[1-9][0-9]{3}",s) for s in syms)):
        raise ValueError("invalid_eps_scope")
    j=job("janus-ingestion-core")
    c=j["template"]["template"]["containers"]
    if len(c)!=1 or c[0].get("command") not in (None,[],["python"]):
        raise ValueError("job_entrypoint_drift")
    override={
        "args":(["python"] if not c[0].get("command") else [])+["-m","ingestion_core.runtime_entrypoint"],
        "env":[{"name":"QUEUE_CONSUMER","value":"false"},
               {"name":"JANUS_DATA_SUPPLEMENT_MODE","value":"fundamental-history"},
               {"name":"JANUS_DATA_SUPPLEMENT_SYMBOLS","value":",".join(syms)}]}
    if c[0].get("name"):override["name"]=c[0]["name"]
    op=cloud(f"{ROOT}/jobs/janus-ingestion-core:run",
             {"etag":j["etag"],"overrides":{"taskCount":1,"timeout":"1800s",
                                            "containerOverrides":[override]}},"POST")
    name=op.get("name","")
    if not name.startswith(ROOT+"/operations/"):raise RuntimeError("operation_invalid")
    deadline=time.monotonic()+1860
    while not op.get("done") and time.monotonic()<deadline:
        time.sleep(8)
        op=cloud(name)
    if not op.get("done") or op.get("error"):raise RuntimeError("eps_job_not_successful")
    exe=op.get("response",{})
    if not terminal(exe) or exe.get("succeededCount")!=1 or exe.get("failedCount",0):
        raise RuntimeError("eps_execution_unverified")
    execution=exe.get("name","").rsplit("/",1)[-1]
    if not execution.startswith("janus-ingestion-core-"):raise RuntimeError("execution_name_invalid")
    out={"execution":execution,"symbol_count":len(syms),
         "job_status":"EXECUTION_PASS","core_history_readback":"NOT_VERIFIED",
         "job_template_mutation":False,"provider_created":False}
    Path("/tmp/drl01-eps-canary.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out,sort_keys=True))
if __name__=="__main__":
    main()
