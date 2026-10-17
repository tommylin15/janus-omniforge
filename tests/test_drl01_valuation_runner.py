"""Guard one-shot DRL-01D source scope and reversible existing Job path."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def script():
    target=Path(__file__).resolve().parents[1] / "scripts" / "gcp" / "drl01_valuation_2y.py"
    sys.path.insert(0,str(target.parent))
    spec=importlib.util.spec_from_file_location("drl01_valuation_2y",target)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_61_month_windows_are_bounded_and_do_not_overlap():
    runner=script()
    months=[]
    for offset,count in runner.OFFSETS:
        ending=2026*12+10-1-offset
        months.extend(divmod(value,12) for value in range(ending-count+1,ending+1))
    assert len(months)==len(set(months))==25
    assert min(months)==(2024,9)
    assert max(months)==(2026,9)
    assert runner.SYMBOLS == ["1513","2327","2382","3231","3711","5876"]


def test_request_must_be_explicit_and_deployment_sha_bound(tmp_path):
    runner=script()
    data={
        "intent":"drl01-official-twse-focus-two-year-valuation",
        "approved":True, "no_new_provider":True,
        "no_owner_mutation":True, "no_job_template_mutation":True,
        "symbols":runner.SYMBOLS, "target_start":"2024-10","target_end":"2026-10",
        "deployed_sha":"a"*40,
    }
    target=tmp_path/"req.json"
    target.write_text(json.dumps(data))
    assert runner.checked(str(target))==data
    for mutation in ({"approved":False}, {"symbols":runner.SYMBOLS+["2330"]},
                     {"deployed_sha":"main"}, {"no_job_template_mutation":False}):
        target.write_text(json.dumps({**data,**mutation}))
        with pytest.raises(ValueError,match="invalid_drl01_valuation_scope"):
            runner.checked(str(target))


def test_cloud_run_override_path_is_execution_scoped():
    source=Path(__file__).resolve().parents[1]/"scripts"/"gcp"/"drl01_valuation_2y.py"
    text=source.read_text()
    assert '"containerOverrides":[overrides]' in text
    assert '"etag":current["etag"]' in text
    assert "wait_for_terminal_executions" in text
    assert "cloud(f\"{ROOT}/jobs/{JOB}:run\"" in text
    assert ":update" not in text
    assert "POST" in text
    assert 'report["status"] = "FAILED_JOB_EXECUTION"' in text
    assert 'report["blocked_operation"] = name' in text
    assert "valuation_execution_failed_check_terminal_logs_before_retry" in text
    assert 'report["slices"][-1].get("two_year_ready")==12' in text
    assert 'and not any(s["valuation_failures"]' not in text
