import unittest

import mujoco
import numpy as np

from scripts.v4.adapters.model_utils import BoxEnvironmentGeometry, model_factory, object_bounds


class ModelUtilityTests(unittest.TestCase):
    def fixture(self):
        model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
          <geom name="table" type="box" pos="0 0 .5" size="1 1 .2"/>
          <body name="target" pos="0 0 1"><freejoint/>
            <geom name="object" type="box" size=".03 .02 .04" mass=".1"/>
          </body></worldbody></mujoco>''')
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        return model, data

    def test_box_separation_and_overlap(self):
        model, data = self.fixture()
        geom = BoxEnvironmentGeometry(model, model.geom('object').id, [0, 0])
        self.assertAlmostEqual(geom.sample(data)[0], .26, places=12)
        data.qpos[2] = .70
        mujoco.mj_forward(model, data)
        self.assertLess(geom.sample(data)[0], 0.)

    def test_rotated_box_clearance(self):
        model, data = self.fixture()
        data.qpos[3:7] = [np.sqrt(.5), 0, np.sqrt(.5), 0]
        mujoco.mj_forward(model, data)
        geom = BoxEnvironmentGeometry(model, model.geom('object').id, [0, 0])
        self.assertAlmostEqual(geom.sample(data)[0], .27, places=12)

    def test_legal_rigid_rotation_preserves_clearance(self):
        model, data = self.fixture()
        angle = .61
        rotation = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
        model.geom_quat[model.geom('table').id] = [np.cos(angle/2), 0, 0, np.sin(angle/2)]
        data.qpos[:3] = rotation@data.qpos[:3]
        data.qpos[3:] = [np.cos(angle/2), 0, 0, np.sin(angle/2)]
        mujoco.mj_forward(model, data)
        geom = BoxEnvironmentGeometry(model, model.geom('object').id, [0, 0])
        self.assertAlmostEqual(geom.sample(data)[0], .26, places=12)

    def test_binary_clone_preserves_modified_model(self):
        model, _ = self.fixture()
        model.body_mass[model.body('target').id] = .123
        copy = model_factory(model)()
        self.assertEqual(copy.body_mass[model.body('target').id], .123)
        np.testing.assert_array_equal(copy.geom_size, model.geom_size)

    def test_object_bound_is_pose_independent(self):
        model, data = self.fixture()
        first = object_bounds(model, model.body('target').id)
        data.qpos[2] += .5
        mujoco.mj_forward(model, data)
        second = object_bounds(model, model.body('target').id)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first['length_scale_m'], np.linalg.norm([.03, .02, .04]))


if __name__ == '__main__':
    unittest.main()
