"""Complete P1 without filling missing full-wrench telemetry by conjecture."""
from collections import Counter, defaultdict
import json

import numpy as np

from .common import OUT, read_csv, read_json, sha256, write_csv, write_json, yes
from .contracts import Calibration, evaluate, longest_interval
from .natural_pilot import SOURCE, adapt


def run():
    source = OUT/'retrospective/complete/candidate_support_diagnosis.csv'
    inputs = read_csv(source)
    config = Calibration(version='merged-v4-calibration-nominal-20261001')
    rows = []
    for original in inputs:
        key = original['job_id']
        required = yes(original['global_common']) and float(original['longest_local_common_s']) >= 15-1e-9
        if not required:
            rows.append(dict(job_id=key, case_id=original['case_id'], family=original['family'],
                             B5='FAIL', B4='FAIL', reason='UNCHANGED_COMMON_CONDITION_FAIL',
                             replay_required=False, complete_wrench_observed=False))
            continue
        record = read_json(SOURCE/(key+'.json'))
        if not record['equivalence_pass']:
            raise ValueError('Historical replay not equivalent')
        with np.load(SOURCE/(key+'.npz'), allow_pickle=False) as data:
            arrays = {k: data[k] for k in ('steps', 'samples', 'legacy_step_index', 'legacy_telemetry')}
        metadata, gap = adapt(arrays, record)
        args = (arrays['steps'], metadata['step_columns'], arrays['common_q'], metadata, config)
        full = evaluate(*args, geometry_gap=gap)
        simple = evaluate(*args, use_geometry=False)
        columns = metadata['step_columns']
        steps = arrays['steps']
        weight = metadata['mass_kg']*np.linalg.norm(metadata['gravity'])
        force = steps[:, columns.index('env_abs_force_n')]/weight
        torque = steps[:, columns.index('env_abs_torque_nm')]/(weight*metadata['length_scale_m'])
        active_load = arrays['common_q'] & ((force >= config.force_fail_ratio) | (torque >= config.torque_fail_ratio))
        dt = steps[0, columns.index('dt')]
        rows.append(dict(job_id=key, case_id=original['case_id'], family=original['family'],
                         B5=full['no_external_load_verdict'], B4=simple['no_external_load_verdict'],
                         reason=';'.join(full['reason_codes']), replay_required=True, complete_wrench_observed=True,
                         longest_decisive_load_during_common_s=longest_interval(active_load, dt)['duration_s'],
                         no_load_definite_s=full['definite_interval']['duration_s'],
                         no_load_possible_s=full['possible_interval']['duration_s'],
                         independent_geometry_error_m=metadata['geometry_reconstruction_error_m'],
                         metadata_sha256=sha256(SOURCE/(key+'.json'))))
    if len(rows) != len(inputs):
        raise RuntimeError('Candidate denominator changed')
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['case_id']].append(row)
    scenes = [dict(case_id=case, family=group[0]['family'], candidates=len(group),
                   B5_any_pass=any(r['B5'] == 'PASS' for r in group), B4_any_pass=any(r['B4'] == 'PASS' for r in group),
                   any_unknown=any(r['B5'] == 'INDETERMINATE' for r in group)) for case, group in sorted(grouped.items())]
    result = dict(scope='Post-hoc union of the identical baseline/repair 85-case V3 exclusions; not 170 independent cases',
                  candidates=len(rows), scenes=len(scenes), replayed=sum(r['replay_required'] for r in rows),
                  common_failure_without_replay=sum(not r['replay_required'] for r in rows),
                  B5=dict(Counter(r['B5'] for r in rows)), B4=dict(Counter(r['B4'] for r in rows)),
                  rescued_scene_count=sum(r['B5_any_pass'] for r in scenes),
                  unknown_scene_count=sum(r['any_unknown'] for r in scenes),
                  candidate_reference_missing_for_full_wrench=sum(not r['complete_wrench_observed'] for r in rows),
                  interpretation='Missing wrench evidence in common-condition failures is not presented as measured zero load. '
                                 'Only all-condition verdicts and the declared excluded-scene coverage are complete.',
                  calibration_version=config.version, source_sha256=sha256(source))
    destination = OUT/'retrospective/final_adjudication'
    write_csv(destination/'candidates.csv', rows, fields=list(dict.fromkeys(k for r in rows for k in r)))
    write_csv(destination/'scenes.csv', scenes)
    write_json(destination/'summary.json', result, exclusive=True)
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    run()
