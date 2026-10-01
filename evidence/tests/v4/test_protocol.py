from dataclasses import asdict
import unittest

from scripts.v4.contracts import Calibration
from scripts.v4.protocol import REQUIRED, validate_protocol


class ProtocolTests(unittest.TestCase):
    def protocol(self):
        p = {k: 'registered' for k in REQUIRED}
        p.update(calibration=asdict(Calibration()), risk_max=.05, delta_min=.05,
                 utility=dict(route='U2', k_primary=6), branch=dict(horizon_s=3, times={'controls': 8}),
                 sample_sizes=dict(controls=240, allegro_scenes=120, allegro_candidates=720, fetch=100, dexgraspbench=100),
                 design_hashes={str(i): 'hash' for i in range(5)})
        return p

    def test_missing_each_required_field_rejected(self):
        for key in REQUIRED:
            p = self.protocol()
            del p[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_protocol(p)

    def test_complete_protocol(self):
        validate_protocol(self.protocol())

    def test_missing_threshold_rejected(self):
        for key in ('risk_max', 'delta_min'):
            p = self.protocol()
            p[key] = 0
            with self.assertRaises(ValueError):
                validate_protocol(p)

    def test_unregistered_route_rejected(self):
        p = self.protocol()
        p['utility']['route'] = 'U1'
        with self.assertRaises(ValueError):
            validate_protocol(p)

    def test_missing_fixed_branch_time_rejected(self):
        p = self.protocol()
        p['branch'].pop('times')
        with self.assertRaises(ValueError):
            validate_protocol(p)


if __name__ == '__main__':
    unittest.main()
