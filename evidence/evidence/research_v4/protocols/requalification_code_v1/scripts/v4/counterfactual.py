"""Development full-state sham and target-environment-only contact intervention."""
from __future__ import annotations

import numpy as np
import mujoco


def remove_target_environment(model, target, roles):
    targets = np.flatnonzero(model.geom_bodyid == target)
    if model.npair and any(int(g) in targets for g in np.r_[model.pair_geom1, model.pair_geom2]):
        raise ValueError('Explicit target pairs require a separate intervention adapter')
    environment = [g for g in range(model.ngeom) if g not in targets and roles[model.geom_bodyid[g]] == 0]
    possible = [(int(a), int(b)) for a in targets for b in environment
                if model.geom_contype[a] & model.geom_conaffinity[b] or model.geom_contype[b] & model.geom_conaffinity[a]]
    if not possible:
        return dict(method='no_op_no_target_environment_permissions', target_geoms=targets.tolist(),
                    removed_scope='target_environment_only', removed_pair_count=0)
    used = int(np.bitwise_or.reduce(np.r_[model.geom_contype, model.geom_conaffinity]))
    bit = next((1 << i for i in range(30) if not (used & (1 << i))), None)
    if bit is None:
        raise ValueError('No unused collision bit')
    hand = np.flatnonzero(np.asarray(roles)[model.geom_bodyid] > 0)
    pairs = []
    for a in targets:
        for b in hand:
            if (model.geom_contype[a] & model.geom_conaffinity[b] or
                    model.geom_contype[b] & model.geom_conaffinity[a]):
                pairs.append((int(a), int(b)))
    # A single spare bit is exact only when target geoms share hand-pair permissions.
    expected = {(a, b) for a in targets for b in {p[1] for p in pairs}}
    if expected != set(pairs):
        raise ValueError('Nonuniform target-hand permissions require a richer bit mapping')
    before = np.c_[model.geom_contype.copy(), model.geom_conaffinity.copy()]
    for _, b in pairs:
        model.geom_contype[b] |= bit
    for a in targets:
        model.geom_contype[a] = 0
        model.geom_conaffinity[a] = bit
    after = np.c_[model.geom_contype, model.geom_conaffinity]
    for a in range(model.ngeom):
        for b in range(a):
            old = bool(before[a, 0] & before[b, 1] or before[b, 0] & before[a, 1])
            new = bool(after[a, 0] & after[b, 1] or after[b, 0] & after[a, 1])
            target_pair = (a in targets) != (b in targets)
            other = b if a in targets else a
            environment_pair = target_pair and roles[model.geom_bodyid[other]] == 0
            if new != (False if environment_pair else old):
                raise RuntimeError('Intervention changed an undeclared collision permission')
    return dict(method='unused_collision_bit', spare_bit=bit, preserved_target_hand_pairs=pairs,
                target_geoms=targets.tolist(), removed_scope='target_environment_only')


def endpoint(qpos, qvel, initial, *, position_limit=.03, angle_limit=.35, speed_limit=.2):
    displacement = np.linalg.norm(qpos[:, :3] - initial[:3], axis=1)
    dots = np.abs(qpos[:, 3:7] @ initial[3:7])
    angles = 2*np.arccos(np.clip(dots, 0., 1.))
    speeds = np.linalg.norm(qvel[:, :3], axis=1)
    return dict(success=bool(np.all(displacement <= position_limit) and
                             np.all(angles <= angle_limit) and np.all(speeds <= speed_limit)),
                max_position_error_m=float(displacement.max()), max_angle_error_rad=float(angles.max()),
                max_linear_speed_m_s=float(speeds.max()))


def branch_fixture(arrays, metadata, *, horizon_s=3.):
    return branch_model(arrays, metadata,
                        lambda: mujoco.MjModel.from_xml_string(metadata['model_xml']), horizon_s=horizon_s)


def branch_precondition(arrays, metadata):
    snap = metadata.get('snapshot')
    if snap is None:
        return 'NO_DECLARED_SNAPSHOT'
    first = snap['step']
    if not metadata.get('branch_prefix_ok', metadata['global_common']) or not arrays['common_q'][first]:
        return 'COMMON_PREFIX_PRECONDITION_FAILED'
    columns = metadata['step_columns']
    if any(arrays['steps'][:first+1, columns.index(k)].any()
           for k in ('applied_any', 'target_qpos_write', 'target_qvel_write')):
        return 'PREFIX_ASSISTANCE_OR_TARGET_WRITE'
    return None


def _relative_pose(model, source, scratch, target, reference):
    # Only the separate kinematic scratch data is changed; no branch solver call.
    scratch.qpos[:] = source.qpos
    scratch.mocap_pos[:] = source.mocap_pos
    scratch.mocap_quat[:] = source.mocap_quat
    mujoco.mj_kinematics(model, scratch)
    rotation = scratch.xmat[reference].reshape(3, 3)
    position = rotation.T @ (scratch.xpos[target]-scratch.xpos[reference])
    conjugate = scratch.xquat[reference].copy()
    conjugate[1:] *= -1
    quaternion = np.empty(4)
    mujoco.mju_mulQuat(quaternion, conjugate, scratch.xquat[target])
    return np.r_[position, quaternion]


def branch_model(arrays, metadata, model_factory, *, horizon_s=3.):
    snap = metadata['snapshot']
    reason = branch_precondition(arrays, metadata)
    if reason:
        return dict(status='UNREACHABLE', reason=reason)
    first = snap['step']
    dt = float(arrays['steps'][0, metadata['step_columns'].index('dt')])
    count = round(horizon_s/dt)
    if first+count > len(arrays['steps']):
        return dict(status='UNREACHABLE', reason='INSUFFICIENT_CONTINUATION_TAPE')
    target, qadr, vadr = metadata['target_body'], metadata['target_qadr'], metadata['target_vadr']
    trajectories, audits, relative = {}, {}, {}
    reference = metadata.get('reference_body_id')
    for name in ('sham', 'removed'):
        model = model_factory()
        if name == 'removed':
            audits[name] = remove_target_environment(model, target, metadata['body_roles'])
        data = mujoco.MjData(model)
        mujoco.mj_setState(model, data, arrays['snapshot_state'], mujoco.mjtState(snap['flag']))
        restored = np.empty_like(arrays['snapshot_state'])
        mujoco.mj_getState(model, data, restored, mujoco.mjtState(snap['flag']))
        if not np.array_equal(restored, arrays['snapshot_state']):
            raise RuntimeError('Full integration-state restoration failed')
        initial = data.qpos[qadr:qadr+7].copy()
        scratch = mujoco.MjData(model) if reference is not None else None
        relative_initial = _relative_pose(model, data, scratch, target, reference) if reference is not None else initial
        qs, vs, rs = [], [], []
        for step in range(first, first+count):
            data.ctrl[:] = arrays['controls'][step]
            tape = arrays['mocap'][step]
            data.mocap_pos[:] = tape[:3*model.nmocap].reshape(-1, 3)
            data.mocap_quat[:] = tape[3*model.nmocap:].reshape(-1, 4)
            mujoco.mj_step(model, data)
            qs.append(data.qpos[qadr:qadr+7].copy())
            vs.append(data.qvel[vadr:vadr+6].copy())
            if reference is not None:
                rs.append(_relative_pose(model, data, scratch, target, reference))
        trajectories[name] = (np.asarray(qs), np.asarray(vs))
        if reference is not None:
            r = np.asarray(rs)
            relative_velocity = np.diff(np.vstack([relative_initial[:3], r[:, :3]]), axis=0)/dt
            relative[name] = (r, relative_velocity)
    expected_q = arrays['post_qpos'][first:first+count]
    expected_v = arrays['post_qvel'][first:first+count]
    equal = all(np.array_equal(a, b) for a, b in zip(trajectories['sham'], (expected_q, expected_v)))
    if not equal:
        return dict(status='INVALID', reason='SHAM_TRAJECTORY_MISMATCH',
                    max_q_error=float(np.max(np.abs(trajectories['sham'][0]-expected_q))),
                    max_v_error=float(np.max(np.abs(trajectories['sham'][1]-expected_v))))
    endpoints = {name: endpoint(*trajectory, relative_initial if reference is not None else initial)
                 for name, trajectory in (relative if reference is not None else trajectories).items()}
    cell = (endpoints['sham']['success'], endpoints['removed']['success'])
    labels = {(True, True): 'BOTH_RETAIN', (True, False): 'DEPENDENT',
              (False, False): 'BOTH_FAIL', (False, True): 'REMOVAL_RESCUES'}
    return dict(status='VALID', sham_bit_equal=True, horizon_s=horizon_s, t0_s=snap['time'],
                continuation='Recorded controls and mocap, not controller recovery',
                endpoint_frame='reference_body' if reference is not None else 'world', reference_body_id=reference,
                intervention_audit=audits['removed'], endpoints=endpoints, cell=labels[cell])
