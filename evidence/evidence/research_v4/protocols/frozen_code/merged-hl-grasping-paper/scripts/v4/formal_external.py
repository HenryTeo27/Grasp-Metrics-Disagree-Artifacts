"""Source-stratified external execution with separate native and added tasks."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json

import numpy as np

from .baselines import historical, verdict
from .common import OUT, output_path, read_json, sha256, write_json
from .contracts import Calibration
from .counterfactual import branch_model
from .external_reference import adjudicate
from .mechanical_baselines import signed_force_probe, static_feasibility


def one(request):
    source, row, base, config = request
    base = Path(base)
    if source == 'fetch':
        from .adapters.fetch import rollout
        arrays, metadata, traces, factory = rollout(row['seed'])
        plain = rollout(row['seed'], observed=False)
        equal = all(np.array_equal(a, b) for a, b in zip(traces, plain))
        native = dict(success=metadata['native_success'], success_at_50=metadata['native_success_at_50'],
                      first_terminal_actions=metadata['native_terminal_actions'], goal_unchanged=metadata['native_goal_unchanged'])
    elif source == 'dexgraspbench':
        from .adapters.dexgraspbench import ROOT, added_retention
        selected = ROOT/row['source_input']
        if sha256(selected) != row['input_sha256']:
            raise RuntimeError('Pinned source grasp changed')
        arrays, metadata, traces, factory = added_retention(selected)
        plain = added_retention(selected, observed=False)
        equal = np.array_equal(traces, plain)
        # Native six-force behavior is executed independently with upstream semantics.
        from .dexgraspbench_smoke import in_directory
        from .adapters.dexgraspbench import setup
        with in_directory(ROOT):
            task = setup(selected)
            native_value = task._eval_simulate_under_extforce()
        native = dict(result=[bool(native_value[0]), float(native_value[1]), float(native_value[2])],
                      scope='Unmodified upstream gravity-off signed-force task, not added retention')
    else:
        raise ValueError('Unregistered source')
    if not equal:
        raise RuntimeError('Observer changed external execution')
    methods = historical(arrays, metadata, config)
    methods['B0']['scope'] = 'Added-task accumulated-Q proxy; native task outcome is stored separately'
    cf = branch_model(arrays, metadata, factory) if row['counterfactual_selected'] else dict(status='NOT_SELECTED')
    b6 = static_feasibility(arrays, metadata, factory) if row['counterfactual_selected'] else dict(status='NOT_SELECTED')
    b7 = signed_force_probe(arrays, metadata, factory) if row['counterfactual_selected'] else dict(status='NOT_SELECTED')
    reference = adjudicate(arrays, metadata) if row['reference_selected'] else dict(verdict='NOT_SELECTED')
    output = base/'cases'/row['case_id']
    with output_path(output.with_suffix('.npz')).open('xb') as handle:
        np.savez_compressed(handle, **arrays)
    result = dict(case=row, metadata=metadata, methods=methods, native=native, reference=reference,
        counterfactual=cf, B6=b6, B7=b7, observer_bit_equal=equal, trace_sha256=sha256(output.with_suffix('.npz')),
        nominal_physics_steps=2*metadata['planned_steps'],
        branch_cost_steps=(2*round(3/arrays['steps'][0, metadata['step_columns'].index('dt')]) if cf['status'] == 'VALID' else 0)+b7.get('physics_steps', 0))
    write_json(output.with_suffix('.json'), result, exclusive=True)
    return dict(case_id=row['case_id'], B5=verdict(methods['B5']), native=native, cf=cf.get('cell', cf['status']))


def run(source, workers=2, qualification=False):
    if qualification:
        rows = [dict(case_id='native_goal_qualification_900001', seed=900001,
                     counterfactual_selected=True, reference_selected=True)]
        if source != 'fetch':
            raise ValueError('Only native-goal Fetch qualification is registered')
        config = Calibration()
        base = OUT/'calibration/fetch_native_goal_v1'
        write_json(base/'design.json', dict(role='DEVELOPMENT_ONLY', rows=rows), exclusive=True)
    else:
        from .protocol import verify_lock
        lock = verify_lock(runtime=source)
        config = Calibration(**lock['calibration'])
        rows = read_json(OUT/'protocols'/('final_'+source+'.json'))
        base = OUT/'external'/source/'final'
    todo = [(source, r, str(base), config) for r in rows if not (base/'cases'/(r['case_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(one, todo):
            print(json.dumps(result), flush=True)
    return dict(source=source, cases=len(rows), role='development' if qualification else 'formal')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('source', choices=('fetch', 'dexgraspbench'))
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--qualification', action='store_true')
    args = parser.parse_args()
    print(run(args.source, args.workers, args.qualification))
