"""Additional apparatus qualification for the explicitly required continuity property."""
from dataclasses import asdict
from pathlib import Path
import json

import numpy as np

from .baselines import historical, verdict
from .common import OUT, output_path, read_json, sha256, write_json
from .control_reference import adjudicate
from .controls import Fixture, run_fixture

DEST = OUT/'calibration/temporal_property_v1'


def run():
    rows = [Fixture('intermittent_floor', 52000+i, mass=.055+.01*i, support_schedule='single_burst') for i in range(4)]
    plan = dict(role='ADDITIONAL_DEVELOPMENT_APPARATUS_QUALIFICATION_NOT_PART_OF_80',
                reason='Periodic floor test did not distinguish total unloaded time from continuous time; '
                       'qualify a single .1s physical support interruption before formal registration',
                cases=[asdict(r) for r in rows], hashes={n: sha256(Path(__file__).with_name(n)) for n in
                                                       ('temporal_calibration.py', 'controls.py', 'baselines.py', 'contracts.py', 'contact_observer.py')})
    write_json(DEST/'design.json', plan, exclusive=True)
    records = []
    for i, row in enumerate(rows):
        arrays, metadata = run_fixture(row)
        reference = adjudicate(arrays, metadata)
        methods = historical(arrays, metadata)
        result = dict(fixture=asdict(row), metadata=metadata, reference=reference,
                      methods={k: verdict(v) for k, v in methods.items()},
                      definite_seconds=methods['B5']['definite_interval']['duration_s'],
                      accumulated_seconds=methods['A_accumulated']['definite_interval']['duration_s'])
        with output_path(DEST/f'case_{i}.npz').open('xb') as handle:
            np.savez_compressed(handle, **arrays)
        write_json(DEST/f'case_{i}.json', result, exclusive=True)
        records.append(result)
        print(json.dumps({k: result[k] for k in ('methods', 'definite_seconds', 'accumulated_seconds')}), flush=True)
    write_json(DEST/'summary.json', dict(count=len(rows), results=[{k: r[k] for k in ('methods', 'definite_seconds', 'accumulated_seconds')} for r in records]), exclusive=True)


if __name__ == '__main__':
    run()
