"""Registered numerical and controlled support-withdrawal development checks."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path
import json

import mujoco
import numpy as np

from .calibration import BASE
from .common import OUT, read_json, sha256, write_json
from .contracts import evaluate
from .controls import Fixture, run_fixture
from .control_reference import adjudicate
from .counterfactual import branch_fixture, endpoint
from .mechanical_baselines import precondition, restore

DEST = OUT/'calibration/sensitivity_v1'


def gradual_withdrawal(arrays, metadata, *, duration_s=.2, distance_m=.2, horizon_s=3.):
    reason = precondition(arrays, metadata)
    if reason:
        return dict(status='UNREACHABLE', reason=reason, physics_steps=0)
    model, data = restore(arrays, metadata, lambda: mujoco.MjModel.from_xml_string(metadata['model_xml']))
    first, dt = metadata['snapshot']['step'], model.opt.timestep
    count = round(horizon_s/dt)
    if first+count > len(arrays['steps']):
        return dict(status='UNREACHABLE', reason='INSUFFICIENT_TAPE', physics_steps=0)
    scratch = mujoco.MjData(model)
    scratch.qpos[:] = data.qpos
    scratch.mocap_pos[:] = data.mocap_pos
    scratch.mocap_quat[:] = data.mocap_quat
    mujoco.mj_kinematics(model, scratch)
    movements = {}
    for gid in metadata['plane_geoms']:
        mid = int(model.body_mocapid[model.geom_bodyid[gid]])
        if mid < 0:
            return dict(status='NOT_APPLICABLE', reason='NON_MOCAP_PLANE', physics_steps=0)
        direction = -scratch.geom_xmat[gid].reshape(3, 3)[:, 2].copy()
        if mid in movements and not np.array_equal(movements[mid], direction):
            raise ValueError('A support body has conflicting withdrawal directions')
        movements[mid] = direction
    qa, va = metadata['target_qadr'], metadata['target_vadr']
    initial = data.qpos[qa:qa+7].copy()
    qs, vs = [], []
    for i in range(count):
        step = first+i
        data.ctrl[:] = arrays['controls'][step]
        tape = arrays['mocap'][step]
        data.mocap_pos[:] = tape[:3*model.nmocap].reshape(-1, 3)
        data.mocap_quat[:] = tape[3*model.nmocap:].reshape(-1, 4)
        progress = min((i+1)*dt/duration_s, 1.)
        progress = progress*progress*(3-2*progress)
        for mid, direction in movements.items():
            data.mocap_pos[mid] += distance_m*progress*direction
        mujoco.mj_step(model, data)
        qs.append(data.qpos[qa:qa+7].copy())
        vs.append(data.qvel[va:va+6].copy())
    return dict(status='VALID', endpoint=endpoint(np.asarray(qs), np.asarray(vs), initial),
                duration_s=duration_s, distance_m=distance_m, horizon_s=horizon_s, physics_steps=count,
                intervention='Cubic mocap-plane position withdrawal opposite each inward normal; '
                             'collision/friction remain active and original mocap schedule is retained plus offset. '
                             'Kinematic boundary experiment, not asserted equivalent to collision removal.')


def one(row):
    fixture = Fixture(**row['parameters'])
    arrays, metadata = run_fixture(fixture)
    plain = run_fixture(fixture, record=False)
    if not np.array_equal(plain, arrays['post_qpos']):
        raise RuntimeError('Sensitivity observer changed trajectory')
    reference = adjudicate(arrays, metadata)
    result = evaluate(arrays['steps'], metadata['step_columns'], arrays['common_q'], metadata,
                      geometry_gap=arrays['geometry_gap'])
    cf = branch_fixture(arrays, metadata)
    withdrawal = gradual_withdrawal(arrays, metadata)
    record = dict(case=row, observer_bit_equal=True, reference=reference, B5=result,
                  counterfactual=cf, gradual_withdrawal=withdrawal)
    write_json(DEST/'cases'/(row['id']+'.json'), record, exclusive=True)
    return dict(id=row['id'], B5=result['no_external_load_verdict'], cf=cf.get('cell', cf['status']),
                withdrawal=withdrawal.get('endpoint', {}).get('success', withdrawal['status']))


def run():
    cases = read_json(BASE/'design.json')['cases'][:8]
    rows = []
    for case in cases:
        p = Fixture(**case['parameters'])
        for label, fixture in (('nominal', p), ('dt_half', replace(p, timestep_s=.001)),
                               ('dt_double', replace(p, timestep_s=.004)),
                               ('solver_looser', replace(p, solver_iterations=50, solver_tolerance=1e-8))):
            rows.append(dict(id=case['case_id']+'_'+label, base_case=case['case_id'], variant=label, parameters=asdict(fixture)))
    protocol = dict(role='DEVELOPMENT_SENSITIVITY_NOT_NEW_INDEPENDENT_N',
                    selection='First registered calibration instance of each of eight groups, selected without sensitivity outcomes',
                    rows=rows, horizons=dict(main_s=3., withdrawal_s=.2, withdrawal_distance_m=.2),
                    hashes={n: sha256(Path(__file__).with_name(n)) for n in
                            ('sensitivity.py', 'controls.py', 'contact_observer.py', 'counterfactual.py', 'contracts.py', 'control_reference.py')})
    path = DEST/'design.json'
    if path.exists():
        if read_json(path) != protocol:
            raise RuntimeError('Sensitivity protocol changed')
    else:
        write_json(path, protocol, exclusive=True)
    todo = [r for r in rows if not (DEST/'cases'/(r['id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, todo):
            print(json.dumps(result), flush=True)
    records = [read_json(DEST/'cases'/(r['id']+'.json')) for r in rows]
    agreement = []
    for case in cases:
        group = [r for r in records if r['case']['base_case'] == case['case_id']]
        agreement.append(dict(case_id=case['case_id'],
            B5_stable=len({r['B5']['no_external_load_verdict'] for r in group}) == 1,
            cf_stable=len({r['counterfactual'].get('cell', r['counterfactual']['status']) for r in group}) == 1,
            withdrawal_matches_removal=all(r['gradual_withdrawal']['endpoint']['success'] ==
                r['counterfactual']['endpoints']['removed']['success'] for r in group if r['counterfactual']['status'] == 'VALID')))
    summary = dict(count=len(records), base_initializations=len(cases), agreement=agreement,
                   reference_match=all(r['B5']['no_external_load_verdict'] == r['reference']['verdict'] for r in records),
                   observer_bit_equal=all(r['observer_bit_equal'] for r in records),
                   cf_status=dict(Counter(r['counterfactual']['status'] for r in records)),
                   interpretation='Variant trajectories need not be equal; stability means retained categorical labels on this declared small subset only.')
    write_json(DEST/'summary.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    run()
