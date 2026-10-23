"""Research acceptance. Execute: python -m unittest -v test_experiment.py"""
from __future__ import annotations
import json,unittest
from pathlib import Path
import numpy as np,pandas as pd
import experiment as e

class TailChallengerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.panel,cls.common,cls.total=e.load()
  cls.pred=pd.read_csv(e.HERE/'predictions.csv',dtype={'symbol':str})
  cls.manifest=json.loads((e.HERE/'manifest.json').read_text())

 def test_source_fingerprint_and_same_cohort(self):
  self.assertEqual(len(self.pred),18106)
  self.assertEqual(len(self.common),18106)
  self.assertEqual(self.total,23101)
  self.assertEqual(self.manifest['source_sha256'][e.PANEL.name],e.checksum(e.PANEL))
  self.assertEqual(self.manifest['source_sha256'][e.OLD.name],e.checksum(e.OLD))
  self.assertFalse(self.pred.duplicated(['market','symbol','month']).any())

 def test_historical_pit_is_not_falsely_marked_true(self):
  self.assertFalse(self.panel.pit_eligible.astype(bool).any())
  self.assertFalse(self.panel.published_at.notna().any())
  self.assertFalse(self.pred.pit_verified.astype(bool).any())
  self.assertFalse(self.pred.publication_allowed.astype(bool).any())
  self.assertFalse(self.manifest['publication_allowed'])

 def test_no_historical_time_proxy_leakage(self):
  meta=[json.loads((e.HERE/f'fold_{m}.json').read_text()) for m in e.MONTHS]
  self.assertEqual(len(meta),12)
  for v in meta:
   self.assertLess(v['train_max_month'],v['month'])
   self.assertLessEqual(v['train_max_proxy_maturity'],v['month']+'-01')
   self.assertGreaterEqual(v['train_months'],12)

 def test_feature_columns_do_not_depend_on_y(self):
  self.assertEqual(len(e.FEATURES),15)
  self.assertNotIn('y',e.FEATURES)
  self.assertNotIn('target_revenue',e.FEATURES)
  self.assertNotIn('label_available_at',e.FEATURES)
  c=e.add_features(self.common)
  self.assertTrue(np.allclose(c.base_log_twd,np.log1p(c.prior_target_revenue)))
  self.assertTrue(np.isfinite(c.base_to_recent_log).all())

 def test_target_revenue_identity_vs_next_month_observation(self):
  nxt=self.pred[['market','symbol','month','y','prior_target_revenue']].copy()
  nxt['next_month']=(pd.PeriodIndex(nxt.month,freq='M')+1).astype(str)
  raw=self.panel[['market','symbol','month','revenue_twd']].rename(columns={'month':'next_month'})
  comp=nxt.merge(raw,on=['market','symbol','next_month'],how='left',validate='one_to_one')
  self.assertEqual(len(comp),18106)
  self.assertFalse(comp.revenue_twd.isna().any())
  pred=comp.prior_target_revenue*(1+comp.y/100)
  self.assertTrue(np.allclose(pred,comp.revenue_twd,rtol=1e-8,atol=100))

 def test_prediction_coverage_without_clipping_true_y(self):
  p=self.pred
  self.assertEqual(set(p.month),set(e.MONTHS))
  self.assertGreater(float(p.y.max()),3e6)
  self.assertFalse(p.y.isna().any())
  self.assertTrue((p.prior_target_revenue>0).all())
  for col in e.NEW_NAMES:
   self.assertTrue(np.isfinite(p[col]).all(),col)
  old=e.score(p,'combo_baseline')
  self.assertLess(old['n'],len(p)) # missing values preserved, never filled in silently

 def test_gate_is_fixed_train_only_and_coherent(self):
  p=self.pred
  self.assertGreater(int(p.low_base_gate.sum()),500)
  self.assertLess(int(p.low_base_gate.sum()),len(p)*.2)
  m=p.low_base_gate.astype(bool)
  self.assertTrue(np.allclose(p.loc[m,'lgb_regime_gate'],p.loc[m,'lgb_level_log']))
  self.assertTrue(np.allclose(p.loc[~m,'lgb_regime_gate'],p.loc[~m,'lgb_yoy_mae']))
  self.assertTrue(np.allclose(p.loc[m,'cat_regime_gate'],p.loc[m,'cat_level_log']))
  self.assertTrue(np.allclose(p.loc[~m,'cat_regime_gate'],p.loc[~m,'cat_yoy_mae']))

 def test_comparisons_month_paired_and_research_only(self):
  p=self.pred
  paired=pd.read_csv(e.HERE/'paired.csv')
  self.assertTrue((paired.n<=len(p)).all())
  self.assertTrue((paired.n>=17000).all())
  self.assertTrue((paired.positive_months<=12).all())
  self.assertTrue((paired.ci95_low<=paired.ci95_high).all())
  self.assertTrue((paired.already_exposed_test==True).all())
  self.assertFalse(paired.publication_allowed.any())

 def test_no_hidden_inference_of_quality_from_tail(self):
  p=self.pred
  flag=p.y.abs().ge(1000)
  self.assertGreater(int(flag.sum()),100)
  self.assertGreater(float(p.loc[flag,'low_base_gate'].mean()),.5)
  loss=np.abs(p.y-p.lgb_regime_gate)
  self.assertGreater(float(loss.nlargest(int(np.ceil(len(loss)*.01))).sum()/loss.sum()),.9)

if __name__=='__main__':unittest.main()
