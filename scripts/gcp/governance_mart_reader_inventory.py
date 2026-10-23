#!/usr/bin/env python3
"""C1-A bounded Mart code-reference audit plus GET-only deployed reader inventory.

This is a *reference* inventory, not proof that absence of a literal means
there are no dynamic/indirect readers or that a deployed revision matches main.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as gcp

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "governance-mart-reader-inventory.json"
SCAN_DIRS = ("jobs", "packages", "apps", "infra", "scripts", "research", ".github")
SUFFIXES = {".py", ".sql", ".dart", ".yaml", ".yml", ".sh"}
SKIP_DIRS = {"tests", "test", "archive", "__pycache__", ".git", "node_modules"}
TABLE_NAMES = (
    "mart_screening_signals_v1",
    "mart_core_alpha_v1",
    "mart_risk_portfolio_v1",
    "mart_alternative_sentiment_v1",
    "mart_market_regime_daily_v1",
    "mart_sector_rotation_daily_v1",
    "mart_topic_trends_daily_v1",
    "mart_candidate_health_v1",
    "mart_daily_brief_v1",
    "mart_llm_narratives_v1",
)
MAX_CODE_FILES = 2000
MAX_FILE_BYTES = 1_000_000
MAX_MATCHES = 400

def code_references():
    files = []
    for directory in SCAN_DIRS:
        top = ROOT / directory
        if not top.exists():
            continue
        for path in top.rglob("*"):
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            rel = path.relative_to(ROOT)
            # The inventory's own table-name allowlist is NOT a business reader.
            if path.resolve() == Path(__file__).resolve():
                continue
            if any(segment.lower() in SKIP_DIRS for segment in rel.parts):
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            files.append(path)
    if len(files) > MAX_CODE_FILES:
        raise ValueError("reader_scan_file_limit_exceeded")
    patterns = {table: re.compile(r"\b" + re.escape(table[:-3]) + r"(?:_v1)?\b")
                for table in TABLE_NAMES}
    refs = {name: [] for name in TABLE_NAMES}
    for path in sorted(files):
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8",errors="replace").splitlines(),1):
            for table, pat in patterns.items():
                if pat.search(line):
                    if sum(len(x) for x in refs.values()) >= MAX_MATCHES:
                        raise ValueError("reader_scan_reference_limit_exceeded")
                    refs[table].append({"path": relative, "line": line_number,
                                        "reference_kind": ("DECLARATION_ONLY" if relative == "jobs/intelligence-mart/intelligence_mart/storage.py" else "LITERAL_OR_HANDLE_ONLY")})
    return len(files), refs

def deployed_context():
    resources = [("service", "janus-api"),
                 ("job", "janus-intelligence-mart"),
                 ("job", "janus-ingestion-core")]
    results = []
    for kind, name in resources:
        path = gcp.ROOT + ("/services/" if kind == "service" else "/jobs/") + name
        row = {"kind": kind, "name": name, "state": "UNREADABLE"}
        try:
            doc = gcp.cloud(path)  # GET only; never print the raw job/service configuration
            if doc.get("name") != path:
                raise ValueError("resource_name_mismatch")
            template = doc.get("template", {})
            if kind == "job":
                template = template.get("template", {})
            image = (template.get("containers") or [{}])[0].get("image","")
            match = re.search(r"@sha256:([a-f0-9]{64})$",image)
            row.update(state="READABLE", updated_time=doc.get("updateTime"),
                       generation=doc.get("generation"),
                       image_digest_sha256=match.group(1) if match else None,
                       latest_ready_revision=doc.get("latestReadyRevision"))
        except Exception as e:
            row["error_class"] = type(e).__name__[:64]
        results.append(row)
    return results

def main():
    scanned, refs = code_references()
    deployed = deployed_context()
    out = {"component": "janus_governance_c1a_mart_reader_inventory_v1",
           "checked_at_utc": datetime.now(timezone.utc).isoformat(),
           "source_git_sha": __import__("os").environ.get("GITHUB_SHA","UNKNOWN"),
           "status": "CODE_SCAN_PASS_RUNTIME_PARTIAL" if any(r["state"]!="READABLE" for r in deployed)
                   else "CODE_SCAN_AND_DEPLOYED_METADATA_PASS",
           "source": "current GitHub checkout only; not necessarily deployed reader code",
           "scanned_files": scanned, "references_by_table": refs,
           "shared_dynamic_maintenance": "jobs/intelligence-mart/intelligence_mart/retention.py loops all MartMaintenanceStore.IDENTIFIERS and table scans",
           "deployed_readers": deployed,
           "actual_per_table_reader_usage": "UNKNOWN_NO_TABLE_LEVEL_RUNTIME_TRACE",
           "no_literal_hit_means_no_reader": False,
           "read_only": True, "data_mutations": 0, "iam_changes": 0,
           "new_resources": 0}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print("JANUS_GOVERNANCE_C1A_MART_READER_INVENTORY_V1:" +
          json.dumps({"status":out["status"],"scanned_files":scanned,
                      "references": {k:len(v) for k,v in refs.items()},
                      "deployed_readers":deployed,"data_mutations":0},sort_keys=True))
    return out

if __name__ == "__main__":
    main()
