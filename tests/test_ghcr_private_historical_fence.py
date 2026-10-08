"""Historical failed-before-task fence: zero false terminal passes."""
from copy import deepcopy
from pathlib import Path
import runpy

import pytest

ROOT=Path(__file__).resolve().parents[1]
f=runpy.run_path(str(ROOT/"scripts/gcp/ghcr_private_historical_fence.py"))
verified_failed_count=f["verified_failed_count"]
NAMES=sorted(f["KNOWN_FAILED_PRETASK"])


def snapshot():
    v1=[{"execution":n,"describe_status":"READABLE",
         "created":"2026-09-24T13:30:25.745166Z","started":None,"completed":None,
         "runningCount":0,"succeededCount":0,"failedCount":0,"cancelledCount":0,
         "conditions":[{"type":"Completed","status":"False","reason":None}]} for n in NAMES]
    tasks=[{"execution":n,"task_readback":"READABLE_BOUNDED",
            "tasks_scanned":0,"tasks_started":0,"tasks_completed":0,
            "terminal_confirmed":False} for n in NAMES]
    v2={"scope":"cloud_run_v2_read_only_execution_status",
        "expected_count":9,"all_readable":True,"all_terminal_confirmed":True,
        "resource_writes":0,"cancel_executions":False,"authorize_job_promotion":False,
        "records":[{"execution":n,"v2_readback":"READABLE","readback_reason":"NONE",
                    "reconciling":False,"start_observed":False,
                    "completion_observed":False,"running_count":None,"task_count":1,
                    "terminal_confirmed":True,
                    "terminal_outcome":"FAILED_TERMINAL_CONDITION",
                    "condition_states":[{"type":"Completed","state":"CONDITION_FAILED",
                                         "execution_reason":None}]}
                   for n in NAMES]}
    return v1,tasks,v2


def test_exact_nine_failed_control_plane_and_zero_task_evidence_fence():
    v1,tasks,v2=snapshot()
    assert verified_failed_count(v1,tasks,v2,9)==9
    assert verified_failed_count(v1,tasks,v2,0)==0


@pytest.mark.parametrize("kind",[
    "unexpected_id","duplicate_id","started","completed","running",
    "successful_task","failed_task","wrong_v1_condition",
    "missing_task","task_started","task_completed","task_unreadable",
    "v2_not_terminal","v2_pending","v2_error","v2_running",
    "v2_started","v2_wrong_expected_count","v2_not_all_readable",
    "v2_cancel_requested","v2_authorizes_promotion",
    "transient_reason","new_2026_execution",
])
def test_any_unverified_dimension_blocks_all_historical_release(kind):
    v1,tasks,v2=snapshot()
    if kind=="unexpected_id": v1[0]["execution"]="janus-private-pipeline-new-unknown"
    if kind=="duplicate_id": v1[0]["execution"]=v1[1]["execution"]
    if kind=="started": v1[0]["started"]="2026-09-24T13:31:00Z"
    if kind=="completed": v1[0]["completed"]="2026-09-24T13:31:00Z"
    if kind=="running": v1[0]["runningCount"]=1
    if kind=="successful_task": v1[0]["succeededCount"]=1
    if kind=="failed_task": v1[0]["failedCount"]=1
    if kind=="wrong_v1_condition": v1[0]["conditions"][0]["status"]="True"
    if kind=="missing_task": tasks.pop()
    if kind=="task_started": tasks[0]["tasks_started"]=1
    if kind=="task_completed": tasks[0]["tasks_completed"]=1
    if kind=="task_unreadable": tasks[0]["task_readback"]="UNKNOWN_OR_BLOCKED"
    if kind=="v2_not_terminal": v2["records"][0]["terminal_confirmed"]=False
    if kind=="v2_pending": v2["records"][0]["condition_states"][0]["state"]="CONDITION_PENDING"
    if kind=="v2_error": v2["records"][0]["readback_reason"]="HTTP_403"
    if kind=="v2_running": v2["records"][0]["reconciling"]=True
    if kind=="v2_started": v2["records"][0]["start_observed"]=True
    if kind=="v2_wrong_expected_count": v2["expected_count"]=8
    if kind=="v2_not_all_readable": v2["all_readable"]=False
    if kind=="v2_cancel_requested": v2["cancel_executions"]=True
    if kind=="v2_authorizes_promotion": v2["authorize_job_promotion"]=True
    if kind=="transient_reason":
        v2["records"][0]["condition_states"][0]["execution_reason"]="CANCELLING"
    if kind=="new_2026_execution": v1[0]["created"]="2026-10-08T00:00:00Z"
    assert verified_failed_count(v1,tasks,v2,9)==0


def test_fake_boolean_count_does_not_fence():
    v1,tasks,v2=snapshot()
    assert verified_failed_count(v1,tasks,v2,True)==0


def test_no_owner_payload_is_allowed_in_result():
    v1,tasks,v2=snapshot()
    v2["secrets"]={"refresh_token":"SECRET_NOT_FOR_LOG"}
    result=verified_failed_count(v1,tasks,v2,9)
    assert result==9
    assert "SECRET" not in str(result)
