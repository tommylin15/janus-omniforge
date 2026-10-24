from pathlib import Path
import gzip
import csv
import json
import tempfile
import unittest
import valuation_v22_integrate as m

HERE=Path(__file__).resolve().parent

class V22IntegrationTests(unittest.TestCase):
    def test_input_guards(self):
        self.assertFalse(m.is_positive(0))
        self.assertFalse(m.is_positive(-1))
        self.assertFalse(m.is_positive(None))
        self.assertFalse(m.is_positive(float('nan')))
        self.assertTrue(m.is_positive('2.2'))
        self.assertEqual(str(m.last_day('2024-02')), '2024-02-29')
    def test_v22_full_raw_replay_and_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            stats=m.assemble(HERE/'input',Path(d))
            self.assertEqual(stats['tasks_replayed'],311)
            self.assertEqual(stats['distinct_positive_recovered_months'],2672)
            self.assertEqual(stats['remaining_below_30_pairs_full_roster'],836)
            self.assertEqual(stats['remaining_below_30_pairs_among_311'],117)
            self.assertEqual(stats['pe']['after_30'],1325)
            self.assertEqual(stats['pb']['after_30'],1799)
            with gzip.open(Path(d)/'01_valuation_v22_monthly_overlay.csv.gz','rt',encoding='utf-8-sig') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2672)
            self.assertEqual(len({(x['market'],x['symbol'],x['branch'],x['month']) for x in rows}),2672)
            self.assertTrue(all(x['month']<'2023-10' and x['publication_allowed']=='False' for x in rows))
            gate=json.loads((Path(d)/'05_model_training_gate.json').read_text())
            self.assertEqual(gate['state'],'BLOCKED_NOT_TRAINED')
            self.assertFalse(gate['publication_allowed'])
    def test_frozen_plan_is_unchanged(self):
        import hashlib
        p=HERE/'input/frozen_plan_v22.json'
        before=hashlib.sha256(p.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as d:m.assemble(HERE/'input',Path(d))
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),before)

if __name__=='__main__':unittest.main()
