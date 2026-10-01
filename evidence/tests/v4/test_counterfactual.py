import unittest

import mujoco
import numpy as np

from scripts.v4.controls import Fixture, run_fixture
from scripts.v4.counterfactual import _relative_pose, branch_fixture, endpoint, remove_target_environment
from scripts.v4.control_reference import adjudicate


class CounterfactualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = {name: run_fixture(Fixture(name, i, duration_s=11.05))
                       for i, name in enumerate(('independent', 'necessary_floor', 'redundant_floor'))}

    def test_full_state_sham_and_causal_cells(self):
        expected = dict(independent='BOTH_RETAIN', necessary_floor='DEPENDENT', redundant_floor='BOTH_RETAIN')
        for name, (arrays, metadata) in self.records.items():
            with self.subTest(name=name):
                result = branch_fixture(arrays, metadata)
                self.assertEqual(result['status'], 'VALID')
                self.assertTrue(result['sham_bit_equal'])
                self.assertEqual(result['cell'], expected[name])

    def test_unreachable_not_silently_replaced(self):
        arrays, metadata = self.records['independent']
        altered = dict(arrays, common_q=np.zeros_like(arrays['common_q']))
        self.assertEqual(branch_fixture(altered, metadata)['status'], 'UNREACHABLE')

    def test_branch_does_not_condition_on_future_native_outcome(self):
        arrays, metadata = self.records['independent']
        meta = dict(metadata, global_common=False, branch_prefix_ok=True)
        self.assertEqual(branch_fixture(arrays, meta)['status'], 'VALID')

    def test_prefix_target_write_is_not_a_valid_causal_state(self):
        arrays, metadata = self.records['independent']
        altered = dict(arrays, steps=arrays['steps'].copy())
        altered['steps'][0, metadata['step_columns'].index('target_qpos_write')] = 1
        self.assertEqual(branch_fixture(altered, dict(metadata, branch_prefix_ok=True))['status'], 'UNREACHABLE')

    def test_changed_tape_fails_sham(self):
        arrays, metadata = self.records['independent']
        altered = dict(arrays, controls=arrays['controls'].copy())
        altered['controls'][metadata['snapshot']['step']:] = -.1
        self.assertEqual(branch_fixture(altered, metadata)['status'], 'INVALID')

    def test_all_pair_permissions_checked(self):
        arrays, metadata = self.records['redundant_floor']
        model = mujoco.MjModel.from_xml_string(metadata['model_xml'])
        audit = remove_target_environment(model, metadata['target_body'], metadata['body_roles'])
        self.assertEqual(len(audit['preserved_target_hand_pairs']), 2)

    def test_explicit_target_pair_rejected(self):
        xml = self.records['independent'][1]['model_xml']
        xml = xml.replace('</mujoco>', '<contact><pair geom1="object" geom2="base_floor"/></contact></mujoco>')
        model = mujoco.MjModel.from_xml_string(xml)
        with self.assertRaises(ValueError):
            remove_target_environment(model, model.body('target').id,
                                      self.records['independent'][1]['body_roles'])

    def test_environment_free_mesh_and_visual_target_is_noop(self):
        model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
          <body name="hand"><geom size=".01" contype="1" conaffinity="2"/></body>
          <body name="target"><freejoint/>
            <geom size=".01" contype="2" conaffinity="1"/>
            <geom size=".01" contype="0" conaffinity="0"/>
          </body></worldbody></mujoco>''')
        before = np.c_[model.geom_contype, model.geom_conaffinity].copy()
        r = remove_target_environment(model, model.body('target').id, [0, 1, 0])
        self.assertEqual(r['removed_pair_count'], 0)
        self.assertTrue(np.array_equal(before, np.c_[model.geom_contype, model.geom_conaffinity]))

    def test_reference_reconstructs_without_contract_import(self):
        for arrays, metadata in self.records.values():
            result = adjudicate(arrays, metadata, hold_s=3)
            self.assertTrue(result['common_conditions_agree'])
            self.assertLess(result['wrench_reconstruction_error'], 1e-10)
            self.assertLess(result['geometry_reconstruction_error_m'], 1e-12)

    def test_raw_geometry_disagreement_stays_unknown(self):
        arrays, metadata = self.records['independent']
        altered = dict(arrays, geometry_gap=arrays['geometry_gap']+.1)
        self.assertEqual(adjudicate(altered, metadata, hold_s=3)['verdict'], 'INDETERMINATE')

    def test_endpoint_rotation_and_translation_are_independent(self):
        q = np.array([[0., 0., 0., 1., 0., 0., 0.]])
        v = np.zeros((1, 6))
        initial = q[0].copy()
        self.assertTrue(endpoint(q, v, initial)['success'])
        q[0, 3:] = [0, 0, 0, 1]
        self.assertFalse(endpoint(q, v, initial)['success'])
        q[0] = initial
        q[0, 0] = .04
        self.assertFalse(endpoint(q, v, initial)['success'])

    def test_relative_frame_tracks_hand_motion_without_branch_state_writes(self):
        model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
          <body name="hand"><joint name="slide" type="slide" axis="1 0 0"/>
            <geom size=".01" mass="1"/></body>
          <body name="target" pos=".1 0 0"><freejoint/><geom size=".01" mass="1"/></body>
          </worldbody></mujoco>''')
        data, scratch = mujoco.MjData(model), mujoco.MjData(model)
        before = data.qpos.copy()
        initial = _relative_pose(model, data, scratch, model.body('target').id, model.body('hand').id)
        self.assertTrue(np.array_equal(before, data.qpos))
        data.qpos[0] += .2
        data.qpos[1] += .2
        moved = _relative_pose(model, data, scratch, model.body('target').id, model.body('hand').id)
        self.assertTrue(np.allclose(initial, moved, atol=1e-14))
        data.qpos[1] -= .2
        slip = _relative_pose(model, data, scratch, model.body('target').id, model.body('hand').id)
        self.assertAlmostEqual(float(np.linalg.norm(slip[:3]-initial[:3])), .2)


if __name__ == '__main__':
    unittest.main()
