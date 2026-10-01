"""Offline label-level reproduction. No simulator, assets, network, or source writes."""
from collections import Counter
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def equal(actual, expected, path='result'):
    if isinstance(expected, dict):
        assert set(actual) == set(expected), (path, set(actual) ^ set(expected))
        for key in expected:
            equal(actual[key], expected[key], path+'.'+key)
    elif isinstance(expected, list):
        assert len(actual) == len(expected), path
        for i, (a, b) in enumerate(zip(actual, expected)):
            equal(a, b, path+f'[{i}]')
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (path, actual, expected)
    else:
        assert actual == expected, (path, actual, expected)


def verify_manifest():
    manifest = ROOT/'MANIFEST.sha256'
    if not manifest.exists():
        raise RuntimeError('Run from the extracted evidence package; manifest is required')
    count = 0
    for line in manifest.read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        path = (ROOT/relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or digest(path) != expected:
            raise RuntimeError('Missing or changed packaged file: '+relative)
        count += 1
    return count


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def reproduce(destination):
    verified = verify_manifest()
    # Deny network and simulator imports even when installed in the host interpreter.
    def deny_network(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            raise RuntimeError('Offline reproduction attempted network access')
    sys.addaudithook(deny_network)
    sys.modules['mujoco'] = None
    import numpy as np
    from scripts.v4 import formal_analysis as fa
    from scripts.v4.baselines import verdict
    from scripts.v4.statistics import classification, paired_stratified_bootstrap, cluster_mean_interval

    out = ROOT/'evidence/research_v4'
    expected = read(out/'analysis/formal_results.json')
    lock = read(out/'protocols/protocol_lock.json')
    assert digest(out/'protocols/protocol_lock.json') == expected['protocol_sha256']
    for relative, value in read(ROOT/'packaging.json')['packaged_frozen_code'].items():
        assert digest(ROOT/relative) == value, relative
    destination.mkdir(parents=True, exist_ok=True)
    # Redirect the frozen analysis function's CSV sink only; inputs and logic are unchanged.
    fa.write_csv = lambda path, rows: write_csv(destination/path.name, rows)
    records = {source: fa.read_records(source) for source in ('controls', 'allegro', 'fetch', 'dexgraspbench')}
    groups = {'controls': fa.summarize(records['controls'])}
    for source in ('allegro', 'fetch', 'dexgraspbench'):
        rows = records[source]
        selected = [r for r in rows if r['rank'] == 1] if source == 'allegro' else rows
        groups[source] = fa.summarize(selected)
        if source == 'allegro':
            groups[source]['all_candidates_not_independent_scenes'] = fa.summarize(rows)
            groups[source]['families'] = {f: fa.summarize([r for r in selected if r['family'] == f]) for f in sorted({r['family'] for r in selected})}
        if source == 'fetch':
            groups[source]['native_success'] = sum(r['native']['success'] for r in rows)
            groups[source]['native_goal_unchanged_all'] = all(r['native']['goal_unchanged'] for r in rows)
        if source == 'dexgraspbench':
            groups[source]['native_success'] = sum(r['native']['result'][0] for r in rows)
            groups[source]['identity_groups'] = {i: fa.summarize([r for r in rows if r['case']['object_identity'] == i]) for i in sorted({r['case']['object_identity'] for r in rows})}
            groups[source]['B5_identity_cluster_interval'] = cluster_mean_interval([verdict(r['methods']['B5']) == 'PASS' for r in rows], [r['case']['object_identity'] for r in rows])
    controls = records['controls']
    groups['controls']['mechanisms'] = {m: fa.summarize([r for r in controls if r['case']['parameters']['mechanism'] == m]) for m in sorted({r['case']['parameters']['mechanism'] for r in controls})}
    h1 = paired_stratified_bootstrap([verdict(r['methods']['B5']) == 'PASS' and r['reference']['verdict'] == 'PASS' for r in controls],
        [verdict(r['methods']['B4']) == 'PASS' and r['reference']['verdict'] == 'PASS' for r in controls], [r['case']['parameters']['mechanism'] for r in controls])
    h1['risk_max'] = lock['risk_max']
    risk = groups['controls']['reference_comparisons']
    h1['empirical_risk_condition'] = all(risk[m]['accepted_risk'] is not None and risk[m]['accepted_risk'] <= lock['risk_max'] for m in ('B4', 'B5'))
    utility = fa.utility()
    equal(groups, expected['sources'], 'sources')
    equal(h1, expected['H1_B5_minus_B4'], 'H1')
    equal(utility, expected['utility'], 'utility')
    h4 = utility['H4_B5_minus_B4_K6']
    equal(bool(h1['empirical_risk_condition'] and h1['interval975_bonferroni_two_primary'][0] > 0 and h1['effect'] >= lock['delta_min']), expected['confirmatory_gain_supported'])
    equal(bool(h4['interval975_bonferroni_two_primary'][0] > 0 and h4['effect'] >= lock['delta_min']), expected['utility_gain_supported'])
    rows = csv_rows(out/'analysis/operating_curve_cases.csv')
    curves = []
    for low, high in ((1e-6, 1e-4), (1e-5, 1e-3), (1e-4, 1e-2), (1e-3, 1e-1), (1e-2, 1.)):
        for method in sorted({r['method'] for r in rows}):
            group = [r for r in rows if float(r['low']) == low and r['method'] == method]
            curves.append(dict(low=low, high=high, method=method, **classification([r['verdict'] for r in group], [r['reference'] for r in group], [r['validity'] for r in group])))
    equal(curves, read(out/'analysis/operating_curves.json')['curves'], 'curves')
    ledger = csv_rows(ROOT/'notes/v4/claim_evidence_ledger.csv')
    for claim in ledger:
        assert digest(out/claim['source']) == claim['data_sha256'], claim['claim_id']
        assert claim['protocol_sha256'] == expected['protocol_sha256']
        assert claim['analysis_script_sha256'] == digest(ROOT/'scripts/v4/formal_analysis.py')
    properties = read(out/'controls/properties/summary.json')['rows']
    assert sum(r['full_state_bit_equal'] for r in properties) == 8
    assert sum(r['original']['B2'] != r['transformed']['B2'] for r in properties) == 8
    # Verify the ledger against recomputed counts, not only its own file hash.
    facts = {r['claim_id']: r for r in ledger}
    equal(float(facts['C2']['effect']), h1['effect'])
    equal(json.loads(facts['C2']['interval']), h1['interval975_bonferroni_two_primary'])
    equal(float(facts['C3']['effect']), h4['effect'])
    equal(json.loads(facts['C3']['interval']), h4['interval975_bonferroni_two_primary'])
    equal(int(facts['C1']['denominator']), len(properties))
    equal(int(facts['C2']['denominator']), len(controls))
    equal(int(facts['C3']['denominator']), 120)
    historical = read(out/'retrospective/final_adjudication/summary.json')
    equal(historical['rescued_scene_count'], 0)
    equal(int(facts['C5']['denominator']), historical['scenes'])
    chosen = csv_rows(destination/'u2_choices_and_outcomes.csv')
    by_method = {m: {r['case_id']: r['selected_job'] for r in chosen if r['method'] == m and r['k'] == '6'} for m in ('B4', 'B5')}
    same = sum(by_method['B4'][case] == by_method['B5'][case] for case in by_method['B4'])
    usable = next(r['usable'] for r in utility['summary'] if r['method'] == 'B5' and r['k'] == 6)
    facts['C3']['statement'] = f'B5 K6 returns {usable} usable choices; {same} choices identical to B4'
    equal(facts['C3']['statement'], next(r['statement'] for r in csv_rows(ROOT/'notes/v4/claim_evidence_ledger.csv') if r['claim_id'] == 'C3'))
    from scripts.v4.baselines import historical as rescore
    from scripts.v4.contracts import Calibration
    from scripts.v4.control_reference import adjudicate
    raw_checks = []
    for cid in ('final_control_000', 'final_control_001', 'final_control_002'):
        record = read(out/'controls/final/cases'/(cid+'.json'))
        with np.load(out/'controls/final/cases'/(cid+'.npz'), allow_pickle=False) as z:
            arrays = dict(z)
        equal(rescore(arrays, record['metadata'], Calibration(**lock['calibration'])), record['methods'], cid+'.methods')
        equal(adjudicate(arrays, record['metadata']), record['reference'], cid+'.reference')
        raw_checks.append(cid)
    # Y_use is an independent endpoint: reconstruct its success flag from maxima.
    futures_checked = 0
    for path in sorted((out/'selection/future').glob('*.json')):
        future = read(path)['outcome']
        if future['status'] == 'VALID':
            r = future['result']
            success = r['max_position_error_m'] <= .03 and r['max_angle_error_rad'] <= .35 and r['max_linear_speed_m_s'] <= .2
            equal(bool(r['success']), bool(success), path.stem+'.Y_use')
            futures_checked += 1
    old = csv_rows(ROOT/'evidence/prospective_v3/case_results.csv')
    old = [r for r in old if r['block'].startswith('new') and r['k'] == '6']
    left = {r['case_id']: r for r in old if r['policy'] == 'baseline'}
    right = {r['case_id']: r for r in old if r['policy'] == 'repair'}
    assert left.keys() == right.keys() and len(left) == 360
    counts = {p: sum(r['clear_contiguous_success'] == 'True' for r in old if r['policy'] == p) for p in ('baseline', 'repair')}
    equal(counts, dict(baseline=37, repair=48), 'historical_counts')
    gains = [c for c in left if left[c]['clear_contiguous_success'] == 'False' and right[c]['clear_contiguous_success'] == 'True']
    losses = [c for c in left if left[c]['clear_contiguous_success'] == 'True' and right[c]['clear_contiguous_success'] == 'False']
    assert len(gains) == 11 and not losses and all(left[c]['family'] == 'sphere_random' for c in gains)
    rng, draws = np.random.default_rng(2026093040), np.zeros(5000)
    for family in ('cube_random', 'cylinder_random', 'bar_random', 'sphere_random', 'capsule_random', 'flat_box_random'):
        ids = sorted(c for c in left if left[c]['family'] == family)
        assert len(ids) == 60
        delta = np.array([int(right[c]['clear_contiguous_success'] == 'True')-int(left[c]['clear_contiguous_success'] == 'True') for c in ids])
        draws += delta[rng.integers(0, 60, (5000, 60))].sum(axis=1)/360
    old_interval = np.quantile(draws, [.025, .975]).tolist()
    equal(old_interval, read(ROOT/'evidence/prospective_v3/analysis.json')['stratified_bootstrap_clear_delta_95'], 'V3_interval')
    write_csv(destination/'claim_evidence_ledger.csv', ledger)
    write_csv(destination/'source_method_counts.csv', [dict(source=s, method=m, assigned=g['n'], **{k: c.get(k, 0) for k in ('PASS', 'FAIL', 'INDETERMINATE')}) for s, g in groups.items() for m, c in g['methods'].items()])
    (destination/'formal_results_recomputed.json').write_text(json.dumps(dict(sources=groups, H1_B5_minus_B4=h1, utility=utility), indent=2)+'\n', encoding='utf-8')
    import importlib.util
    spec = importlib.util.spec_from_file_location('publication_figures', ROOT/'scripts/v4_figures.py')
    figures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figures)
    figures.FIG = destination/'figures'
    figures.static()
    figures.quantitative()
    report = dict(status='PASS', manifest_files=verified, source_counts={s: g['n'] for s, g in groups.items()},
        candidate_executions=len(records['allegro']), future_outcomes=utility['future_candidate_outcomes'],
        independent_endpoint_flags_checked=futures_checked, raw_trace_rescoring=raw_checks,
        preserved_V3=dict(counts=counts, paired_gains=len(gains), paired_losses=len(losses), interval95=old_interval),
        protocol_sha256=expected['protocol_sha256'], numpy_version=np.__version__,
        checks=['all source summaries and confusion matrices', 'paired 10000-draw intervals', 'sealed U2 choices and every future label',
                'all 60 operating points', 'claim ledger hashes and paired effects', 'three regenerated figure pairs'],
        scope='Label-level aggregate reproduction; not a fresh physical adjudication of all raw traces',
        network='denied', simulator='import blocked', full_dynamic_reproduction='NOT_RUN', full_original_raw='NOT_BUNDLED; see raw_trace_manifest.json')
    (destination/'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    assert verified == verify_manifest(), 'Package inputs changed during reproduction'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    target = args.out.resolve()
    if target.is_relative_to(ROOT):
        raise SystemExit('--out must be outside the immutable package directory')
    print(json.dumps(reproduce(target), indent=2))
