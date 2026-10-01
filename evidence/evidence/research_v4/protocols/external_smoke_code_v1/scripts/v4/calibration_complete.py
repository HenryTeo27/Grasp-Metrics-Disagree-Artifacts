"""Complete the remaining 32 registered instances without changing the first 48."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json

from .calibration import BASE, run_one
from .common import read_json, sha256, write_json


def complete():
    plan = read_json(BASE / 'design.json')
    lock = read_json(BASE / 'execution_lock.json')
    if sha256(BASE / 'design.json') != lock['design_sha256']:
        raise RuntimeError('Calibration design changed')
    for name, expected in lock['source_hashes'].items():
        if sha256(Path(__file__).with_name(name)) != expected:
            raise RuntimeError(f'Calibration source changed: {name}')
    if not (BASE / 'first48_summary.json').exists():
        raise RuntimeError('The first-48 gate must finish before extending')
    first = read_json(BASE / 'first48_summary.json')
    if not first['all_observer_bit_equal'] or first['reference_disagreement'] or first['counterfactual_invalid']:
        raise RuntimeError('First-48 engineering checks failed')
    remaining = [r for r in plan['cases'] if not (BASE / 'cases' / (r['case_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for row in pool.map(run_one, remaining):
            print(json.dumps(row), flush=True)
    records = [read_json(BASE / 'cases' / (r['case_id']+'.json')) for r in plan['cases']]
    summary = dict(count=len(records), role=plan['role'], all_observer_bit_equal=all(r['observer_bit_equal'] for r in records),
                   reference_disagreement=sum(r['b5']['no_external_load_verdict'] != r['reference']['verdict'] for r in records),
                   counterfactual_invalid=sum(r['counterfactual']['status'] == 'INVALID' for r in records),
                   records=[dict(case_id=r['case']['case_id'], b5=r['b5']['no_external_load_verdict'],
                                 b4=r['b4']['no_external_load_verdict'], nc=r['b5']['no_contact_result'],
                                 reference=r['reference']['verdict'], cf=r['counterfactual'].get('cell', r['counterfactual']['status'])) for r in records])
    write_json(BASE / 'all80_summary.json', summary, exclusive=True)
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}))


if __name__ == '__main__':
    complete()
