"""Approximate static feasibility and explicitly costly active perturbation probes."""
from __future__ import annotations

import time

import mujoco
import numpy as np
from scipy.optimize import linprog

from .counterfactual import _relative_pose, branch_precondition, endpoint, remove_target_environment


def restore(arrays, metadata, model_factory):
    model = model_factory()
    data = mujoco.MjData(model)
    flag = mujoco.mjtState(metadata['snapshot']['flag'])
    mujoco.mj_setState(model, data, arrays['snapshot_state'], flag)
    check = np.empty_like(arrays['snapshot_state'])
    mujoco.mj_getState(model, data, check, flag)
    if not np.array_equal(check, arrays['snapshot_state']):
        raise RuntimeError('Mechanical baseline restoration mismatch')
    return model, data


def precondition(arrays, metadata):
    return branch_precondition(arrays, metadata)


def moment_matrix(model, data):
    if data.actuator_moment.shape == (model.nu, model.nv):
        return data.actuator_moment.copy()
    result = np.zeros((model.nu, model.nv))
    for row in range(model.nu):
        start, count = int(data.moment_rowadr[row]), int(data.moment_rownnz[row])
        result[row, data.moment_colind[start:start+count]] = data.actuator_moment[start:start+count]
    return result


def static_feasibility(arrays, metadata, model_factory, *, rays=8):
    started = time.perf_counter()
    reason = precondition(arrays, metadata)
    if reason:
        return dict(status='UNREACHABLE', reason=reason, physics_steps=0)
    model, data = restore(arrays, metadata, model_factory)
    if model.neq or np.any(~model.actuator_forcelimited.astype(bool)):
        return dict(status='NOT_APPLICABLE', reason='EQUALITIES_OR_UNBOUNDED_ACTUATORS_REQUIRE_ADAPTER', physics_steps=0)
    target, vadr = metadata['target_body'], metadata['target_vadr']
    robot_dofs = np.setdiff1d(np.arange(model.nv), np.arange(vadr, vadr+6))
    # This separate approximation is static; it never changes the saved rollout.
    data.qvel[:] = 0
    mujoco.mj_forward(model, data)
    body_roles = metadata['body_roles']
    com = data.xipos[target].copy()
    columns = []
    active = 0
    for contact in data.contact:
        b1, b2 = (int(model.geom_bodyid[g]) for g in (contact.geom1, contact.geom2))
        if target not in (b1, b2) or contact.efc_address < 0:
            continue
        other = b1 if b2 == target else b2
        if body_roles[other] <= 0:
            continue
        active += 1
        sign = 1. if b2 == target else -1.
        frame = contact.frame.reshape(3, 3)
        mu = min(contact.friction[:2]) if contact.dim >= 3 else 0.
        jac = np.zeros((3, model.nv))
        mujoco.mj_jac(model, data, jac, None, contact.pos, other)
        for angle in np.arange(rays)*2*np.pi/rays:
            force = sign * (frame[0] + mu*(np.cos(angle)*frame[1] + np.sin(angle)*frame[2]))
            torque = np.cross(contact.pos-com, force)
            columns.append(np.r_[force, torque, -(jac.T @ force)[robot_dofs]])
    if not columns:
        return dict(status='VALID', feasible=False, hand_contacts=0, physics_steps=0,
                    solver_time_s=time.perf_counter()-started)
    contact_map = np.asarray(columns).T
    actuator_map = np.vstack([np.zeros((6, model.nu)), moment_matrix(model, data)[:, robot_dofs].T])
    equality = np.c_[contact_map, actuator_map]
    external = np.r_[-model.body_mass[target]*model.opt.gravity, np.zeros(3),
                     (data.qfrc_bias-data.qfrc_passive)[robot_dofs]]
    weight = metadata['mass_kg']*np.linalg.norm(metadata['gravity'])
    scale = np.r_[np.repeat(weight, 3), np.repeat(weight*metadata['length_scale_m'], 3),
                  np.maximum(np.max(np.abs(equality[6:]), axis=1), 1.)]
    bounds = [(0., None)]*len(columns) + [tuple(r) for r in model.actuator_forcerange]
    answer = linprog(np.r_[np.ones(len(columns)), np.zeros(model.nu)],
                     A_eq=equality/scale[:, None], b_eq=external/scale, bounds=bounds,
                     method='highs', options=dict(primal_feasibility_tolerance=1e-7,
                                                   dual_feasibility_tolerance=1e-7))
    residual = float(np.max(np.abs((equality@answer.x-external)/scale))) if answer.success else None
    status = 'VALID' if answer.status in (0, 2) else 'INDETERMINATE'
    if residual is not None and residual > 1e-6:
        status = 'INDETERMINATE'
    return dict(status=status, feasible=bool(answer.success) if status == 'VALID' else None,
                hand_contacts=active, cone_rays=rays, solver_status=int(answer.status),
                scaled_equilibrium_residual=residual, physics_steps=0, forward_calls=1,
                solver_time_s=time.perf_counter()-started,
                approximation='Static point-contact inscribed friction cones and bounded actuator forces; '
                              'no rolling/torsional contact couples, acceleration, controller tracking, or joint-limit support. '
                              'Predicts capacity in this approximation, not historical no-load truth or actual retention.')


def signed_force_probe(arrays, metadata, model_factory, *, horizon_s=1., weight_fraction=1.):
    started = time.perf_counter()
    reason = precondition(arrays, metadata)
    if reason:
        return dict(status='UNREACHABLE', reason=reason, physics_steps=0)
    first = metadata['snapshot']['step']
    dt = float(arrays['steps'][0, metadata['step_columns'].index('dt')])
    count = round(horizon_s/dt)
    if first+count > len(arrays['steps']):
        return dict(status='UNREACHABLE', reason='INSUFFICIENT_TAPE', physics_steps=0)
    target, qa, va = (metadata[k] for k in ('target_body', 'target_qadr', 'target_vadr'))
    reference = metadata.get('reference_body_id')
    magnitude = metadata['mass_kg']*np.linalg.norm(metadata['gravity'])*weight_fraction
    outcomes = []
    for axis in range(3):
        for sign in (-1, 1):
            model, data = restore(arrays, metadata, model_factory)
            intervention = remove_target_environment(model, target, metadata['body_roles'])
            scratch = mujoco.MjData(model) if reference is not None else None
            initial = (_relative_pose(model, data, scratch, target, reference) if reference is not None
                       else data.qpos[qa:qa+7].copy())
            qs, vs = [], []
            for step in range(first, first+count):
                data.ctrl[:] = arrays['controls'][step]
                tape = arrays['mocap'][step]
                data.mocap_pos[:] = tape[:3*model.nmocap].reshape(-1, 3)
                data.mocap_quat[:] = tape[3*model.nmocap:].reshape(-1, 4)
                data.xfrc_applied[target, axis] = sign*magnitude
                mujoco.mj_step(model, data)
                qs.append(_relative_pose(model, data, scratch, target, reference) if reference is not None
                          else data.qpos[qa:qa+7].copy())
                vs.append(data.qvel[va:va+6].copy())
            qs, vs = np.asarray(qs), np.asarray(vs)
            if reference is not None:
                vs = np.diff(np.vstack([initial[:3], qs[:, :3]]), axis=0)/dt
            outcomes.append(dict(axis=axis, sign=sign, force_n=float(magnitude), endpoint=endpoint(qs, vs, initial)))
    return dict(status='VALID', robust=all(row['endpoint']['success'] for row in outcomes),
                branches=outcomes, horizon_s=horizon_s, additional_force_weight_fraction=weight_fraction,
                gravity_unchanged=True, physics_steps=6*count, simulated_seconds=6*count*dt,
                elapsed_s=time.perf_counter()-started, intervention=intervention,
                purpose='Active six-direction future stability probe; extra cost, not C_NL ground truth')
