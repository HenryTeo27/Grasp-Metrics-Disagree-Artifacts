"""Prespecified phase-timing pilot on the same 20 old natural scenes, not new N."""
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import json

import mujoco
import numpy as np

from .common import OUT, read_json, write_json
from .natural_pilot import SOURCE, DEST as FIRST, adapt, frozen
from .counterfactual import branch_model

DEST = OUT / 'calibration/natural_allegro_schedule_pilot_v1'


def one(row):
    meta = read_json(SOURCE / (row['job_id']+'.json'))
    with np.load(SOURCE / (row['job_id']+'.npz'), allow_pickle=False) as z:
        arrays = {key: z[key] for key in ('steps', 'controls', 'mocap', 'post_qpos', 'post_qvel', 'snapshot_state',
                                         'samples', 'legacy_step_index', 'legacy_telemetry', 'actuator_forces')}
    m, _ = adapt(arrays, meta)
    def factory():
        model, _ = frozen.compile_case(frozen.old.SCENE, meta['job']['case'])
        frozen.old.apply_object_geom(model, meta['job']['case'])
        return model
    model, data = factory(), None
    data = mujoco.MjData(model)
    snap = m['snapshot']
    flag = mujoco.mjtState(snap['flag'])
    mujoco.mj_setState(model, data, arrays['snapshot_state'], flag)
    first = m['planned_steps'] - round(4/model.opt.timestep)
    if first < snap['step']:
        raise ValueError('Registered phase time predates available snapshot')
    qa, va = m['target_qadr'], m['target_vadr']
    for i in range(snap['step'], first):
        data.ctrl[:] = arrays['controls'][i]
        tape = arrays['mocap'][i]
        data.mocap_pos[:] = tape[:3*model.nmocap].reshape(-1, 3)
        data.mocap_quat[:] = tape[3*model.nmocap:].reshape(-1, 4)
        mujoco.mj_step(model, data)
        if (not np.array_equal(data.qpos[qa:qa+7], arrays['post_qpos'][i]) or
            not np.array_equal(data.qvel[va:va+6], arrays['post_qvel'][i]) or
            not np.array_equal(data.actuator_force, arrays['actuator_forces'][i])):
            raise RuntimeError('Nominal warm continuation changed')
    new_state = np.empty_like(arrays['snapshot_state'])
    mujoco.mj_getState(model, data, new_state, flag)
    arrays['snapshot_state'] = new_state
    m['snapshot'] = dict(step=first, flag=int(flag), time=float(data.time))
    cf = branch_model(arrays, m, factory)
    result = dict(job_id=row['job_id'], t0_rule='planned_schedule_end_minus_4_seconds',
                  same_case_as_first_pilot=True, nominal_warm_continuation_bit_equal=True, counterfactual=cf)
    write_json(DEST / 'cases' / (row['job_id']+'.json'), result, exclusive=True)
    return result


def run():
    rows = [r for r in read_json(FIRST / 'design.json')['rows'] if r['branch_selected']]
    write_json(DEST / 'design.json', dict(role='DEVELOPMENT_ONLY_SAME_20_CASES', rows=rows,
               reason='Fixed 8s often falls in acquisition for long schedules; inspect a declared final retention phase',
               t0_rule='planned_schedule_end_minus_4_seconds, from frozen duration only, never from Q/pass or branch outcomes'), exclusive=True)
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, rows):
            results.append(result)
            print(json.dumps(dict(job=result['job_id'], cf=result['counterfactual'].get('cell', result['counterfactual']['status']))), flush=True)
    summary = dict(count=len(results), cells=dict(Counter(r['counterfactual'].get('cell', r['counterfactual']['status']) for r in results)))
    write_json(DEST / 'summary.json', summary, exclusive=True)
    print(summary)


if __name__ == '__main__':
    run()
