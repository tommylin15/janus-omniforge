"""Checkpointed PostgreSQL-to-Private-Iceberg normalization and marts."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from functools import reduce
from hashlib import sha256
from math import exp
import json
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

    def memberships(self, symbols: set[str], valuation_date: date) -> dict[str, list[dict[str, Any]]]:
        identifier="mart.mart_sector_rotation_daily_v1"
        if not symbols or not self.catalog.table_exists(identifier): return {}
        from pyiceberg.expressions import LessThanOrEqual
        rows=self.catalog.load_table(identifier).scan(
            row_filter=LessThanOrEqual("analysis_date",valuation_date),limit=10_000).to_arrow().to_pylist()
        latest:dict[str,dict[str,Any]]={}
        for row in rows:
            industry=str(row.get("industry") or row.get("scope_id") or "")
            if industry and (industry not in latest or row["analysis_date"]>latest[industry]["analysis_date"]): latest[industry]=row
        result:dict[str,list[dict[str,Any]]]=defaultdict(list)
        for industry,row in latest.items():
            payload=json.loads(row["payload_json"])
            for symbol in payload.get("membership_snapshot",[]):
                if symbol in symbols:
                    result[symbol].append({"industry":industry,"effective_date":str(row["analysis_date"]),
                        "membership_snapshot_hash":row["membership_snapshot_hash"],
                        "provenance_id":"sha256:"+sha256(str(row["artifact_ref"]).encode()).hexdigest()})
        return dict(result)


def xirr(cash_flows: Iterable[tuple[date, Decimal]]) -> dict[str, Any]:
    flows=sorted((day,Decimal(str(amount))) for day,amount in cash_flows if amount)
    if len(flows)<2 or not any(amount<0 for _,amount in flows) or not any(amount>0 for _,amount in flows):
        return {"status":"insufficient_data","value":None}
    origin=flows[0][0]
    def npv(log_rate: float) -> float:
        return sum(float(amount)*exp(max(-700,min(700,-log_rate*((day-origin).days/365.0)))) for day,amount in flows)
    roots=[]; left=-9.0; left_value=npv(left)
    for step in range(1,361):
        right=-9.0+step*.05; right_value=npv(right)
        if left_value==0: roots.append(left)
        elif left_value*right_value<0:
            low,high=left,right
            for _ in range(80):
                middle=(low+high)/2; value=npv(middle)
                if npv(low)*value<=0: high=middle
                else: low=middle
            roots.append((low+high)/2)
        left,left_value=right,right_value
    unique=[]
    for root in roots:
        rate=exp(root)-1
        if not any(abs(rate-known)<1e-7 for known in unique): unique.append(rate)
    if not unique: return {"status":"no_root","value":None}
    if len(unique)>1: return {"status":"multiple_roots","value":None}
    return {"status":"available","value":round(unique[0],10)}


def calculate_risk_marts(events: Iterable[dict[str, Any]], positions: list[dict[str, Any]],
                         profile: dict[str, Any] | None, memberships: dict[str,list[dict[str,Any]]],
                         valuation_date: date) -> dict[str,list[dict[str,Any]]]:
    rows=list(events); user_id=str(rows[0]["user_id"]) if rows else str(profile["user_id"]) if profile else ""
    ledger_version=max((int(row["ledger_version"]) for row in rows),default=0)
    common={"user_id":user_id,"ledger_version":ledger_version,"valuation_date":valuation_date.isoformat()}
    totals:dict[str,dict[str,Any]]=defaultdict(lambda:{"market_value":ZERO,"cost_basis":ZERO,"missing_price_count":0})
    exposure:dict[tuple[str,str],dict[str,Any]]=defaultdict(lambda:{"market_value":ZERO,"symbols":set(),"memberships":[]})
    for position in positions:
        currency=position["currency"]; total=totals[currency]
        total["cost_basis"]+=Decimal(str(position["average_cost"]))*Decimal(str(position["shares"]))
        if position["market_value"] is None: total["missing_price_count"]+=1; continue
        value=Decimal(str(position["market_value"])); total["market_value"]+=value
        refs=memberships.get(position["symbol"],[])
        if not refs: refs=[{"industry":"unclassified","effective_date":None,"membership_snapshot_hash":None,"provenance_id":None}]
        share=value/len(refs)
        for ref in refs:
            bucket=exposure[(currency,ref["industry"])]
            bucket["market_value"]+=share; bucket["symbols"].add(position["symbol"]); bucket["memberships"].append({"symbol":position["symbol"],**ref})
    exposure_rows=[]
    for (currency,industry),value in exposure.items():
        snapshot=json.dumps(sorted(value["memberships"],key=lambda row:(row["symbol"],row["industry"])),sort_keys=True,separators=(",",":"))
        exposure_rows.append({**common,"currency":currency,"industry":industry,"market_value":value["market_value"],
            "portfolio_ratio":value["market_value"]/totals[currency]["market_value"] if totals[currency]["market_value"] else None,
            "allocation_method":"equal_weight_per_membership_v1","symbols":json.dumps(sorted(value["symbols"])),
            "membership_snapshot":snapshot,"membership_snapshot_hash":"sha256:"+sha256(snapshot.encode()).hexdigest()})
    active_ids={str(row["reverses_event_id"]) for row in rows if row.get("event_action")=="REVERSAL"}
    active=[row for row in rows if row.get("event_action")!="REVERSAL" and str(row["event_id"]) not in active_ids]
    performance=[]
    for currency in sorted({row["currency"] for row in active}):
        flows=[]
        for row in active:
            if row["currency"]!=currency: continue
            fee=Decimal(str(row.get("fee") or 0)); tax=Decimal(str(row.get("tax") or 0))
            if row["event_type"]=="BUY": amount=-(Decimal(str(row["shares"]))*Decimal(str(row["price"]))+fee+tax)
            elif row["event_type"]=="SELL": amount=Decimal(str(row["shares"]))*Decimal(str(row["price"]))-fee-tax
            elif row["event_type"]=="CASH_DIV": amount=Decimal(str(row["cash_amount"]))-fee-tax
            else: continue
            flows.append((row["trade_date"],amount))
        terminal=totals[currency]["market_value"]
        if terminal: flows.append((valuation_date,terminal))
        result={"status":"insufficient_data","value":None} if totals[currency]["missing_price_count"] else xirr(flows)
        performance.append({**common,"year":valuation_date.year,"currency":currency,"xirr_status":result["status"],
            "xirr":result["value"],"cash_flow_count":len(flows),"method":"xirr_actual_365_v1"})
    scenarios=(("broad_market_down_20",Decimal("-0.20")),("sector_shock_down_30",Decimal("-0.30")),
               ("liquidity_shock_down_15",Decimal("-0.15")))
    stress=[]; summary=[]
    minimum_cash=Decimal(str(profile["minimum_cash_ratio"])) if profile and profile.get("minimum_cash_ratio") is not None else None
    for currency,total in totals.items():
        for scenario,shock in scenarios:
            stress.append({**common,"currency":currency,"scenario_id":scenario,"shock":shock,
                "portfolio_value_before":total["market_value"],"portfolio_value_after":total["market_value"]*(1+shock),
                "loss":total["market_value"]*shock,"cash_safety_status":"insufficient_data","cash_ratio":None,
                "minimum_cash_ratio":minimum_cash,"valuation_status":"partial" if total["missing_price_count"] else "available",
                "method":"deterministic_parallel_shock_v1"})
        summary.append({**common,"currency":currency,"market_value":total["market_value"],"cost_basis":total["cost_basis"],
            "unrealized_pnl":total["market_value"]-total["cost_basis"] if not total["missing_price_count"] else None,
            "missing_price_count":total["missing_price_count"],"cash_safety_status":"insufficient_data",
            "cash_ratio":None,"minimum_cash_ratio":minimum_cash})
    return {"mart_user_exposure":exposure_rows,"mart_user_annual_performance":performance,
            "mart_user_stress_tests":stress,"mart_user_portfolio_summary":summary}


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
                 assistant_cleanup: Callable[[Any],None] | None = None,
                 memberships: Callable[[set[str],date],dict[str,list[dict[str,Any]]]] | None = None) -> None:
        self.repository,self.store,self.prices,self.assistant_cleanup=repository,store,prices,assistant_cleanup
        self.memberships=memberships or (lambda _symbols,_when:{})

    def run(self, valuation_date: date, limit: int = 500) -> int:
        checkpoint=self.repository.pipeline_checkpoint(); changes=self.repository.pipeline_batch(checkpoint,limit)
        completed=checkpoint
        if changes:
            user_ids={row["user_id"] for row in changes}
            for user_id in user_ids:
                ledger=self.repository.ledger_for_pipeline(user_id)
                watchlist=self.repository.watchlist_for_pipeline(user_id)
                profile=self.repository.investment_profile_for_pipeline(user_id)
                self.store.upsert("ledger_events",ledger)
                self.store.upsert("watchlist_events",[{**row,"change_version":row["version"]} for row in watchlist])
                if profile: self.store.upsert("investment_profile_revisions",[profile])
                symbols={row["symbol"] for row in ledger}
                marts=calculate_marts(ledger,self.prices(symbols,valuation_date),valuation_date)
                for table,rows in marts.items():
                    self.store.upsert(table,rows)
                for table,rows in calculate_risk_marts(ledger,marts["mart_user_positions"],profile,
                                                       self.memberships(symbols,valuation_date),valuation_date).items():
                    self.store.upsert(table,rows)
            completed=changes[-1]["change_id"]
            self.repository.advance_pipeline_checkpoint(completed)
        for request in self.repository.pending_deletions():
            self.store.delete_user(request["user_id"])
            if self.assistant_cleanup is None:
                self.repository.mark_deletion_cleanup_pending(request["request_id"],request["user_id"])
                continue
            self.assistant_cleanup(request["user_id"])
            self.repository.complete_deletion(request["request_id"],request["user_id"])
        return completed


def main() -> None:
    from packages.postgres_bundle import load_postgres_bundle
    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "PRIVATE_DATABASE_URL": ("pipeline_database_url", "database_url"),
        "PRIVATE_CATALOG_PASSWORD": ("pipeline_catalog_password", "catalog_password"),
    })
    if os.getenv("ASSISTANT_STORAGE_ACCEPTANCE") == "true":
        from .assistant_storage_acceptance import run
        run()
        print("private assistant GCS/Iceberg acceptance passed")
        return
    from .repository import repository_from_env
    from .store import PrivateIcebergStore
    from .mcp_gateway import McpGatewayClient

    if os.getenv("MCP_GATEWAY_URL") and os.getenv("MCP_OWNER_SIGNING_KEY"):
        gateway=McpGatewayClient.from_env()
        def cleanup(user_id: Any) -> None:
            gateway.logout_codex_session(user_id)
            gateway.destroy_codex_auth(user_id)
    else:
        cleanup=None
    market=CorePriceReader.from_env()
    completed=PrivatePipeline(repository_from_env(),PrivateIcebergStore.from_env(),market,cleanup,market.memberships).run(
        date.fromisoformat(os.getenv("VALUATION_DATE",date.today().isoformat())))
    print(f"private pipeline checkpoint={completed}")


if __name__ == "__main__": main()
