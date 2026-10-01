"""Formal-driver qualification on already exposed development inputs only."""
from pathlib import Path

import numpy as np

from .baselines import historical, verdict
from .common import OUT, read_json, sha256, write_json
from .contracts import Calibration
from .external_reference import adjudicate


def allegro():
    from .formal_allegro import prepare
    source = OUT/'calibration/utility_continuation_v1'
    # These three raw traces were predeclared and exposed in the utility pilot.
    paths = sorted(source.rglob('*.npz'))
    if len(paths) != 3:
        raise RuntimeError('Expected precisely three existing utility traces')
    records = []
    for path in paths:
        metadata_path = path.with_suffix('.json')
        meta = read_json(metadata_path)
        with np.load(path, allow_pickle=False) as z:
            arrays = dict(z)
        metadata = prepare(arrays, meta)
        reference = adjudicate(arrays, metadata)
        methods = historical(arrays, metadata)
        records.append(dict(job_id=meta['job']['job_id'], trace_sha256=sha256(path), reference=reference,
                            B5=verdict(methods['B5']), pass_check=reference['common_conditions_agree'] and
                            reference['geometry_reconstruction_error_m'] < 1e-9 and reference['wrench_reconstruction_error'] < 1e-9))
    write_json(OUT/'calibration/allegro_reference_qualification_v1.json', dict(rows=records, passed=all(r['pass_check'] for r in records)), exclusive=True)
    return records


def dgb():
    from .formal_external import one
    from .adapters.dexgraspbench import ROOT
    selected = sorted((ROOT/'output/example_shadow/graspdata').rglob('*.npy'))[0]
    row = dict(case_id='previously_exposed_lexfirst', source_input=selected.relative_to(ROOT).as_posix(),
               input_sha256=sha256(selected), counterfactual_selected=True, reference_selected=True)
    return one(('dexgraspbench', row, str(OUT/'calibration/dgb_formal_driver_v1'), Calibration()))


def finish():
    fetch = read_json(OUT/'calibration/fetch_native_goal_v1/cases/native_goal_qualification_900001.json')
    dgb_record = read_json(OUT/'calibration/dgb_formal_driver_v1/cases/previously_exposed_lexfirst.json')
    allegro_record = read_json(OUT/'calibration/allegro_reference_qualification_v1.json')
    result = dict(pass_check=fetch['observer_bit_equal'] and dgb_record['observer_bit_equal'] and allegro_record['passed'] and
        all(r['reference']['common_conditions_agree'] and r['reference']['geometry_reconstruction_error_m'] < 1e-9 and
            r['reference']['wrench_reconstruction_error'] < 1e-9 for r in (fetch, dgb_record)),
        sources=dict(fetch='new predeclared development seed 900001, native goal unchanged',
                     dgb='same first exposed public record, not a held-out identity', allegro='same three development utility traces'),
        formal_outcomes=False)
    result['pass'] = result.pop('pass_check')
    write_json(OUT/'calibration/formal_adapter_qualification_v1.json', result, exclusive=True)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('allegro', 'dgb', 'finish'))
    args = parser.parse_args()
    print(globals()[args.action]())
