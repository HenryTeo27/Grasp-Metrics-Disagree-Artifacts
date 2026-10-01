"""Shared calibrated/final control runner; final execution requires the G2 lock."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
import json
import time

import mujoco
import numpy as np

from .baselines import historical, verdict
from .common import OUT, output_path, read_json, sha256, write_json
from .contracts import Calibration
from .controls import Fixture, run_fixture
from .control_reference import adjudicate
from .counterfactual import branch_fixture
from .mechanical_baselines import signed_force_probe, static_feasibility


def one(request):
    row, base, config, do_branch = request
    base = Path(base)
    started = time.perf_counter()
    parameters = row['parameters']
    fixture = Fixture(**parameters)
    arrays, metadata = run_fixture(fixture, verify_full_state=True)
    plain = run_fixture(fixture, record=False, verify_full_state=True)
    if not np.array_equal(arrays['integration_states'], plain):
        raise RuntimeError('Full integration-state observer equivalence failed')
    result = historical(arrays, metadata, config)
    reference = adjudicate(arrays, metadata, force_low=config.force_pass_ratio, force_high=config.force_fail_ratio,
                          torque_low=config.torque_pass_ratio, torque_high=config.torque_fail_ratio,
                          hold_s=config.hold_s, penetration_tol=config.penetration_tolerance_m)
    cf = branch_fixture(arrays, metadata) if do_branch else dict(status='NOT_SELECTED')
    factory = lambda: mujoco.MjModel.from_xml_string(metadata['model_xml'])
    b6 = static_feasibility(arrays, metadata, factory) if do_branch else dict(status='NOT_SELECTED')
    b7 = signed_force_probe(arrays, metadata, factory) if do_branch else dict(status='NOT_SELECTED')
    output = base/'cases'/row['case_id']
    with output_path(output.with_suffix('.npz')).open('xb') as handle:
        np.savez_compressed(handle, **arrays)
    record = dict(case=row, metadata=metadata, methods=result, reference=reference, counterfactual=cf, B6=b6, B7=b7,
                  observer_full_integration_bit_equal=True, trace_sha256=sha256(output.with_suffix('.npz')),
                  elapsed_s=time.perf_counter()-started,
                  nominal_physics_steps=2*metadata['planned_steps'],
                  branch_cost_steps=(2*round(3/fixture.timestep_s) if cf['status'] == 'VALID' else 0)+b7.get('physics_steps', 0))
    write_json(output.with_suffix('.json'), record, exclusive=True)
    return dict(case_id=row['case_id'], methods={k: verdict(v) for k, v in result.items()},
                reference=reference['verdict'], cf=cf.get('cell', cf['status']))


def run(split='final', workers=4):
    if split == 'calibration':
        base = OUT/'calibration/requalified_controls_v2'
        design = read_json(OUT/'calibration/free_controls_v1/design.json')['cases']
        config = Calibration(version='merged-v4-calibration-nominal-20261001')
        protocol = dict(role='SAME_REGISTERED_80_REQUALIFIED_NOT_NEW_N', calibration=asdict(config),
                        design_sha256=sha256(OUT/'calibration/free_controls_v1/design.json'),
                        source_hashes={n: sha256(Path(__file__).with_name(n)) for n in
                                       ('formal_controls.py', 'controls.py', 'control_reference.py', 'contact_observer.py',
                                        'contracts.py', 'baselines.py', 'counterfactual.py', 'mechanical_baselines.py')})
        path = base/'execution_lock.json'
        if path.exists():
            if read_json(path) != protocol:
                raise RuntimeError('Calibration requalification source changed')
        else:
            write_json(path, protocol, exclusive=True)
        requests = [(r, str(base), config, True) for r in design]
    elif split == 'final':
        from .protocol import verify_lock
        protocol = verify_lock()
        base = OUT/'controls/final'
        config = Calibration(**protocol['calibration'])
        design = read_json(OUT/'protocols/final_controls.json')
        requests = [(r, str(base), config, r['counterfactual_selected']) for r in design]
    else:
        raise ValueError('Unknown control split')
    todo = [r for r in requests if not (base/'cases'/(r[0]['case_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(one, todo):
            print(json.dumps(result), flush=True)
    records = [read_json(base/'cases'/(r['case_id']+'.json')) for r in design]
    summary = dict(n=len(records), role=split,
                   methods={k: dict(Counter(verdict(r['methods'][k]) for r in records)) for k in records[0]['methods']},
                   reference=dict(Counter(r['reference']['verdict'] for r in records)),
                   cf=dict(Counter(r['counterfactual'].get('cell', r['counterfactual']['status']) for r in records)),
                   observer_full_integration_bit_equal=all(r['observer_full_integration_bit_equal'] for r in records),
                   nominal_physics_steps=sum(r['nominal_physics_steps'] for r in records),
                   branch_cost_steps=sum(r['branch_cost_steps'] for r in records))
    write_json(base/'summary.json', summary)
    print(json.dumps(summary), flush=True)
    return summary


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', choices=('calibration', 'final'), default='final')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    run(args.split, args.workers)
