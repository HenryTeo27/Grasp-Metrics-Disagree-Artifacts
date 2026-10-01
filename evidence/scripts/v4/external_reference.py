"""Independent raw-evidence reconstruction for the explicitly supported adapters.

No imports from the tested auditor or geometry helper. This shares the simulator
and the declared task specification; it is not human or real-world ground truth.
"""
import numpy as np


def duration(mask, dt):
    current = best = 0
    for value in mask:
        current = current+1 if value else 0
        best = max(best, current)
    return best*dt


def quaternion_rotations(q):
    w, x, y, z = q.T
    return np.stack([1-2*y*y-2*z*z, 2*x*y-2*z*w, 2*x*z+2*y*w,
                     2*x*y+2*z*w, 1-2*x*x-2*z*z, 2*y*z-2*x*w,
                     2*x*z-2*y*w, 2*y*z+2*x*w, 1-2*x*x-2*y*y], axis=-1).reshape(-1, 3, 3)


def vertex_geometry(raw, specification):
    n = len(raw)
    nb, np_ = len(specification['environment_box_geoms']), len(specification['environment_plane_geoms'])
    signs = np.array([[i, j, k] for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)])
    center, rotation = raw[:, :3], raw[:, 3:12].reshape(n, 3, 3)
    target_vertices = center[:, None]+np.einsum('nij,kj->nki', rotation, signs*np.asarray(specification['target_half_size']))
    cursor = 12
    box_centers = raw[:, cursor:cursor+3*nb].reshape(n, nb, 3)
    cursor += 3*nb
    box_rotations = raw[:, cursor:cursor+9*nb].reshape(n, nb, 3, 3)
    cursor += 9*nb
    plane_origins = raw[:, cursor:cursor+3*np_].reshape(n, np_, 3)
    cursor += 3*np_
    plane_normals = raw[:, cursor:cursor+3*np_].reshape(n, np_, 3)
    clearance = np.full(n, 1e10)
    for b in range(nb):
        rb = box_rotations[:, b]
        other_vertices = box_centers[:, b, None]+np.einsum('nij,kj->nki', rb, signs*np.asarray(specification['environment_box_halves'][b]))
        axes = [rotation[:, :, j] for j in range(3)]+[rb[:, :, j] for j in range(3)]
        axes += [np.cross(rotation[:, :, i], rb[:, :, j]) for i in range(3) for j in range(3)]
        best = np.full(n, -1e10)
        for axis in axes:
            length = np.linalg.norm(axis, axis=1)
            unit = axis/np.where(length < 1e-10, 1., length)[:, None]
            ta = np.einsum('nkj,nj->nk', target_vertices, unit)
            ea = np.einsum('nkj,nj->nk', other_vertices, unit)
            separation = np.maximum(ta.min(axis=1)-ea.max(axis=1), ea.min(axis=1)-ta.max(axis=1))
            separation[length < 1e-10] = -1e10
            best = np.maximum(best, separation)
        clearance = np.minimum(clearance, best)
    for p in range(np_):
        distances = np.einsum('nkj,nj->nk', target_vertices-plane_origins[:, p, None], plane_normals[:, p])
        clearance = np.minimum(clearance, distances.min(axis=1))
    return clearance


def adjudicate(arrays, metadata, *, force_low=1e-4, force_high=1e-2, torque_low=1e-4,
               torque_high=1e-2, hold_s=15., penetration_tol=1e-5):
    s, contacts = arrays['steps'], arrays['contacts']
    sc = {k: i for i, k in enumerate(metadata['step_columns'])}
    cc = {k: i for i, k in enumerate(metadata['contact_columns'])}
    n = len(s)
    com = s[:, [sc['com_'+a] for a in 'xyz']]
    forces, moments = np.zeros((len(contacts), 3)), np.zeros((len(contacts), 3))
    if len(contacts):
        frames = contacts[:, cc['frame_0']:cc['frame_8']+1].reshape(-1, 3, 3)
        direction = np.where(contacts[:, cc['body2']] == metadata['target_body'], 1., -1.)
        local_f = contacts[:, cc['local_fn']:cc['local_ft2']+1]
        local_m = contacts[:, cc['local_tn']:cc['local_tt2']+1]
        forces = np.einsum('ni,nij->nj', local_f, frames)*direction[:, None]
        moments = np.einsum('ni,nij->nj', local_m, frames)*direction[:, None]
    ticks = contacts[:, cc['step']].astype(int)
    roles = contacts[:, cc['role']].astype(int)
    active = contacts[:, cc['efc_address']] >= 0
    points = contacts[:, cc['point_x']:cc['point_z']+1]
    moments += np.cross(points-com[ticks], forces)
    load, torque, env_active, env_count, hand_active = (np.zeros(n) for _ in range(5))
    normals = np.zeros((n, 2))
    counts = np.zeros((n, 2), dtype=int)
    env = roles == 0
    np.add.at(load, ticks[env], np.linalg.norm(forces[env], axis=1))
    np.add.at(torque, ticks[env], np.linalg.norm(moments[env], axis=1))
    np.add.at(env_active, ticks[env], active[env])
    np.add.at(env_count, ticks[env], 1)
    np.add.at(hand_active, ticks[~env], active[~env])
    for role in (1, 2):
        selected = roles == role
        np.add.at(counts[:, role-1], ticks[selected], 1)
        np.add.at(normals[:, role-1], ticks[selected], contacts[selected, cc['local_fn']])
    wrench_error = max(float(np.max(np.abs(load-s[:, sc['env_abs_force_n']]))),
                       float(np.max(np.abs(torque-s[:, sc['env_abs_torque_nm']]))))
    passive_error = 0.
    if 'target_damping_force_n' in sc:
        damping = np.asarray(metadata['target_damping_coefficients'])
        velocity = s[:, [sc[f'free_qvel_{i}'] for i in range(6)]]
        if not metadata.get('damping_enabled', True):
            damping = np.zeros(6)
        rotation = quaternion_rotations(s[:, [sc['quat_'+a] for a in 'wxyz']])
        arm = np.einsum('nij,j->ni', rotation, metadata['target_body_ipos'])
        passive = []
        for v in (velocity, arrays['post_qvel'] if metadata.get('implicit_joint_damping', True) else velocity):
            generalized = -v*damping
            f = generalized[:, :3]
            t = np.einsum('nij,nj->ni', rotation, generalized[:, 3:])-np.cross(arm, f)
            passive.append((np.linalg.norm(f, axis=1), np.linalg.norm(t, axis=1)))
        for suffix, (f, t) in zip(('', '_post'), passive):
            passive_error = max(passive_error, float(np.max(np.abs(f-s[:, sc['target_damping'+suffix+'_force_n']]))),
                                float(np.max(np.abs(t-s[:, sc['target_damping'+suffix+'_torque_nm']]))))
        load += np.maximum(passive[0][0], passive[1][0])
        torque += np.maximum(passive[0][1], passive[1][1])
    dt = float(s[0, sc['dt']])
    if 'allegro_reference' in metadata:
        spec = metadata['allegro_reference']
        present, maximum = np.zeros((n, 3), dtype=int), np.zeros((n, 3))
        for role in (1, 2, 3):
            selected = roles == role
            np.add.at(present[:, role-1], ticks[selected], 1)
            np.maximum.at(maximum[:, role-1], ticks[selected], contacts[selected, cc['local_fn']])
        opposition = present[:, 1] > 0
        opposition_force = maximum[:, 1] > 1e-4
        if spec['palm_opposition']:
            opposition |= present[:, 2] > 0
            opposition_force |= maximum[:, 2] > 1e-4
        settle = spec['settle_steps']
        common = ((np.arange(n) >= settle) & (com[:, 2]-com[settle-1, 2] >= spec['min_lift_m']) &
                  (present[:, 0] > 0) & opposition & (maximum[:, 0] > 1e-4) & opposition_force)
        rotation = quaternion_rotations(s[:, [sc['quat_'+a] for a in 'wxyz']])
        size, shape = np.asarray(spec['size']), spec['shape']
        if shape == 'box':
            vertices = np.asarray([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])*size
            bottom = np.einsum('nj,kj->nk', rotation[:, 2], vertices).min(axis=1)
        elif shape == 'sphere':
            bottom = np.full(n, -size[0])
        elif shape == 'capsule':
            bottom = -size[0]-size[1]*np.abs(rotation[:, 2, 2])
        elif shape == 'cylinder':
            bottom = -size[1]*np.abs(rotation[:, 2, 2])-size[0]*np.linalg.norm(rotation[:, 2, :2], axis=1)
        else:
            raise ValueError('Unknown primitive reference')
        gap = com[:, 2]+bottom-spec['floor_z']
    elif 'initial_object_height_m' in metadata:
        common = ((com[:, 2]-metadata['initial_object_height_m'] >= .004) & counts.all(axis=1) & (normals.min(axis=1) > 1e-4))
        gap = vertex_geometry(arrays['raw_geometry'], metadata['geometry'])
    elif 'reference_initial_pose' in metadata:
        pose = arrays['relative_pose']
        initial = np.asarray(metadata['reference_initial_pose'])
        angle = 2*np.arccos(np.clip(np.abs(pose[:, 3:]@initial[3:]), 0., 1.))
        speed = np.linalg.norm(s[:, [sc[f'free_qvel_{i}'] for i in range(3)]], axis=1)
        common = ((np.arange(n)*dt >= .5) & (np.linalg.norm(pose[:, :3]-initial[:3], axis=1) <= .03) &
                  (angle <= .35) & (speed <= .2) & (hand_active > 0))
        if env_count.any():
            raise ValueError('Environment-free task has environmental contacts')
        gap = np.full(n, 1e10)
    else:
        raise ValueError('Unregistered external reference adapter')
    geometry_error = float(np.max(np.abs(gap-arrays['geometry_gap'])))
    common_agree = bool(np.array_equal(common, arrays['common_q']))
    assisted = any(s[:, sc[k]].any() for k in ('applied_any', 'target_qpos_write', 'target_qvel_write'))
    common &= metadata['global_common'] and not assisted
    weight = metadata['mass_kg']*np.linalg.norm(metadata['gravity'])
    rf, rm = load/weight, torque/(weight*metadata['length_scale_m'])
    loaded = (rf >= force_high) | (rm >= torque_high)
    safe = (rf <= force_low) & (rm <= torque_low) & (gap >= -penetration_tol) & (env_active == 0)
    paths = metadata['support_paths']['complete_for_declared_model']
    if not paths:
        safe[:] = False
    if 'passive_meter_residual' in sc:
        safe &= s[:, sc['passive_meter_residual']] <= 1e-10
    lower, upper = duration(common & safe, dt), duration(common & ~loaded, dt)
    verdict = 'PASS' if lower >= hold_s-1e-9 else 'FAIL' if upper < hold_s-1e-9 else 'INDETERMINATE'
    if not common_agree or max(geometry_error, wrench_error, passive_error) > 1e-9:
        verdict = 'INDETERMINATE'
    return dict(reference_version='external-raw-vertex-passive-reference-1', verdict=verdict,
                definite_seconds=lower, possible_seconds=upper, common_conditions_agree=common_agree,
                geometry_reconstruction_error_m=geometry_error, wrench_reconstruction_error=wrench_error,
                passive_reconstruction_error=passive_error, human_annotation=False,
                independence='Separate vertex/force/interval implementations, shared simulator, saved FK and task specification; '
                             'not real-world truth or blinded human annotation')
