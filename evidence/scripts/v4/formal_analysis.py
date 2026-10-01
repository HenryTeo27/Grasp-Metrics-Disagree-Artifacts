"""Frozen offline estimands. Reads stored outcomes; never executes physics."""
from collections import Counter

import numpy as np

from .baselines import verdict
from .common import OUT, read_json, sha256, write_csv, write_json
from .statistics import classification, cluster_mean_interval, paired_stratified_bootstrap, wilson

METHODS = ('B0', 'B1', 'B2', 'B3', 'B4_normal', 'B4', 'B5', 'A_no_geometry', 'A_no_torque',
           'A_binary_unknown_fail', 'A_accumulated', 'A_net_aggregation')


def summarize(records):
    counts, errors = {}, {}
    labeled = [r for r in records if r['reference']['verdict'] != 'NOT_SELECTED']
    for method in METHODS:
        counts[method] = dict(Counter(verdict(r['methods'][method]) for r in records))
        if labeled:
            errors[method] = classification([verdict(r['methods'][method]) for r in labeled],
                [r['reference']['verdict'] for r in labeled],
                [r['methods'][method].get('trace_validity', 'VALID') for r in labeled])
    return dict(n=len(records), methods=counts, reference_sample=len(labeled), reference_comparisons=errors,
                counterfactual=dict(Counter(r['counterfactual'].get('cell', r['counterfactual']['status']) for r in records)),
                B6=dict(Counter(r['B6']['status'] for r in records)), B7=dict(Counter(r['B7']['status'] for r in records)),
                nominal_physics_steps=sum(r['nominal_physics_steps'] for r in records),
                branch_cost_steps=sum(r['branch_cost_steps'] for r in records))


def read_records(source):
    if source == 'controls':
        rows = read_json(OUT/'protocols/final_controls.json')
        return [read_json(OUT/'controls/final/cases'/(r['case_id']+'.json')) for r in rows]
    if source == 'allegro':
        jobs = read_json(OUT/'protocols/final_allegro_jobs.json')
        return [read_json(OUT/'external/allegro/final/scores'/(j['job_id']+'.json')) for j in jobs]
    rows = read_json(OUT/'protocols'/('final_'+source+'.json'))
    return [read_json(OUT/'external'/source/'final/cases'/(r['case_id']+'.json')) for r in rows]


def utility():
    sealed = read_json(OUT/'selection/u2_sealed.json')
    for jid, expected in sealed['score_hashes'].items():
        if sha256(OUT/'external/allegro/final/scores'/(jid+'.json')) != expected:
            raise RuntimeError('Changed sealed selection evidence')
    future = {jid: read_json(OUT/'selection/future'/(jid+'.json')) for jid in sealed['score_hashes']}
    rows = []
    for choice in sealed['choices']:
        jid = choice['selected_job']
        outcome = future[jid]['outcome'] if jid else None
        valid = outcome is not None and outcome['status'] == 'VALID'
        usable = bool(valid and outcome['result']['success'])
        possible = usable or (outcome is not None and not valid)
        oracle = any(future[j]['outcome']['status'] == 'VALID' and future[j]['outcome']['result']['success'] for j in choice['candidate_pool'])
        rows.append(dict(**choice, abstained=jid is None, future_status='ABSTAINED' if jid is None else outcome['status'],
                         usable=usable, possibly_usable=possible, pool_oracle_usable=oracle, empirical_regret=int(oracle)-int(usable)))
    groups = []
    for k in (1, 3, 6):
        for method in ('B0', 'B1', 'B2', 'B3', 'B4', 'B4_normal', 'B5'):
            group = [r for r in rows if r['k'] == k and r['method'] == method]
            n = len(group)
            groups.append(dict(k=k, method=method, scenes=n, accepted=sum(not r['abstained'] for r in group),
                usable=sum(r['usable'] for r in group), possible_usable=sum(r['possibly_usable'] for r in group),
                abstained=sum(r['abstained'] for r in group), invalid=sum(r['future_status'] == 'INVALID' for r in group),
                usable_fraction=sum(r['usable'] for r in group)/n,
                pool_oracle_usable=sum(r['pool_oracle_usable'] for r in group),
                mean_empirical_regret=sum(r['empirical_regret'] for r in group)/n,
                nominal_physics_budget=sum(r['budget_physics_steps'] for r in group)))
    primary = {}
    for method in ('B5', 'B4'):
        primary[method] = sorted([r for r in rows if r['k'] == 6 and r['method'] == method], key=lambda r: r['case_id'])
    comparison = paired_stratified_bootstrap([r['usable'] for r in primary['B5']], [r['usable'] for r in primary['B4']],
                                             [r['family'] for r in primary['B5']])
    write_csv(OUT/'analysis/u2_choices_and_outcomes.csv', rows)
    write_csv(OUT/'analysis/u2_summary.csv', groups)
    return dict(summary=groups, H4_B5_minus_B4_K6=comparison, future_physics_steps=sum(r['outcome'].get('physics_steps', 0) for r in future.values()),
                future_candidate_outcomes=len(future), independent_scenes=120,
                interpretation='Added intervention-conditioned future retention, not native acquisition success')


def run():
    from .protocol import verify_lock
    lock = verify_lock(check_runtime=False)
    controls = read_records('controls')
    groups = {'controls': summarize(controls)}
    for source in ('allegro', 'fetch', 'dexgraspbench'):
        records = read_records(source)
        selected = [r for r in records if r['rank'] == 1] if source == 'allegro' else records
        groups[source] = summarize(selected)
        if source == 'allegro':
            groups[source]['all_candidates_not_independent_scenes'] = summarize(records)
            groups[source]['families'] = {family: summarize([r for r in selected if r['family'] == family])
                for family in sorted({r['family'] for r in selected})}
        if source == 'fetch':
            groups[source]['native_success'] = sum(r['native']['success'] for r in records)
            groups[source]['native_goal_unchanged_all'] = all(r['native']['goal_unchanged'] for r in records)
        if source == 'dexgraspbench':
            groups[source]['native_success'] = sum(r['native']['result'][0] for r in records)
            groups[source]['identity_groups'] = {identity: summarize([r for r in records if r['case']['object_identity'] == identity])
                for identity in sorted({r['case']['object_identity'] for r in records})}
            groups[source]['B5_identity_cluster_interval'] = cluster_mean_interval(
                [verdict(r['methods']['B5']) == 'PASS' for r in records], [r['case']['object_identity'] for r in records])
    groups['controls']['mechanisms'] = {m: summarize([r for r in controls if r['case']['parameters']['mechanism'] == m])
        for m in sorted({r['case']['parameters']['mechanism'] for r in controls})}
    h1 = paired_stratified_bootstrap(
        [verdict(r['methods']['B5']) == 'PASS' and r['reference']['verdict'] == 'PASS' for r in controls],
        [verdict(r['methods']['B4']) == 'PASS' and r['reference']['verdict'] == 'PASS' for r in controls],
        [r['case']['parameters']['mechanism'] for r in controls])
    risks = groups['controls']['reference_comparisons']
    h1['risk_max'] = lock['risk_max']
    h1['empirical_risk_condition'] = all(risks[m]['accepted_risk'] is not None and risks[m]['accepted_risk'] <= lock['risk_max'] for m in ('B4', 'B5'))
    result = dict(protocol_sha256=sha256(OUT/'protocols/protocol_lock.json'), sources=groups, H1_B5_minus_B4=h1, utility=utility(),
                  claim_rule='Positive method gain requires 97.5% interval lower bound above zero and effect >=.05; no equivalence claim from zero discordance')
    result['confirmatory_gain_supported'] = bool(h1['empirical_risk_condition'] and h1['interval975_bonferroni_two_primary'][0] > 0 and h1['effect'] >= lock['delta_min'])
    u = result['utility']['H4_B5_minus_B4_K6']
    result['utility_gain_supported'] = bool(u['interval975_bonferroni_two_primary'][0] > 0 and u['effect'] >= lock['delta_min'])
    write_json(OUT/'analysis/formal_results.json', result)
    rows = []
    for source, group in groups.items():
        for method, counts in group['methods'].items():
            rows.append(dict(source=source, method=method, assigned=group['n'], **{k: counts.get(k, 0) for k in ('PASS', 'FAIL', 'INDETERMINATE')}))
    write_csv(OUT/'analysis/source_method_counts.csv', rows)
    return result


if __name__ == '__main__':
    result = run()
    print({k: result[k] for k in ('confirmatory_gain_supported', 'utility_gain_supported', 'H1_B5_minus_B4')})
