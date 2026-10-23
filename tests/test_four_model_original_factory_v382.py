from pathlib import Path
import sys, unittest
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'research/chatgpt' if (ROOT/'research/chatgpt').exists() else Path(__file__).resolve().parent
sys.path.insert(0,str(SRC))
from factor_factory_v1 import build_ohlcv_panel,build_revenue_panel,build_valuation_panel,build_financial_panel

class FeatureFactoryTests(unittest.TestCase):
    def make_prices(self):
        dt=pd.bdate_range('2025-01-01',periods=165)
        rows=[]
        for market in ('twse','tpex'):
            for symbol in ('1001','2001'):
                for i,t in enumerate(dt):
                    if symbol=='2001' and i==31:continue
                    c=100+i*.05
                    rows.append({'market':market,'symbol':symbol,'trade_date':t.strftime('%Y-%m-%d'),
                         'open':c-0.1,'high':c+1,'low':c-1,'close':c,'volume':1000+i*5,'turnover':c*(1000+i*5)})
        return pd.DataFrame(rows)
    def test_no_future_leakage_into_daily_x(self):
        raw=self.make_prices()
        x,y,m=build_ohlcv_panel(raw)
        self.assertFalse(any(c.startswith('forward_') or c.startswith('future_') or c.startswith('label_') for c in x))
        self.assertFalse(x.publication_allowed.any())
        self.assertTrue({'ret5','ret20','ret60','ret120','atr14_pct','amihud_illiquidity','turnover_mean20','volume_ratio20','realized_vol60','session_window_60_ok','ret20_market_rank'}.issubset(x.columns))
        self.assertTrue({'breadth_up_ratio','breadth_above_ma20'}.issubset(m))
        row=y.loc[(y.market=='twse')&(y.symbol=='1001')].iloc[100]
        self.assertEqual(str(row['mature_session_20'].date()),'2025-01-01' if False else str(pd.bdate_range('2025-01-01',periods=121)[120].date()))
        self.assertAlmostEqual(row['forward_return_20'],(100+120*.05)/(100+100*.05)-1)
        self.assertTrue(pd.isna(y.loc[(y.market=='twse')&(y.symbol=='1001')].iloc[-1]['forward_return_20']))
        # changing future prices cannot alter earlier X
        edited=raw.copy(); sel=(edited.market=='twse')&(edited.symbol=='1001')&(pd.to_datetime(edited.trade_date)>pd.Timestamp('2025-03-01'))
        edited.loc[sel,'close']*=1.02; edited.loc[sel,'high']*=1.02;edited.loc[sel,'low']*=1.02;edited.loc[sel,'open']*=1.02
        nx,_,_=build_ohlcv_panel(edited)
        keys=(x.market=='twse')&(x.symbol=='1001')&(x.trade_date<=pd.Timestamp('2025-03-01'))
        self.assertTrue(x.loc[keys,['ret20','volume_mean20','atr14_pct']].reset_index(drop=True).equals(nx.loc[keys,['ret20','volume_mean20','atr14_pct']].reset_index(drop=True)))
    def test_missing_session_does_not_shift(self):
        x,y,_=build_ohlcv_panel(self.make_prices())
        a=x[(x.market=='twse')&(x.symbol=='2001')].reset_index(drop=True)
        self.assertFalse(a.iloc[32]['session_window_20_ok'])
        z=y[(y.market=='twse')&(y.symbol=='2001')].reset_index(drop=True)
        self.assertTrue(pd.isna(z.iloc[20]['forward_return_20']))
    def test_duplicate_rejected(self):
        d=self.make_prices();d=pd.concat([d,d.iloc[[0]]],ignore_index=True)
        with self.assertRaisesRegex(ValueError,'duplicate'):build_ohlcv_panel(d)
    def test_monthly_revenue_pit_and_label_separation(self):
        months=pd.period_range('2024-01','2026-06',freq='M')
        a=pd.DataFrame([{'market':'twse','symbol':'1001','fiscal_month':str(m),'revenue_twd':100+i,'published_at':None} for i,m in enumerate(months)])
        x,y=build_revenue_panel(a)
        self.assertTrue(pd.notna(x.loc[x.fiscal_month=='2025-01','revenue_yoy']).all())
        self.assertFalse(x.pit_eligible.any())
        self.assertTrue(pd.isna(y.iloc[-1].label_next_revenue_yoy))
        self.assertFalse('label_next_revenue_yoy' in x.columns)
        self.assertFalse(x.publication_allowed.any())
    def test_valuation_y_isolated_and_bad_multiple_rows(self):
        a=pd.DataFrame([{'market':'twse','symbol':'1001','trade_date':'2025-01-03','pe_ratio':9,'pb_ratio':1.1,'published_at':None}])
        x,y=build_valuation_panel(a)
        self.assertNotIn('target_log_pe',x.columns)
        self.assertEqual(float(y['target_log_pe'].iloc[0]),float(np.log(9)))
        with self.assertRaisesRegex(ValueError,'duplicate'):build_valuation_panel(pd.concat([a,a]))
    def test_financial_units_not_automatic_pit(self):
        a=pd.DataFrame([{'market':'twse','symbol':'1001','fiscal_quarter':'2025Q1','dataset':'income','item':'營業收入','value':100,'unit_basis':'UNKNOWN','period_basis':'CUMULATIVE','published_at':None},
                        {'market':'twse','symbol':'1001','fiscal_quarter':'2025Q1','dataset':'balance','item':'資產總計','value':200,'unit_basis':'TWD','period_basis':'BALANCE','published_at':None}])
        x,audit=build_financial_panel(a)
        self.assertIn('fin_raw_sales',x)
        self.assertFalse(x.pit_eligible.any());self.assertFalse(x.publication_allowed.any())
        self.assertTrue(all(audit['status']=='RAW_UNIT_AND_PERIOD_BASIS_UNVERIFIED'))

if __name__=='__main__':unittest.main()

class OptionalFactorsTests(unittest.TestCase):
    def test_market_context(self):
        from factor_factory_v1 import build_market_index_panel
        idx=pd.DataFrame([{'market':'twse','trade_date':str(t.date()),'index_id':'TAIEX','close':100+i,
                           'available_at':None} for i,t in enumerate(pd.bdate_range('2025-01-01',periods=125))])
        x=build_market_index_panel(idx)
        self.assertIn('index_ret60',x)
        self.assertFalse(x.pit_eligible.any())
        self.assertFalse(x.publication_allowed.any())
    def test_membership_current_snapshot_cannot_backfill(self):
        from factor_factory_v1 import build_industry_panel
        raw=FeatureFactoryTests().make_prices()
        daily,_,_=build_ohlcv_panel(raw)
        m=pd.DataFrame([{'market':'twse','symbol':'1001','industry_code':'001','valid_from':'2025-01-01',
                         'valid_to':None,'first_observed_at':'2026-10-23'}])
        got=build_industry_panel(daily,m)
        self.assertEqual(len(got),0)
        m.loc[0,'first_observed_at']='2025-01-01'
        got=build_industry_panel(daily,m)
        self.assertGreater(len(got),0)
        self.assertFalse(got.publication_allowed.any())

class EventCandidateTests(unittest.TestCase):
    def test_no_auto_corporate_adjustment_or_benchmark_mix(self):
        from factor_factory_v1 import build_corporate_event_panel
        import json
        raw=pd.DataFrame([{'market':'twse','symbol':'1101','dataset':'split','published_at':None,
            'event_payload_json':json.dumps({'date':'2025-08-01','type':'split','available_at':'2026-10-22'})},
            {'market':'twse','symbol':'TAIEX','dataset':'benchmark_total_return','published_at':None,
            'event_payload_json':json.dumps({'date':'2025-08-01','return_basis':'TOTAL_RETURN_NOT_PRICE_INDEX'})}])
        out=build_corporate_event_panel(raw)
        self.assertTrue(out['action_multiplier'].isna().all())
        self.assertFalse(out['pit_eligible'].any())
        self.assertEqual(out['return_basis'].dropna().iloc[0],'TOTAL_RETURN_NOT_PRICE_INDEX')
