from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import shutil
from uuid import UUID, uuid4

import pytest

from services.api.private_pipeline import PrivatePipeline, calculate_marts, calculate_risk_marts, resolve_valuation_date, xirr
from services.api.store import PrivateIcebergStore


USER=UUID("00000000-0000-0000-0000-000000000001")


def event(version,event_type,when,shares=None,price=None,cash=None,action="ORIGINAL",reverses=None):
    return {"event_id":uuid4(),"user_id":USER,"ledger_version":version,"event_action":action,"event_type":event_type,
            "trade_date":when,"symbol":"2330","shares":shares,"price":price,"cash_amount":cash,"fee":Decimal("0"),
            "tax":Decimal("0"),"currency":"TWD","reverses_event_id":reverses}


def test_moving_average_cross_year_reversal_and_missing_price_are_deterministic():
    original=event(1,"BUY",date(2025,12,1),Decimal("10"),Decimal("100"))
    reversal=event(2,"BUY",date(2025,12,1),Decimal("10"),Decimal("100"),action="REVERSAL",reverses=original["event_id"])
    replacement=event(3,"BUY",date(2025,12,2),Decimal("20"),Decimal("90"),action="REPLACEMENT")
    sell=event(4,"SELL",date(2026,1,2),Decimal("5"),Decimal("110"))
    marts=calculate_marts([original,reversal,replacement,sell],{"2330":None},date(2026,9,4))
    position=marts["mart_user_positions"][0]
    assert position["shares"]==Decimal("15")
    assert position["average_cost"]==Decimal("90")
    assert position["market_value"] is None
    assert marts["mart_user_unrealized_pnl"][0]["unrealized_pnl"] is None
    annual={row["year"]:row for row in marts["mart_user_annual_pnl"]}
    assert annual[2026]["realized_pnl"]==Decimal("100")


def test_fees_and_taxes_are_included_in_moving_average_realized_pnl():
    buy=event(1,"BUY",date(2026,1,1),Decimal("10"),Decimal("100"));buy["fee"]=Decimal("10")
    sell=event(2,"SELL",date(2026,2,1),Decimal("5"),Decimal("120"));sell["fee"]=Decimal("2");sell["tax"]=Decimal("3")
    marts=calculate_marts([buy,sell],{"2330":Decimal("130")},date(2026,9,4))
    assert marts["mart_user_positions"][0]["average_cost"]==Decimal("101")
    assert marts["mart_user_realized_pnl"][0]["realized_pnl"]==Decimal("90")
    assert marts["mart_user_annual_pnl"][0]["fees"]==Decimal("12")
    assert marts["mart_user_annual_pnl"][0]["taxes"]==Decimal("3")


def test_monthly_ledger_summary_uses_canonical_moving_average_and_net_cash_flows():
    buy=event(1,"BUY",date(2026,2,1),Decimal("5"),Decimal("100"));buy["fee"]=Decimal("2");buy["tax"]=Decimal("3")
    sell=event(2,"SELL",date(2026,2,10),Decimal("2"),Decimal("120"));sell["fee"]=Decimal("1");sell["tax"]=Decimal("2")
    dividend=event(3,"CASH_DIV",date(2026,2,20),cash=Decimal("50"));dividend["fee"]=Decimal("1")
    summary=calculate_marts([buy,sell,dividend],{"2330":Decimal("130")},date(2026,3,1))["mart_user_monthly_ledger_summary"][0]
    assert summary["purchase_outflow"]==Decimal("505")
    assert summary["sale_proceeds"]==Decimal("237")
    assert summary["cash_dividends"]==Decimal("50")
    assert summary["realized_pnl"]==Decimal("84")
    assert summary["transaction_count"]==3


def test_price_dates_drive_stale_status_and_withhold_aggregate_unrealized_pnl():
    buy=event(1,"BUY",date(2026,9,1),Decimal("2"),Decimal("100"))
    marts=calculate_marts([buy],{"2330":(Decimal("120"),date(2026,9,3))},date(2026,9,4))
    position=marts["mart_user_positions"][0]
    assert position["price_status"]=="stale" and position["price_date"]=="2026-09-03"
    risk=calculate_risk_marts([buy],marts["mart_user_positions"],None,{},date(2026,9,4))
    summary=risk["mart_user_portfolio_summary"][0]
    assert summary["valuation_status"]=="stale"
    assert summary["stale_price_count"]==1 and summary["unrealized_pnl"] is None


class Repository:
    def __init__(self): self.advanced=[]
    def pipeline_checkpoint(self): return 7
    def pipeline_batch(self,checkpoint,limit): return [{"change_id":8,"user_id":USER}]
    def ledger_for_pipeline(self,user_id): return [event(1,"BUY",date(2026,1,1),Decimal("1"),Decimal("10"))]
    def watchlist_for_pipeline(self,user_id): return []
    def investment_profile_for_pipeline(self,user_id): return None
    def advance_pipeline_checkpoint(self,value): self.advanced.append(value)
    def pending_deletions(self): return []


class Store:
    def __init__(self,fail=False): self.tables=[]; self.fail=fail
    def upsert(self,table,rows):
        self.tables.append(table)
        if self.fail: raise RuntimeError("write failed")


def test_checkpoint_advances_only_after_all_private_writes():
    repo,store=Repository(),Store()
    assert PrivatePipeline(repo,store,lambda symbols,when:{"2330":Decimal("12")}).run(date(2026,9,4))==8
    assert repo.advanced==[8]
    assert "mart_user_positions" in store.tables
    assert "mart_user_monthly_ledger_summary" in store.tables
    failed_repo=Repository()
    with pytest.raises(RuntimeError): PrivatePipeline(failed_repo,Store(True),lambda symbols,when:{}).run(date(2026,9,4))
    assert failed_repo.advanced==[]


def test_empty_queue_does_not_resolve_valuation_rewrite_marts_or_advance_checkpoint():
    class EmptyRepository:
        def pipeline_checkpoint(self): return 7
        def pipeline_batch(self,checkpoint,limit): return []
        def pending_deletions(self): return []
        def advance_pipeline_checkpoint(self,value): raise AssertionError("checkpoint advanced")
    store=Store()
    pipeline=PrivatePipeline(EmptyRepository(),store,lambda *_: {},
        valuation_date_resolver=lambda: (_ for _ in ()).throw(AssertionError("valuation resolved")))
    assert pipeline.run()==7
    assert store.tables==[]


@pytest.mark.parametrize(("now","persisted"),(
    (datetime(2026,9,19,8,tzinfo=timezone(timedelta(hours=8))),date(2026,9,18)),  # weekend
    (datetime(2026,9,16,11,tzinfo=timezone(timedelta(hours=8))),date(2026,9,15)), # holiday/incomplete ingestion
    (datetime(2026,9,16,21,30,tzinfo=timezone(timedelta(hours=8))),date(2026,9,16)), # completed ingestion
))
def test_normal_valuation_uses_latest_persisted_date(now,persisted):
    calls=[]
    def latest(eligible_through):
        calls.append(eligible_through)
        return persisted
    assert resolve_valuation_date(None,latest,now)==persisted
    assert calls==[now.date()]


def test_valuation_override_and_future_data_prevention():
    assert resolve_valuation_date("2025-12-31",lambda _: (_ for _ in ()).throw(AssertionError()))==date(2025,12,31)
    with pytest.raises(ValueError,match="future data"):
        resolve_valuation_date(None,lambda _:date(2026,9,21),datetime(2026,9,20,tzinfo=timezone.utc))


def test_core_price_reader_selects_latest_eligible_persisted_date():
    from services.api.private_pipeline import CorePriceReader
    class Scan:
        def to_arrow(self): return self
        def to_pylist(self): return [{"trade_date":date(2026,9,17)},{"trade_date":date(2026,9,18)}]
    class Table:
        def scan(self,**kwargs):
            assert kwargs["selected_fields"]==("trade_date",)
            return Scan()
    class Catalog:
        def table_exists(self,name): return name=="core.ohlcv_v1"
        def load_table(self,name): return Table()
    assert CorePriceReader(Catalog()).latest_valuation_date(date(2026,9,20))==date(2026,9,18)


def test_core_price_reader_keeps_the_quote_date_for_stale_detection():
    from services.api.private_pipeline import CorePriceReader
    class Scan:
        def to_arrow(self): return self
        def to_pylist(self): return [
            {"symbol":"2330","trade_date":date(2026,9,3),"close":Decimal("120")},
            {"symbol":"2330","trade_date":date(2026,9,2),"close":Decimal("110")},
        ]
    class Table:
        def scan(self,**kwargs):
            assert kwargs["selected_fields"]==("symbol","trade_date","close")
            return Scan()
    class Catalog:
        def table_exists(self,name): return name=="core.ohlcv_v1"
        def load_table(self,name): return Table()
    assert CorePriceReader(Catalog())({"2330"},date(2026,9,4))=={
        "2330":(Decimal("120"),date(2026,9,3))
    }


def test_partial_write_replay_is_logically_idempotent():
    class ReplayRepository(Repository):
        def __init__(self): super().__init__(); self.checkpoint=7
        def pipeline_checkpoint(self): return self.checkpoint
        def pipeline_batch(self,checkpoint,limit):
            return [] if checkpoint>=8 else [{"change_id":8,"user_id":USER}]
        def advance_pipeline_checkpoint(self,value): self.checkpoint=value
    class ReplayStore:
        def __init__(self): self.rows={}; self.calls=0; self.fail=True
        def upsert(self,table,rows):
            self.calls+=1
            bucket=self.rows.setdefault(table,set())
            bucket.update(tuple(sorted((key,str(value)) for key,value in row.items())) for row in rows)
            if self.fail and self.calls==3: raise RuntimeError("partial write")
    repo,store=ReplayRepository(),ReplayStore()
    pipeline=PrivatePipeline(repo,store,lambda symbols,when:{"2330":Decimal("12")})
    with pytest.raises(RuntimeError,match="partial write"): pipeline.run(date(2026,9,18))
    assert repo.checkpoint==7
    before={table:len(rows) for table,rows in store.rows.items()}
    store.fail=False
    assert pipeline.run(date(2026,9,18))==8
    assert repo.checkpoint==8
    assert all(len(rows)>=before.get(table,0) for table,rows in store.rows.items())


def test_current_mart_prefers_latest_valuation_over_historical_replay():
    store=object.__new__(PrivateIcebergStore)
    store.rows=lambda *_args,**_kwargs:[
        {"valuation_date":"2026-09-18","ledger_version":4,"value":"current"},
        {"valuation_date":"2026-09-05","ledger_version":5,"value":"replay"},
        {"valuation_date":"2026-09-18","ledger_version":5,"value":"corrected"},
    ]
    assert store.mart("mart_user_positions",USER)==[
        {"valuation_date":"2026-09-18","ledger_version":5,"value":"corrected"}]


def test_xirr_reports_unique_missing_and_multiple_roots_without_filling_zero():
    unique=xirr([(date(2025,1,1),Decimal("-100")),(date(2026,1,1),Decimal("110"))])
    assert unique["status"]=="available" and abs(unique["value"]-.1)<1e-6
    assert xirr([(date(2025,1,1),Decimal("100")),(date(2026,1,1),Decimal("10"))])=={
        "status":"insufficient_data","value":None}
    multiple=xirr([(date(2024,1,1),Decimal("-100")),(date(2025,1,1),Decimal("230")),
                   (date(2026,1,1),Decimal("-132"))])
    assert multiple=={"status":"multiple_roots","value":None}


def test_exposure_splits_multi_industry_and_stress_is_deterministic():
    buy=event(1,"BUY",date(2025,1,1),Decimal("10"),Decimal("100"))
    positions=calculate_marts([buy],{"2330":Decimal("120")},date(2026,1,1))["mart_user_positions"]
    memberships={"2330":[
        {"industry":"semiconductor","effective_date":"2026-01-01","membership_snapshot_hash":"a","provenance_id":"p1"},
        {"industry":"ai","effective_date":"2026-01-01","membership_snapshot_hash":"b","provenance_id":"p2"},
    ]}
    profile={"user_id":USER,"minimum_cash_ratio":Decimal("0.1")}
    first=calculate_risk_marts([buy],positions,profile,memberships,date(2026,1,1))
    second=calculate_risk_marts([buy],positions,profile,memberships,date(2026,1,1))
    assert first==second
    assert sum(row["market_value"] for row in first["mart_user_exposure"])==Decimal("1200")
    assert {row["market_value"] for row in first["mart_user_exposure"]}=={Decimal("600")}
    assert first["mart_user_portfolio_summary"][0]["cash_safety_status"]=="insufficient_data"
    assert first["mart_user_annual_performance"][0]["xirr_status"]=="available"


def test_deletion_removes_iceberg_before_postgres_completion():
    calls=[]
    class DeletionRepository:
        def pipeline_checkpoint(self): return 9
        def pipeline_batch(self,checkpoint,limit): return []
        def pending_deletions(self): return [{"request_id":uuid4(),"user_id":USER}]
        def complete_deletion(self,request_id,user_id): calls.append(("postgres",user_id))
    class DeletionStore:
        def delete_user(self,user_id): calls.append(("iceberg",user_id))
    assert PrivatePipeline(DeletionRepository(),DeletionStore(),lambda symbols,when:{}).run(date(2026,9,4))==9
    assert calls==[("iceberg",USER),("postgres",USER)]


def test_private_iceberg_note_rows_are_scoped_by_user():
    from pyiceberg.catalog.sql import SqlCatalog

    root=Path(".tmp")/f"private-iceberg-{uuid4()}"; root.mkdir(parents=True)
    try:
        warehouse=(root/"warehouse").as_posix()
        catalog=SqlCatalog("test",uri="sqlite:///"+(root.resolve()/"catalog.db").as_posix(),warehouse=warehouse)
        store=PrivateIcebergStore(catalog,warehouse)
        other=UUID("00000000-0000-0000-0000-000000000002")
        store.write_note(user_id=USER,note_id=uuid4(),revision=1,body="mine",symbol=None,trade_event_id=None,needs_follow_up=False)
        store.write_note(user_id=other,note_id=uuid4(),revision=1,body="other",symbol=None,trade_event_id=None,needs_follow_up=False)
        rows=store.rows("note_revisions",USER)
        assert [row["body"] for row in rows]==["mine"]

    finally:
        catalog.engine.dispose()
        shutil.rmtree(root)


def test_core_price_reader_uses_canonical_iceberg_catalog(monkeypatch):
    from pyiceberg.catalog import sql
    from services.api.private_pipeline import CorePriceReader

    captured=[]

    class Catalog:
        def __init__(self, name, **kwargs):
            captured.append(name)

    monkeypatch.setattr(sql, "SqlCatalog", Catalog)
    for name in ("POSTGRES_HOST", "POSTGRES_DB", "CORE_CATALOG_USER", "CORE_CATALOG_PASSWORD",
                 "CORE_ICEBERG_WAREHOUSE", "GCP_PROJECT_ID"):
        monkeypatch.setenv(name, "test")

    CorePriceReader.from_env()

    assert captured == ["janus"]


def test_private_iceberg_normalizes_postgres_gmt_timestamps():
    value=PrivateIcebergStore._value(datetime(2026,9,5,tzinfo=timezone(timedelta(0),"GMT")))
    assert str(value.tzinfo)=="UTC"
