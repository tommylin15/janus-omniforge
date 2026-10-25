"""Weekly-or-change deterministic reports; no provider calls or trading signals."""
from datetime import date
from math import isfinite
from packages.analysis_product import content_hash

VERSION = "stock-report-weekly-change-v1"
ROLES = ("quant", "risk", "fundamental", "valuation")


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def report_decision(current, previous=None, *, force=False):
    today = date.fromisoformat(current["analysis_as_of"])
    if not previous:
        return True, "first_report"
    prior = date.fromisoformat(previous["report_as_of"])
    if today < prior:
        raise ValueError("report cannot move backwards")
    if force:
        return True, "on_demand"
    if previous.get("policy_version") != VERSION:
        return True, "policy_changed"
    if current["model_signature"] != previous["model_signature"]:
        return True, "model_changed"
    if current["financial_input_hash"] != previous["financial_input_hash"]:
        return True, "financial_changed"
    if current["input_signature"] == previous["input_signature"]:
        return False, "same_inputs"
    close, old_close = current.get("latest_close"), previous.get("latest_close")
    if _number(close) and _number(old_close) and old_close > 0 and abs(close / old_close - 1) >= .05:
        return True, "price_move_5pct"
    if (today - prior).days >= 7:
        return True, "weekly_new_inputs"
    return False, "reuse_until_change_or_week"


def attach_stock_report(payload, analyst, previous_payload=None, *, force=False):
    """Daily facts stay fresh; reused report retains its original date and hash."""
    previous = (previous_payload or {}).get("stock_report")
    if previous:
        if previous.get("report_hash") != content_hash({k: v for k, v in previous.items() if k != "report_hash"}):
            raise ValueError("previous stock report hash mismatch")
        if previous.get("symbol") != payload["symbol"]:
            raise ValueError("previous stock report symbol mismatch")
    specialists = [s for s in payload["specialists"] if s["role"] in ROLES]
    # Versioned ML serving is separate from deterministic compatibility roles.
    # Never infer an ACTIVE ML result from a baseline or the presence of a report.
    serving = payload.get("four_model_serving") or {}
    serving_roles = [{
        "role": role, "status": (serving.get(role) or {}).get("status", "NOT_VERIFIED"),
        "model_version": (serving.get(role) or {}).get("model_version"),
        "model_sha256": (serving.get(role) or {}).get("model_sha256"),
        "output_name": (serving.get(role) or {}).get("output_name"),
        "prediction": (serving.get(role) or {}).get("prediction"),
        "input_as_of": (serving.get(role) or {}).get("input_as_of"),
    } for role in ROLES]
    model_signature = content_hash({
        "baseline": [{"role": s["role"], "model_version": s.get("model_version"),
                      "feature_version": s.get("feature_version"),
                      "model_status": s.get("model_status")}
                     for s in sorted(specialists, key=lambda x: x["role"])],
        "serving": [{k: r[k] for k in ("role", "status", "model_version", "model_sha256", "output_name")}
                    for r in serving_roles]})
    current = {"analysis_as_of": payload["analysis_as_of"], "latest_close": analyst.get("latest_close"),
        "financial_input_hash": analyst["financial_input_hash"], "model_signature": model_signature,
        "input_signature": content_hash({"roles": analyst["roles"], "latest_close": analyst.get("latest_close"),
                                         "financial_input_hash": analyst["financial_input_hash"],
                                         "serving": serving_roles})}
    due, reason = report_decision(current, previous, force=force)
    if due:
        report = {"schema_version": "stock-report.v1", "policy_version": VERSION,
            "symbol": payload["symbol"], "report_as_of": payload["analysis_as_of"],
            "inputs_as_of": {r: analyst["roles"][r]["input_as_of"] for r in ROLES},
            "source_execution_id": payload["execution_id"],
            "model_signature": model_signature, "input_signature": current["input_signature"],
            "financial_input_hash": current["financial_input_hash"], "latest_close": current["latest_close"],
            "generation_reason": reason, "report_kind": "deterministic_facts_not_ceo",
            "roles": [{k: s.get(k) for k in ("role", "model_version", "model_status", "status",
                                            "metrics", "missing_data", "plain_language")} for s in specialists],
            "input_gaps": {r: analyst["roles"][r]["missing_features"] for r in ROLES},
            "serving_roles": serving_roles,
            "model_readiness": "USE_ROLE_STATUS_NOT_IMPLIED_BY_REPORT", "llm_api_tokens": 0}
        report["report_hash"] = content_hash(report)
    else:
        report = previous
    payload["stock_report"] = report
    payload["stock_report_refresh"] = {"generated": due, "reason": reason,
                                       "checked_as_of": payload["analysis_as_of"]}
    return payload
