import unittest

import mujoco
import numpy as np

from scripts.v4.contact_observer import ContactRecorder, STEP_COLUMNS, CONTACT_COLUMNS, body_scale, support_paths


def fixture(extra="", target='type="box" size=".03 .03 .03"', z=.029,
            gravity="0 0 -9.81", attrs="", integrator="implicitfast"):
    return mujoco.MjModel.from_xml_string(f'''<mujoco>
      <option timestep=".002" gravity="{gravity}" integrator="{integrator}"/>
      <default><geom condim="6" friction="1 .01 .01"/></default>
      <worldbody><geom name="floor" type="plane" size="1 1 .01"/>
      {extra}<body name="target" pos="0 0 {z}" {attrs}>
      <freejoint/><geom name="target" {target} mass=".1"/></body></worldbody>
    </mujoco>''')


def record(model, n=100, hook=None):
    data = mujoco.MjData(model)
    rec = ContactRecorder(model, model.body("target").id, np.zeros(model.nbody), snapshot_step=40)
    for step in range(n):
        if hook:
            hook(data, step)
        rec.before_step(data, step)
        mujoco.mj_step(model, data)
        rec.after_step(data)
    return data, rec


class ContactTests(unittest.TestCase):
    def test_contact_force_direction(self):
        m = fixture()
        _, rec = record(m, 400)
        a = rec.arrays()["steps"]
        self.assertAlmostEqual(a[-1, STEP_COLUMNS.index("env_net_force_z")], .981, places=5)
        self.assertGreater(a[-1, STEP_COLUMNS.index("env_constraint_count")], 0)

    def test_observer_does_not_change_state(self):
        m = fixture()
        nominal = mujoco.MjData(m)
        for _ in range(200):
            mujoco.mj_step(m, nominal)
        observed, rec = record(m, 200)
        for field in ("qpos", "qvel", "qacc_warmstart", "ctrl", "act"):
            np.testing.assert_array_equal(getattr(nominal, field), getattr(observed, field))
        self.assertLess(rec.metadata()["geometry_clock_max_error"], 1e-12)

    def test_shapes_and_no_contact_sentinel(self):
        _, rec = record(fixture(z=3), 3)
        a = rec.arrays()
        self.assertEqual(a["steps"].shape, (3, len(STEP_COLUMNS)))
        self.assertEqual(a["contacts"].shape, (0, len(CONTACT_COLUMNS)))
        self.assertTrue(np.all(a["steps"][:, STEP_COLUMNS.index("env_dist_present")] == 0))
        self.assertTrue(np.isfinite(a["steps"]).all())

    def test_equal_opposing_loads_not_lost(self):
        walls = '''<geom type="box" pos="-.045 0 1" size=".02 .1 .1"/>
                   <geom type="box" pos=".045 0 1" size=".02 .1 .1"/>'''
        _, rec = record(fixture(extra=walls, z=1, gravity="0 0 0"), 1)
        row = rec.arrays()["steps"][0]
        self.assertGreater(row[STEP_COLUMNS.index("env_abs_force_n")], 1.)
        self.assertLess(abs(row[STEP_COLUMNS.index("env_net_force_x")]), 1e-10)

    def test_torsional_contact_keeps_six_components(self):
        def spin(d, step):
            if step == 0:
                d.qvel[5] = 5.
        _, rec = record(fixture(target='type="sphere" size=".03"'), 3, spin)
        contacts = rec.arrays()["contacts"]
        self.assertGreater(np.max(np.abs(contacts[:, CONTACT_COLUMNS.index("local_tn")])), 0.)
        self.assertGreater(rec.arrays()["steps"][0, STEP_COLUMNS.index("env_abs_torque_nm")], 0.)

    def test_hidden_assistance_is_recorded(self):
        _, rec = record(fixture(z=2), 2, lambda d, step: d.xfrc_applied.__setitem__((1, 2), .981))
        self.assertTrue(np.all(rec.arrays()["steps"][:, STEP_COLUMNS.index("applied_any")] == 1))
        self.assertGreater(rec.arrays()["steps"][0, STEP_COLUMNS.index("target_applied_norm")], .9)

    def test_target_edits_between_steps_detected(self):
        def edit(d, step):
            if step == 1:
                d.qpos[0] += .01
                d.qvel[0] += .01
        _, rec = record(fixture(z=2), 2, edit)
        a = rec.arrays()["steps"]
        self.assertEqual(a[1, STEP_COLUMNS.index("target_qpos_write")], 1)
        self.assertEqual(a[1, STEP_COLUMNS.index("target_qvel_write")], 1)

    def test_direct_noncontact_paths_flagged(self):
        m = fixture(attrs='gravcomp="1"')
        report = support_paths(m, m.body("target").id)
        self.assertFalse(report["complete_for_declared_model"])
        self.assertIn("TARGET_GRAVITY_COMPENSATION", report["reason_codes"])

    def test_damping_wrench_matches_independent_jacobian_conversion(self):
        m = fixture(z=2)
        target = m.body('target').id
        m.body_ipos[target] = [.01, .02, .03]
        m.dof_damping[:] = .1
        def initialize(d, step):
            d.qpos[3:7] = np.array([1., 2., 3., 4.])/np.sqrt(30.)
            d.qvel[:] = [.4, -.3, .2, -1., 2., .5]
        d, rec = record(m, 1, initialize)
        jp, jr = np.zeros((3, m.nv)), np.zeros((3, m.nv))
        mujoco.mj_jacBodyCom(m, d, jp, jr, target)
        mapping = np.c_[jp.T, jr.T]
        wrench = np.linalg.solve(mapping, d.qfrc_damper)
        row = rec.arrays()['steps'][0]
        self.assertAlmostEqual(row[STEP_COLUMNS.index('target_damping_force_n')], np.linalg.norm(wrench[:3]), places=12)
        self.assertAlmostEqual(row[STEP_COLUMNS.index('target_damping_torque_nm')], np.linalg.norm(wrench[3:]), places=12)
        self.assertLess(row[STEP_COLUMNS.index('passive_meter_residual')], 1e-12)
        self.assertTrue(rec.metadata()['support_paths']['requires_passive_meter'])
        self.assertTrue(rec.metadata()['support_paths']['complete_for_declared_model'])

    def test_disabled_damping_not_invented(self):
        m = fixture(z=2)
        m.dof_damping[:] = .1
        flag = 'mjDSBL_DAMPER' if mujoco.__version__ == '3.8.0' else 'mjDSBL_PASSIVE'
        m.opt.disableflags |= int(getattr(mujoco.mjtDisableBit, flag))
        _, rec = record(m, 1, lambda d, step: d.qvel.__setitem__(slice(None), 1.))
        row = rec.arrays()['steps'][0]
        for k in ('target_damping_force_n', 'target_damping_post_force_n', 'passive_meter_residual'):
            self.assertEqual(row[STEP_COLUMNS.index(k)], 0.)

    def test_target_joint_frictionloss_unresolved(self):
        m = fixture(z=2)
        m.dof_frictionloss[:] = .1
        self.assertIn('TARGET_JOINT_FRICTIONLOSS', support_paths(m, m.body('target').id)['reason_codes'])

    def test_object_frame_scale(self):
        m = fixture()
        self.assertAlmostEqual(body_scale(m, m.geom("target").id), np.sqrt(3)*.03)

    def test_rk4_rejected(self):
        m = fixture(integrator="RK4")
        with self.assertRaises(ValueError):
            ContactRecorder(m, m.body("target").id, np.zeros(m.nbody))

    def test_integration_snapshot(self):
        m = fixture()
        _, rec = record(m, 50)
        restored = mujoco.MjData(m)
        mujoco.mj_setState(m, restored, rec.snapshot["state"], mujoco.mjtState.mjSTATE_INTEGRATION)
        self.assertAlmostEqual(restored.time, .08)
        self.assertEqual(rec.snapshot["step"], 40)


if __name__ == "__main__":
    unittest.main()
