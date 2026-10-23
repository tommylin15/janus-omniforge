"""Offline tests: TPEx independent calendar and research checkpoint integrity. No network access."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parent / 'market_sector_tpex_v2.py'
spec = importlib.util.spec_from_file_location('tpex_independent_v2', MODULE_PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def days(month='2026-02', n=14):
    from datetime import date, timedelta
    current=date.fromisoformat(month+'-01')
    out=[]
    while len(out)<n:
        if current.weekday()<5:out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def month_payload(month, source, dates=None):
    dates=dates or days(month)
    if source == 'market':
        return {'stat':'ok','tables':[{'title':'櫃買指數（月查詢）',
            'fields':['日期','開市','最高','最低','收市'],
            'data':[[d.replace('-','/'),'201.00','204.00','199.00','203.00'] for d in dates]}]}
    fields=['日期']+['半導體業','電子工業','鋼鐵工業','紡織纖維','化學工業','資訊服務業',
                   '觀光餐旅','航運業','其他電子業','通信網路業','光電業','電子通路業',
                   '電子零組件業','數位雲端','居家生活','文化創意業','電機機械',
                   '綠能環保','電腦及週邊設備業','半導體業報酬指數']
    return {'stat':'ok','tables':[{'title':'產業分類指數(月查詢)',
            'fields':fields,'data':[[d.replace('-','/')]+['133.33']*20 for d in dates]}]}


def daily_payload(day):
    names=['櫃買指數','半導體業','電子工業','鋼鐵工業','紡織纖維','化學工業','資訊服務業',
           '觀光餐旅','航運業','其他電子業','通信網路業','光電業','電子通路業']
    return {'stat':'ok','date':day.replace('-',''),
        'tables':[{'title':'櫃買指數暨產業分類指數(日查詢)',
        'fields':['類股名稱','收市','漲跌','開市','最高','最低'],
        'data':[[nm,'203.00','1.0','201.00','204.00','199.00'] for nm in names]}]}


class TPExIndependentCalendar(unittest.TestCase):
    def test_month_market_standalone_sector_uses_it(self):
        market=m.parse_tpex(month_payload('2026-02','market'), '2026-02','tpex_market')
        self.assertEqual(len(market),14)
        sector=m.parse_tpex(month_payload('2026-02','sector'),'2026-02','tpex_sector',
                            [r['trade_date'] for r in market])
        self.assertEqual(len(sector),14*19)
        self.assertNotIn('報酬',set(r['index_id'] for r in sector))

    def test_month_sector_date_gap_fails_closed(self):
        expected=days()
        with self.assertRaisesRegex(m.SourceError,'CALENDAR_MISMATCH'):
            m.parse_tpex(month_payload('2026-02','sector',expected[:-1]),'2026-02',
                         'tpex_sector',expected)

    def test_market_self_partial_fails_closed(self):
        with self.assertRaisesRegex(m.SourceError,'DAYCOUNT'):
            m.parse_tpex(month_payload('2026-02','market',days(n=6)), '2026-02', 'tpex_market')

    def test_no_twse_dependency_and_resumable_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m.ROOT=root; m.OUT=root/'資料源'/'trial'
            m.START_MONTH=m.END_MONTH='2026-02'
            m.states.clear();m.n_requests=0
            calls=[]
            def get_json(url,params=None,method='GET'):
                calls.append(url)
                p=month_payload('2026-02','market' if url==m.TPEX['tpex_market'] else 'sector')
                return p,m.jbytes(p),url+'?date=2026/02/01'
            with patch.object(m,'get_json',side_effect=get_json):
                report=m.run()
            self.assertEqual(len(calls),2)
            self.assertTrue(all('tpex.org.tw' in url for url in calls))
            self.assertEqual(report['summary']['tpex_market']['verified'],1)
            self.assertEqual(report['summary']['tpex_sector']['verified'],1)
            self.assertTrue((m.OUT/'progress_tpex_latest.csv').is_file())
            self.assertFalse((m.OUT/'progress_latest.csv').exists())
            old=(m.OUT/'tpex_market'/'2026-02'/'receipt.json').read_bytes()
            with patch.object(m,'get_json',side_effect=AssertionError('cache must skip')):
                again=m.run()
            self.assertEqual(again['summary']['tpex_market']['verified'],1)
            self.assertEqual(old,(m.OUT/'tpex_market'/'2026-02'/'receipt.json').read_bytes())

    def test_market_month_fallback_uses_tpex_sector_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            m.ROOT=Path(tmp);m.OUT=Path(tmp)/'trial'
            dates=days()
            calls=[]
            def get_json(url,params=None,method='GET'):
                calls.append(url)
                if url==m.TPEX['tpex_market']:
                    raise m.SourceError('NON_JSON_RESPONSE')
                if url==m.TPEX['tpex_sector']:
                    payload=month_payload('2026-02','sector')
                else:
                    day=params['date'].replace('/','-')
                    payload=daily_payload(day)
                return payload,m.jbytes(payload),url
            m._daily_cache.clear()
            with patch.object(m,'get_json',side_effect=get_json):
                rows,raw,url=m.fetch_tpex('tpex_market','2026-02')
            self.assertEqual(len(rows),len(dates))
            self.assertEqual(calls.count(m.TPEX['tpex_market']),1)
            self.assertEqual(calls.count(m.TPEX['tpex_sector']),1)
            self.assertEqual(calls.count(m.TPEX_DAILY),len(dates))
            self.assertEqual(len(json.loads(raw)['requests']),len(dates))

    def test_prior_corrupted_raw_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            m.ROOT=Path(tmp);m.OUT=Path(tmp)/'trial'
            rows=m.parse_tpex(month_payload('2026-02','market'),'2026-02','tpex_market')
            m.save_verified('tpex_market','2026-02',rows,b'{"stat":"ok"}','https://www.tpex.org.tw/')
            folder=m.OUT/'tpex_market'/'2026-02'
            raw=next(folder.glob('raw-*.json'))
            raw.write_bytes(b'bad')
            with self.assertRaisesRegex(m.SourceError,'CHECKSUM_MISMATCH'):
                m.verified_rows('tpex_market','2026-02')

if __name__=='__main__':unittest.main()
