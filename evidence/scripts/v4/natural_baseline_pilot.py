"""Pre-test baseline and numerical checks on the same registered 20 old scenes."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json

import mujoco
import numpy as np

from .common import OUT, read_json, sha256, write_json
from .counterfactual import _relative_pose, endpoint, remove_target_environment
from .mechanical_baselines import signed_force_probe, static_feasibility
from .natural_pilot import SOURCE, DEST as FIRST, adapt, frozen

DEST = OUT/'calibration/natural_baselines_sensitivity_v1'


def load_phase(row):
    record = read_json(SOURCE/(row['job_id']+'.json'))
    with np.load(SOURCE/(row['job_id']+'.npz'), allow_pickle=False) as z:
        arrays = {k: z[k] for k in ('steps', 'controls', 'mocap', 'post_qpos', 'post_qvel', 'snapshot_state',
                                  'samples', 'legacy_step_index', 'legacy_telemetry', 'actuator_forces')}
    metadata, gap = adapt(arrays, record)
    arrays['geometry_gap'] = gap
    def factory():
        model, _ = frozen.compile_case(frozen.old.SCENE, record['job']['case'])
        frozen.old.apply_object_geom(model, record['job']['case'])
        return model
    model = factory()
    data = mujoco.MjData(model)
    flag = mujoco.mjtState(metadata['snapshot']['flag'])
    mujoco.mj_setState(model, data, arrays['snapshot_state'], flag)
    first = metadata['planned_steps']-round(4/model.opt.timestep)
    qa, va = metadata['target_qadr'], metadata['target_vadr']
    for i in range(metadata['snapshot']['step'], first):
        data.ctrl[:] = arrays['controls'][i]
        tape = arrays['mocap'][i]
        data.mocap_pos[:] = tape[:3*model.nmocap].reshape(-1, 3)
        data.mocap_quat[:] = tape[3*model.nmocap:].reshape(-1, 4)
        mujoco.mj_step(model, data)
        if (not np.array_equal(data.qpos[qa:qa+7], arrays['post_qpos'][i]) or
                not np.array_equal(data.qvel[va:va+6], arrays['post_qvel'][i]) or
                not np.array_equal(data.actuator_force, arrays['actuator_forces'][i])):
            raise RuntimeError('Natural pilot warm continuation mismatch')
    state = np.empty_like(arrays['snapshot_state'])
    mujoco.mj_getState(model, data, state, flag)
    arrays['snapshot_state'] = state
    metadata['snapshot'] = dict(step=first, flag=int(flag), time=float(data.time))
    return arrays, metadata, factory


def numerical_branches(arrays, metadata, factory, variant):
    first = metadata['snapshot']['step']
    old_dt = float(arrays['steps'][0, metadata['step_columns'].index('dt')])
    flag = mujoco.mjtState(metadata['snapshot']['flag'])
    target, ref = metadata['target_body'], metadata['reference_body_id']
    qa, va = metadata['target_qadr'], metadata['target_vadr']
    results = {}
    for removed in (False, True):
        model = factory()
        if variant == 'half_dt':
            model.opt.timestep *= .5
        elif variant == 'double_dt':
            model.opt.timestep *= 2
        elif variant == 'half_iterations':
            model.opt.iterations = max(1, model.opt.iterations//2)
        elif variant != 'nominal':
            raise ValueError(variant)
        if removed:
            remove_target_environment(model, target, metadata['body_roles'])
        data, scratch = mujoco.MjData(model), mujoco.MjData(model)
        mujoco.mj_setState(model, data, arrays['snapshot_state'], flag)
        initial = _relative_pose(model, data, scratch, target, ref)
        dt = model.opt.timestep
        count = round(3/dt)
        qs = []
        for i in range(count):
            step = first+int(np.floor(i*dt/old_dt+1e-9))
            data.ctrl[:] = arrays['controls'][step]
            tape = arrays['mocap'][step]
            data.mocap_pos[:] = tape[:3*model.nmocap].reshape(-1, 3)
            data.mocap_quat[:] = tape[3*model.nmocap:].reshape(-1, 4)
            mujoco.mj_step(model, data)
            if variant == 'nominal' and not removed:
                if (not np.array_equal(data.qpos[qa:qa+7], arrays['post_qpos'][step]) or
                        not np.array_equal(data.qvel[va:va+6], arrays['post_qvel'][step])):
                    raise RuntimeError('Nominal sham changed')
            qs.append(_relative_pose(model, data, scratch, target, ref))
        qs = np.asarray(qs)
        speed = np.diff(np.vstack([initial[:3], qs[:, :3]]), axis=0)/dt
        results['removed' if removed else 'nominal'] = endpoint(qs, speed, initial)
    key = (results['nominal']['success'], results['removed']['success'])
    labels = {(True, True): 'BOTH_RETAIN', (True, False): 'DEPENDENT', (False, False): 'BOTH_FAIL', (False, True): 'REMOVAL_RESCUES'}
    return dict(cell=labels[key], endpoints=results, dt_s=float(dt), iterations=int(model.opt.iterations),
                horizon_s=3., physics_steps=2*count, variant=variant)


def one(row):
    arrays, metadata, factory = load_phase(row)
    first = metadata['snapshot']['step']
    window = arrays['steps'][first-250:first]
    columns = metadata['step_columns']
    weight = metadata['mass_kg']*np.linalg.norm(metadata['gravity'])
    features = dict(mean_force_ratio=float(np.mean(window[:, columns.index('env_abs_force_n')])/weight),
                    mean_torque_ratio=float(np.mean(window[:, columns.index('env_abs_torque_nm')])/(weight*metadata['length_scale_m'])),
                    min_geometry_gap_m=float(np.min(arrays['geometry_gap'][first-250:first])))
    variants = [numerical_branches(arrays, metadata, factory, v) for v in ('nominal', 'half_dt', 'double_dt', 'half_iterations')]
    record = dict(job_id=row['job_id'], same_original_scene=True, features=features, numerical_variants=variants,
                  B6=static_feasibility(arrays, metadata, factory), B7=signed_force_probe(arrays, metadata, factory))
    old = read_json(OUT/'calibration/natural_allegro_schedule_pilot_v1/cases'/(row['job_id']+'.json'))
    if variants[0]['cell'] != old['counterfactual']['cell']:
        raise RuntimeError('Nominal result differs from original phase pilot')
    write_json(DEST/'cases'/(row['job_id']+'.json'), record, exclusive=True)
    return dict(job_id=row['job_id'], labels=[r['cell'] for r in variants], B6=record['B6'].get('feasible', record['B6']['status']),
                B7=record['B7'].get('robust', record['B7']['status']))


def run():
    rows = [r for r in read_json(FIRST/'design.json')['rows'] if r['branch_selected']]
    lock = dict(role='DEVELOPMENT_ONLY_SAME_20_OLD_SCENES', rows=rows,
                variants=['nominal', 'half_dt', 'double_dt', 'half_iterations'], horizon_s=3.,
                continuation='Fixed original command/mocap tape, zero-order resampled at each variant dt; same full initial state',
                hashes={n: sha256(Path(__file__).with_name(n)) for n in
                        ('natural_baseline_pilot.py', 'mechanical_baselines.py', 'counterfactual.py')})
    path = DEST/'design.json'
    if path.exists():
        if read_json(path) != lock:
            raise RuntimeError('Natural pilot lock changed')
    else:
        write_json(path, lock, exclusive=True)
    todo = [r for r in rows if not (DEST/'cases'/(r['job_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, todo):
            print(json.dumps(result), flush=True)
    records = [read_json(DEST/'cases'/(r['job_id']+'.json')) for r in rows]
    summary = dict(n=len(records), stable_cases=sum(len({v['cell'] for v in r['numerical_variants']}) == 1 for r in records),
                   by_variant={v: dict(Counter(r['numerical_variants'][i]['cell'] for r in records))
                               for i, v in enumerate(lock['variants'])},
                   B6_status=dict(Counter(r['B6']['status'] for r in records)),
                   B7_values=dict(Counter(str(r['B7'].get('robust')) for r in records)),
                   B7_physics_steps=sum(r['B7']['physics_steps'] for r in records),
                   interpretation='Exclusion-selected development cases, not a natural prevalence estimate or unseen accuracy test')
    write_json(DEST/'summary.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    run()
