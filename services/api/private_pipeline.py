"""Checkpointed PostgreSQL-to-Private-Iceberg normalization and marts."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from functools import reduce
import os
from typing import Any, Callable, Iterable


ZERO = Decimal("0")


class CorePriceReader:
    def __init__(self, catalog: Any) -> None: self.catalog=catalog

    @classmethod
    def from_env(cls) -> "CorePriceReader":
        from pyiceberg.catalog.sql import SqlCatalog
        from sqlalchemy import URL
        names=("POSTGRES_HOST","POSTGRES_DB","CORE_CATALOG_USER","CORE_CATALOG_PASSWORD","CORE_ICEBERG_WAREHOUSE","GCP_PROJECT_ID")
        values={name:os.getenv(name,"") for name in names}; missing=[name for name,value in values.items() if not value]
        if missing: raise ValueError(f"missing Core price settings: {','.join(missing)}")
        uri=URL.create("postgresql+psycopg",username=values["CORE_CATALOG_USER"],password=values["CORE_CATALOG_PASSWORD"],
                       host=values["POSTGRES_HOST"],port=5432,database=values["POSTGRES_DB"],
                       query={"sslmode":os.getenv("POSTGRES_SSLMODE","require"),"options":"-csearch_path=catalog"})
        return cls(SqlCatalog("janus-core-prices",type="sql",uri=uri,warehouse=values["CORE_ICEBERG_WAREHOUSE"],
                   init_catalog_tables="false",**{"py-io-impl":"pyiceberg.io.pyarrow.PyArrowFileIO","gcs.project-id":values["GCP_PROJECT_ID"],
                   "pool_size":1,"max_overflow":0,"pool_timeout":5}))

    def __call__(self, symbols: set[str], valuation_date: date) -> dict[str, Decimal | None]:
        if not symbols or not self.catalog.table_exists("core.ohlcv_v1"): return {}
        from pyiceberg.expressions import And, EqualTo, LessThanOrEqual, Or
        symbol_filter=reduce(Or,(EqualTo("symbol",symbol) for symbol in sorted(symbols)))
        rows=self.catalog.load_table("core.ohlcv_v1").scan(
            row_filter=And(symbol_filter,LessThanOrEqual("trade_date",valuation_date)),
            selected_fields=("symbol","trade_date","close"),limit=len(symbols)*260).to_arrow().to_pylist()
        latest:dict[str,dict[str,Any]]={}
        for row in rows:
            if row["symbol"] not in latest or row["trade_date"]>latest[row["symbol"]]["trade_date"]: latest[row["symbol"]]=row
        return {symbol:Decimal(str(row["close"])) for symbol,row in latest.items()}


def calculate_marts(events: Iterable[dict[str, Any]], prices: dict[str, Decimal | None],
                    valuation_date: date) -> dict[str, list[dict[str, Any]]]:
    rows=list(events)
    reversed_ids={str(row["reverses_event_id"]) for row in rows if row.get("event_action")=="REVERSAL"}
    active=[row for row in rows if row.get("event_action")!="REVERSAL" and str(row["event_id"]) not in reversed_ids]
    states:dict[tuple[str,str,str],dict[str,Any]]={}
    annual:dict[tuple[str,int,str],dict[str,Any]]=defaultdict(lambda:{"realized_pnl":ZERO,"fees":ZERO,"taxes":ZERO,"cash_dividends":ZERO,"transaction_count":0})
    realized_rows=[]
    ledger_version=max((int(row["ledger_version"]) for row in rows),default=0)
    for row in sorted(active,key=lambda item:(item["trade_date"],item["ledger_version"])):
        user_id,symbol,currency=str(row["user_id"]),row["symbol"],row["currency"]
        key=(user_id,symbol,currency); state=states.setdefault(key,{"shares":ZERO,"cost":ZERO,"realized":ZERO})
        shares=Decimal(str(row.get("shares") or 0)); price=Decimal(str(row.get("price") or 0))
        fee=Decimal(str(row.get("fee") or 0)); tax=Decimal(str(row.get("tax") or 0))
        bucket=annual[(user_id,row["trade_date"].year,currency)]
        bucket["fees"]+=fee; bucket["taxes"]+=tax; bucket["transaction_count"]+=1
        if row["event_type"]=="BUY": state["shares"]+=shares; state["cost"]+=shares*price+fee+tax
        elif row["event_type"]=="SELL":
            average=state["cost"]/state["shares"] if state["shares"] else ZERO
            realized=shares*price-fee-tax-shares*average
            state["shares"]-=shares; state["cost"]-=shares*average; state["realized"]+=realized; bucket["realized_pnl"]+=realized
            realized_rows.append({"user_id":user_id,"symbol":symbol,"currency":currency,"event_id":str(row["event_id"]),"realized_pnl":realized})
        elif row["event_type"]=="STOCK_DIV": state["shares"]+=shares
        elif row["event_type"]=="CASH_DIV":
            cash=Decimal(str(row.get("cash_amount") or 0)); state["realized"]+=cash-fee-tax; bucket["cash_dividends"]+=cash; bucket["realized_pnl"]+=cash-fee-tax
    common={"ledger_version":ledger_version,"valuation_date":valuation_date.isoformat(),"cost_basis_method":"MOVING_AVERAGE"}
    positions=[]; unrealized=[]
    for (user_id,symbol,currency),state in states.items():
        if state["shares"]<=0: continue
        average=state["cost"]/state["shares"]; price=prices.get(symbol)
        lineage={"ledger_version":ledger_version,"price_status":"available" if price is not None else "missing"}
        positions.append({"user_id":user_id,"symbol":symbol,"currency":currency,"shares":state["shares"],"average_cost":average,
                          "market_price":price,"market_value":price*state["shares"] if price is not None else None,"lineage":str(lineage),**common})
        unrealized.append({"user_id":user_id,"symbol":symbol,"currency":currency,"unrealized_pnl":
                           (price-average)*state["shares"] if price is not None else None,"price_status":lineage["price_status"],"lineage":str(lineage),**common})
    realized=[{**row,**common,"lineage":f"ledger:{row['event_id']}"} for row in realized_rows]
    annual_rows=[{"user_id":user,"year":year,"currency":currency,**values,**common,"lineage":f"ledger-version:{ledger_version}"}
                 for (user,year,currency),values in annual.items()]
    return {"mart_user_positions":positions,"mart_user_realized_pnl":realized,
            "mart_user_unrealized_pnl":unrealized,"mart_user_annual_pnl":annual_rows}


class PrivatePipeline:
    def __init__(self, repository: Any, store: Any,
                 prices: Callable[[set[str],date],dict[str,Decimal|None]],
                 assistant_cleanup: Callable[[Any],None] | None = None) -> None:
        self.repository,self.store,self.prices,self.assistant_cleanup=repository,store,prices,assistant_cleanup

    def run(self, valuation_date: date, limit: int = 500) -> int:
        checkpoint=self.repository.pipeline_checkpoint(); changes=self.repository.pipeline_batch(checkpoint,limit)
        completed=checkpoint
        if changes:
            user_ids={row["user_id"] for row in changes}
            for user_id in user_ids:
                ledger=self.repository.ledger_for_pipeline(user_id)
                watchlist=self.repository.watchlist_for_pipeline(user_id)
                self.store.upsert("ledger_events",ledger)
                self.store.upsert("watchlist_events",[{**row,"change_version":row["version"]} for row in watchlist])
                symbols={row["symbol"] for row in ledger}
                for table,rows in calculate_marts(ledger,self.prices(symbols,valuation_date),valuation_date).items():
                    self.store.upsert(table,rows)
            completed=changes[-1]["change_id"]
            self.repository.advance_pipeline_checkpoint(completed)
        for request in self.repository.pending_deletions():
            self.store.delete_user(request["user_id"])
            cleanup_required=getattr(self.repository,"assistant_cleanup_required",lambda _user_id:False)(request["user_id"])
            if cleanup_required and self.assistant_cleanup is None:
                self.repository.mark_deletion_cleanup_pending(request["request_id"],request["user_id"])
                continue
            if cleanup_required: self.assistant_cleanup(request["user_id"])
            self.repository.complete_deletion(request["request_id"],request["user_id"])
        return completed


def main() -> None:
    if os.getenv("ASSISTANT_STORAGE_ACCEPTANCE") == "true":
        from .assistant_storage_acceptance import run
        run()
        print("private assistant GCS/Iceberg acceptance passed")
        return
    from .repository import repository_from_env
    from .store import PrivateIcebergStore

    completed=PrivatePipeline(repository_from_env(),PrivateIcebergStore.from_env(),CorePriceReader.from_env()).run(
        date.fromisoformat(os.getenv("VALUATION_DATE",date.today().isoformat())))
    print(f"private pipeline checkpoint={completed}")


if __name__ == "__main__": main()
