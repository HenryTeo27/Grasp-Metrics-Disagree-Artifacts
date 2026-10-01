"""Prespecified development-only 80-instance calibration, first 48 nested inside."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
import time

import numpy as np

from .common import OUT, fingerprint, output_path, read_json, sha256, write_json
from .controls import Fixture, MECHANISMS, build, run_fixture
from .control_reference import adjudicate
from .counterfactual import branch_fixture
from .contracts import Calibration, evaluate

BASE = OUT / 'calibration/free_controls_v1'


def design():
    rng = np.random.default_rng(51001)
    rows = []
    for j in range(10):
        for i, mechanism in enumerate(MECHANISMS):
            fixture = Fixture(mechanism=mechanism, seed=51000+j*8+i,
                              mass=float(rng.uniform(.05, .10)), half_x=float(rng.uniform(.025, .035)),
                              half_y=float(rng.uniform(.022, .029)), half_z=float(rng.uniform(.025, .035)),
                              pad_friction=float(rng.uniform(.55, .9)),
                              jaw_command=(float(rng.uniform(.00302, .00315)) if mechanism == 'independent' and j in (2, 5, 8)
                                           else float(rng.uniform(.010, .016))),
                              gap_m=float(rng.uniform(.010, .014)),
                              target_tilt_rad=(float(rng.uniform(-.15, .15)) if j % 3 == 2 else 0.),
                              target_offset_y=(float(rng.uniform(-.007, .007)) if j % 3 == 1 else 0.),
                              initial_angular_speed=(float(rng.uniform(-1., 1.)) if j % 3 == 2 else 0.))
            _, xml = build(fixture)
            physical = fingerprint(dict(xml=xml, initial_angular_speed=fixture.initial_angular_speed,
                                        command=fixture.jaw_command, mechanism=fixture.mechanism))
            rows.append(dict(case_id=f'cal_{j*8+i:03d}', first48=j < 6, physical_signature=physical,
                             parameters=asdict(fixture)))
    if len({r['physical_signature'] for r in rows}) != 80:
        raise RuntimeError('Repeated physical initializations')
    payload = dict(role='DEVELOPMENT_CALIBRATION_NOT_FORMAL_TEST', seed=51001, cases=rows,
                   early_subset='First six instances of each group: 48 of the same 80, not additional N',
                   purpose='Instrument, threshold and mechanism calibration; weak/lateral/rotational controls are deliberately included',
                   count=80, thresholds='Development defaults; no frozen operating point yet')
    write_json(BASE / 'design.json', payload, exclusive=True)
    return payload


def run_one(row):
    started = time.perf_counter()
    fixture = Fixture(**row['parameters'])
    arrays, metadata = run_fixture(fixture)
    plain = run_fixture(fixture, record=False)
    if not np.array_equal(plain, arrays['post_qpos']):
        raise RuntimeError('Observer equivalence failed')
    config = Calibration()
    result = evaluate(arrays['steps'], metadata['step_columns'], arrays['common_q'], metadata,
                      config, geometry_gap=arrays['geometry_gap'])
    simple = evaluate(arrays['steps'], metadata['step_columns'], arrays['common_q'], metadata,
                      config, use_geometry=False)
    reference = adjudicate(arrays, metadata)
    cf = branch_fixture(arrays, metadata)
    base = BASE / 'cases' / row['case_id']
    with output_path(base.with_suffix('.npz')).open('xb') as handle:
        np.savez_compressed(handle, **arrays)
    record = dict(case=row, metadata=metadata, b5=result, b4=simple, reference=reference, counterfactual=cf,
                  observer_bit_equal=True, elapsed_s=time.perf_counter()-started)
    write_json(base.with_suffix('.json'), record, exclusive=True)
    return dict(case_id=row['case_id'], mechanism=fixture.mechanism,
                b5=result['no_external_load_verdict'], b4=simple['no_external_load_verdict'],
                nc=result['no_contact_result'], reference=reference['verdict'],
                cf=cf.get('cell', cf['status']), elapsed_s=record['elapsed_s'])


def run_first48(workers=4):
    path = BASE / 'design.json'
    plan = read_json(path) if path.exists() else design()
    source_names = ('calibration.py', 'controls.py', 'control_reference.py', 'counterfactual.py',
                    'contact_observer.py', 'contracts.py')
    source_lock = {name: sha256(__import__('pathlib').Path(__file__).with_name(name)) for name in source_names}
    lock_path = BASE / 'execution_lock.json'
    if lock_path.exists():
        if read_json(lock_path)['source_hashes'] != source_lock:
            raise RuntimeError('Calibration implementation changed; use a new registered development attempt')
    else:
        write_json(lock_path, dict(source_hashes=source_lock, design_sha256=sha256(path)), exclusive=True)
    rows = [r for r in plan['cases'] if r['first48'] and not (BASE / 'cases' / (r['case_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(run_one, rows):
            print(json.dumps(row), flush=True)
    records = [read_json(BASE / 'cases' / (r['case_id']+'.json')) for r in plan['cases'] if r['first48']]
    summary = dict(count=len(records), role=plan['role'], all_observer_bit_equal=all(r['observer_bit_equal'] for r in records),
                   reference_disagreement=sum(r['b5']['no_external_load_verdict'] != r['reference']['verdict'] for r in records),
                   counterfactual_invalid=sum(r['counterfactual']['status'] == 'INVALID' for r in records),
                   records=[dict(case_id=r['case']['case_id'], b5=r['b5']['no_external_load_verdict'],
                                 b4=r['b4']['no_external_load_verdict'], nc=r['b5']['no_contact_result'],
                                 reference=r['reference']['verdict'], cf=r['counterfactual'].get('cell', r['counterfactual']['status'])) for r in records])
    write_json(BASE / 'first48_summary.json', summary, exclusive=True)
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}))


if __name__ == '__main__':
    run_first48()
