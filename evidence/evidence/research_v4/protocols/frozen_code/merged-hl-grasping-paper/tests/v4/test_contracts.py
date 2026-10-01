import unittest

import numpy as np

from scripts.v4.contracts import Calibration, evaluate

COLUMNS = ["step", "solve_time", "dt", "env_count", "env_constraint_count", "env_abs_force_n",
           "env_abs_torque_nm", "env_min_dist", "env_dist_present", "applied_any",
           "target_qpos_write", "target_qvel_write", "geometry_clock_error"]


def example(n=7500):
    a = np.zeros((n, len(COLUMNS)))
    a[:, 0] = np.arange(n)
    a[:, 1] = np.arange(n)*.002
    a[:, 2] = .002
    a[:, 7] = 1e10
    meta = dict(planned_steps=n, terminal_reason="controller_schedule_completed", global_common=True,
                support_paths=dict(complete_for_declared_model=True), mass_kg=1., length_scale_m=.1,
                gravity=[0., 0., -9.81])
    return a, np.ones(n, dtype=bool), meta, np.full(n, .01)


def judge(parts, **kwargs):
    a, q, meta, gap = parts
    return evaluate(a, COLUMNS, q, meta, geometry_gap=gap, **kwargs)


class ContractTests(unittest.TestCase):
    def test_passive_meter_required_when_damping_detected(self):
        e = example()
        e[2]['support_paths']['requires_passive_meter'] = True
        r = judge(e)
        self.assertEqual(r['trace_validity'], 'INVALID')
        self.assertIn('MISSING_REQUIRED_PASSIVE_METER', r['reason_codes'])

    def test_passive_load_cannot_hide_behind_zero_contact_force(self):
        a, q, meta, gap = example()
        columns = COLUMNS + ['target_damping_force_n', 'target_damping_torque_nm',
                             'target_damping_post_force_n', 'target_damping_post_torque_nm', 'passive_meter_residual']
        a = np.c_[a, np.zeros((len(a), 5))]
        a[:, -3] = .981
        meta['support_paths']['requires_passive_meter'] = True
        result = evaluate(a, columns, q, meta, geometry_gap=gap)
        self.assertEqual(result['no_external_load_verdict'], 'FAIL')
        self.assertEqual(result['no_contact_result'], 'PASS')

    def test_unexplained_passive_force_abstains(self):
        a, q, meta, gap = example()
        a = np.c_[a, np.ones(len(a))]
        r = evaluate(a, COLUMNS+['passive_meter_residual'], q, meta, geometry_gap=gap)
        self.assertEqual(r['no_external_load_verdict'], 'INDETERMINATE')

    def test_exact_15_seconds(self):
        r = judge(example())
        self.assertEqual(r["no_external_load_verdict"], "PASS")
        self.assertEqual(r["definite_interval"]["duration_s"], 15.)

    def test_one_step_short(self):
        self.assertEqual(judge(example(7499))["no_external_load_verdict"], "FAIL")

    def test_continuous_not_accumulated(self):
        e = example(9000)
        e[1][4500] = False
        self.assertEqual(judge(e)["no_external_load_verdict"], "FAIL")
        self.assertEqual(judge(e, contiguous=False)["no_external_load_verdict"], "PASS")

    def test_zero_force_record_can_pass(self):
        e = example()
        e[0][:, COLUMNS.index("env_count")] = 1
        e[0][:, COLUMNS.index("env_dist_present")] = 1
        e[0][:, COLUMNS.index("env_min_dist")] = .005
        r = judge(e)
        self.assertEqual(r["no_contact_result"], "FAIL")
        self.assertEqual(r["no_external_load_verdict"], "PASS")

    def test_load_rejected(self):
        e = example()
        e[0][:, COLUMNS.index("env_abs_force_n")] = 9.81
        self.assertEqual(judge(e)["no_external_load_verdict"], "FAIL")

    def test_torque_only_load(self):
        e = example()
        e[0][:, COLUMNS.index("env_abs_torque_nm")] = .1
        self.assertEqual(judge(e)["no_external_load_verdict"], "FAIL")
        self.assertEqual(judge(e, use_torque=False)["no_external_load_verdict"], "PASS")

    def test_uncertainty_is_not_false(self):
        e = example()
        e[0][:, COLUMNS.index("env_abs_force_n")] = .005*9.81
        r = judge(e)
        self.assertEqual(r["no_external_load_verdict"], "INDETERMINATE")
        self.assertEqual(r["possible_interval"]["duration_s"], 15.)
        self.assertEqual(r["definite_interval"]["duration_s"], 0.)

    def test_geometry_disagreement_abstains(self):
        e = example()
        e[3][:] = -.002
        self.assertEqual(judge(e)["no_external_load_verdict"], "INDETERMINATE")
        self.assertEqual(judge(e, use_geometry=False)["no_external_load_verdict"], "PASS")

    def test_active_zero_force_abstains(self):
        e = example()
        e[0][:, [COLUMNS.index("env_count"), COLUMNS.index("env_dist_present"), COLUMNS.index("env_constraint_count")]] = 1
        self.assertEqual(judge(e)["no_external_load_verdict"], "INDETERMINATE")

    def test_noncontact_path_unknown(self):
        e = example()
        e[2]["support_paths"] = dict(complete_for_declared_model=False, reason_codes=["TARGET_TENDON_PATH"])
        self.assertEqual(judge(e)["no_external_load_verdict"], "INDETERMINATE")

    def test_hidden_force_veto(self):
        e = example()
        e[0][0, COLUMNS.index("applied_any")] = 1
        self.assertEqual(judge(e)["no_external_load_verdict"], "FAIL")

    def test_native_global_condition_not_relaxed(self):
        e = example()
        e[2]["global_common"] = False
        self.assertEqual(judge(e)["no_external_load_verdict"], "FAIL")

    def test_missing_row_invalid(self):
        a, q, meta, gap = example()
        self.assertEqual(judge((a[:-1], q[:-1], meta, gap[:-1]))["trace_validity"], "INVALID")

    def test_duplicate_step_invalid(self):
        e = example()
        e[0][1, 0] = 0
        self.assertEqual(judge(e)["trace_validity"], "INVALID")

    def test_wrong_timestamp_invalid(self):
        e = example()
        e[0][1, 1] = .003
        self.assertEqual(judge(e)["trace_validity"], "INVALID")

    def test_unverified_terminal_invalid(self):
        e = example()
        e[2]["terminal_reason"] = "crashed"
        self.assertEqual(judge(e)["trace_validity"], "INVALID")

    def test_normal_failure_not_infrastructure_error(self):
        e = example(100)
        e[2].update(planned_steps=7500, terminal_reason="normal_task_failure", global_common=False)
        r = judge(e)
        self.assertEqual(r["trace_validity"], "VALID")
        self.assertEqual(r["no_external_load_verdict"], "FAIL")

    def test_nonfinite_invalid(self):
        e = example()
        e[0][0, 5] = np.nan
        self.assertEqual(judge(e)["trace_validity"], "INVALID")

    def test_no_oracle_or_policy_identity_input(self):
        e = example()
        first = judge(e)
        e[2].update(oracle_label="FAIL", expected_result=False, policy_name="bad_program")
        self.assertEqual(first, judge(e))

    def test_binary_ablation_has_no_unknown(self):
        e = example()
        e[3][:] = -.002
        self.assertEqual(judge(e, binary=True)["no_external_load_verdict"], "FAIL")

    def test_invalid_calibration(self):
        with self.assertRaises(ValueError):
            Calibration(force_pass_ratio=.1, force_fail_ratio=.01)


if __name__ == "__main__":
    unittest.main()
