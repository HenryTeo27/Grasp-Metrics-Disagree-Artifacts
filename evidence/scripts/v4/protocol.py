"""Generate input-only designs and seal the complete G2 contract before outcomes."""
from dataclasses import asdict
from pathlib import Path
import importlib.metadata
import platform
import shutil

import numpy as np

from .common import OUT, PAPER, REPO, V3, fingerprint, output_path, read_json, sha256, utc_now, write_csv, write_json
from .contracts import Calibration

REQUIRED = ('calibration', 'sources', 'seeds', 'sample_sizes', 'unknown_rules', 'branch', 'reference',
            'utility', 'statistics', 'risk_max', 'delta_min', 'cost_limit', 'roles', 'recovery', 'allowed_claims',
            'runtime', 'code_hashes', 'design_hashes', 'qualification')


def validate_protocol(protocol):
    missing = [k for k in REQUIRED if k not in protocol or protocol[k] in (None, {}, [], '')]
    if missing:
        raise ValueError('Incomplete G2 protocol: '+', '.join(missing))
    if not 0 < protocol['risk_max'] < 1 or not 0 < protocol['delta_min'] < 1:
        raise ValueError('Risk and practical difference must be concrete probabilities')
    if protocol['utility']['route'] != 'U2' or protocol['utility']['k_primary'] != 6:
        raise ValueError('Unqualified utility route')
    if protocol['sample_sizes'] != dict(controls=240, allegro_scenes=120, allegro_candidates=720, fetch=100, dexgraspbench=100):
        raise ValueError('Unregistered sample budget')
    if protocol['branch']['horizon_s'] != 3 or not protocol['branch'].get('times'):
        raise ValueError('Missing fixed branch mapping')
    if len(protocol['design_hashes']) != 5:
        raise ValueError('Missing complete input designs')
    Calibration(**protocol['calibration'])


def control_design():
    from .controls import Fixture, MECHANISMS, build
    rng = np.random.default_rng(2026100201)
    old = read_json(OUT/'calibration/free_controls_v1/design.json')['cases']
    seen = {r['physical_signature'] for r in old}
    rows = []
    for j in range(30):
        for i, mechanism in enumerate(MECHANISMS):
            f = Fixture(mechanism=mechanism, seed=62000+j*8+i,
                mass=float(rng.uniform(.05, .10)), half_x=float(rng.uniform(.025, .035)),
                half_y=float(rng.uniform(.022, .029)), half_z=float(rng.uniform(.025, .035)),
                pad_friction=float(rng.uniform(.55, .9)),
                jaw_command=float(rng.uniform(.00302, .00315) if mechanism == 'independent' and j % 10 in (2, 5, 8)
                                  else rng.uniform(.010, .016)), gap_m=float(rng.uniform(.010, .014)),
                target_tilt_rad=float(rng.uniform(-.15, .15)) if j % 3 == 2 else 0.,
                target_offset_y=float(rng.uniform(-.007, .007)) if j % 3 == 1 else 0.,
                initial_angular_speed=float(rng.uniform(-1., 1.)) if j % 3 == 2 else 0.,
                support_schedule='single_burst' if mechanism == 'intermittent_floor' and j >= 15 else 'periodic')
            _, xml = build(f)
            signature = fingerprint(dict(xml=xml, initial_angular_speed=f.initial_angular_speed,
                                         command=f.jaw_command, mechanism=f.mechanism))
            if signature in seen:
                raise RuntimeError('Control initialization overlaps prior evidence')
            seen.add(signature)
            rows.append(dict(case_id=f'final_control_{j*8+i:03d}', physical_signature=signature,
                parameters=asdict(f), counterfactual_selected=j in (0, 5, 10, 15, 20, 25), reference_selected=True,
                representation_selected=mechanism == 'inactive_margin' and j < 8))
    return rows


def allegro_design():
    from .adapters.allegro import frozen
    old = frozen.old
    rng = np.random.default_rng(2026100202)
    seen = {old._signature(c) for c in read_json(V3/'cases.json')}
    for base in (PAPER/'evidence/prospective_v2', PAPER/'evidence/voided_engineering_run_incomplete_anchor_lock'):
        seen.update(old._signature(c) for c in read_json(base/'cases.json'))
    for path in (REPO/'configs/open_hand_hl/menagerie').rglob('*.json'):
        payload = read_json(path)
        if isinstance(payload, dict):
            seen.update(old._signature(c) for c in payload.get('cases', []) if isinstance(c, dict))
    cases, jobs = [], []
    reference = set(rng.choice(120, 30, replace=False).tolist())
    counterfactual = set(rng.choice(120, 20, replace=False).tolist())
    for family in old.DEFAULT_FAMILIES:
        for index in range(20):
            case = old._make_case(family, index, rng)
            signature = old._signature(case)
            if signature in seen:
                raise RuntimeError('Formal scene overlaps old data')
            seen.add(signature)
            number = len(cases)
            case['case_id'] = f'v4_final_{family}_{index:02d}'
            cases.append(dict(family=family, **case))
            candidates = old.candidates(case, family, 'v4_1', None)
            if len(candidates) != 6:
                raise RuntimeError('Unchanged repair pool does not have six candidates')
            for rank, candidate in enumerate(candidates, 1):
                key = fingerprint([case, candidate, 'compiled'])[:20]
                jobs.append(dict(job_id=key, block='v4_final', physics='compiled', case=case, family=family,
                    candidate=candidate, rank=rank, reference_selected=rank == 1 and number in reference,
                    reference_inclusion_probability=.25, counterfactual_selected=rank == 1 and number in counterfactual))
    if len({j['job_id'] for j in jobs}) != 720:
        raise RuntimeError('Duplicate candidate executions in the genuine pool')
    return cases, jobs


def external_design():
    rng = np.random.default_rng(2026100203)
    seeds = rng.choice(np.arange(1000000, 2000000), 100, replace=False)
    cf, ref = set(rng.choice(100, 20, replace=False)), set(rng.choice(100, 30, replace=False))
    fetch = [dict(case_id=f'fetch_final_{i:03d}', seed=int(seed), counterfactual_selected=i in cf,
                  reference_selected=i in ref, reference_inclusion_probability=.3) for i, seed in enumerate(seeds)]
    root = OUT/'external/dexgraspbench/dependency_source'
    groups = sorted((root/'output/example_shadow/graspdata').iterdir())
    if len(groups) != 5:
        raise RuntimeError('Unexpected upstream example-object roster')
    selected = []
    for group in groups[1:]:
        paths = sorted(group.rglob('*.npy'))
        if len(paths) != 80:
            raise RuntimeError('Unexpected grasp roster')
        chosen = sorted(rng.choice(len(paths), 25, replace=False).tolist())
        selected.extend((group.name, paths[i]) for i in chosen)
    cf, ref = set(rng.choice(100, 20, replace=False)), set(rng.choice(100, 30, replace=False))
    dgb = [dict(case_id=f'dgb_final_{i:03d}', object_identity=identity, source_input=p.relative_to(root).as_posix(),
                input_sha256=sha256(p), counterfactual_selected=i in cf, reference_selected=i in ref,
                reference_inclusion_probability=.3) for i, (identity, p) in enumerate(selected)]
    return fetch, dgb


def collect_hashes():
    files = set()
    for path in (PAPER/'scripts/v4').rglob('*.py'):
        files.add(path)
    for path in (PAPER/'tests/v4').rglob('*.py'):
        files.add(path)
    for name in read_json(V3/'protocol.json')['files']:
        files.add(REPO/name)
    files.update(PAPER/'scripts'/name for name in ('external_v3_fetch_audit.py', 'temporal_contract.py'))
    for base in (PAPER/'evidence/external_v3/upstream', PAPER/'evidence/external_v3/deps/gymnasium',
                 PAPER/'evidence/external_v3/deps/gymnasium_robotics'):
        for path in base.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                files.add(path)
    root = OUT/'external/dexgraspbench/dependency_source'
    for directory in ('src', 'config', 'assets/hand', 'assets/example_object', 'third_party/mujoco_menagerie/shadow_hand'):
        for path in (root/directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                files.add(path)
    return {p.relative_to(REPO).as_posix(): sha256(p) for p in sorted(files)}


def freeze():
    destination = OUT/'protocols/protocol_lock.json'
    if destination.exists():
        raise FileExistsError('G2 already exists; never overwrite')
    if any((OUT/'controls/final').rglob('*.json')) or any((OUT/'external').glob('*/final/cases/*.json')):
        raise RuntimeError('Formal outcomes predate the lock')
    if any((OUT/'external/allegro/final').rglob('*.json')):
        raise RuntimeError('Allegro outcomes predate the lock')
    qualified = read_json(OUT/'calibration/unit_test_qualification_preG2_final.json')
    native_fetch = read_json(OUT/'calibration/fetch_native_goal_v1/cases/native_goal_qualification_900001.json')
    adapter_qualification = read_json(OUT/'calibration/formal_adapter_qualification_v1.json')
    if not qualified['passed'] or not adapter_qualification['pass'] or not native_fetch['observer_bit_equal']:
        raise RuntimeError('Formal adapter qualification failed')
    if any(sha256(PAPER/path) != expected for path, expected in qualified['source_hashes'].items()):
        raise RuntimeError('Research source changed since final unit qualification')
    controls = control_design()
    cases, jobs = allegro_design()
    fetch, dgb = external_design()
    designs = {'final_controls.json': controls, 'final_allegro_cases.json': cases, 'final_allegro_jobs.json': jobs,
               'final_fetch.json': fetch, 'final_dexgraspbench.json': dgb}
    for name, content in designs.items():
        write_json(OUT/'protocols'/name, content, exclusive=True)
    protocol = dict(version='merged-v4-G2-1', frozen_utc=utc_now(), outcome_access_before_freeze=False,
        calibration=asdict(Calibration(version='merged-v4-frozen-nominal-20261001')),
        risk_max=.05, delta_min=.05, cost_limit=dict(selector_nominal_physics_ratio=1., max_k=6,
            B7_extra_seconds_per_candidate=6, future_evaluation_seconds_per_candidate=15,
            reason='Auditing must not require extra nominal rollouts; intervention probes and use evaluation are charged separately'),
        sources=dict(allegro='Unchanged repair K6 library, six primitive parameter families; MuJoCo 3.8.0',
            fetch='Pinned native goal/reset/state-machine controller plus separately declared 500-action retention extension; MuJoCo 3.8.0',
            dexgraspbench='Pinned public static Shadow grasp library; four held-out object identities, not learned acquisition; MuJoCo 3.3.2',
            unsupported='robomimic native mujoco-py stack unavailable on this Windows host; external learned-policy objective unsupported'),
        seeds=dict(controls=2026100201, allegro=2026100202, external=2026100203, analysis=2026100101),
        sample_sizes=dict(controls=240, allegro_scenes=120, allegro_candidates=720, fetch=100, dexgraspbench=100),
        design_hashes={name: sha256(OUT/'protocols'/name) for name in designs},
        unknown_rules=dict(verdicts=['PASS', 'FAIL', 'INDETERMINATE'], validity=['VALID', 'INVALID'],
            interpretation='Gray load, unmetered support paths, ambiguous active-zero-load or enclosing-geometry overlap remain unknown; '
                           'invalid is separate and not physical failure. All unknown/invalid/abstentions stay in assigned denominators.',
            missing_or_conflicting_reference='INDETERMINATE, never forced to a label'),
        branch=dict(horizon_s=3., endpoint=dict(relative_displacement_m=.03, rotation_rad=.35, relative_speed_m_s=.2),
            times=dict(controls='8s', allegro='planned schedule end minus 4s', fetch='16s after rollout start',
                       dexgraspbench='2s after added gravity-on boundary'),
            intervention='Remove only target-environment collision permission, preserving all other pairs, controls, mocap, gravity and full integration state',
            continuation='Recorded open-loop tape, not recovered closed-loop policy',
            counts=dict(controls=48, allegro=20, fetch=20, dexgraspbench=20),
            missing='UNREACHABLE/INVALID remains at registered index; no outcome-dependent replacements',
            dependency_predictor='STOP: natural development force threshold already separated 20 biased cases; no new predictor superiority claim'),
        reference=dict(controls='All 240 raw wrench/vertex/interval reconstructions',
            natural='Simple random sample of 30 rank-1 Allegro scenes and 30 entries per other source, probabilities recorded',
            diagnostic_max_per_source=10, diagnostic_role='Separate exploratory convenience sample, never pooled into prevalence',
            independence='Separate code implementation using raw local contact wrenches, geometry and timestamps; shared simulator and task definitions',
            human_annotation=False, blind_annotators=0, access='Single-agent execution; no independent human or agent blinding claimed'),
        roles=dict(controls='two pads HAND; plane/opposing supports ENV', allegro='thumb, long fingers and palm HAND; floor ENV',
                   fetch='two fingers and gripper palm HAND; other links, table, floor ENV',
                   dexgraspbench='Shadow hand subtree HAND, compound object TARGET; no environmental collision geoms'),
        utility=dict(route='U2', pool='Unmodified V4.1 repair ordered six candidates', k_primary=6, k_secondary=[1, 3],
            selector_methods=['B0', 'B1', 'B2', 'B3', 'B4', 'B4_normal', 'B5'],
            selection='First PASS else abstain; all K full schedules used and charged equally; seal before future outcomes',
            Y_use='Additional 15s hold-last-command continuation after removing target-environment permissions; all-sample '
                  'palm-relative displacement <=.03m, angle <=.35rad, speed <=.2m/s; never reads auditor outputs',
            future_all_candidates=True, transport_endpoint=False,
            U1='STOP: two genuine programs, all development scores promote repair; no fabricated checkpoints'),
        statistics=dict(primary_H1='B5 minus B4 correct accepted/assigned controls, empirical accepted risk <=.05; '
                                   'no low-risk population certificate unless risk uncertainty also supports it',
            primary_H4='B5 minus B4 usable selected/assigned Allegro scenes at K6; abstention remains failure to provide a usable selection',
            intervals='Paired scene bootstrap within fixed mechanism/family strata, 10000 draws, seed 2026100101',
            multiplicity='97.5% two-sided Bonferroni intervals for two confirmatory comparisons; 95% descriptive elsewhere',
            additional='FPR/FNR, conditional rates, conservative unknown bounds, accepted risk NA if no acceptance; source/task separate',
            clustering='Scene is unit for Allegro, control initialization within mechanism, Fetch seed; DGB clustered by four object identities',
            power='Fixed resource budget, not powered to establish 5% gains: worst-case iid 95% rate margins about 6.3pp at N240, '
                  '8.9pp at N120, 9.8pp at N100; dependence and few identities widen uncertainty. No post-outcome sample extension.',
            zero_difference='No observed gain is not equivalence; no equivalence claim or tolerance is registered'),
        secondary_designs=dict(controls_operating_curves=dict(grid=[[1e-6, 1e-4], [1e-5, 1e-3], [1e-4, 1e-2], [1e-3, .1], [.01, 1.]],
                target='Fixed nominal raw-evidence reference; both normalized force and torque change together; no test-based selection'),
            representation='First eight inactive-margin controls, remove only margin/gap and require complete integration bit equality',
            temporal='Thirty intermittent controls: first fifteen periodic, last fifteen one 0.1s support burst at 8s',
            coordinate='Legal rigid re-expression checked by offline unit tests only; not extra physical rollout evidence'),
        runtime=dict(default=dict(python=platform.python_version(), numpy=np.__version__, mujoco='3.8.0', scipy=importlib.metadata.version('scipy')),
                     dexgraspbench=dict(python='3.11.1', numpy='1.26.4', mujoco='3.3.2', scipy='1.17.1')),
        recovery='Resume only untouched inputs and exact code; completed records hash-verified. Orphan/failed attempts retained and reported. '
                 'Any semantic code/protocol/data/physics change voids confirmation and requires a deviation record; no quiet lock replacement.',
        allowed_claims=['Contract-specific measurement reliability within registered apparatus and task definitions',
                        'Short-horizon intervention-conditioned dependence distinct from historical no-load/no-contact',
                        'Conditional utility only if frozen paired outcomes and uncertainty support it'],
        prohibited_claims=['General dexterous grasping solved', 'New temporal logic, force closure or evaluator selection principle',
                           'Cross-engine or sim-to-real validation', 'DGB learned tabletop acquisition', 'Independent human ground truth'],
        qualification=dict(unit_test_report_sha256=sha256(OUT/'calibration/unit_test_qualification_preG2_final.json'),
            adapter_qualification_sha256=sha256(OUT/'calibration/formal_adapter_qualification_v1.json'),
            observer_full_state_calibration='80/80 bit-exact; source-specific qualifications also recorded',
            development_baseline='B4 and B5 tied; no positive additional-geometry claim assumed'),
        code_hashes=collect_hashes())
    validate_protocol(protocol)
    write_json(destination, protocol, exclusive=True)
    for path, expected in protocol['code_hashes'].items():
        if path.startswith('merged-hl-grasping-paper/scripts/v4/') or path.startswith('merged-hl-grasping-paper/tests/v4/'):
            target = output_path(OUT/'protocols/frozen_code'/path)
            shutil.copy2(REPO/path, target)
            if sha256(target) != expected:
                raise RuntimeError('Source snapshot failed')
    write_json(OUT/'protocols/calibration.json', protocol['calibration'], exclusive=True)
    write_json(OUT/'protocols/baseline_registry.json', dict(
        B0='Actual native gate for Allegro; accumulated common-Q proxy on added tasks, with native results separate',
        B1='Continuous common-Q', B2='Continuous no generated environment-contact records',
        B3='Positive geometric clearance and common-Q', B4='Same full per-contact wrench/temporal/unknown logic as B5, without geometry',
        B4_normal='Environment normal load, no torque, same passive meter',
        B5='Common-Q, geometric guard, full wrench and metered passive load, unknowns and integrity',
        B6='Eight-ray friction-cone static feasibility with bounded actuator balance, on fixed CF subset; not historical no-load truth',
        B7='Six signed one-weight world-axis one-second force probes with gravity retained, on fixed CF subset; additional steps charged',
        ablations=['no geometry', 'no torque', 'net rather than per-contact aggregation', 'binary unknown failure', 'accumulated rather than contiguous']), exclusive=True)
    write_csv(OUT/'protocols/mechanism_registry.csv', [dict(mechanism=m, count=30, calibration_count=10,
        scope='Fixed apparatus group, not independent physical mechanism population') for m in sorted({r['parameters']['mechanism'] for r in controls})])
    return dict(status='G2_FROZEN', sha256=sha256(destination), counts=protocol['sample_sizes'], files=len(protocol['code_hashes']))


def verify_lock(runtime='default', check_runtime=True):
    protocol = read_json(OUT/'protocols/protocol_lock.json')
    validate_protocol(protocol)
    failures = []
    for path, expected in protocol['code_hashes'].items():
        if not (REPO/path).is_file() or sha256(REPO/path) != expected:
            failures.append(path)
    for name, expected in protocol['design_hashes'].items():
        if sha256(OUT/'protocols'/name) != expected:
            failures.append(name)
    if failures:
        raise RuntimeError('G2 frozen inputs changed: '+repr(failures[:20]))
    if check_runtime:
        key = 'dexgraspbench' if runtime == 'dexgraspbench' else 'default'
        expected = protocol['runtime'][key]
        actual = dict(python=platform.python_version(), numpy=np.__version__,
                      mujoco=importlib.metadata.version('mujoco'), scipy=importlib.metadata.version('scipy'))
        if actual != expected:
            raise RuntimeError(f'Wrong runtime: {actual} != {expected}')
    return protocol


if __name__ == '__main__':
    print(freeze())
