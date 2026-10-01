"""Generate historical/distribution appendix from preserved inputs only."""
from collections import defaultdict
from pathlib import Path
import csv
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v4.common import OUT, V3, read_csv, read_json, sha256

GEN = ROOT/'paper_v4/generated'


def write(name, text):
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN/(name+'.tex')).write_text(text+'\n', encoding='utf-8')


def span(values, factor=1, decimals=1):
    v = np.asarray(values)*factor
    return f'{v.min():.{decimals}f}--{v.max():.{decimals}f}'


def run():
    old = read_csv(V3/'case_results.csv')
    paired = read_csv(V3/'physics_sensitivity.csv')
    retrospective = read_json(OUT/'retrospective/final_adjudication/summary.json')
    summary = read_json(V3/'analysis.json')
    selected = [r for r in old if r['block'].startswith('new') and r['k'] == '6']
    counts = {policy: {key: sum(r[key] == 'True' for r in selected if r['policy'] == policy)
                        for key in ('legacy_success', 'contiguous_success', 'clear_contiguous_success')}
              for policy in ('baseline', 'repair')}
    assert counts['baseline']['clear_contiguous_success'] == 37 and counts['repair']['clear_contiguous_success'] == 48
    sensitivity = {(r['policy'], r['metric']): r for r in paired}
    churn = sensitivity['repair', 'legacy_success']
    lo, hi = [100*x for x in summary['stratified_bootstrap_clear_delta_95']]
    write('history', rf'''The earlier in-house hand study's 150/150 successes used an explicit assistance
mechanism and are not strict no-stabilizer successes; the locked final strict
evaluation was 0/150. Earlier open-hand validation reached 60/60 on the declared
three-family suites, whereas later frozen blind suites yielded 38/120 and
50/120 for the successive program versions. Those historical splits and
physical settings are not replaced or pooled with the present experiment.

In the preserved V3 compiled-primitive experiment, K6 native, contiguous and
environment-clear counts were {counts['baseline']['legacy_success']},
{counts['baseline']['contiguous_success']}, and {counts['baseline']['clear_contiguous_success']}
for baseline, versus {counts['repair']['legacy_success']},
{counts['repair']['contiguous_success']}, and {counts['repair']['clear_contiguous_success']}
for repair, each over 360 scenes. The 11 clear-support gains were spheres.
Its actual uncertainty calculation was a paired scene bootstrap within six
fixed family strata of 60 scenes, 5,000 draws, seed 2026093040, two-sided 95\%
percentile interval: {lo:.2f}--{hi:.2f} percentage points. Candidates and blocks
were not separately resampled as independent scenes. All paired case keys
were required to exist; no missing-record imputation was used. This historical
analysis differs from the new registered 10,000-draw protocol.

On the same earlier 120 scenes, compiled primitive physics reduced no-contact
success from 18 to 13 for baseline and 24 to 18 for repair. This changes
geometry-dependent bounds and derived quantities as well as inertia, so it is
not an isolated inertia intervention. Repair native totals remained
{churn['old']} versus {churn['compiled']} while {churn['gains']} cases gained and
{churn['losses']} lost success. Equal totals therefore did not mean case-level
stability. A stricter definition is likewise not automatically more accurate
for a different target.

The present development retrospective covers {retrospective['scenes']} excluded
scenes and {retrospective['candidates']} candidate slots. Exactly
{retrospective['replayed']} candidates were fully replayed with wrench telemetry;
{retrospective['common_failure_without_replay']} already failed unchanged common
conditions. The new contract rescues {retrospective['rescued_scene_count']}/{retrospective['scenes']}
scenes. The 333 unmeasured load histories are not claimed to have zero load or
to have independent wrench-reference labels.''')
    registry = read_csv(OUT/'manifests/candidate_registry.csv')
    grouped = defaultdict(dict)
    for row in registry:
        grouped[row['case_id']].setdefault(row['policy'], []).append(row)
    difference = defaultdict(lambda: [0, 0, set(), set(), []])
    for case, policy in grouped.items():
        a = sorted(policy['baseline'], key=lambda r: int(r['rank']))
        b = sorted(policy['repair'], key=lambda r: int(r['rank']))
        fam = a[0]['family']
        difference[fam][0] += 1
        difference[fam][1] += [r['candidate_hash'] for r in a] != [r['candidate_hash'] for r in b]
        difference[fam][2].update(r['candidate_hash'] for r in a)
        difference[fam][3].update(r['candidate_hash'] for r in b)
        difference[fam][4].extend(a+b)
    lines = [r'\begin{table}[h]\centering\small',
             r'\caption{Candidate membership in the historical V3 360-scene pool. Shared/new/dropped refer to distinct complete candidate specifications by family, not new independent program checkpoints.}',
             r'\begin{tabular}{lrrrrl}\toprule Family & Changed scenes & Shared & New & Dropped & Order / runner\\\midrule']
    for family, (n, changed, a, b, rows) in sorted(difference.items()):
        runner = 'fixed / staged' if rows[0]['runner'] == 'staged' else 'nearest XY / hold'
        lines.append(f"{family.replace('_random', '').replace('_', ' ')} & {changed}/{n} & {len(a & b)} & {len(b-a)} & {len(a-b)} & {runner} \\\\")
    lines.extend([r'\bottomrule\end{tabular}\end{table}',
        r'The pool uses six candidates per scene; K=1 and K=3 are prefixes. There are no repeated candidates within a scene/policy prefix. No-extra equals baseline in all 360 scenes, rather than padding its budget with duplicates. The three conditions have 6,480 logical slots and share 2,278 distinct executions. Baseline has 29 complete candidate specifications and repair 35. Non-sphere ordered lists are unchanged; sphere additions alter the nearest-anchor neighborhood.',
        r'Candidate identity contains runner, anchor, derived-control offsets, hold extension and native thresholds. Staged schedules have pre-position, finger ramp/hold, thumb ramp/hold, lift and support phases. Hold schedules retain each anchor\textquotesingle s settling/contact/grip stages and any micro, bridge, cradle or feedback phases, followed by lift, support ramp and hold. Full numerical phase/control arrays are preserved in hash-locked anchor JSONs; no phase is refitted for V4.'])
    write('candidate_table', '\n'.join(lines))
    v3, v4 = read_json(V3/'cases.json'), read_json(OUT/'protocols/final_allegro_cases.json')
    distributions = []
    for label, cases in (('V3', v3), ('V4', v4)):
        for family in sorted({c['family'] for c in cases}):
            group = [c for c in cases if c['family'] == family]
            distributions.append(dict(split=label, family=family, n=len(group),
                mass_g=span([c['object_geom']['mass'] for c in group], 1000, 2),
                s1_mm=span([c['object_geom']['size'][0] for c in group], 1000, 2),
                s2_mm=span([c['object_geom']['size'][1] for c in group], 1000, 2),
                s3_mm=span([c['object_geom']['size'][2] for c in group], 1000, 2),
                x_mm=span([c['object_xyz'][0] for c in group], 1000, 2),
                y_mm=span([c['object_xyz'][1] for c in group], 1000, 2)))
    lines = [r'\begin{table}[h]\centering\small',
        r'\caption{Realized geometry and mass ranges in the actual new V3 360 and V4 120 scene manifests, not substituted from an older 20-case suite. Box sizes are half-extents; curved objects use radius and axial half-length. All lengths below are mm and masses g.}',
        r'\begin{tabular}{llrrrrr}\toprule Split & Family & N & Size 1 & Size 2 & Size 3 & Mass\\\midrule']
    for r in distributions:
        lines.append(f"{r['split']} & {r['family'].replace('_random','').replace('_',' ')} & {r['n']} & {r['s1_mm']} & {r['s2_mm']} & {r['s3_mm']} & {r['mass_g']} \\\\")
    lines.extend([r'\bottomrule\end{tabular}\end{table}',
        r'The two studies use the same parametric family generator with different frozen seeds. V3 seeds are 2026093031--2026093033; V4 uses 2026100202 and records input-selection randomness before scene generation. Sizes and XY positions are drawn uniformly within family-specific ranges, but mass is a deterministic function of sampled size and height is coupled to the geometry: the lowest point starts 20 mm above the floor. Thus these are not independent mass/size/height factors or unseen object categories. Bar XY ranges are $[-2.5,8.5]\times[77,84.5]$ mm; other families use $[-9.5,9.5]\times[75,98.5]$ mm. Yaw is uniform within $\pm0.25$ rad for cubes, $\pm0.18$ for bars and $\pm0.30$ for flat boxes; rotationally symmetric families have zero initial yaw. Contact friction parameters remain $(0.9,0.015,0.004)$.',
        r'For the free-object apparatus, mass is uniform 50--100 g; half-extents are 25--35, 22--29 and 25--35 mm; pad friction is 0.55--0.90. Nominal jaw command is 10--16 mm, with nine deliberately weak hand-only initializations at 3.02--3.15 mm and necessary-floor command fixed at 3.1 mm. Inactive-floor gap is 10--14 mm and the boundary group uses 0.7 times that gap. Every third initialization uses either a lateral offset within $\pm7$ mm or tilt within $\pm0.15$ rad and angular speed within $\pm1$ rad/s. All values and their coupling are listed in the frozen input design.'])
    write('distributions', '\n'.join(lines))
    report = dict(counts=counts, retrospective=retrospective, distribution_rows=distributions,
        source_hashes={str(p.relative_to(ROOT)): sha256(p) for p in (V3/'analysis.json', V3/'case_results.csv', V3/'physics_sensitivity.csv',
                      V3/'cases.json', OUT/'protocols/final_allegro_cases.json', OUT/'manifests/candidate_registry.csv')})
    path = OUT/'reports/historical_appendix.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(dict(historical_counts=counts, distributions=len(distributions)))


if __name__ == '__main__':
    run()
