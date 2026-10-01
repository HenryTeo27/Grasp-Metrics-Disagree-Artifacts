"""Predeclared three-category old-data smoke of the independent added use task."""
import json

import numpy as np

from .adapters.allegro import execute, frozen
from .common import OUT, V3, read_json, write_json
from .natural_pilot import adapt
from .selection import future_retention

DEST = OUT/'calibration/utility_continuation_v1'


def run():
    choices = read_json(OUT/'calibration/utility_route_pilot.json')
    if not choices['U2']['enabled']:
        raise RuntimeError('U2 not admitted by development pilot')
    jobs = {j['job_id']: j for j in read_json(V3/'jobs.json')}
    members = [m for m in read_json(V3/'membership.json') if m['block'].startswith('new') and m['policy'] == 'repair']
    groups = {}
    for m in sorted(members, key=lambda r: (r['case_id'], r['rank'])):
        r = read_json(V3/'trials'/(m['job_id']+'.json'))
        category = 'clear_pass' if r['temporal']['clear_contiguous_success'] else 'native_only' if r['legacy_success'] else 'native_failure'
        if category not in groups:
            groups[category] = jobs[m['job_id']]
        if len(groups) == 3:
            break
    write_json(DEST/'design.json', dict(role='DEVELOPMENT_ONLY_THREE_OLD_TRAJECTORIES', jobs=groups,
               selection='Lexicographically first old repair case/rank in native-failure, native-only, clear-pass categories; no future endpoint known'), exclusive=True)
    results = []
    for category, job in groups.items():
        execute(job, DEST/'nominal', compare_archive=True, snapshot_time='late')
        record = read_json(DEST/'nominal'/(job['job_id']+'.json'))
        with np.load(DEST/'nominal'/(job['job_id']+'.npz'), allow_pickle=False) as data:
            arrays = dict(data)
        metadata, _ = adapt(arrays, record)
        def factory():
            model, _ = frozen.compile_case(frozen.old.SCENE, job['case'])
            frozen.old.apply_object_geom(model, job['case'])
            return model
        use = future_retention(arrays['final_integration_state'], record['final_state_flag'], metadata, factory)
        result = dict(category=category, job_id=job['job_id'], nominal_archive_bit_equal=record['equivalence_pass'], Y_use=use)
        write_json(DEST/(job['job_id']+'_use.json'), result, exclusive=True)
        results.append(result)
        print(json.dumps(result), flush=True)
    write_json(DEST/'summary.json', results, exclusive=True)


if __name__ == '__main__':
    run()
