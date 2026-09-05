from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import shutil
from uuid import UUID, uuid4

import pytest

from services.api.private_pipeline import PrivatePipeline, calculate_marts
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


class Repository:
    def __init__(self): self.advanced=[]
    def pipeline_checkpoint(self): return 7
    def pipeline_batch(self,checkpoint,limit): return [{"change_id":8,"user_id":USER}]
    def ledger_for_pipeline(self,user_id): return [event(1,"BUY",date(2026,1,1),Decimal("1"),Decimal("10"))]
    def watchlist_for_pipeline(self,user_id): return []
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
    failed_repo=Repository()
    with pytest.raises(RuntimeError): PrivatePipeline(failed_repo,Store(True),lambda symbols,when:{}).run(date(2026,9,4))
    assert failed_repo.advanced==[]


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


def test_private_iceberg_normalizes_postgres_gmt_timestamps():
    value=PrivateIcebergStore._value(datetime(2026,9,5,tzinfo=timezone(timedelta(0),"GMT")))
    assert str(value.tzinfo)=="UTC"
