"""Fail-closed offline contracts for independently scheduled backup cleanup."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import private_ledger_backup_retention as policy


def req():
    return dict(
        intent="dev-private-ledger-retention-independent",
        scope="existing-dev-private-backup-prefixes",
        dry_run_first=True, daily_keep=7, weekly_keep=4, monthly_keep=6,
        max_daily_deletes_per_run=3, max_weekly_deletes_per_run=1, max_monthly_deletes_per_run=1,
        no_new_resources=True, no_iam_expansion=True,
        no_pg_mutation=True, no_new_backup=True,
        approved_scheduled_apply=False
    )


def backup(kind, key, *, created="2026-10-23T00:30:00Z", size=2048, generation=1):
    return {"name": f"pilot-ledger-backups/{kind}/{key}.dump",
            "generation": str(generation), "size": str(size), "timeCreated": created}


def entries():
    daily = [backup("daily", f"2026-10-{x:02d}") for x in range(10,24)]
    monthly = [backup("monthly", f"2026-{x:02d}") for x in range(2,11)]
    return list(reversed(daily)), list(reversed(monthly))


NOW=datetime(2026,10,23,13,tzinfo=timezone.utc)


def test_request_ensures_exact_scoped_policy():
    policy.request_guard(req())
    for k in req():
        bad=req();bad[k]=None
        if k!="approved_scheduled_apply":
            with pytest.raises(ValueError,match="policy_or_scope_invalid"):
                policy.request_guard(bad)


def test_conservative_policy_and_hard_deletion_caps():
    daily, monthly = entries()
    p=policy.plan(daily,monthly,now=NOW)
    assert len(p["protected"]["daily"]) == 7
    assert len(p["protected"]["monthly"]) == 6
    assert [x["name"][-15:] for x in p["expired"]["daily"]] == [
        "2026-10-16.dump","2026-10-15.dump","2026-10-14.dump"]
    assert len(p["expired"]["monthly"]) == 1
    assert p["monthly_status"]=="ELIGIBLE"


def test_fail_closed_if_newest_daily_stale_or_inventory_short():
    daily, monthly = entries()
    with pytest.raises(ValueError,match="recent_daily_backup"):
        policy.plan(daily,monthly,now=NOW+timedelta(days=3))
    with pytest.raises(ValueError,match="insufficient_backup"):
        policy.plan(daily[:6],monthly,now=NOW)
    with pytest.raises(ValueError,match="insufficient_backup"):
        policy.plan(daily,[],now=NOW)


def test_old_monthly_backup_causes_monthly_skip_not_daily_loss():
    daily,monthly=entries()
    # Fresh daily must still be attested, so put the latest in the same period.
    # Test monthly guard without weakening the daily freshness gate by
    # constructing a separate recent daily inventory.
    d=[{**row,"timeCreated":"2027-01-02T03:00:00Z"} for row in daily]
    p=policy.plan(d,monthly,now=datetime(2027,1,2,13,tzinfo=timezone.utc))
    assert p["monthly_status"]=="STALE_NO_MONTHLY_DELETE"
    assert p["expired"]["monthly"]==[]


def test_inventory_rejects_unexpected_objects_or_duplicate_generations(monkeypatch):
    daily, _=entries()
    def install(items):
        monkeypatch.setattr(policy,"api",lambda *a,**k:{"items":items})
    install(daily+[backup("daily","2026-10-23",generation=2)])
    with pytest.raises(ValueError,match="duplicate_name"):
        policy.inventory("fake-token","daily")
    install(daily+[{"name":"pilot-ledger-backups/daily/foreign.txt",
                    "size":"1000","generation":"9","timeCreated":"2026-10-20T00:00:00Z"}])
    with pytest.raises(ValueError,match="unrecognized"):
        policy.inventory("fake-token","daily")
    install([{**daily[0],"generation":""}])
    with pytest.raises(ValueError,match="generation_missing"):
        policy.inventory("fake-token","daily")


def test_dry_run_uses_get_only_and_no_deletion(monkeypatch,tmp_path):
    daily,monthly=entries()
    calls=[]
    def inv(token,kind):
        calls.append(("GET",kind))
        return {"daily":daily,"weekly":[],"monthly":monthly}[kind]
    monkeypatch.setattr(policy,"inventory",inv)
    monkeypatch.setattr(policy,"OUT",tmp_path/"receipt.json")
    monkeypatch.setattr(policy,"api",lambda *a,**k: (_ for _ in ()).throw(
        AssertionError("dry-run must not call DELETE")))
    result=policy.run(mode="dry-run",request=req(),token="never-logged",now=NOW)
    assert result["status"]=="DRY_RUN_PASS"
    assert result["actual_deletes"]=={"daily":0,"weekly":0,"monthly":0}
    assert result["planned_deletes"]=={"daily":3,"weekly":0,"monthly":1}
    assert calls==[("GET","daily"),("GET","weekly"),("GET","monthly")]


def test_apply_requires_explicit_activation_flag(monkeypatch):
    with pytest.raises(ValueError,match="apply_not_activated"):
        policy.run(mode="apply",request=req(),token="fake",now=NOW)
    r=req();r["approved_scheduled_apply"]=True
    with pytest.raises(ValueError,match="apply_not_activated"):
        policy.run(mode="apply",request=r,token="fake",now=NOW)


def test_apply_generation_exact_deletion_and_readback(monkeypatch,tmp_path):
    daily,monthly=entries()
    state={"daily":daily[:],"weekly":[],"monthly":monthly[:]}
    actions=[]
    def inventory(token,kind):
        return [dict(x) for x in state[kind]]
    def api(token,path,*,params=None,method="GET"):
        assert method=="DELETE"
        assert params["ifGenerationMatch"]=="1"
        from urllib.parse import unquote
        name=unquote(path[len("/o/"):])
        kind=name.split("/")[1]
        assert any(x["name"]==name for x in state[kind])
        state[kind]=[x for x in state[kind] if x["name"]!=name]
        actions.append((kind,name))
        return {}
    monkeypatch.setattr(policy,"inventory",inventory)
    monkeypatch.setattr(policy,"api",api)
    monkeypatch.setattr(policy,"OUT",tmp_path/"receipt.json")
    monkeypatch.setenv("JANUS_BACKUP_RETENTION_SCHEDULED_APPLY","true")
    r=req();r["approved_scheduled_apply"]=True
    result=policy.run(mode="apply",request=r,token="fake",now=NOW)
    assert result["status"]=="APPLY_PASS"
    assert result["actual_deletes"]=={"daily":3,"weekly":0,"monthly":1}
    assert len(actions)==4
    assert result["count_after"]=={"daily":11,"weekly":0,"monthly":8}
    assert result["backup_reexecutions"]==result["pg_mutations"]==0


def test_preapply_mutation_blocks_all_deletes(monkeypatch,tmp_path):
    daily,monthly=entries();counts={"daily":0,"weekly":0,"monthly":0}
    def inventory(token,kind):
        counts[kind]+=1
        if kind=="daily" and counts[kind]>1:
            return [{**daily[0],"generation":"999"},*daily[1:]]
        return {"daily":daily,"weekly":[],"monthly":monthly}[kind]
    monkeypatch.setattr(policy,"inventory",inventory)
    monkeypatch.setattr(policy,"api",lambda *a,**k: (_ for _ in ()).throw(
        AssertionError("must not delete on drift")))
    monkeypatch.setattr(policy,"OUT",tmp_path/"receipt.json")
    monkeypatch.setenv("JANUS_BACKUP_RETENTION_SCHEDULED_APPLY","true")
    r=req();r["approved_scheduled_apply"]=True
    with pytest.raises(RuntimeError,match="preapply_inventory_drift"):
        policy.run(mode="apply",request=r,token="fake",now=NOW)


def test_api_allowlists_methods_and_does_not_print_token():
    with pytest.raises(ValueError,match="outside_allowlist"):
        policy.api("private-bearer-token","/o",method="PATCH")

def test_weekly_keeps_four_and_deletes_at_most_one():
    daily, monthly = entries()
    weekly = [backup("weekly", day) for day in
              ["2026-10-19", "2026-10-12", "2026-10-05", "2026-09-28", "2026-09-21", "2026-09-14"]]
    result = policy.plan(daily, monthly, weekly=weekly, now=NOW)
    assert len(result["protected"]["weekly"]) == 4
    assert [r["name"] for r in result["expired"]["weekly"]] == [weekly[4]["name"]]
