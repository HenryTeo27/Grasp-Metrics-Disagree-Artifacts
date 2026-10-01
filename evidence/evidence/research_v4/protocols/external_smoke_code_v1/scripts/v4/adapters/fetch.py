"""Pinned Fetch controller, natural reset distribution, explicit horizon extension."""
import importlib.util
import sys
import time

import mujoco
import numpy as np

from ..common import OUT, PAPER, output_path, read_json, write_json
from ..contact_observer import CONTACT_COLUMNS, STEP_COLUMNS, ContactRecorder, body_scale
from ..contracts import evaluate
from ..counterfactual import branch_model
from .model_utils import BoxEnvironmentGeometry, model_factory


def source():
    sys.path.insert(0, str(PAPER/'scripts'))
    import external_v3_fetch_audit as old
    spec = importlib.util.spec_from_file_location('v4_frozen_fetch_expert', old.OUT/'upstream/fetch_expert.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old.gym.register_envs(old.gymnasium_robotics)
    return old, module.FetchExpert


def rollout(seed, *, observed=True, control_steps=500, raised_goal=None):
    old, Expert = source()
    protocol = read_json(old.OUT/'protocol.json')
    env = old.gym.make(protocol['environment'], max_episode_steps=control_steps)
    obs, _ = env.reset(seed=seed)
    base = env.unwrapped
    model, data = base.model, base.data
    if raised_goal is not None:
        base.goal[2] = obs['achieved_goal'][2]+raised_goal
    expert = Expert(old.StateAdapter(env))
    expert.reset()
    target = model.body('object0').id
    gid = model.geom('object0').id
    roles = np.zeros(model.nbody, dtype=int)
    for name, role in (('robot0:l_gripper_finger_link', 1), ('robot0:r_gripper_finger_link', 2), ('robot0:gripper_link', 3)):
        roles[model.geom_bodyid[model.geom(name).id]] = role
    start_height = float(obs['achieved_goal'][2])
    initial_contact = any(target in (int(model.geom_bodyid[c.geom1]), int(model.geom_bodyid[c.geom2])) and
                          roles[int(model.geom_bodyid[c.geom2 if int(model.geom_bodyid[c.geom1]) == target else c.geom1])] > 0
                          for c in data.contact)
    geometry = BoxEnvironmentGeometry(model, gid, roles)
    planned = control_steps*base.n_substeps
    time_origin = float(data.time)
    recorder = ContactRecorder(model, target, roles, snapshot_step=round(16/model.opt.timestep)) if observed else None
    original_step = mujoco.mj_step
    index = 0
    q, gaps, raw_geometry, legacy_samples = [], [], [], []

    def step(m, d, nstep=1):
        nonlocal index
        if m is not model or d is not data:
            raise RuntimeError('Unscoped Fetch step callback')
        for _ in range(nstep):
            recorder.before_step(d, index)
            original_step(m, d)
            recorder.after_step(d)
            count, normal = [0, 0], [0., 0.]
            environment_records = 0
            # Read normal loads from the already recorded contact slice; no extra solve.
            start = int(recorder.steps[-1][STEP_COLUMNS.index('contact_start')])
            for row in recorder.contacts[start:]:
                role = int(row[CONTACT_COLUMNS.index('role')])
                if role in (1, 2):
                    count[role-1] += 1
                    normal[role-1] += row[CONTACT_COLUMNS.index('local_fn')]
                if role == 0:
                    environment_records += 1
            lift = float(d.xipos[target, 2]-start_height)
            eligible = lift >= protocol['lift_threshold_m'] and all(count) and min(normal) > protocol['normal_force_floor_N']
            q.append(bool(eligible))
            legacy_samples.append([lift >= protocol['lift_threshold_m'], count[0] > 0, count[1] > 0,
                                   min(normal) > protocol['normal_force_floor_N'], environment_records > 0])
            gap, raw = geometry.sample(d)
            gaps.append(gap)
            raw_geometry.append(raw)
            index += 1

    states, actions, success = [], [], []
    started = time.perf_counter()
    try:
        if observed:
            mujoco.mj_step = step
        for _ in range(control_steps):
            action = expert.act()
            obs, _, terminated, _, info = env.step(action)
            if terminated:
                raise RuntimeError('Unexpected absorbing termination')
            actions.append(action.copy())
            states.append(np.r_[data.qpos, data.qvel, data.ctrl, data.mocap_pos.ravel(), data.mocap_quat.ravel()])
            success.append(bool(info['is_success']))
    finally:
        mujoco.mj_step = original_step
        env.close()
    traces = (np.asarray(states), np.asarray(actions), np.asarray(success))
    if not observed:
        return traces
    arrays = recorder.arrays()
    arrays.update(common_q=np.asarray(q), geometry_gap=np.asarray(gaps), raw_geometry=np.asarray(raw_geometry),
                  control_states=traces[0], actions=traces[1], native_success=traces[2], legacy_samples=np.asarray(legacy_samples))
    metadata = recorder.metadata()
    metadata.update(source='Pinned public Fetch privileged-state expert; unchanged weights and state machine',
                    seed=seed, start_time_s=time_origin, planned_steps=planned, terminal_reason='controller_schedule_completed',
                    global_common=bool(success[-1] and not initial_contact), reference_body_id=model.body('robot0:gripper_link').id,
                    length_scale_m=body_scale(model, gid), geometry=geometry.specification(), initial_object_height_m=start_height,
                    initial_hand_contact=initial_contact, native_horizon_actions=50, native_success_at_50=success[49],
                    native_success_ever_first50=any(success[:50]), extended_final_goal_success=success[-1],
                    native_goal_unchanged=raised_goal is None, raised_goal_m=raised_goal,
                    native_goal=base.goal.tolist(), controller_final_state=dict(phase=expert.phase.name, step_count=expert._phase_step_count),
                    task_contract='Extended 500-action public controller on natural native reset/goal; 15s continuous '
                                  'lift >=4mm, both opposing finger records and each normal force >1e-4N; '
                                  'final extended goal success and no initial hand contact. Not an anatomical Allegro contract.',
                    endpoint_scope='Native 50-action completion reported separately from the added 500-action retention task',
                    elapsed_s=time.perf_counter()-started)
    return arrays, metadata, traces, model_factory(model)


def smoke():
    arrays, metadata, traces, factory = rollout(0, raised_goal=.15)
    plain = rollout(0, observed=False, raised_goal=.15)
    equivalent = all(np.array_equal(a, b) for a, b in zip(traces, plain))
    if not equivalent:
        raise RuntimeError('Observer changed Fetch execution')
    with np.load(PAPER/'evidence/external_v3/rollouts/seed0_raised/trace.npz', allow_pickle=False) as previous:
        original_equal = all(np.array_equal(a, previous[k]) for a, k in zip(traces, ('control_states', 'actions', 'native_success')))
    if not original_equal:
        raise RuntimeError('New adapter differs from the preserved raised-goal smoke')
    result = evaluate(arrays['steps'], metadata['step_columns'], arrays['common_q'], metadata, geometry_gap=arrays['geometry_gap'])
    cf = branch_model(arrays, metadata, factory)
    destination = OUT/'external/fetch/smoke/full_state_retention'
    with output_path(destination.with_suffix('.npz')).open('xb') as handle:
        np.savez_compressed(handle, **arrays)
    record = dict(role='ENGINEERING_SMOKE_ONLY', metadata=metadata, B5=result, counterfactual=cf,
                  observer_bit_equal=equivalent, previous_smoke_bit_equal=original_equal)
    write_json(destination.with_suffix('.json'), record, exclusive=True)
    print(dict(observer_bit_equal=equivalent, previous_smoke_bit_equal=original_equal,
               verdict=result['no_external_load_verdict'], cf=cf.get('cell', cf['status']),
               reason=result['reason_codes'], elapsed_s=metadata['elapsed_s']))


if __name__ == '__main__':
    smoke()
