"""Generate claim-facing V4 text and ledgers from completed frozen results."""
from collections import Counter
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v4.baselines import verdict
from scripts.v4.common import OUT, NOTES, read_csv, read_json, sha256, write_csv, write_json
from scripts.v4.formal_analysis import read_records
from scripts.v4.statistics import wilson

GEN = ROOT/'paper_v4/generated'


def tex(name, content):
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN/(name+'.tex')).write_text(content+'\n', encoding='utf-8')


def pct(value):
    return 'NA' if value is None else f'{100*value:.1f}\\%'


def triplet(counts):
    return '/'.join(str(counts.get(k, 0)) for k in ('PASS', 'FAIL', 'INDETERMINATE'))


def table(columns, header, rows):
    return '\n'.join([r'\begin{tabular}{'+columns+r'}\toprule', ' & '.join(header)+r'\\\midrule']+
                     [' & '.join(map(str, row))+r'\\' for row in rows]+[r'\bottomrule\end{tabular}'])


def run():
    result = read_json(OUT/'analysis/formal_results.json')
    groups = result['sources']
    controls = groups['controls']
    records = {s: read_records(s) for s in ('controls', 'allegro', 'fetch', 'dexgraspbench')}
    curves = read_json(OUT/'analysis/operating_curves.json')
    properties = read_json(OUT/'controls/properties/summary.json')['rows']
    choices = read_csv(OUT/'analysis/u2_choices_and_outcomes.csv')
    urows = result['utility']['summary']
    u = {(r['method'], r['k']): r for r in urows}
    chosen = {m: {r['case_id']: r['selected_job'] for r in choices if r['method'] == m and r['k'] == '6'} for m in ('B0', 'B2', 'B4', 'B5')}
    same_choices = sum(chosen['B4'][c] == chosen['B5'][c] for c in chosen['B4'])
    no_contact_changed = sum(chosen['B2'][c] != chosen['B5'][c] for c in chosen['B2'])
    invalid_allegro = [r for r in records['allegro'] if r['methods']['B5'].get('trace_validity') != 'VALID']
    invalid_dgb = [r for r in records['dexgraspbench'] if r['methods']['B5'].get('trace_validity') != 'VALID']
    fp_nc = controls['reference_comparisons']['B2']['false_accept']
    fn_nc = controls['reference_comparisons']['B2']['false_reject']
    correct = controls['reference_comparisons']['B5']['reference_positive']
    prop_equal = sum(r['full_state_bit_equal'] for r in properties)
    prop_nc_flip = sum(r['original']['B2'] != r['transformed']['B2'] for r in properties)
    no_gain = not result['confirmatory_gain_supported'] and not result['utility_gain_supported']
    tex('numbers', '% Generated exclusively from analysis/formal_results.json\n'+
        '\n'.join(f'\\newcommand{{\\{key}}}{{{value}}}' for key, value in {
            'ControlPositive': correct, 'ControlNegative': 240-correct, 'ControlNCFalseReject': fn_nc,
            'UtwoUsable': u['B5', 6]['usable'], 'UtwoAccepted': u['B5', 6]['accepted'],
            'FetchUnknown': groups['fetch']['methods']['B5'].get('INDETERMINATE', 0),
            'DGBPositive': groups['dexgraspbench']['methods']['B5'].get('PASS', 0)}.items()))
    last = ('The integrated monitor provides no demonstrated improvement over the full-wrench baseline in either primary comparison. '
            'The evidence supports explicit construct selection and simpler monitoring, not a new grasping or causal-inference algorithm.' if no_gain else
            'Incremental effects are reported with paired uncertainty and restricted to these frozen apparatus and task distributions.')
    tex('abstract', f'''Grasping metrics can disagree because they measure different physical targets,
not because one is universally more accurate. We separate literal absence of
contact records, absence of realized non-hand load, and retention after a
specified environment-removal intervention. A read-only MuJoCo instrument
records full contact wrenches, geometry, passive-load accounting and temporal
uncertainty. After development qualification, a frozen study evaluates 240
free-object controls, 120 fresh Allegro scenes with six candidates each, 100
native-goal Fetch episodes and 100 Shadow-hand library records across four
held-out object identities. On controls, both the integrated monitor and a
simple full-wrench baseline match all {240} raw-evidence reference labels;
the literal no-contact rule rejects {fn_nc} of {correct} reference positives.
All {prop_equal} representation pairs preserve complete integration states while
{prop_nc_flip} no-contact verdicts change. However, the corrected contract rescues
none of 85 historical excluded scenes. Sealed candidate choices yield
{u['B5',6]['usable']}/120 usable selections under a separate 15-second future
continuation, with {same_choices}/120 choices identical to the simple baseline.
{last}''')
    control_rows = []
    for method in ('B0', 'B1', 'B2', 'B3', 'B4_normal', 'B4', 'B5', 'A_accumulated'):
        c = controls['reference_comparisons'][method]
        control_rows.append([method.replace('_', r'\_'), controls['methods'][method].get('PASS', 0), c['false_accept'],
                            c['false_reject'], c['unknown_prediction'], pct(c['accepted_risk'])])
    tex('control_table', table('lrrrrr', ['Method', 'Accepted', 'FP / 163', 'FN / 77', 'U', 'Accepted risk'], control_rows))
    extrows = []
    for source, label in (('allegro', 'Allegro rank-1'), ('fetch', 'Fetch'), ('dexgraspbench', 'Shadow / DGB')):
        g = groups[source]
        native = g.get('native_success', g['methods']['B0'].get('PASS', 0))
        valid_records = [r for r in records[source] if source != 'allegro' or r['rank'] == 1]
        invalid = sum(r['methods']['B5'].get('trace_validity') != 'VALID' for r in valid_records)
        extrows.append([label, g['n'], native, g['methods']['B2'].get('PASS', 0), triplet(g['methods']['B4']), triplet(g['methods']['B5']), invalid])
    tex('external_table', table('lrrrrrr', ['Source', 'N', 'Native', r'$\NC$ P', 'B4 P/F/U', 'B5 P/F/U', 'Invalid'], extrows))
    utility_rows = []
    for method in ('B0', 'B1', 'B2', 'B3', 'B4_normal', 'B4', 'B5'):
        utility_rows.append([method.replace('_', r'\_')]+[f"{u[method,k]['accepted']} / {u[method,k]['usable']}" for k in (1, 3, 6)]+
                            [u[method,6]['abstained'], f"{u[method,6]['mean_empirical_regret']:.3f}"])
    tex('utility_table', table('lrrrrr', ['Method', 'K1 accept/use', 'K3 accept/use', 'K6 accept/use', 'K6 abstain', 'Regret'], utility_rows))
    h1 = result['H1_B5_minus_B4']
    h4 = result['utility']['H4_B5_minus_B4_K6']
    cfrows = []
    for source, group in groups.items():
        cells = group['counterfactual']
        cfrows.append([source.replace('dexgraspbench', 'Shadow/DGB').capitalize()]+[cells.get(k, 0) for k in
            ('BOTH_RETAIN', 'DEPENDENT', 'REMOVAL_RESCUES', 'BOTH_FAIL', 'UNREACHABLE', 'INVALID')])
    cf_table = table('lrrrrrr', ['Source', 'Both retain', 'Dependent', 'Rescue', 'Both fail', 'Unreached', 'Invalid'], cfrows)
    cfp = controls['counterfactual']
    native_fetch = groups['fetch']['native_success']
    fg, dg = groups['fetch']['methods']['B5'], groups['dexgraspbench']['methods']['B5']
    invalid_ids = ', '.join(r['job_id'] for r in invalid_allegro)
    cost_b4, cost_b5 = curves['costs']['B4']['median_s']*1000, curves['costs']['B5']['median_s']*1000
    text = rf'''\paragraph{{Controlled reference agreement and incremental value.}}
The final controls contain {correct} no-load reference positives and {240-correct}
negatives. B4 and B5 have no observed disagreement with those labels. Their
H1 difference in correct acceptance per assigned case is {100*h1['effect']:.1f}
percentage points, with paired 97.5\% interval
[{100*h1['interval975_bonferroni_two_primary'][0]:.1f}, {100*h1['interval975_bonferroni_two_primary'][1]:.1f}].
The empirical risk condition is satisfied, but the tied comparison does not
establish equivalence beyond these apparatus distributions. Positive geometry
alone (B3) also matches the nominal labels. No added-geometry accuracy benefit
is demonstrated. Relative to the no-load target, no-contact has {fp_nc} false
acceptances and {fn_nc} false rejections among {correct} positives; its different
literal semantics remain intact (Table~\ref{{tab:controls}}).

\paragraph{{Which distinctions survive targeted tests?}}
In {prop_equal}/{len(properties)} registered representation pairs the complete
integration trace is bit-identical, while no-contact changes in {prop_nc_flip}.
B4 and B5 do not change. Accumulated no-load accepts
{controls['methods']['A_accumulated'].get('PASS',0)} controls versus {correct}
for continuous time; the additional acceptances arise in the one-burst
intermittent group. The other nominal ablations do not establish an incremental
benefit on this controlled set. The registered branch subset gives
{cfp.get('BOTH_RETAIN',0)} both-retain, {cfp.get('DEPENDENT',0)} dependent and
{cfp.get('UNREACHABLE',0)} unreachable states. Loaded-but-retaining redundant
supports separate realized load from dependence under this intervention.
No empty four-cell category is filled by adding favorable cases.

\paragraph{{Natural tasks expose limits rather than a general accuracy gain.}}
The historical no-contact exclusions yield 0/85 rescued scenes under no-load.
The new external results are source-specific (Table~\ref{{tab:external}}).
Fetch succeeds in {native_fetch}/100 native episodes, while added retention has
{fg.get('PASS',0)} definite passes, {fg.get('FAIL',0)} failures and
{fg.get('INDETERMINATE',0)} indeterminate outcomes. Retained target damping torque
lies in the registered gray band; dropping torque would accept 48 cases but
would change the intended target. This is not evidence that the native expert
failed. The Shadow library yields {dg.get('PASS',0)} no-load passes,
{dg.get('FAIL',0)} failures and {dg.get('INDETERMINATE',0)} indeterminate record;
{len(invalid_dgb)} record has invalid telemetry following a reproducible simulator
instability. Its native force-test successes are {groups['dexgraspbench']['native_success']}/100.
Withdrawal cannot test environmental dependence in this environment-free model.

\paragraph{{Execution recovery and reference limits.}}
{len(invalid_allegro)} of 720 Allegro candidate records fail the frozen
$10^{{-10}}$\,m geometry-consistency assertion. A documented fail-closed recovery
records them as invalid/indeterminate without widening the assertion, replacing
cases, changing physics or exposing future-use scores. Their native outcomes
are retained separately. This bookkeeping recovery was introduced after the
first execution failure and is not described as pre-test code. The 30-entry
probability reference samples per natural source remain separate from control
labels; unknown reference cases are not called verified failures or successes.

\paragraph{{Candidate acceptance does not by itself prove utility.}}
At K6, B5 accepts {u['B5',6]['accepted']} and yields {u['B5',6]['usable']} usable
selections among all 120 scenes, with {u['B5',6]['abstained']} abstentions.
B4 and B5 return the same candidate or abstention on {same_choices}/120 scenes;
their H4 difference is {100*h4['effect']:.1f} points, paired 97.5\% interval
[{100*h4['interval975_bonferroni_two_primary'][0]:.1f}, {100*h4['interval975_bonferroni_two_primary'][1]:.1f}].
No-contact and B5 differ in {no_contact_changed}/120 K6 choices. Native-gate
selection provides {u['B0',6]['usable']} usable choices from
{u['B0',6]['accepted']} acceptances. These secondary contrasts concern the added
intervention-conditioned use, not improvements to the native program.
Unknown candidate futures make the finite-pool oracle a lower bound, so the
reported regret is an observed-pool diagnostic rather than true optimal regret.

\paragraph{{Costs and scope of mechanical baselines.}}
B4/B5 use the same nominal trajectories and no extra physical steps. Median
offline scoring calls on controls take {cost_b4:.2f} and {cost_b5:.2f}\,ms,
excluding instrumentation, IO and simulation. These timings are
hardware-dependent and do not establish a runtime advantage. B6 and B7 are
reported on the fixed subset, with solver time and extra probe steps charged;
neither is relabeled as historical no-load ground truth. Appendix tables give
their applicability and outcomes. Native DGB execution and staging were
performed separately, but their step costs were not metered, so the recorded
audited-segment budget is not presented as an exhaustive benchmark cost.
'''
    tex('results', text)
    intro_discussion = ('The primary result is the absence of demonstrated incremental value from the geometric guard over the information-matched full-wrench baseline. '
                       'The controlled disagreement with a literal contact rule is real, but the old natural exclusions are not rescued and it does not establish a broad new evaluation algorithm. '
                       'The appropriate output is a narrower measurement/diagnostic study and a simplification recommendation within the tested conditions.' if no_gain else
                       'The observed primary comparisons are restricted to the registered distributions and require the source-specific uncertainty accounting reported above.')
    tex('discussion', intro_discussion)
    tex('conclusion', ('No-contact, realized non-hand load and intervention-conditioned retention answer different questions. '
        f'Full-state controls demonstrate that contact representation can change a verdict without changing dynamics, but the integrated monitor adds no observed B4--B5 decision difference in {same_choices} of 120 fresh scenes. '
        'Explicit definitions, valid telemetry, strong simple baselines and preserved unknowns are more defensible here than a claim of a new superior auditor. '
        'The release preserves both constructive distinctions and negative findings, while leaving broader controller transfer and real-world validation unproven.') if no_gain else
        'The frozen study provides source-specific estimates of construct disagreement and candidate-decision utility, with uncertainty and validity limits retained.')
    mech = []
    for name, group in controls['mechanisms'].items():
        mech.append([name.replace('_', ' '), group['n'], group['methods']['B0'].get('PASS',0),
                     group['methods']['B1'].get('PASS',0), group['methods']['B2'].get('PASS',0),
                     group['methods']['B4'].get('PASS',0), group['methods']['B5'].get('PASS',0)])
    tex('mechanism_table', r'\begin{table}[h]\centering\small\caption{Final control pass counts by registered apparatus group.}\label{tab:mechanisms}'+
        table('lrrrrrr', ['Group','N','B0','B1','B2','B4','B5'], mech)+r'\end{table}'+'\n'+
        r'\begin{table}[h]\centering\small\caption{Fixed counterfactual subsets; unreachable/invalid states are not replaced.}\label{tab:cf}'+cf_table+r'\end{table}')
    mechanical, quality, budget = [], [], []
    for source, all_records in records.items():
        selected = [r for r in all_records if r['counterfactual']['status'] != 'NOT_SELECTED']
        b6valid = [r for r in selected if r['B6']['status'] == 'VALID']
        b7valid = [r for r in selected if r['B7']['status'] == 'VALID']
        mechanical.append(dict(source=source, selected=len(selected), B6_valid=len(b6valid),
            B6_feasible=sum(r['B6']['feasible'] for r in b6valid),
            B6_statuses=dict(Counter(r['B6']['status'] for r in selected)),
            B6_solver_wall_s=sum(r['B6'].get('solver_time_s', 0.) for r in selected),
            B7_valid=len(b7valid), B7_robust=sum(r['B7']['robust'] for r in b7valid),
            B7_statuses=dict(Counter(r['B7']['status'] for r in selected)),
            B7_physics_steps=sum(r['B7'].get('physics_steps', 0) for r in selected)))
        n_invalid = sum(r['methods']['B5'].get('trace_validity') != 'VALID' for r in all_records)
        sample = [r for r in all_records if r['reference']['verdict'] != 'NOT_SELECTED']
        quality.append(dict(source=source, executions=len(all_records), invalid=n_invalid,
            unknown_valid=sum(verdict(r['methods']['B5']) == 'INDETERMINATE' and r['methods']['B5'].get('trace_validity') == 'VALID' for r in all_records),
            reference_n=len(sample), reference_labels=dict(Counter(r['reference']['verdict'] for r in sample)),
            incomplete_reference=sum(r['reference'].get('independent_review_complete') is False for r in sample)))
        budget.append(dict(source=source, nominal_executions=len(all_records),
            assigned_scenes_or_records=120 if source == 'allegro' else len(all_records),
            inference_unit='Record clustered within four identities' if source == 'dexgraspbench' else 'Scene within fixed apparatus/family; Fetch seed',
            audited_nominal_steps=sum(r['nominal_physics_steps'] for r in all_records),
            counterfactual_and_probe_steps=sum(r['branch_cost_steps'] for r in all_records),
            B6_solver_wall_s=sum(r['B6'].get('solver_time_s',0.) for r in all_records),
            nominal_observer_off_included=source != 'allegro',
            unmetered_cost='DGB native force tests and two upstream staging phases' if source == 'dexgraspbench' else 'None in physical-step totals; not all wall-clock overhead metered'))
    budget.append(dict(source='U2 future', nominal_executions=720, assigned_scenes_or_records=0,
        inference_unit='Repeated futures in the same 120 scenes; not new independent scenes',
        audited_nominal_steps=0, counterfactual_and_probe_steps=result['utility']['future_physics_steps'], B6_solver_wall_s=0,
        nominal_observer_off_included=False, unmetered_cost='No physical steps for invalid-input futures; these remain INVALID'))
    budget.append(dict(source='Representation pairs', nominal_executions=8, assigned_scenes_or_records=0,
        inference_unit='Paired technical reruns of eight existing controls',
        audited_nominal_steps=sum(r['extra_physics_steps'] for r in properties), counterfactual_and_probe_steps=0,
        B6_solver_wall_s=0, nominal_observer_off_included=False, unmetered_cost='None in physical-step totals'))
    write_csv(OUT/'budget_ledger.csv', budget)
    write_json(OUT/'reports/mechanical_baselines.json', mechanical)
    write_json(OUT/'reports/data_quality.json', quality)
    reference_lines = [r'\begin{table}[h]\centering\small\caption{Mechanical baselines on the preselected branch subset. Valid and feasible/robust are separate counts; no-load truth is not their prediction target.}',
        table('lrrrrr', ['Source','Selected','B6 valid','B6 feasible','B7 valid','B7 robust'],
              [[r[k] for k in ('source','selected','B6_valid','B6_feasible','B7_valid','B7_robust')] for r in mechanical]), r'\end{table}']
    reference_lines += [r'\begin{table}[h]\centering\small\caption{Reference-sample labels and invalid telemetry. Allegro validity counts use 720 candidate executions, not independent scenes.}',
        table('lrrrrrr', ['Source','Executions','Invalid','Ref N','Ref P','Ref F','Ref U'],
              [[r['source'],r['executions'],r['invalid'],r['reference_n']]+[r['reference_labels'].get(k,0) for k in ('PASS','FAIL','INDETERMINATE')] for r in quality]), r'\end{table}']
    reference_lines.append(r'The full confusion matrices, FPR/FNR, conditional error rates, accepted risk, unknown bounds and source-specific denominators are in the machine-readable analysis. For example, no acceptance means accepted risk is NA, not zero; a reference-indeterminate accepted item contributes uncertainty rather than a verified true positive. Binomial Wilson intervals are explicitly conditional-iid summaries, not corrections for shared apparatus or few object identities. The raw reconstruction is code-independent, not simulator-independent.')
    reference_lines.append(r'Invalid Allegro candidate IDs from the geometry-consistency recovery are: '+r'\texttt{'+r'}, \texttt{'.join(r['job_id'] for r in invalid_allegro)+r'}.')
    tex('reference_details', '\n'.join(reference_lines))
    claims = [
        dict(claim_id='C1', statement=f'{prop_nc_flip}/{len(properties)} representation pairs change no-contact while {prop_equal}/{len(properties)} preserve full dynamics',
            contract='No-contact versus no-load', split='formal paired controls', unit='same-scene pair', denominator=8,
            source='controls/properties/summary.json', reference_level='Exact-state equality plus same-simulator raw reconstruction',
            effect='Construct disagreement, not a population effect', interval='Not a population prevalence sample', failure_unknown='0 invalid pairs', scope='Registered inactive-margin apparatus'),
        dict(claim_id='C2', statement='No demonstrated incremental B5 advantage over B4', contract='No-load', split='formal controls', unit='scene within fixed mechanism',
            denominator=240, source='analysis/formal_results.json', reference_level='Independent code, shared simulator',
            effect=h1['effect'], interval=h1['interval975_bonferroni_two_primary'], failure_unknown='77 positive, 163 negative; no invalid control records', scope='Eight apparatus groups; no equivalence claim'),
        dict(claim_id='C3', statement=f'B5 K6 returns {u["B5",6]["usable"]} usable choices; {same_choices} choices identical to B4',
            contract='Independent added 15s future use', split='fresh Allegro test after selection seal', unit='scene decision', denominator=120,
            source='analysis/u2_choices_and_outcomes.csv', reference_level='Independent future endpoint, same simulator', effect=h4['effect'],
            interval=h4['interval975_bonferroni_two_primary'], failure_unknown=f'{len(invalid_allegro)} candidate futures invalid; all abstentions retained',
            scope='Frozen repair pool, hold-last-command environment-removal continuation'),
        dict(claim_id='C4', statement='Source-specific adapter feasibility, not learned-policy or cross-engine generalization', contract='Separate native and added tasks',
            split='formal external', unit='scene/seed; DGB clustered identity', denominator='120 / 100 / 100 separately', source='analysis/formal_results.json',
            reference_level='30 probability raw-code references per source', effect='Source-specific counts', interval='See source/identity summaries',
            failure_unknown=f'Fetch 48 valid indeterminate; DGB {len(invalid_dgb)} invalid; Allegro {len(invalid_allegro)} candidate invalid',
            scope='Three interfaces, one simulator family, four DGB held-out identities'),
        dict(claim_id='C5', statement='No historical excluded scene is rescued by no-load', contract='Full-Q no-load', split='retrospective development', unit='scene', denominator=85,
            source='retrospective/final_adjudication/summary.json', reference_level='177 full replays; 333 common-condition failures', effect='0 rescued / 85',
            interval='Post-hoc complete excluded-scene census, not clean population estimate', failure_unknown='333 candidate wrench histories unmeasured', scope='Declared historical exclusions only')]
    for claim in claims:
        claim.update(protocol_sha256=result['protocol_sha256'], analysis_script_sha256=sha256(ROOT/'scripts/v4/formal_analysis.py'),
                     data_sha256=sha256(OUT/claim['source']))
    write_csv(NOTES/'claim_evidence_ledger.csv', claims)
    write_json(OUT/'reports/publication_facts.json', dict(same_B4_B5_choices=same_choices, differing_NC_B5_choices=no_contact_changed,
        invalid_allegro_jobs=[r['job_id'] for r in invalid_allegro], invalid_dgb_cases=[r['case']['case_id'] for r in invalid_dgb],
        representation_bit_equal=prop_equal, representation_NC_flips=prop_nc_flip, mechanical=mechanical, data_quality=quality,
        claim_ids=[r['claim_id'] for r in claims], source_sha256=sha256(OUT/'analysis/formal_results.json')))
    print(dict(paper_text_generated=True, B4_B5_same_choices=same_choices, invalid_allegro=len(invalid_allegro), invalid_dgb=len(invalid_dgb)))


if __name__ == '__main__':
    run()
