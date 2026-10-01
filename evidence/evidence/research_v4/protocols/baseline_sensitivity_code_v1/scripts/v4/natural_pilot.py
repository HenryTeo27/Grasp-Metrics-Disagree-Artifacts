"""Development adjudication and predeclared natural branches from old V3 evidence."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json

import mujoco
import numpy as np

from .adapters.allegro import frozen
from .common import OUT, read_json, write_json
from .contracts import Calibration, evaluate
from .counterfactual import branch_model

SOURCE = OUT / 'retrospective/replays/complete_attempt_1'
DEST = OUT / 'calibration/natural_allegro_pilot_v1'


def adapt(arrays, meta):
    job = meta['job']
    model, _ = frozen.compile_case(frozen.old.SCENE, job['case'])
    frozen.old.apply_object_geom(model, job['case'])
    m = dict(meta['observer'])
    target = model.body('object').id
    joint = int(model.body_jntadr[target])
    m.update(target_body=target, target_qadr=int(model.jnt_qposadr[joint]), target_vadr=int(model.jnt_dofadr[joint]),
             reference_body_id=model.body('palm').id,
             length_scale_m=meta['length_scale_m'], planned_steps=meta['planned_steps'],
             terminal_reason=meta['terminal_reason'], global_common=bool(meta['result']['legacy_success'] and
                         not meta['result']['initial_hand_contact'] and meta['result']['temporal']['no_assistance']))
    q = np.zeros(len(arrays['steps']), dtype=bool)
    indices = arrays['legacy_step_index'].astype(int)-1
    q[indices] = np.all(arrays['samples'][:, :4].astype(bool), axis=1) & ~arrays['samples'][:, 5].astype(bool)
    # Historical model has exactly one environment plane; never infer this for another source.
    roles = np.asarray(m['body_roles'])
    env = [i for i in range(model.ngeom) if model.geom_bodyid[i] != target and
           roles[model.geom_bodyid[i]] == 0 and (model.geom_contype[i] or model.geom_conaffinity[i])]
    if env != [model.geom('floor').id] or model.geom_type[env[0]] != mujoco.mjtGeom.mjGEOM_PLANE:
        raise ValueError('Unexpected environment geometry')
    gid = model.geom('object').id
    if np.any(model.body_ipos[target]) or np.any(model.geom_pos[gid]):
        raise ValueError('Primitive support assumes a centered object')
    columns = m['step_columns']
    quat = arrays['steps'][:, columns.index('quat_w'):columns.index('quat_z')+1]
    z = arrays['steps'][:, columns.index('com_z')]
    w, x, y, zz = quat.T
    rz = np.c_[2*(x*zz-y*w), 2*(y*zz+x*w), 1-2*(x*x+y*y)]
    size = model.geom_size[gid]
    kind = model.geom_type[gid]
    if kind == mujoco.mjtGeom.mjGEOM_BOX:
        extent = np.abs(rz) @ size
    elif kind == mujoco.mjtGeom.mjGEOM_SPHERE:
        extent = np.repeat(size[0], len(z))
    elif kind == mujoco.mjtGeom.mjGEOM_CYLINDER:
        extent = size[1]*np.abs(rz[:, 2]) + size[0]*np.sqrt(np.maximum(0., 1-rz[:, 2]**2))
    elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
        extent = size[0] + size[1]*np.abs(rz[:, 2])
    else:
        raise ValueError('Unsupported primitive')
    gap = z-extent-model.geom_pos[env[0], 2]
    old_gap = arrays['legacy_telemetry'][:, frozen.EXTRA_COLUMNS.index('primitive_floor_clearance_m')]
    error = float(np.max(np.abs(gap[indices]-old_gap)))
    if error > 1e-10:
        raise RuntimeError(f'Independent geometry reconstruction mismatch: {error}')
    m['geometry_reconstruction_error_m'] = error
    arrays['common_q'] = q
    return m, gap


def one(row):
    meta = read_json(SOURCE / (row['job_id']+'.json'))
    with np.load(SOURCE / (row['job_id']+'.npz'), allow_pickle=False) as z:
        arrays = {key: z[key] for key in ('steps', 'controls', 'mocap', 'post_qpos', 'post_qvel', 'snapshot_state',
                                         'samples', 'legacy_step_index', 'legacy_telemetry')}
    m, gap = adapt(arrays, meta)
    config = Calibration()
    b5 = evaluate(arrays['steps'], m['step_columns'], arrays['common_q'], m, config, geometry_gap=gap)
    b4 = evaluate(arrays['steps'], m['step_columns'], arrays['common_q'], m, config, use_geometry=False)
    cf = None
    if row['branch_selected']:
        def factory():
            model, _ = frozen.compile_case(frozen.old.SCENE, meta['job']['case'])
            frozen.old.apply_object_geom(model, meta['job']['case'])
            return model
        cf = branch_model(arrays, m, factory)
    result = dict(job_id=row['job_id'], case_id=meta['job']['case']['case_id'], family=meta['job']['family'],
                  role='RETROSPECTIVE_DEVELOPMENT_NOT_FORMAL_TEST', b5=b5, b4=b4, counterfactual=cf,
                  geometry_reconstruction_error_m=m['geometry_reconstruction_error_m'])
    write_json(DEST / 'cases' / (row['job_id']+'.json'), result, exclusive=True)
    return dict(job_id=row['job_id'], b5=b5['no_external_load_verdict'], b4=b4['no_external_load_verdict'],
                cf=None if cf is None else cf.get('cell', cf['status']))


def run():
    metas = [read_json(p) for p in sorted(SOURCE.glob('*.json'))]
    selected, seen = set(), set()
    for meta in metas:
        case = meta['job']['case']['case_id']
        if case not in seen and len(selected) < 20:
            seen.add(case)
            selected.add(meta['job']['job_id'])
    rows = [dict(job_id=m['job']['job_id'], branch_selected=m['job']['job_id'] in selected) for m in metas]
    write_json(DEST / 'design.json', dict(role='DEVELOPMENT_ONLY', retrospective_candidates=len(rows),
               branch_cases=len(selected), selection='First job per unique scene in sorted job-id order, first 20 before CF outcomes',
               rows=rows), exclusive=True)
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, rows):
            results.append(result)
            if result['cf'] is not None:
                print(json.dumps(result), flush=True)
    summary = dict(count=len(results), b5=dict(Counter(r['b5'] for r in results)),
                   b4=dict(Counter(r['b4'] for r in results)),
                   cf=dict(Counter(r['cf'] for r in results if r['cf'] is not None)))
    write_json(DEST / 'summary.json', summary, exclusive=True)
    print(summary)


if __name__ == '__main__':
    run()
