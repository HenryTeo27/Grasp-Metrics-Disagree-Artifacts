"""Fixed-pool acceptance rules, development route audit and independent uses."""
from collections import defaultdict
import json

import numpy as np

from .common import OUT, V3, fingerprint, read_csv, read_json, write_csv, write_json, yes


def accept_first(ordered_ids, results, key, k):
    if k not in (1, 3, 6):
        raise ValueError('Only registered K prefixes are supported')
    for identifier in ordered_ids[:k]:
        if results[identifier][key] == 'PASS':
            return identifier
    return None


def development_route_audit():
    cases = [r for r in read_csv(V3/'case_results.csv') if r['block'].startswith('new') and r['k'] == '6']
    versions = []
    for policy in ('baseline', 'repair'):
        rows = [r for r in cases if r['policy'] == policy]
        versions.append(dict(version=policy, scenes=len(rows), native=sum(yes(r['legacy_success']) for r in rows),
                             contiguous=sum(yes(r['contiguous_success']) for r in rows), nc=sum(yes(r['clear_contiguous_success']) for r in rows)))
    chosen = {metric: max(versions, key=lambda r: r[metric])['version'] for metric in ('native', 'contiguous', 'nc')}
    members = [m for m in read_json(V3/'membership.json') if m['block'].startswith('new') and m['policy'] == 'repair']
    grouped = defaultdict(list)
    for m in members:
        grouped[m['case_id']].append(m)
    selections = []
    for case_id, group in sorted(grouped.items()):
        ordered = sorted(group, key=lambda m: m['rank'])
        ids = [m['job_id'] for m in ordered]
        results = {}
        for jid in ids:
            r = read_json(V3/'trials'/(jid+'.json'))
            results[jid] = dict(native='PASS' if r['legacy_success'] else 'FAIL',
                                nc='PASS' if r['temporal']['clear_contiguous_success'] else 'FAIL')
        selections.append(dict(case_id=case_id, family=ordered[0]['family'],
                               native_choice=accept_first(ids, results, 'native', 6),
                               nc_choice=accept_first(ids, results, 'nc', 6), ordered_candidates=ids))
    result = dict(role='DEVELOPMENT_ONLY_OLD_360', real_compatible_versions=versions,
                  excluded_pseudo_version='No-extra is identical to baseline, not a third independent checkpoint',
                  U1=dict(chosen=chosen, enabled=False, reason='All available historical scoring contracts promote repair; no ranking divergence in the genuine two-version pool'),
                  U2=dict(enabled=True, pool='Unmodified V4.1 repair ordered K=6 library; K=1/3 are prefixes',
                          native_accepted=sum(r['native_choice'] is not None for r in selections),
                          nc_accepted=sum(r['nc_choice'] is not None for r in selections),
                          differing_decisions=sum(r['native_choice'] != r['nc_choice'] for r in selections),
                          decision='Use U2 as the sole utility route; independent future test not yet observed',
                          caveat='This establishes a nondegenerate acceptance space, not B5 superiority. B4 and B5 are tied in all existing comparisons.'),
                  primary_utility='Additional 15s hold-last-command retention after removing target-environment permissions; '
                                  'pose relative to palm <=3cm, rotation <=.35rad, speed <=.2m/s for entire interval. '
                                  'Future endpoint does not read any auditor verdict. This is an added intervention-conditioned use, not native policy success.',
                  accounting='Selection observes identical K full schedules. Future evaluation cost is separate. '
                             'B7 active probes are not admitted as cost-free U2 selectors.')
    write_json(OUT/'calibration/utility_route_pilot.json', result, exclusive=True)
    write_csv(OUT/'calibration/utility_route_choices.csv', selections)
    print(json.dumps(result), flush=True)
    return result


def future_retention(final_state, flag, metadata, factory, *, hold_s=15.):
    import mujoco
    from .counterfactual import _relative_pose, endpoint, remove_target_environment
    model = factory()
    target = metadata['target_body']
    intervention = remove_target_environment(model, target, metadata['body_roles'])
    data, scratch = mujoco.MjData(model), mujoco.MjData(model)
    mujoco.mj_setState(model, data, final_state, mujoco.mjtState(flag))
    restored = np.empty_like(final_state)
    mujoco.mj_getState(model, data, restored, mujoco.mjtState(flag))
    if not np.array_equal(restored, final_state):
        raise RuntimeError('Y_use integration state restoration mismatch')
    if np.any(data.xfrc_applied) or np.any(data.qfrc_applied):
        return dict(status='INVALID', reason='UNEXPECTED_INITIAL_APPLIED_FORCE')
    ref = metadata['reference_body_id']
    initial = _relative_pose(model, data, scratch, target, ref)
    dt = model.opt.timestep
    count = round(hold_s/dt)
    poses = []
    # Explicit new continuation: fixed final actuator commands and mocap, no hidden controller.
    for _ in range(count):
        mujoco.mj_step(model, data)
        poses.append(_relative_pose(model, data, scratch, target, ref))
    poses = np.asarray(poses)
    speed = np.diff(np.vstack([initial[:3], poses[:, :3]]), axis=0)/dt
    result = endpoint(poses, speed, initial)
    return dict(status='VALID', result=result, hold_s=hold_s, physics_steps=count,
                intervention=intervention, endpoint='Independent all-sample palm-relative displacement/angle/speed bounds',
                continuation='Fixed final actuator commands and mocap; target initial state is copied only at explicit branch reset')


if __name__ == '__main__':
    development_route_audit()
