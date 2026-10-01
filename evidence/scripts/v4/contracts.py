"""Simulator-free, task-conditioned no-load contract with bounded uncertainty."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np


@dataclass(frozen=True)
class Calibration:
    hold_s: float = 15.
    force_pass_ratio: float = 1e-4
    force_fail_ratio: float = 1e-2
    torque_pass_ratio: float = 1e-4
    torque_fail_ratio: float = 1e-2
    penetration_tolerance_m: float = 1e-5
    positive_gap_m: float = 1e-6
    clock_tolerance_s: float = 1e-8
    duration_tolerance_s: float = 1e-9
    passive_residual_tolerance: float = 1e-10
    version: str = "development-instrumentation-v1-not-frozen"

    def __post_init__(self):
        values = asdict(self)
        if any(not math.isfinite(v) or v <= 0 for k, v in values.items() if k != "version"):
            raise ValueError("Calibration values must be finite and positive")
        if self.force_pass_ratio >= self.force_fail_ratio or self.torque_pass_ratio >= self.torque_fail_ratio:
            raise ValueError("The numerical uncertainty band must have positive width")


def longest_interval(mask, dt):
    padded = np.r_[False, np.asarray(mask, dtype=bool), False].astype(np.int8)
    delta = np.diff(padded)
    starts, ends = np.flatnonzero(delta == 1), np.flatnonzero(delta == -1)
    if not len(starts):
        return dict(start_step=None, end_step_exclusive=None, duration_s=0.)
    j = int(np.argmax(ends - starts))
    return dict(start_step=int(starts[j]), end_step_exclusive=int(ends[j]), duration_s=float((ends[j]-starts[j])*dt))


def validate(steps, columns, q, metadata, config):
    a, q = np.asarray(steps), np.asarray(q)
    if a.ndim != 2 or a.shape[1] != len(columns) or len(columns) != len(set(columns)) or not len(a):
        raise ValueError("MALFORMED_STEP_SCHEMA")
    if q.shape != (len(a),) or not np.isin(q, (0, 1)).all() or not np.isfinite(a).all():
        raise ValueError("MISSING_OR_NONFINITE_EVIDENCE")
    required = ("step", "solve_time", "dt", "env_count", "env_constraint_count", "env_abs_force_n",
                "env_abs_torque_nm", "env_min_dist", "env_dist_present", "applied_any",
                "target_qpos_write", "target_qvel_write", "geometry_clock_error")
    if any(k not in columns for k in required):
        raise ValueError("MISSING_REQUIRED_SIGNAL")
    c = {key: a[:, columns.index(key)] for key in required}
    passive_keys = ('target_damping_force_n', 'target_damping_torque_nm', 'target_damping_post_force_n',
                    'target_damping_post_torque_nm', 'passive_meter_residual')
    if metadata.get('support_paths', {}).get('requires_passive_meter') and any(k not in columns for k in passive_keys):
        raise ValueError('MISSING_REQUIRED_PASSIVE_METER')
    for key in passive_keys:
        c[key] = a[:, columns.index(key)] if key in columns else np.zeros(len(a))
        if np.any(c[key] < 0):
            raise ValueError('INVALID_PASSIVE_METER')
    dt = float(c["dt"][0])
    if dt <= 0 or not np.all(c["dt"] == dt):
        raise ValueError("INVALID_OR_VARIABLE_TIMESTEP")
    if not np.array_equal(c["step"], np.arange(len(a))):
        raise ValueError("MISSING_DUPLICATE_OR_REORDERED_STEP")
    if not np.allclose(c["solve_time"], np.arange(len(a))*dt + metadata.get("start_time_s", 0.),
                       atol=config.clock_tolerance_s, rtol=0):
        raise ValueError("SOLVE_CLOCK_MISMATCH")
    if np.any(c["geometry_clock_error"] > config.clock_tolerance_s):
        raise ValueError("GEOMETRY_SOLVE_STAGE_MISMATCH")
    expected, terminal = metadata.get("planned_steps"), metadata.get("terminal_reason")
    if not isinstance(expected, int) or expected <= 0:
        raise ValueError("MISSING_PLANNED_HORIZON")
    if terminal == "controller_schedule_completed":
        if len(a) != expected:
            raise ValueError("TRUNCATED_OR_EXTENDED_LOG")
    elif terminal == "normal_task_failure":
        if len(a) > expected or metadata.get("global_common") is not False:
            raise ValueError("UNVERIFIED_FAILURE_TERMINATION")
    else:
        raise ValueError("UNKNOWN_OR_INFRASTRUCTURE_TERMINATION")
    if any(np.any(c[k] < 0) for k in ("env_abs_force_n", "env_abs_torque_nm", "env_count", "env_constraint_count")):
        raise ValueError("IMPOSSIBLE_CONTACT_SIGNAL")
    for k in ("env_dist_present", "applied_any", "target_qpos_write", "target_qvel_write"):
        if not np.isin(c[k], (0, 1)).all():
            raise ValueError("NONBINARY_SIGNAL")
    if np.any(c["env_dist_present"] != (c["env_count"] > 0)) or np.any(c["env_constraint_count"] > c["env_count"]):
        raise ValueError("INCONSISTENT_CONTACT_COUNTS")
    for key in ("mass_kg", "length_scale_m"):
        if key not in metadata or not math.isfinite(metadata[key]) or metadata[key] <= 0:
            raise ValueError("INVALID_NORMALIZATION")
    gravity = np.asarray(metadata.get("gravity"), dtype=float)
    if gravity.shape != (3,) or not np.isfinite(gravity).all() or np.linalg.norm(gravity) <= 0:
        raise ValueError("INVALID_GRAVITY")
    if not isinstance(metadata.get("global_common"), bool):
        raise ValueError("MISSING_GLOBAL_COMMON_CONDITIONS")
    return c, dt


def evaluate(steps, columns, common_q, metadata, config=Calibration(), *, geometry_gap=None,
             use_geometry=True, use_torque=True, binary=False, contiguous=True):
    result = dict(contract_version="merged-v4-no-external-load-2", calibration_version=config.version,
                  applicable=metadata.get("applicable", True), trace_validity="VALID",
                  no_external_load_verdict="INDETERMINATE", no_contact_result="INDETERMINATE",
                  definite_interval=None, possible_interval=None, reason_codes=[])
    try:
        c, dt = validate(steps, columns, common_q, metadata, config)
    except (ValueError, TypeError, KeyError) as error:
        result.update(trace_validity="INVALID", reason_codes=[str(error)])
        return result
    if not result["applicable"]:
        result["reason_codes"] = ["CONTRACT_NOT_APPLICABLE"]
        return result
    q = np.asarray(common_q, dtype=bool)
    weight = metadata["mass_kg"] * float(np.linalg.norm(metadata["gravity"]))
    rf = (c["env_abs_force_n"] + np.maximum(c['target_damping_force_n'], c['target_damping_post_force_n'])) / weight
    rm = (c["env_abs_torque_nm"] + np.maximum(c['target_damping_torque_nm'], c['target_damping_post_torque_nm'])) / (weight * metadata["length_scale_m"])
    passed = rf <= config.force_pass_ratio
    failed = rf >= config.force_fail_ratio
    if use_torque:
        passed &= rm <= config.torque_pass_ratio
        failed |= rm >= config.torque_fail_ratio
    uncertain = ~(passed | failed)
    unresolved_passive = c['passive_meter_residual'] > config.passive_residual_tolerance
    if unresolved_passive.any():
        result['reason_codes'].append('UNEXPLAINED_PASSIVE_FORCE')
        uncertain |= unresolved_passive & ~failed
        passed &= ~unresolved_passive
    global_ok = metadata["global_common"] and not np.any(c["applied_any"].astype(bool) | c["target_qpos_write"].astype(bool) | c["target_qvel_write"].astype(bool))
    # Unsupported model paths are unknown, not asserted physical failures.
    paths = metadata.get("support_paths")
    paths_known = True
    if paths is None or "complete_for_declared_model" not in paths:
        result["reason_codes"].append("UNVERIFIED_NONCONTACT_SUPPORT_PATHS")
        uncertain |= ~failed
        passed[:] = False
        paths_known = False
    elif not paths["complete_for_declared_model"]:
        uncertain |= ~failed
        passed[:] = False
        paths_known = False
        result["reason_codes"].extend(paths.get("reason_codes", ["NONCONTACT_SUPPORT_PATH"]))
    if use_geometry:
        if geometry_gap is None:
            result["reason_codes"].append("MISSING_INDEPENDENT_ENVIRONMENT_GEOMETRY")
            conflict = ~failed
        else:
            gap = np.asarray(geometry_gap)
            if gap.shape != q.shape or not np.isfinite(gap).all():
                result.update(trace_validity="INVALID", reason_codes=["MALFORMED_GEOMETRY_SIGNAL"])
                return result
            conflict = (gap < -config.penetration_tolerance_m) & ~failed
        # Nonzero constraint activity with no decisive force needs explicit numerical resolution.
        conflict |= (c["env_constraint_count"] > 0) & passed
        if conflict.any():
            result["reason_codes"].append("GEOMETRY_OR_ACTIVE_CONSTRAINT_WITH_LOW_LOAD")
        uncertain |= conflict
        passed &= ~conflict
    if binary:
        passed &= ~uncertain
        failed |= uncertain
        uncertain[:] = False
    definite = q & passed & global_ok
    possible = q & (passed | uncertain) & global_ok
    interval = lambda mask: longest_interval(mask, dt) if contiguous else dict(
        start_step=None, end_step_exclusive=None, duration_s=float(np.sum(mask)*dt))
    lower, upper = interval(definite), interval(possible)
    result["definite_interval"], result["possible_interval"] = lower, upper
    nc = interval(q & (c["env_count"] == 0) & global_ok)
    result["no_contact_result"] = "PASS" if nc["duration_s"] + config.duration_tolerance_s >= config.hold_s else "FAIL"
    if result["no_contact_result"] == "PASS" and not paths_known:
        result["no_contact_result"] = "INDETERMINATE"
    if lower["duration_s"] + config.duration_tolerance_s >= config.hold_s:
        verdict = "PASS"
    elif upper["duration_s"] + config.duration_tolerance_s < config.hold_s:
        verdict = "FAIL"
    else:
        verdict = "INDETERMINATE"
    result["no_external_load_verdict"] = verdict
    if not global_ok:
        result["reason_codes"].append("GLOBAL_COMMON_CONDITION_FAILED")
    elif verdict == "FAIL":
        result["reason_codes"].append("NO_QUALIFYING_CONTINUOUS_INTERVAL")
    elif verdict == "INDETERMINATE":
        result["reason_codes"].append("NUMERICAL_OR_EVIDENCE_UNCERTAINTY")
    result.update(no_contact_interval=nc, unknown_sample_count=int(np.sum(q & uncertain)),
                  max_environment_force_ratio=float((c['env_abs_force_n']/weight).max()),
                  max_environment_torque_ratio=float((c['env_abs_torque_nm']/(weight*metadata['length_scale_m'])).max()),
                  max_external_force_ratio=float(rf.max()), max_external_torque_ratio=float(rm.max()),
                  config=asdict(config))
    return result
