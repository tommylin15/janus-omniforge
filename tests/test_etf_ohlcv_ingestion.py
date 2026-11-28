"""Offline tests for registered-ETF official EOD OHLCV ingestion and bounded backfill."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ingestion_core.adapters import SourceResponse
from ingestion_core.control import AuthorizationStatus, CollectionConfig, SQLiteControlPlane
from ingestion_core.etf_ohlcv_backfill import backfill_registered_etf_ohlcv
from ingestion_core.sources import parse_registered_etf_ohlcv
from ingestion_core.stage import LocalObjectStore, StageWriter


def _twse_mi_index_bytes(
    day: str = "20261127",
    extra_rows: list[list[str]] | None = None,
    *,
    stat: str = "OK",
) -> bytes:
    fields = [
        "證券代號",
        "證券名稱",
        "成交股數",
        "成交筆數",
        "成交金額",
        "開盤價",
        "最高價",
        "最低價",
        "收盤價",
    ]
    rows = [
        ["2330", "台積電", "10,000,000", "50,000", "10,000,000,000", "990", "1,010", "985", "1,000"],
        ["0050", "元大台灣50", "25,000,000", "30,000", "2,310,000,000", "92.00", "92.80", "91.90", "92.40"],
        ["0056", "元大高股息", "12,000,000", "15,000", "560,000,000", "46.80", "47.10", "46.70", "46.97"],
        ["00878", "國泰永續高股息", "18,000,000", "22,000", "520,000,000", "29.10", "29.35", "29.05", "29.26"],
        ["00919", "群益台灣精選高息", "14,000,000", "18,000", "400,000,000", "28.60", "28.80", "28.55", "28.72"],
        ["00999", "未註冊ETF", "100,000", "100", "1,000,000", "10.00", "10.10", "9.90", "10.05"],
        ["0051", "休市無成交ETF", "0", "0", "0", "--", "--", "--", "--"],
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return json.dumps(
        {"stat": stat, "date": day, "tables": [{"fields": fields, "data": rows}]},
        ensure_ascii=False,
    ).encode("utf-8")


def _tpex_daily_quotes_bytes(day: str = "2026/11/27") -> bytes:
    fields = ["代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "均價", "成交股數", "成交金額(元)"]
    bond_rows = [
        ["00719B", "元大美債1-3", "31.68", "+0.05", "31.60", "31.70", "31.59", "31.65", "500,000", "15,825,000"],
        ["00697B", "元大美債7-10", "34.95", "+0.10", "34.88", "35.00", "34.85", "34.92", "300,000", "10,476,000"],
    ]
    dup_and_other = [
        ["00719B", "元大美債1-3", "31.68", "+0.05", "31.60", "31.70", "31.59", "31.65", "500,000", "15,825,000"],
        ["6488", "環球晶", "400.00", "+5.00", "396.00", "402.00", "395.00", "399.00", "1,000,000", "399,000,000"],
    ]
    return json.dumps(
        {
            "stat": "ok",
            "date": day,
            "tables": [
                {"title": "其他表格", "fields": ["欄位A"], "data": [["x"]]},
                {"title": "ETF", "fields": fields, "data": bond_rows},
                {"title": "上櫃股票行情", "fields": fields, "data": dup_and_other},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")


def test_parse_registered_etf_ohlcv_twse_extracts_only_allowed_and_skips_untraded():
    raw = _twse_mi_index_bytes()
    observed = datetime(2026, 11, 27, tzinfo=timezone.utc)
    rows = parse_registered_etf_ohlcv(
        raw,
        market="TWSE",
        source_id="twse",
        expected_date=date(2026, 11, 27),
        allowed_symbols={"0050", "0056", "00878", "00919", "0051"},
        observed_at=observed,
    )
    assert [row["symbol"] for row in rows] == ["0050", "0056", "00878", "00919"]
    assert all(row["market"] == "TWSE" and row["trade_date"] == "2026-11-27" for row in rows)
    assert all(row["source_id"] == "twse" and row["change_percent"] is None for row in rows)
    assert rows[0]["close"] == "92.40"
    assert rows[0]["volume_shares"] == 25_000_000
    assert rows[0]["turnover_twd"] == "2310000000"

    with pytest.raises(ValueError, match="requested trading date"):
        parse_registered_etf_ohlcv(
            raw,
            market="TWSE",
            source_id="twse",
            expected_date=date(2026, 11, 26),
            allowed_symbols={"0050"},
            observed_at=observed,
        )


def test_parse_registered_etf_ohlcv_tpex_multi_table_deduplicates():
    raw = _tpex_daily_quotes_bytes()
    rows = parse_registered_etf_ohlcv(
        raw,
        market="TPEX",
        source_id="tpex",
        expected_date=date(2026, 11, 27),
        allowed_symbols={"00719B", "00697B"},
        observed_at=datetime(2026, 11, 27, tzinfo=timezone.utc),
    )
    assert [(row["symbol"], row["market"], row["close"]) for row in rows] == [
        ("00719B", "TPEX", "31.68"),
        ("00697B", "TPEX", "34.95"),
    ]


def test_sqlite_control_plane_registered_etf_symbols_handles_provenance_table():
    with SQLiteControlPlane() as control:
        assert control.registered_etf_symbols() == ()
        control.connection.execute(
            """CREATE TABLE official_instrument_identity_provenance (
                   symbol TEXT PRIMARY KEY,
                   instrument_kind TEXT NOT NULL
               )"""
        )
        now_iso = datetime(2026, 11, 27, tzinfo=timezone.utc).isoformat()
        for sym, name, market, enabled, kind in (
            ("2330", "台積電", "TWSE", 1, "EQUITY"),
            ("0050", "元大台灣50", "TWSE", 1, "ETF"),
            ("0056", "元大高股息", "TWSE", 0, "ETF"),
            ("00719B", "元大美債1-3", "TPEX", 1, "BOND_ETF"),
        ):
            control.connection.execute(
                """INSERT INTO stock_master(symbol, name, market, enabled, updated_at, listing_status, effective_from)
                   VALUES (?, ?, ?, ?, ?, 'listed', ?)""",
                (sym, name, market, enabled, now_iso, now_iso),
            )
            control.connection.execute(
                "INSERT INTO official_instrument_identity_provenance(symbol, instrument_kind) VALUES (?, ?)",
                (sym, kind),
            )
        control.connection.commit()
        assert control.registered_etf_symbols() == ("0050", "00719B")
        assert control.registered_etf_symbols("TWSE") == ("0050",)
        assert control.registered_etf_symbols("TPEX") == ("00719B",)


def test_collect_stage_market_volume_publishes_registered_etfs_without_polluting_equity_universe(monkeypatch):
    from ingestion_core import __main__ as entry

    control = MagicMock()
    control.get_collection_config.return_value = SimpleNamespace(source_ids=("twse",), market="TWSE")
    control.config_symbols.return_value = ("2330",)
    control.enabled_stock_symbols.return_value = ("2330", "0050")
    control.registered_etf_symbols.return_value = ("0050",)
    control.portfolio_coverage_symbols.return_value = ()
    control.get_admin_setting.return_value = None
    control.full_market_snapshot.return_value = {
        "status": "available",
        "version": 1,
        "items": [
            {"symbol": "2330", "market": "TWSE", "stock_name": "台積電"},
            {"symbol": "6488", "market": "TPEX", "stock_name": "環球晶"},
        ],
    }

    stored_objects: dict[str, bytes] = {}

    class Store:
        def __init__(self, bucket):
            self.bucket = bucket

        def create(self, name, payload, media_type):
            stored_objects[name] = payload
            return True

        def read(self, name):
            return stored_objects[name]

        def delete(self, name):
            stored_objects.pop(name, None)

        def list(self, prefix):
            return tuple(sorted(name for name in stored_objects if name.startswith(prefix)))

    core_writes: list[dict] = []

    class Core:
        IDENTIFIERS = {"ohlcv": ("symbol", "market", "trade_date")}

        def table_identifier(self, dataset_id):
            return f"core.{dataset_id}_v1"

        def table_exists(self, dataset_id):
            return False

        def write(self, **kwargs):
            core_writes.append(kwargs)
            return SimpleNamespace(
                inserted=len(kwargs["rows"]),
                updated=0,
                reused=0,
                row_count=len(kwargs["rows"]),
                snapshot_id=777,
                table_identifier=f"core.{kwargs['dataset_id']}_v1",
                metadata_location="gs://core/meta.json",
            )

        def close(self):
            pass

    projection_calls: list[dict] = []

    class Projection:
        DATASETS = frozenset({"ohlcv"})

        @classmethod
        def from_env(cls):
            return cls()

        def publish(self, dataset_id, rows, **kwargs):
            projection_calls.append({"dataset_id": dataset_id, "rows": rows, **kwargs})
            return len(rows)

        def materialize_home_market_snapshot(self):
            return {"status": "succeeded", "as_of": "2026-11-27"}

    raw_bytes = _twse_mi_index_bytes()
    equity_row = {
        "symbol": "2330",
        "stock_name": "台積電",
        "market": "TWSE",
        "trade_date": "2026-11-27",
        "volume_shares": 10_000_000,
        "turnover_twd": "10000000000",
        "open": "990",
        "high": "1010",
        "low": "985",
        "close": "1000",
        "source_id": "twse",
        "observed_at": "2026-11-27T00:00:00Z",
    }

    monkeypatch.setattr(entry, "GcsObjectStore", Store)
    monkeypatch.setattr(entry, "_iceberg_core", lambda _: Core())
    monkeypatch.setattr("ingestion_core.serving_projection.StockServingProjection", Projection)
    monkeypatch.setattr(
        entry,
        "dataset_adapters",
        lambda: {
            "twse-market-volume": SimpleNamespace(
                source_id="twse",
                dataset_id="market-volume",
                market="TWSE",
                batch_scope="market",
            )
        },
    )
    monkeypatch.setattr(
        entry,
        "_fetch_source",
        lambda *_: SourceResponse(
            rows=(equity_row,),
            observed_at=datetime(2026, 11, 27, tzinfo=timezone.utc),
            raw_payload=raw_bytes,
            source_url="https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
        ),
    )
    for key, value in {
        "STAGE_BUCKET": "stage",
        "CORE_BUCKET": "core",
        "INGESTION_DATE": "2026-11-27",
        "INGESTION_DATASETS": "twse-market-volume",
        "FORCE_REFRESH": "true",
        "STAGE_EXECUTION_SCOPED": "false",
        "STOCK_SERVING_PROJECTION_ENABLED": "true",
    }.items():
        monkeypatch.setenv(key, value)

    entry.collect_stage(control=control)

    ohlcv_write = next(call for call in core_writes if call["dataset_id"] == "ohlcv")
    written_symbols = [row["symbol"] for row in ohlcv_write["rows"]]
    assert written_symbols == ["2330", "0050"]
    assert "00999" not in written_symbols

    ohlcv_pub = next(call for call in projection_calls if call["dataset_id"] == "ohlcv")
    assert [row["symbol"] for row in ohlcv_pub["rows"]] == ["2330", "0050"]
    assert ohlcv_pub["provenance_id"] == ohlcv_write["provenance_id"]
    assert ohlcv_pub["core_snapshot_id"] == 777

    # Ordinary-equity stock_master profile refresh & coverage remain untouched.
    refreshed_rows = control.refresh_official_stock_profiles.call_args.args[0]
    assert [row["symbol"] for row in refreshed_rows] == ["2330"]
    inventory_key = next(k for k in stored_objects if k.endswith("coverage-inventory.json"))
    inventory = json.loads(stored_objects[inventory_key])
    ohlcv_cov = next(item for item in inventory["items"] if item["dataset"] == "ohlcv" and item["market"] == "TWSE")
    assert ohlcv_cov["expected"] == ["2330"]
    assert ohlcv_cov["received"] == ["2330"]
    assert ohlcv_cov["missing"] == []
    assert ohlcv_cov["etf_received_count"] == 1


def test_backfill_registered_etf_ohlcv_end_to_end_and_bounds(tmp_path):
    with SQLiteControlPlane() as control:
        now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        now_iso = now.isoformat()
        control.connection.execute(
            """CREATE TABLE official_instrument_identity_provenance (
                   symbol TEXT PRIMARY KEY,
                   instrument_kind TEXT NOT NULL
               )"""
        )
        for sym, name, market, kind in (
            ("0050", "元大台灣50", "TWSE", "ETF"),
            ("0056", "元大高股息", "TWSE", "ETF"),
            ("00719B", "元大美債1-3", "TPEX", "BOND_ETF"),
        ):
            control.connection.execute(
                """INSERT INTO stock_master(symbol, name, market, enabled, updated_at, listing_status, effective_from)
                   VALUES (?, ?, ?, 1, ?, 'listed', ?)""",
                (sym, name, market, now_iso, now_iso),
            )
            control.connection.execute(
                "INSERT INTO official_instrument_identity_provenance(symbol, instrument_kind) VALUES (?, ?)",
                (sym, kind),
            )
        control.connection.commit()

        control.put_collection_config(
            CollectionConfig(
                config_id="first-batch",
                dataset_id="ohlcv",
                source_ids=("twse", "tpex"),
                expected_fields=frozenset({"close"}),
                market="TWSE",
                batch_scope="market",
                authorization_status=AuthorizationStatus.OFFICIAL.value,
            ),
            symbols=("0050",),
        )

        before_master = control.connection.execute(
            "SELECT symbol, name, market, enabled FROM stock_master ORDER BY symbol"
        ).fetchall()

        stage_store = LocalObjectStore(tmp_path / "stage")
        writer = StageWriter(stage_store)

        core_calls: list[dict] = []

        class FakeCore:
            def write(self, **kwargs):
                core_calls.append(kwargs)
                return SimpleNamespace(inserted=len(kwargs["rows"]), updated=0, reused=0, snapshot_id=501)

        proj_calls: list[dict] = []

        class FakeProjection:
            def publish(self, dataset_id, rows, **kwargs):
                proj_calls.append({"dataset_id": dataset_id, "rows": rows, **kwargs})
                return len(rows)

        fetched_urls: list[str] = []

        def fake_fetch(url: str) -> bytes:
            fetched_urls.append(url)
            if "date=20261125" in url:
                return json.dumps({"stat": "很抱歉，沒有符合條件的資料!"}).encode("utf-8")
            if "date=20261126" in url:
                return _twse_mi_index_bytes("20261126")
            if "date=20261127" in url:
                return _twse_mi_index_bytes("20261127")
            if "date=2026%2F11%2F25" in url:
                return json.dumps({"stat": "ok", "tables": [{"fields": ["代號"], "data": []}]}).encode("utf-8")
            if "date=2026%2F11%2F26" in url:
                return _tpex_daily_quotes_bytes("2026/11/26")
            if "date=2026%2F11%2F27" in url:
                return _tpex_daily_quotes_bytes("2026/11/27")
            raise AssertionError(f"unexpected url: {url}")

        # 2026-11-25 (holiday), 2026-11-26 (Thu), 2026-11-27 (Fri), 2026-11-28 (Sat skipped)
        receipt = backfill_registered_etf_ohlcv(
            date(2026, 11, 25),
            date(2026, 11, 28),
            control=control,
            core=FakeCore(),
            writer=writer,
            projection=FakeProjection(),
            fetch=fake_fetch,
        )

        assert receipt["status"] == "succeeded"
        assert receipt["errors"] == []
        assert receipt["days_processed"] == 3  # Nov 25, 26, 27 (Nov 28 Saturday skipped)
        assert not any("20261128" in u or "2026%2F11%2F28" in u for u in fetched_urls)
        assert {(item["date"], item["market"]) for item in receipt["skipped_days"]} == {
            ("2026-11-25", "TWSE"),
            ("2026-11-25", "TPEX"),
        }
        assert receipt["per_day_counts"] == {
            "2026-11-26:TWSE": 2,
            "2026-11-26:TPEX": 1,
            "2026-11-27:TWSE": 2,
            "2026-11-27:TPEX": 1,
        }
        assert receipt["core_inserted"] == 6
        assert receipt["serving_published"] == 6
        assert len(core_calls) == 4
        assert len(proj_calls) == 4
        assert stage_store.list(f"executions/{receipt['execution_id']}/core-commit.json")

        after_master = control.connection.execute(
            "SELECT symbol, name, market, enabled FROM stock_master ORDER BY symbol"
        ).fetchall()
        assert after_master == before_master

        with pytest.raises(ValueError, match="exceed 31 days"):
            backfill_registered_etf_ohlcv(
                date(2026, 10, 1),
                date(2026, 11, 5),
                control=control,
                core=FakeCore(),
                writer=writer,
                projection=FakeProjection(),
                fetch=fake_fetch,
            )


def test_etf_ohlcv_backfill_workflow_and_script_contracts():
    root = Path(__file__).resolve().parents[1]
    wf_text = (root / ".github/workflows/etf-ohlcv-backfill-dev.yml").read_text(encoding="utf-8")
    assert "\n  schedule:" not in wf_text
    assert "workflow_dispatch:" in wf_text
    assert "janus-dev-runtime-writers" in wf_text
    assert "cancel-in-progress: false" in wf_text
    assert "backfill_etf_ohlcv_dev.py" in wf_text
