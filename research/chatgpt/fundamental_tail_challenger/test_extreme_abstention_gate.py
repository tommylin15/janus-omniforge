"""Offline tests of X-only Fundamental abstention. No publication or deployment."""
import unittest
try:
    from .extreme_abstention_gate import classify
except ImportError:
    from extreme_abstention_gate import classify

T = {'base_twd_max': 600000.0, 'ratio_min': 10.4, 'abs_known_yoy_min_pp': 780.0}

class TestExtremeAbstentionGate(unittest.TestCase):
    def test_ordinary(self):
        q = classify(10_000_000, 12_000_000, 30, T)
        self.assertEqual(q.decision,'MODEL_ELIGIBLE_BY_TAIL_GATE')
        self.assertTrue(q.model_prediction_allowed_by_this_gate)
        self.assertFalse(q.publication_allowed)
    def test_tiny_base(self):
        q=classify(100_000,120_000,20,T)
        self.assertEqual(q.decision,'ANALYST_ONLY')
        self.assertIn('TINY_PRIOR_YEAR_TARGET_REVENUE',q.reason_codes)
    def test_ratio(self):
        q=classify(1_000_000,15_000_000,0,T)
        self.assertIn('UNUSUAL_TRAILING_REVENUE_TO_BASE_RATIO',q.reason_codes)
    def test_known_yoy_spike(self):
        q=classify(1_000_000,1_500_000,800,T)
        self.assertIn('EXTREME_KNOWN_CURRENT_YOY',q.reason_codes)
    def test_missing(self):
        self.assertEqual(classify(None,1_500_000,1,T).decision,'DATA_UNVERIFIED')
    def test_nonfinite(self):
        self.assertEqual(classify(float('inf'),1_500_000,1,T).decision,'DATA_UNVERIFIED')
    def test_zero_base(self):
        self.assertEqual(classify(0,1_500_000,1,T).decision,'ANALYST_ONLY')
    def test_impossible_known_yoy(self):
        self.assertEqual(classify(1_000_000,1_500_000,-101,T).decision,'DATA_UNVERIFIED')
    def test_bad_threshold(self):
        with self.assertRaises(ValueError):
            classify(1_000_000,1_500_000,1,{'base_twd_max':-1,'ratio_min':10,'abs_known_yoy_min_pp':100})

if __name__=='__main__':
    unittest.main()
