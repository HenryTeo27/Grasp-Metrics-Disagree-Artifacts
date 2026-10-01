"""Fixed first-case dynamic release checks in a separate, non-claim namespace."""
from pathlib import Path
import argparse
import importlib.metadata
import json
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v4.common import OUT, read_json, sha256, write_json
from scripts.v4.contracts import Calibration


def run(source):
    from scripts.v4.protocol import verify_lock
    lock = verify_lock(check_runtime=source != 'dexgraspbench')
    config = Calibration(**lock['calibration'])
    base = OUT/'reports/dynamic_release'/source
    if (base/'verification.json').exists():
        raise FileExistsError('Do not overwrite completed dynamic checks')
    if source == 'controls':
        from scripts.v4.formal_controls import one
        row = read_json(OUT/'protocols/final_controls.json')[0]
        one((row, base, config, True))
        result = read_json(base/'cases'/(row['case_id']+'.json'))
        original = read_json(OUT/'controls/final/cases'/(row['case_id']+'.json'))
        neutral = result['observer_full_integration_bit_equal']
    elif source in ('fetch', 'dexgraspbench'):
        from scripts.v4.formal_external import one
        row = read_json(OUT/'protocols'/('final_'+source+'.json'))[0]
        one((source, row, base, config))
        result = read_json(base/'cases'/(row['case_id']+'.json'))
        original = read_json(OUT/'external'/source/'final/cases'/(row['case_id']+'.json'))
        neutral = result['observer_bit_equal']
    else:
        from scripts.v4 import formal_allegro as fa
        job = read_json(OUT/'protocols/final_allegro_jobs.json')[0]
        fa.BASE = base
        fa.one((job, config))
        result = read_json(base/'scores'/(job['job_id']+'.json'))
        original = read_json(OUT/'external/allegro/final/scores'/(job['job_id']+'.json'))
        neutral = 'Not independently rerun observer-off here; see pre-G2 qualification'
    from scripts.v4.baselines import verdict
    equal = {m: verdict(result['methods'][m]) == verdict(original['methods'][m]) for m in result['methods']}
    cf = result['counterfactual']
    assert all(equal.values()), equal
    assert neutral is not False
    if cf['status'] == 'VALID':
        assert result['counterfactual'] == original['counterfactual'], 'Changed branch replay'
    report = dict(status='PASS', source=source, fixed_case='First registered formal row; no selection from outcome',
        method_verdicts_equal=equal, observer_neutral=neutral, counterfactual=cf,
        interpreter=sys.executable, python=platform.python_version(),
        versions={p: importlib.metadata.version(p) for p in ('numpy', 'mujoco', 'scipy')},
        original_protocol_sha256=sha256(OUT/'protocols/protocol_lock.json'), script_sha256=sha256(__file__),
        scope='One exact runtime re-execution; existing isolated declared venv, not clean-machine installation or full-matrix reproduction')
    write_json(base/'verification.json', report, exclusive=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('source', choices=('controls', 'allegro', 'fetch', 'dexgraspbench'))
    print(json.dumps(run(parser.parse_args().source), indent=2))
