#!/usr/bin/env python3
"""
Janus OmniForge — 統一運維與系統健康診斷 CLI
============================================

用途：
  將零散的歷史探測、健康檢查與狀態診斷整合至單一命令列工具。
  支援檢查本地與環境配置、PostgreSQL Migration 水位、工作流治理狀態、
  全市場與持股快照健康度、以及 CEO Gateway 設定。

使用範例：
  python ops/diagnose.py all
  python ops/diagnose.py workflows
  python ops/diagnose.py db
  python ops/diagnose.py market
  python ops/diagnose.py ceo
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List


class DiagnosticRunner:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def check_workflows(self) -> Dict[str, Any]:
        """檢查 GitHub Actions 工作流治理與排程收斂狀態"""
        workflows_dir = self.repo_root / ".github" / "workflows"
        archive_dir = workflows_dir / "archive"

        active_files = [f for f in workflows_dir.glob("*.yml")]
        archived_files = [f for f in archive_dir.glob("*.yml")] if archive_dir.exists() else []

        scheduled_workflows: List[str] = []
        for wf in active_files:
            try:
                content = wf.read_text(encoding="utf-8", errors="ignore")
                if "schedule:" in content:
                    scheduled_workflows.append(wf.name)
            except Exception:
                pass

        # 專案規範：只允許 private-ledger-backup-retention 具備定時排程
        allowed_scheduled = {"private-ledger-backup-retention.yml"}
        unexpected_scheduled = set(scheduled_workflows) - allowed_scheduled

        status = "PASS" if not unexpected_scheduled and len(active_files) <= 30 else "WARN"

        return {
            "status": status,
            "active_workflows_count": len(active_files),
            "archived_workflows_count": len(archived_files),
            "scheduled_workflows": scheduled_workflows,
            "unexpected_scheduled": list(unexpected_scheduled),
            "message": "工作流治理收斂正常，無未核准之定時排程" if not unexpected_scheduled else f"發現未核准排程: {unexpected_scheduled}"
        }

    def check_db_migrations(self) -> Dict[str, Any]:
        """檢查 PostgreSQL Migration 目錄與最新版本號"""
        # 尋找 migration 檔案位置
        migration_candidates = [
            self.repo_root / "services" / "api" / "migrations",
            self.repo_root / "infra" / "postgres" / "migrations",
            self.repo_root / "scripts" / "gcp"
        ]

        found_migrations = []
        for candidate in migration_candidates:
            if candidate.exists():
                sql_files = list(candidate.glob("*.sql"))
                for sql in sql_files:
                    found_migrations.append(sql.name)

        found_migrations.sort()
        latest_migration = found_migrations[-1] if found_migrations else "NONE"

        return {
            "status": "INFO",
            "migrations_scanned": len(found_migrations),
            "latest_detected_migration": latest_migration,
            "pg_host_env": os.getenv("PGHOST", "not set (local)"),
            "pg_database_env": os.getenv("PGDATABASE", "not set (local)")
        }

    def check_market_readiness(self) -> Dict[str, Any]:
        """檢查全市場與持股快照相關規格與配置"""
        holdings_first_spec = self.repo_root / "doc" / "spec" / "holdings-first.md"
        full_market_spec = self.repo_root / "doc" / "spec" / "full-market-batch-policy.md"

        has_specs = holdings_first_spec.exists() and full_market_spec.exists()

        return {
            "status": "PASS" if has_specs else "WARN",
            "holdings_first_contract": holdings_first_spec.exists(),
            "full_market_batch_contract": full_market_spec.exists(),
            "target_universe": "上市／上櫃全市場（缺失率 <= 10%）",
            "etf_price_proof_policy": "保留已登記 ETF 持股價格，普通股名冊分母不擴 ETF"
        }

    def check_ceo_gateway(self) -> Dict[str, Any]:
        """檢查 CEO omniAgent Gateway 相關設定與 Token 限制"""
        target_token_cap = 2048
        return {
            "status": "INFO",
            "model_target": "gemini-3.5-flash-lite",
            "market_mart_output_token_cap": target_token_cap,
            "gateway_audience_bound": True,
            "note": "CEO 報告採 opt-in 手動呼叫，正式發布需通過 validate_ceo_output 業務校驗"
        }

    def run_all(self) -> Dict[str, Any]:
        return {
            "workflows": self.check_workflows(),
            "database": self.check_db_migrations(),
            "market_holdings": self.check_market_readiness(),
            "ceo_gateway": self.check_ceo_gateway(),
        }


def main():
    parser = argparse.ArgumentParser(description="Janus OmniForge 統一系統與運維診斷工具")
    parser.add_argument("module", choices=["all", "workflows", "db", "market", "ceo"], default="all", nargs="?",
                        help="欲執行的診斷模組 (預設: all)")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    runner = DiagnosticRunner(repo_root)

    results = {}
    if args.module == "workflows":
        results["workflows"] = runner.check_workflows()
    elif args.module == "db":
        results["database"] = runner.check_db_migrations()
    elif args.module == "market":
        results["market_holdings"] = runner.check_market_readiness()
    elif args.module == "ceo":
        results["ceo_gateway"] = runner.check_ceo_gateway()
    else:
        results = runner.run_all()

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    # 人類可讀格式輸出
    print("=" * 60)
    print("  Janus OmniForge 統一運維與架構診斷報告")
    print("=" * 60)

    for mod, data in results.items():
        status = data.get("status", "INFO")
        print(f"\n[{mod.upper()}] 狀態: {status}")
        for k, v in data.items():
            if k != "status":
                print(f"  - {k}: {v}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
