"""Registered offline operating curves and unamortized scoring cost on controls."""
from dataclasses import replace
import time

import numpy as np

from .baselines import historical, verdict
from .common import OUT, read_json, sha256, write_csv, write_json
from .contracts import Calibration, evaluate
from .statistics import classification

GRID = ((1e-6, 1e-4), (1e-5, 1e-3), (1e-4, 1e-2), (1e-3, 1e-1), (1e-2, 1.))


def run():
    from .protocol import verify_lock
    lock = verify_lock(check_runtime=False)
    rows, costs = [], []
    design = read_json(OUT/'protocols/final_controls.json')
    for case in design:
        path = OUT/'controls/final/cases'/(case['case_id']+'.json')
        record = read_json(path)
        if sha256(path.with_suffix('.npz')) != record['trace_sha256']:
            raise RuntimeError('Control trace changed')
        with np.load(path.with_suffix('.npz'), allow_pickle=False) as z:
            arrays = {k: z[k] for k in ('steps', 'common_q', 'geometry_gap')}
        config = Calibration(**lock['calibration'])
        for low, high in GRID:
            operating = replace(config, force_pass_ratio=low, force_fail_ratio=high,
                                torque_pass_ratio=low, torque_fail_ratio=high)
            methods = historical(arrays, record['metadata'], operating)
            for method, result in methods.items():
                rows.append(dict(case_id=case['case_id'], low=low, high=high, method=method,
                    verdict=verdict(result), reference=record['reference']['verdict'],
                    validity=result.get('trace_validity', 'VALID')))
        for method in ('B4', 'B5'):
            start = time.perf_counter()
            result = evaluate(arrays['steps'], record['metadata']['step_columns'], arrays['common_q'],
                              record['metadata'], config, geometry_gap=arrays['geometry_gap'], use_geometry=method == 'B5')
            costs.append(dict(case_id=case['case_id'], method=method, wall_s=time.perf_counter()-start,
                physical_steps=0, trace_bytes=path.with_suffix('.npz').stat().st_size,
                matching_nominal_verdict=verdict(result) == verdict(record['methods'][method])))
    curves = []
    for low, high in GRID:
        for method in sorted({r['method'] for r in rows}):
            group = [r for r in rows if r['low'] == low and r['method'] == method]
            curves.append(dict(low=low, high=high, method=method, **classification(
                [r['verdict'] for r in group], [r['reference'] for r in group], [r['validity'] for r in group])))
    write_csv(OUT/'analysis/operating_curve_cases.csv', rows)
    write_csv(OUT/'analysis/operating_curves.csv', curves)
    write_csv(OUT/'analysis/scoring_costs.csv', costs)
    summary = dict(curves=curves, costs={m: dict(median_s=float(np.median([r['wall_s'] for r in costs if r['method'] == m])),
        p95_s=float(np.quantile([r['wall_s'] for r in costs if r['method'] == m], .95))) for m in ('B4', 'B5')},
        scope='Registered five-point controls sensitivity relative to fixed nominal reference; not post-test threshold selection. '
              'CPU timing is single offline scoring call, excludes telemetry/IO and simulator, hardware-dependent.',
        nominal_verdicts_match=all(r['matching_nominal_verdict'] for r in costs))
    write_json(OUT/'analysis/operating_curves.json', summary)
    return dict(rows=len(rows), nominal_verdicts_match=summary['nominal_verdicts_match'])


if __name__ == '__main__':
    print(run())
