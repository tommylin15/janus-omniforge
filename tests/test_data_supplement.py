import unittest
import json
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock, patch
from ingestion_core.data_supplement import months_ending, normalise_monthly


class DataSupplementTests(unittest.TestCase):
    def test_backfill_stages_original_bytes_commits_history_and_composes_snapshot(self):
        from ingestion_core.data_supplement import run_backfill
        from ingestion_core.stage import LocalObjectStore
        from packages.duckdb_query import DuckDBEngine, DuckDBIcebergCore
        from pyiceberg.catalog import load_catalog
        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 2, 12, tzinfo=tz)

        control = MagicMock()
        control.connection.cursor.return_value.__enter__.return_value.fetchall.return_value = [("5876", "上海商銀", "TWSE")]
        control.source_is_approved.return_value = True
        control.enqueue_collection.return_value = SimpleNamespace(execution_id="bounded-test")
        control.complete_collection.return_value = (SimpleNamespace(status=SimpleNamespace(value="partial")), None)

        def upstream(url, payload=None):
            query = parse_qs(urlparse(url).query)
            if "t57sb01" in url:
                year = int(query["year"][0])+1911
                cells = ["5876", f"{year-1911} 年 第二季", "財務報告書", "", "", "IFRSs合併財報", "",
                         f'<a href=\'javascript:readfile2("A","5876","{year}02_5876_AI1.pdf");\'>file</a>',
                         "100", f"{year-1911}/08/14 15:00:00", "無"]
                html = "<tr><th>上傳日期</th><th>電子檔案</th></tr><tr>"+"".join(f"<td>{c}</td>" for c in cells)+"</tr>"
                return html.encode("big5"), "big5"
            if "t164sb01" in url:
                year = int(query["SYEAR"][0])
                html = f'''<ix:nonNumeric name="tifrs-notes:CompanyID">5876</ix:nonNumeric>
                <ix:nonNumeric name="tifrs-notes:Year">{year}</ix:nonNumeric>
                <ix:nonNumeric name="tifrs-notes:Quarter">2</ix:nonNumeric>
                <ix:nonNumeric name="tifrs-notes:ReportCategory">Consolidated report</ix:nonNumeric>
                <xbrli:context id="q"><xbrli:entity><xbrli:identifier>5876</xbrli:identifier></xbrli:entity>
                <xbrli:period><xbrli:startDate>{year}-04-01</xbrli:startDate><xbrli:endDate>{year}-06-30</xbrli:endDate></xbrli:period></xbrli:context>
                <xbrli:unit id="EPS"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:TWD</xbrli:measure></xbrli:unitNumerator>
                <xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>
                <ix:nonFraction name="ifrs-full:BasicEarningsLossPerShare" contextRef="q" unitRef="EPS" format="ixt:numdotdecimal" scale="0">1.04</ix:nonFraction>'''
                return html.encode(), "utf-8"
            if payload:
                return json.dumps({"code": 200, "result": {"yymm": f"{payload['year']}{int(payload['month']):02d}",
                    "companyAbbreviation": "上海商銀", "data": [["本月", "1,000"]]}}).encode(), "utf-8"
            year, month = int(query["date"][0][:4]), int(query["date"][0][4:6])
            day = f"{year-1911}/{month:02d}/01"
            if "STOCK_DAY" in url:
                return json.dumps({"data": [[day, "1000", "1500", "1", "2", "0.5", "1.5", "0", "0"]]}).encode(), "utf-8"
            return json.dumps({"fields": ["日期", "收盤指數"], "data": [[day, "20000"]]}).encode(), "utf-8"

        Path(".tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path(".tmp")) as folder:
            root = Path(folder)
            warehouse = (root/"warehouse").relative_to(Path.cwd()).as_posix()
            catalog = load_catalog("unit", type="sql", uri="sqlite:///"+str(root/"catalog.db").replace("\\", "/"), warehouse=warehouse)
            core = DuckDBIcebergCore(catalog, warehouse, engine=DuckDBEngine(temp_directory=str(root/"duckdb")))
            stores = lambda bucket: LocalObjectStore(root/bucket)
            with patch("ingestion_core.__main__._control_plane", return_value=control), patch("ingestion_core.__main__._iceberg_core", return_value=core), \
                 patch("ingestion_core.__main__.GcsObjectStore", side_effect=stores), patch("ingestion_core.data_supplement.GcsObjectStore", side_effect=stores), \
                 patch("ingestion_core.data_supplement._fetch", side_effect=upstream), patch("ingestion_core.data_supplement.datetime", FixedDatetime), \
                 patch.dict("os.environ", {"JANUS_DATA_SUPPLEMENT_SYMBOLS": "5876", "CORE_BUCKET": "core", "STAGE_BUCKET": "stage"}):
                summary = run_backfill()
            self.assertEqual(summary["failures"], [])
            self.assertEqual(summary["coverage"]["5876"]["revenue_months"], 12)
            self.assertEqual(summary["coverage"]["5876"]["financial_quarters"], 4)
            self.assertFalse(summary["coverage"]["5876"]["history_complete"])
            ready = control.complete_collection.call_args.args[1]
            self.assertEqual(ready["featureVersion"], "2")
            manifest = json.loads(stores("core").read("executions/bounded-test/core-snapshot.json"))
            self.assertEqual(set(manifest["iceberg_tables"]), {"core.financials_v1", "core.ohlcv_v1", "core.benchmark_v1"})
            self.assertTrue(list((root/"stage").rglob("*.html")))
            control.put_admin_setting.assert_called_once()

    def test_monthly_window_and_unknown_publication_preserve_period_and_units(self):
        self.assertEqual(months_ending(2026, 2, 3), [(2025, 11), (2026, 0), (2026, 1)])
        document = {"code": 200, "result": {"yymm": "11508", "companyAbbreviation": "國巨*",
                     "data": [["本月", "16,332,196"], ["本年累計", "115,085,359"]]}}
        row = normalise_monthly(document, "2327", 2026, 8, received_at="2026-10-02T01:00:00Z", expected_name="國巨*")[0]
        self.assertEqual((row["value"], row["unit"], row["fiscal_period_end"]), ("16332196000", "TWD", "2026-08-31"))
        self.assertIsNone(row["published_at"])
        self.assertFalse(row["publication_time_authoritative"])
        self.assertEqual(row["availability_at"], "2026-10-02T01:00:00Z")
        for broken in (
            {**document, "code": 400},
            {**document, "result": {**document["result"], "yymm": "11507"}},
            {**document, "result": {**document["result"], "companyAbbreviation": "台積電"}},
            {**document, "result": {**document["result"], "data": [["本月", "NaN"]]}},
        ):
            with self.assertRaises(ValueError):
                normalise_monthly(broken, "2327", 2026, 8, received_at="2026-10-02T01:00:00Z", expected_name="國巨*")
