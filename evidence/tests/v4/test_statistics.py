import unittest

from scripts.v4.selection import accept_first
from scripts.v4.statistics import classification, paired_stratified_bootstrap, wilson


class StatisticsTests(unittest.TestCase):
    def test_no_acceptance_risk_is_na(self):
        r = classification(['FAIL', 'INDETERMINATE'], ['FAIL', 'PASS'])
        self.assertIsNone(r['accepted_risk'])
        self.assertEqual(r['FNR_bounds'], [0., 1.])

    def test_invalid_retained_in_denominator(self):
        r = classification(['PASS', 'PASS'], ['PASS', 'FAIL'], ['VALID', 'INVALID'])
        self.assertEqual(r['n'], 2)
        self.assertEqual(r['invalid'], 1)
        self.assertEqual(r['unknown_negative'], 1)
        self.assertEqual(r['correct_accept_per_assigned'], .5)

    def test_unknown_reference_not_forced_to_failure(self):
        r = classification(['PASS'], ['INDETERMINATE'])
        self.assertIsNone(r['FPR'])
        self.assertEqual(r['accepted_risk_bounds'], [0., 1.])

    def test_bootstrap_keeps_pairs(self):
        r = paired_stratified_bootstrap([0, 1, 1], [0, 1, 1], ['a', 'a', 'b'], draws=100)
        self.assertEqual(r['interval95'], [0., 0.])
        self.assertGreater(r['zero_discordance_iid_upper95'], 0.)

    def test_exact_zero_has_nonzero_uncertainty(self):
        self.assertGreater(wilson(0, 100)[1], 0)
        self.assertEqual(wilson(0, 0), [None, None])

    def test_selection_prefix_and_abstention(self):
        results = {'a': {'B5': 'INDETERMINATE'}, 'b': {'B5': 'PASS'}, 'c': {'B5': 'FAIL'}}
        self.assertIsNone(accept_first(['a', 'b', 'c'], results, 'B5', 1))
        self.assertEqual(accept_first(['a', 'b', 'c'], results, 'B5', 3), 'b')


if __name__ == '__main__':
    unittest.main()
