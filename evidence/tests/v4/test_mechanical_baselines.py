import unittest

import mujoco
import numpy as np

from scripts.v4.controls import Fixture, run_fixture
from scripts.v4.mechanical_baselines import signed_force_probe, static_feasibility


class MechanicalBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arrays, cls.metadata = run_fixture(Fixture('independent', 1, duration_s=9.))

    def factory(self):
        return mujoco.MjModel.from_xml_string(self.metadata['model_xml'])

    def test_bounded_two_pad_grasp_feasible(self):
        r = static_feasibility(self.arrays, self.metadata, self.factory)
        self.assertTrue(r['feasible'])
        self.assertLess(r['scaled_equilibrium_residual'], 1e-6)

    def test_small_actuator_bound_rejects(self):
        def weak():
            model = self.factory()
            model.actuator_forcerange[:] = [-.001, .001]
            return model
        self.assertFalse(static_feasibility(self.arrays, self.metadata, weak)['feasible'])

    def test_frictionless_pads_cannot_hold_gravity(self):
        def slippery():
            model = self.factory()
            model.geom_friction[:, 0] = 0
            return model
        self.assertFalse(static_feasibility(self.arrays, self.metadata, slippery)['feasible'])

    def test_no_contacts_rejects(self):
        def missing():
            model = self.factory()
            model.geom_contype[:] = model.geom_conaffinity[:] = 0
            return model
        self.assertFalse(static_feasibility(self.arrays, self.metadata, missing)['feasible'])

    def test_unbounded_actuator_is_not_applicable(self):
        def unsupported():
            model = self.factory()
            model.actuator_forcelimited[:] = False
            return model
        self.assertEqual(static_feasibility(self.arrays, self.metadata, unsupported)['status'], 'NOT_APPLICABLE')

    def test_probe_cost_and_immutability(self):
        before = self.arrays['snapshot_state'].copy()
        r = signed_force_probe(self.arrays, self.metadata, self.factory)
        self.assertEqual(r['physics_steps'], 3000)
        self.assertEqual(len(r['branches']), 6)
        self.assertTrue(r['robust'])
        self.assertTrue(np.array_equal(before, self.arrays['snapshot_state']))

    def test_assistance_is_unreachable_not_rejection(self):
        a = dict(self.arrays)
        a['steps'] = self.arrays['steps'].copy()
        a['steps'][0, self.metadata['step_columns'].index('applied_any')] = 1
        self.assertEqual(signed_force_probe(a, self.metadata, self.factory)['status'], 'UNREACHABLE')


if __name__ == '__main__':
    unittest.main()
