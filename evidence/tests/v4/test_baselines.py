import unittest

import numpy as np

from scripts.v4.baselines import confusion, historical, verdict
from test_contracts import COLUMNS, example


class BaselineTests(unittest.TestCase):
    def run_example(self, example_tuple):
        a, q, meta, gap = example_tuple
        return historical(dict(steps=a, common_q=q, geometry_gap=gap), dict(meta, step_columns=COLUMNS))

    def test_normal_baseline_requires_normal_force_field(self):
        self.assertEqual(verdict(self.run_example(example())['B4_normal']), 'INDETERMINATE')

    def test_no_geometry_ablation_is_strong_baseline(self):
        r = self.run_example(example())
        self.assertEqual(r['B4'], r['A_no_geometry'])

    def test_accumulated_not_native_without_explicit_equivalence(self):
        e = example(9000)
        e[1][4500] = False
        r = self.run_example(e)
        self.assertEqual(verdict(r['B0']), 'PASS')
        self.assertEqual(verdict(r['B1']), 'FAIL')
        self.assertIn('proxy', r['B0']['scope'])

    def test_clearance_detects_positive_inactive_record(self):
        e = example()
        e[0][:, COLUMNS.index('env_count')] = 1
        e[0][:, COLUMNS.index('env_dist_present')] = 1
        r = self.run_example(e)
        self.assertEqual(verdict(r['B2']), 'FAIL')
        self.assertEqual(verdict(r['B3']), 'PASS')
        self.assertEqual(verdict(r['B5']), 'PASS')

    def test_incomplete_paths_cannot_certify(self):
        e = example()
        e[2]['support_paths']['complete_for_declared_model'] = False
        self.assertEqual(verdict(self.run_example(e)['B3']), 'INDETERMINATE')

    def test_no_unknown_relabeling(self):
        r = confusion(['PASS', 'FAIL', 'INDETERMINATE'], ['FAIL', 'PASS', 'FAIL'])
        self.assertEqual((r['false_accept'], r['false_reject'], r['unknown']), (1, 1, 1))
        self.assertEqual(r['reference_negative'], 2)
        self.assertEqual(r['false_accept_rate'], .5)

    def test_invalid_evidence_not_failure(self):
        e = example()
        e[0][20, 2] = np.nan
        r = self.run_example(e)
        self.assertTrue(all(verdict(v) == 'INDETERMINATE' for v in r.values()))


if __name__ == '__main__':
    unittest.main()
