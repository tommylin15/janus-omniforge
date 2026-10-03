import unittest
from decimal import Decimal
from ingestion_core.financial_publication import parse_filing_index, parse_correction_index, parse_xbrl_report, normalise_xbrl_financials


class FilingPublicationTests(unittest.TestCase):
    def test_inline_eps_and_signed_cash_flow_preserve_context_basis(self):
        html = '''<ix:nonNumeric name="tifrs-notes:CompanyID">5876</ix:nonNumeric>
        <ix:nonNumeric name="tifrs-notes:Year">2026</ix:nonNumeric>
        <ix:nonNumeric name="tifrs-notes:Quarter">2</ix:nonNumeric>
        <ix:nonNumeric name="tifrs-notes:ReportCategory">Consolidated report</ix:nonNumeric>
        <xbrli:context id="q2"><xbrli:entity><xbrli:identifier>5876</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
        <xbrli:context id="h1"><xbrli:entity><xbrli:identifier>5876</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
        <xbrli:unit id="TWD"><xbrli:measure>iso4217:TWD</xbrli:measure></xbrli:unit>
        <xbrli:unit id="EPS"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:TWD</xbrli:measure></xbrli:unitNumerator>
        <xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>
        <ix:nonFraction name="ifrs-full:BasicEarningsLossPerShare" contextRef="q2" unitRef="EPS" format="ixt:numdotdecimal" scale="0">1.04</ix:nonFraction>
        <ix:nonFraction name="ifrs-full:CashFlowsFromUsedInOperatingActivities" contextRef="h1" unitRef="TWD" format="ixt:numdotdecimal" scale="3" sign="-">49,399,929</ix:nonFraction>'''
        rows = parse_xbrl_report(html, "5876", 2026, 2)
        self.assertEqual([(r["period_basis"], r["value"], r["unit"]) for r in rows],
                         [("single_quarter", "1.04", "TWD_per_share"), ("year_to_date", "-49399929000", "TWD")])
        self.assertTrue(all(not r["numeric_revision_verified"] for r in rows))
        research = normalise_xbrl_financials(html, "5876", 2026, 2, received_at="2026-10-02T01:00:00Z")
        self.assertEqual([r["metric"] for r in research], ["eps_single_quarter", "operating_cash_flow_year_to_date"])
        self.assertTrue(all(r["published_at"] is None and r["availability_at"] == "2026-10-02T01:00:00Z" for r in research))
        comparative = html[html.index('<xbrli:context id="q2"'):html.index('<xbrli:context id="h1"')].replace('id="q2"', 'id="prior"').replace("2026", "2025")
        comparative += '<ix:nonFraction name="ifrs-full:BasicEarningsLossPerShare" contextRef="prior" unitRef="EPS" format="ixt:numdotdecimal" scale="0">0.52</ix:nonFraction>'
        paired = normalise_xbrl_financials(html+comparative, "5876", 2026, 2, received_at="2026-10-02T01:00:00Z")
        growth = next(r for r in paired if r["metric"] == "eps_yoy_percent_same_filing")
        self.assertEqual(Decimal(growth["value"]), 100)
        self.assertEqual((growth["unit"], growth["comparison_period_end"], growth["context_id"]), ("percent", "2025-06-30", "q2|prior"))
        self.assertEqual(growth["share_basis_status"], "same_filing_reported_comparison")
        self.assertTrue(all(r["published_at"] is None and r["availability_at"] == "2026-10-02T01:00:00Z" for r in paired))
        for broken in (comparative.replace('>0.52<', '>0<'), comparative.replace('2025-04-01', '2025-02-01'), comparative.replace('unitRef="EPS"', 'unitRef="TWD"')):
            rows = normalise_xbrl_financials(html+broken, "5876", 2026, 2, received_at="2026-10-02T01:00:00Z")
            self.assertFalse(any(r["metric"] == "eps_yoy_percent_same_filing" for r in rows))
        with self.assertRaises(ValueError):
            normalise_xbrl_financials(html, "5876", 2026, 2, received_at="2026-10-02")
        for broken in (html.replace("5876", "2801"), html.replace("scale=\"3\"", "scale=\"9\""),
                       html + html[html.index('<ix:nonFraction name="ifrs-full:Basic'):].split('</ix:nonFraction>')[0].replace('1.04', '1.05')+'</ix:nonFraction>'):
            with self.assertRaises(ValueError):
                parse_xbrl_report(broken, "5876", 2026, 2)
        with self.assertRaises(ValueError):
            parse_xbrl_report(html, "5876", 2026, 1)

    def test_official_upload_identity_and_time_fail_closed(self):
        cells = ["2327", "115 年 第二季", "財務報告書", "", "", "IFRSs合併財報", "",
                 '<a href=\'javascript:readfile2("A","2327","202602_2327_AI1.pdf");\'>file</a>',
                 "2150692", "115/08/14 15:04:28", "無"]
        html = "<tr><th>上傳日期</th><th>電子檔案</th></tr><tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"
        row = parse_filing_index(html, "2327", 2026)[0]
        self.assertEqual(row["official_uploaded_at"], "2026-08-14T15:04:28+08:00")
        self.assertFalse(row["numeric_revision_verified"])
        self.assertEqual(row["report_scope"], "consolidated")
        self.assertEqual(parse_filing_index(html.replace("IFRSs合併財報", "IFRSs英文版-合併財報"), "2327", 2026), [])
        with self.assertRaises(ValueError):
            parse_filing_index(html.replace("202602_", "202601_"), "2327", 2026)
        with self.assertRaises(ValueError):
            parse_filing_index(html.replace("115/08/14 15:04:28", ""), "2327", 2026)
        with self.assertRaises(ValueError):
            parse_filing_index("服務暫停", "2327", 2026)
        separate = html.replace("IFRSs合併財報", "IFRSs個別財報").replace("AI1.pdf", "AI2.pdf")
        self.assertEqual(parse_filing_index(separate, "2327", 2026), [])
        self.assertEqual(parse_filing_index(separate, "2327", 2026, report_scope="separate")[0]["report_scope"], "separate")
        with self.assertRaises(ValueError):
            parse_filing_index(separate.replace("AI2.pdf", "AI1.pdf"), "2327", 2026, report_scope="separate")

    def test_correction_date_does_not_invent_numeric_revision_or_time(self):
        html = '''<input name="YEAR_SEASON" value="202602">
        <tr><th>公司代號</th><th>公告日期</th><th>詳細資料</th></tr>
        <tr><td>1605</td><td>華新</td><td>20260814</td><td>IFRSs合併財報</td>
        <td>關係人交易</td><td><input onclick='document.fm.SKEY.value="1";
        document.fm.CID.value="1605";document.fm.RID.value="4";
        document.fm.DTYPE.value="I1";'></td></tr>'''
        row = parse_correction_index(html, 2026, 2)[0]
        self.assertEqual(row["official_announcement_date"], "2026-08-14")
        self.assertEqual(row["time_precision"], "date")
        self.assertFalse(row["numeric_revision_verified"])
        with self.assertRaises(ValueError):
            parse_correction_index(html, 2025, 2)
        with self.assertRaises(ValueError):
            parse_correction_index(html.replace('CID.value="1605"', 'CID.value="2327"'), 2026, 2)
