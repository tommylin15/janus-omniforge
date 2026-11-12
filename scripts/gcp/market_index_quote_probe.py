"""Bounded public TAIEX lightweight quote acceptance; no credentials or Owner data."""
import argparse
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal

TAIPEI = timezone(timedelta(hours=8))
PATH = "/api/v1/public/market-index-quote"
SOURCES = {"shioaji", "twse_mis"}
STATUSES = {"updated", "fresh", "idle", "unavailable", "in_flight", "blocked", "throttled"}


def probe(base, observe_seconds=0):
    def read(force=False):
        req = urllib.request.Request(base.rstrip("/") + PATH + ("?force=true" if force else ""),
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as response:
            assert response.status == 200
            assert "no-store" in response.headers.get("Cache-Control", "")
            body = json.loads(response.read(64000))
        assert body["schema_version"] == "market-index-quote.v1" and body["symbol"] == "TAIEX"
        assert body["refresh_status"] in STATUSES
        checked = datetime.fromisoformat(body["checked_at"])
        assert checked.tzinfo is not None
        section = body["section"]
        if section is None:
            return {"session": body["session"], "refresh": body["refresh_status"], "quote": None}
        data = section["data"]
        price = Decimal(str(data["close"]))
        assert price.is_finite() and price > 0
        day = datetime.fromisoformat(section["as_of"]).date()
        source = data["quote_source"]
        state = data["quote_state"]
        raw_at = data.get("quote_at")
        at = datetime.fromisoformat(raw_at) if raw_at else None
        if at is not None:
            assert at.tzinfo is not None and at.astimezone(TAIPEI).date() == day
            assert at <= datetime.now(TAIPEI) + timedelta(seconds=5)
        assert state in {"intraday", "closing_pending_eod", "stale", "eod_final"}
        if state == "intraday":
            assert source in SOURCES and at is not None
            assert day == datetime.now(TAIPEI).date()
            assert (datetime.now(TAIPEI) - at).total_seconds() <= 125
        return {"session": body["session"], "refresh": body["refresh_status"],
                "quote": {"day": str(day), "source": source, "state": state, "at": raw_at}}

    first = read()
    # Explicit manual path; allow one bounded recheck for in-flight/cache
    # contention, but never relabel a missing or old provider tick as live.
    second = read(True)
    if second["session"] == "regular":
        for delay in (3, 8):
            if second["quote"] and second["quote"]["state"] == "intraday":
                break
            time.sleep(delay)
            second = read()
        assert second["quote"] and second["quote"]["state"] == "intraday", "index_live_quote_unavailable"
    if first["quote"] and second["quote"]:
        old, new = first["quote"], second["quote"]
        assert new["day"] >= old["day"], "index_date_regressed"
        if new["at"] and old["at"]:
            assert datetime.fromisoformat(new["at"]) >= datetime.fromisoformat(old["at"]), "index_tick_regressed"
    observation = {"status": "NOT_REQUESTED"}
    if observe_seconds:
        assert 15 <= observe_seconds <= 20
        observation = {"status": "OFF_SESSION", "interval_seconds": observe_seconds}
        if second["session"] == "regular":
            baseline = second["quote"]
            samples = []
            for _ in range(2):
                time.sleep(observe_seconds)
                sample = read()
                samples.append(sample)
                if (sample["quote"] and sample["quote"]["state"] == "intraday"
                        and datetime.fromisoformat(sample["quote"]["at"]) >
                            datetime.fromisoformat(baseline["at"])):
                    break
            observation = {"status": "ADVANCED" if samples[-1]["quote"]
                           and samples[-1]["quote"]["state"] == "intraday"
                           and datetime.fromisoformat(samples[-1]["quote"]["at"]) >
                               datetime.fromisoformat(baseline["at"]) else "NOT_ADVANCED",
                           "interval_seconds": observe_seconds, "samples": samples}
            print(json.dumps({"scope": "public_index_quote_observation",
                              "baseline": baseline, **observation}, sort_keys=True))
            assert observation["status"] == "ADVANCED", "index_real_timestamp_did_not_advance"
    print(json.dumps({"result": "PASS", "scope": "public_index_quote_auto_and_manual",
                      "first": first, "last": second, "observation": observation}, sort_keys=True))
    return first, second


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--observe-seconds", type=int, default=0)
    args = parser.parse_args()
    probe(args.base, args.observe_seconds)
