"""Independent raw-contact reconstruction for the declared box/plane controls.

This is implementation independence inside one simulator, not external physics
ground truth or a human annotation. It does not import the tested contracts.
"""
from __future__ import annotations

import numpy as np


def _duration(values, dt):
    best = current = 0
    for value in values:
        current = current + 1 if value else 0
        best = max(best, current)
    return best * dt


def adjudicate(arrays, metadata, *, force_low=1e-4, force_high=1e-2,
               torque_low=1e-4, torque_high=1e-2, hold_s=15., penetration_tol=1e-5):
    s, c = arrays['steps'], arrays['contacts']
    sc = {k: i for i, k in enumerate(metadata['step_columns'])}
    cc = {k: i for i, k in enumerate(metadata['contact_columns'])}
    n, target = len(s), metadata['target_body']
    raw = arrays['raw_geometry']
    count = len(metadata['plane_geoms'])
    centers, rotations = raw[:, :3], raw[:, 3:12].reshape(n, 3, 3)
    origins = raw[:, 12:12+count*3].reshape(n, count, 3)
    normals = raw[:, 12+count*3:].reshape(n, count, 3)
    # Explicit eight-vertex support distances, independent of the auditor's OBB formula.
    signs = np.array([[a, b, d] for a in (-1, 1) for b in (-1, 1) for d in (-1, 1)])
    local_vertices = signs * np.asarray(metadata['target_half_size'])
    vertices = centers[:, None, :] + np.einsum('nij,kj->nki', rotations, local_vertices)
    distances = np.einsum('npkj,npj->npk', vertices[:, None, :, :]-origins[:, :, None, :], normals)
    gap = distances.min(axis=(1, 2))
    geometry_error = float(np.max(np.abs(gap-arrays['geometry_gap'])))
    if len(c):
        frames = c[:, cc['frame_0']:cc['frame_8']+1].reshape(-1, 3, 3)
        local = c[:, cc['local_fn']:cc['local_tt2']+1]
        direction = np.where(c[:, cc['body2']] == target, 1., -1.)
        forces = np.einsum('ki,kij->kj', local[:, :3], frames)*direction[:, None]
        moments = np.einsum('ki,kij->kj', local[:, 3:], frames)*direction[:, None]
        ticks = c[:, cc['step']].astype(int)
        points = c[:, cc['point_x']:cc['point_z']+1]
        torques = moments + np.cross(points-centers[ticks], forces)
        wrench_error = max(float(np.max(np.abs(forces-c[:, cc['target_force_x']:cc['target_force_z']+1]))),
                           float(np.max(np.abs(torques-c[:, cc['target_com_torque_x']:cc['target_com_torque_z']+1]))))
    else:
        ticks = np.zeros(0, dtype=int)
        forces = torques = np.zeros((0, 3))
        wrench_error = 0.
    load, moment, records, active = (np.zeros(n) for _ in range(4))
    hand = np.zeros((n, 2), dtype=bool)
    for i, step in enumerate(ticks):
        role = int(c[i, cc['role']])
        constrained = c[i, cc['efc_address']] >= 0
        if role == 0:
            load[step] += np.linalg.norm(forces[i])
            moment[step] += np.linalg.norm(torques[i])
            records[step] += 1
            active[step] += constrained
        elif role in (1, 2) and constrained:
            hand[step, role-1] = True
    weight = metadata['mass_kg'] * np.linalg.norm(metadata['gravity'])
    force_ratio, torque_ratio = load/weight, moment/(weight*metadata['length_scale_m'])
    dt = float(s[0, sc['dt']])
    angles = np.arccos(np.clip((np.trace(rotations, axis1=1, axis2=2)-1)/2, -1., 1.))
    velocity = s[:, sc['free_qvel_0']:sc['free_qvel_2']+1]
    common = ((np.arange(n)*dt >= 1) & (np.linalg.norm(centers-[0, 0, .5], axis=1) < .04) &
              (np.linalg.norm(velocity, axis=1) < .2) & (angles < .8) & hand.all(axis=1))
    writes = any(s[:, sc[k]].any() for k in ('applied_any', 'target_qpos_write', 'target_qvel_write'))
    common &= metadata['global_common'] and not writes
    q_expected = arrays['common_q'] & (metadata['global_common'] and not writes)
    eligible = (force_ratio <= force_low) & (torque_ratio <= torque_low)
    loaded = (force_ratio >= force_high) | (torque_ratio >= torque_high)
    geometric_conflict = ((gap < -penetration_tol) | (active > 0)) & ~loaded
    definite = eligible & ~geometric_conflict & common
    possible = ~loaded & common
    lower, upper = _duration(definite, dt), _duration(possible, dt)
    verdict = 'PASS' if lower >= hold_s-1e-9 else ('FAIL' if upper < hold_s-1e-9 else 'INDETERMINATE')
    if geometry_error > 1e-12 or wrench_error > 1e-10 or not np.array_equal(common, q_expected):
        verdict = 'INDETERMINATE'
    return dict(reference_version='free-box-plane-raw-reference-1', verdict=verdict,
                definite_seconds=lower, possible_seconds=upper,
                no_contact_seconds=_duration((records == 0) & common, dt),
                geometry_reconstruction_error_m=geometry_error, wrench_reconstruction_error=wrench_error,
                common_conditions_agree=bool(np.array_equal(common, q_expected)),
                independence='Separate raw wrench, vertex geometry and interval implementations; shared MuJoCo physics and task specification',
                human_annotation=False, external_physical_truth=False)
