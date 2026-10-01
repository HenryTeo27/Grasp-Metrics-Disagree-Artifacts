"""Development-only calibration curves, ablations and charged mechanical probes."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path
import json

import mujoco
import numpy as np
import scipy

from .baselines import confusion, historical, verdict
from .calibration import BASE
from .common import OUT, read_json, sha256, write_csv, write_json
from .contracts import Calibration
from .mechanical_baselines import signed_force_probe, static_feasibility

DEST = OUT / 'calibration/baselines_v1'
POINTS = [(1e-6, 1e-4), (1e-5, 1e-3), (1e-4, 1e-2), (1e-3, .1), (.01, 1.)]


def run_one(case):
    prefix = BASE/'cases'/case['case_id']
    record = read_json(prefix.with_suffix('.json'))
    with np.load(prefix.with_suffix('.npz'), allow_pickle=False) as data:
        arrays = dict(data)
    metadata = record['metadata']
    operating = historical(arrays, metadata)
    curve = []
    for low, high in POINTS:
        config = replace(Calibration(), force_pass_ratio=low, force_fail_ratio=high,
                         torque_pass_ratio=low, torque_fail_ratio=high)
        results = historical(arrays, metadata, config)
        curve.append(dict(low=low, high=high, **{k: verdict(results[k]) for k in ('B4', 'B4_normal', 'B5')}))
    geometry = []
    for tolerance in (1e-6, 1e-5, 1e-4):
        results = historical(arrays, metadata, replace(Calibration(), penetration_tolerance_m=tolerance))
        geometry.append(dict(penetration_tolerance_m=tolerance, B5=verdict(results['B5'])))
    factory = lambda: mujoco.MjModel.from_xml_string(metadata['model_xml'])
    b6 = static_feasibility(arrays, metadata, factory)
    b7 = signed_force_probe(arrays, metadata, factory)
    result = dict(case_id=case['case_id'], mechanism=case['parameters']['mechanism'],
                  reference=record['reference']['verdict'], fixed_reference_source_sha256=sha256(prefix.with_suffix('.json')),
                  historical={k: verdict(v) for k, v in operating.items()}, curve=curve,
                  geometry_sensitivity=geometry, B6=b6, B7=b7, counterfactual=record['counterfactual'])
    write_json(DEST/'cases'/(case['case_id']+'.json'), result, exclusive=True)
    return dict(case_id=case['case_id'], B6=b6.get('feasible', b6['status']), B7=b7.get('robust', b7['status']))


def run(workers=4):
    design = read_json(BASE/'design.json')
    lock_path = DEST/'execution_lock.json'
    lock = dict(role='DEVELOPMENT_ONLY_SAME_80_NOT_NEW_N', sources={n: sha256(Path(__file__).with_name(n))
                for n in ('baseline_calibration.py', 'baselines.py', 'mechanical_baselines.py', 'contracts.py', 'counterfactual.py')},
                design_sha256=sha256(BASE/'design.json'), operating_point=asdict(Calibration()),
                curve_points=POINTS, scipy_version=scipy.__version__, mujoco_version=mujoco.__version__,
                reference='Fixed archived independent-implementation labels at the declared nominal numerical tolerance; '
                          'sensitivity is relative to that specification, not a change in physical ground truth')
    if lock_path.exists():
        if read_json(lock_path)['sources'] != lock['sources']:
            raise RuntimeError('Baseline source changed; register a new development attempt')
    else:
        write_json(lock_path, lock, exclusive=True)
    todo = [r for r in design['cases'] if not (DEST/'cases'/(r['case_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(run_one, todo):
            print(json.dumps(row), flush=True)
    records = [read_json(DEST/'cases'/(r['case_id']+'.json')) for r in design['cases']]
    references = [r['reference'] for r in records]
    comparisons = {name: confusion([r['historical'][name] for r in records], references)
                   for name in records[0]['historical']}
    curve = []
    for j, (low, high) in enumerate(POINTS):
        for method in ('B4', 'B4_normal', 'B5'):
            curve.append(dict(method=method, low=low, high=high,
                              **confusion([r['curve'][j][method] for r in records], references)))
    cf_rows = [r for r in records if r['counterfactual']['status'] == 'VALID']
    mechanical = {}
    for method, key in (('B6', 'feasible'), ('B7', 'robust')):
        mechanical[method] = dict(status=dict(Counter(r[method]['status'] for r in records)),
                                 value=dict(Counter(str(r[method].get(key)) for r in records)),
                                 physics_steps=sum(r[method]['physics_steps'] for r in records),
                                 cf_valid_n=len(cf_rows),
                                 comparison=confusion(['PASS' if r[method].get(key) is True else 'FAIL'
                                                      if r[method].get(key) is False else 'INDETERMINATE' for r in cf_rows],
                                                     ['PASS' if r['counterfactual']['endpoints']['removed']['success']
                                                      else 'FAIL' for r in cf_rows]))
    summary = dict(n=len(records), role='DEVELOPMENT_ONLY', historical=comparisons, curves=curve,
                   mechanical=mechanical, geometry_sensitivity={str(t): dict(Counter(r['geometry_sensitivity'][i]['B5']
                                               for r in records)) for i, t in enumerate((1e-6, 1e-5, 1e-4))},
                   operating_point_decision='Retain nominal 1e-4 pass / 1e-2 fail for force and torque; '
                                            'do not optimize toward selected old exclusions. Formal G2 still pending.',
                   limitations='Control-apparatus instances are not independent mechanisms. The reference shares simulator '
                               'and numerical specification. B6/B7 predict future capacity, not the historical C_NL contract.')
    write_json(DEST/'summary.json', summary)
    write_csv(DEST/'historical_comparison.csv', [dict(method=k, **v) for k, v in comparisons.items()])
    write_csv(DEST/'curves.csv', curve)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    run()
