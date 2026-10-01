"""Fail-closed execution recovery, without modifying the G2 scientific sources.

Only the named frozen geometry-consistency exception is converted to INVALID.
Its tolerance and every scientific input remain unchanged. Other exceptions stop.
"""
from concurrent.futures import ProcessPoolExecutor
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v4.common import OUT, read_json, sha256, utc_now, write_json

ERROR_PREFIX = 'Independent geometry reconstruction mismatch:'
DEST = OUT/'protocols/execution_recovery_1.json'


def registered():
    from scripts.v4.protocol import verify_lock
    verify_lock()
    if DEST.exists():
        report = read_json(DEST)
        if sha256(__file__) != report['recovery_script_sha256']:
            raise RuntimeError('Recovery implementation changed')
        return report
    report = dict(created_utc=utc_now(), type='FAIL_CLOSED_BOOKKEEPING_RECOVERY',
        protocol_sha256=sha256(OUT/'protocols/protocol_lock.json'), recovery_script_sha256=sha256(__file__),
        exposed_at_registration=dict(controls=240, allegro_scores=167, future_use_outcomes=0),
        trigger='Two native-failed cylinder traces have primitive geometry reconstruction differences above the existing 1e-10 m assertion; '
                'the first observed failure was 1.172649061187414e-09 m',
        rule='Only RuntimeError beginning with the exact registered geometry-mismatch prefix becomes invalid telemetry. '
             'All methods receive INDETERMINATE/INVALID, native result retained separately. No tolerance is changed and no case is replaced.',
        future_rule='A candidate with this invalid diagnostic input has INVALID future evidence, never physical FAIL; '
                    'all-scene selection denominators and missing-outcome bounds are retained.',
        limits='Bookkeeping after an exposed implementation failure, not a pre-test code addition. '
               'G2 scientific sources, thresholds, physics, candidate pool and primary estimands are unchanged. '
               'Finite-pool oracle is a lower bound when any candidate future is invalid.')
    write_json(DEST, report, exclusive=True)
    return report


def safe_score(request):
    from scripts.v4.formal_allegro import BASE, one
    job, config = request
    try:
        return one(request)
    except RuntimeError as error:
        if not str(error).startswith(ERROR_PREFIX):
            raise
        jid = job['job_id']
        raw = BASE/'raw'/(jid+'.json')
        meta = read_json(raw)
        if sha256(raw.with_suffix('.npz')) != meta['trace_sha256']:
            raise RuntimeError('Invalid record also has changed raw evidence') from error
        methods = {name: dict(verdict='INDETERMINATE', trace_validity='INVALID', reason='GEOMETRY_RECONSTRUCTION_MISMATCH')
                   for name in ('B0', 'B1', 'B2', 'B3', 'B4_normal', 'B4', 'B5', 'A_no_geometry', 'A_no_torque',
                                'A_binary_unknown_fail', 'A_accumulated', 'A_net_aggregation')}
        result = dict(job_id=jid, case_id=job['case']['case_id'], family=job['family'], rank=job['rank'],
            methods=methods, reference=dict(verdict='INDETERMINATE' if job['reference_selected'] else 'NOT_SELECTED',
                                          reason='INVALID_INPUT', independent_review_complete=False),
            counterfactual=dict(status='INVALID' if job['counterfactual_selected'] else 'NOT_SELECTED', reason='INVALID_NOMINAL_TELEMETRY'),
            B6=dict(status='INVALID' if job['counterfactual_selected'] else 'NOT_SELECTED'),
            B7=dict(status='INVALID' if job['counterfactual_selected'] else 'NOT_SELECTED'),
            raw_sha256=meta['trace_sha256'], raw_metadata_sha256=sha256(raw),
            nominal_physics_steps=meta['planned_steps'], branch_cost_steps=0, elapsed_s=meta['elapsed_s'],
            native_result_retained_but_not_used_as_valid_audit=meta['result']['legacy_success'],
            execution_recovery=dict(error=str(error), recovery_sha256=sha256(DEST)))
        write_json(BASE/'scores'/(jid+'.json'), result, exclusive=True)
        return dict(job_id=jid, validity='INVALID', error=str(error))


def resume_scores(workers):
    from scripts.v4.contracts import Calibration
    from scripts.v4.formal_allegro import BASE
    registered()
    lock = read_json(OUT/'protocols/protocol_lock.json')
    jobs = read_json(OUT/'protocols/final_allegro_jobs.json')
    todo = [(job, Calibration(**lock['calibration'])) for job in jobs if not (BASE/'scores'/(job['job_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(safe_score, todo):
            print(json.dumps(result), flush=True)
    records = [read_json(BASE/'scores'/(job['job_id']+'.json')) for job in jobs]
    summary = dict(completed=len(records), invalid_geometry_records=[r['job_id'] for r in records if 'execution_recovery' in r],
                   original_protocol_sha256=sha256(OUT/'protocols/protocol_lock.json'))
    write_json(OUT/'reports/allegro_execution_recovery.json', summary, exclusive=True)
    return summary


def safe_future(job):
    from scripts.v4.formal_allegro import BASE, future_one
    score = read_json(BASE/'scores'/(job['job_id']+'.json'))
    if 'execution_recovery' not in score:
        return future_one(job)
    result = dict(job_id=job['job_id'], case_id=job['case']['case_id'], elapsed_s=0.,
        outcome=dict(status='INVALID', reason='REGISTERED_INVALID_NOMINAL_INPUT', physics_steps=0,
                     recovery_sha256=sha256(DEST)))
    write_json(OUT/'selection/future'/(job['job_id']+'.json'), result, exclusive=True)
    return result


def evaluate(workers):
    from scripts.v4.formal_allegro import BASE
    registered()
    sealed = read_json(OUT/'selection/u2_sealed.json')
    if sealed['protocol_sha256'] != sha256(OUT/'protocols/protocol_lock.json'):
        raise RuntimeError('Protocol changed after seal')
    for jid, expected in sealed['score_hashes'].items():
        score_path = BASE/'scores'/(jid+'.json')
        score = read_json(score_path)
        if sha256(score_path) != expected or sha256(BASE/'raw'/(jid+'.json')) != score['raw_metadata_sha256'] or sha256(BASE/'raw'/(jid+'.npz')) != score['raw_sha256']:
            raise RuntimeError('Sealed input changed')
    jobs = read_json(OUT/'protocols/final_allegro_jobs.json')
    todo = [j for j in jobs if not (OUT/'selection/future'/(j['job_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(safe_future, todo):
            print(json.dumps(result), flush=True)
    return dict(completed=len(jobs), recovery_sha256=sha256(DEST))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('register', 'scores', 'evaluate'))
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    print(registered() if args.action == 'register' else resume_scores(args.workers) if args.action == 'scores' else evaluate(args.workers))
