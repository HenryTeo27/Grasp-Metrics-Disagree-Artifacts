"""Added gravity-retention task, separate from the unchanged native DGB test."""
from pathlib import Path
import sys
import time

import mujoco
import numpy as np
from omegaconf import OmegaConf

from ..common import OUT, output_path, sha256, write_json
from ..contact_observer import ContactRecorder
from ..contracts import evaluate
from ..counterfactual import _relative_pose, branch_model
from ..dexgraspbench_smoke import in_directory
from .model_utils import model_factory, object_bounds

ROOT = OUT/'external/dexgraspbench/dependency_source'


def setup(selected):
    sys.path.insert(0, str(ROOT/'src'))
    from task.eval_func.fc_mocap import fcMocapEval
    config = OmegaConf.create(dict(setting='fc', hand=OmegaConf.load(ROOT/'config/hand/shadow.yaml'),
                                   task=OmegaConf.load(ROOT/'config/task/eval.yaml')))
    return fcMocapEval(str(selected), config)


def added_retention(selected, *, observed=True, duration_s=18.):
    started = time.perf_counter()
    with in_directory(ROOT):
        task = setup(selected)
        runtime = task.mj_ho
        grasp = task.grasp_data
        runtime.reset_pose_qpos(grasp['pregrasp_qpos'], grasp['obj_pose'])
        runtime.control_hand_with_interp(grasp['pregrasp_qpos'], grasp['grasp_qpos'])
        runtime.control_hand_with_interp(grasp['grasp_qpos'], grasp['squeeze_qpos'])
        model, data = runtime.model, runtime.data
        closure_time = float(data.time)
        # The upstream closure is unchanged. Gravity on defines the new task boundary.
        model.opt.disableflags &= ~int(mujoco.mjtDisableBit.mjDSBL_GRAVITY)
        if np.any(data.xfrc_applied) or np.any(data.qfrc_applied):
            raise ValueError('Unexpected upstream assistance')
        target = model.body('object').id
        qa = int(model.jnt_qposadr[model.body_jntadr[target]])
        va = int(model.jnt_dofadr[model.body_jntadr[target]])
        roles = np.zeros(model.nbody, dtype=int)
        for b in range(1, model.nbody):
            name = model.body(b).name
            if name.startswith('child-'):
                roles[b] = 1 if 'rh_th' in name else 2
        reference = model.body('child-rh_palm').id
        roles[reference] = 3
        target_geoms = set(np.flatnonzero(model.geom_bodyid == target).tolist())
        environmental = [g for g in range(model.ngeom) if g not in target_geoms and
                         roles[model.geom_bodyid[g]] == 0 and (model.geom_contype[g] or model.geom_conaffinity[g])]
        if environmental or model.npair:
            raise ValueError('This task adapter requires the native environment-free FC model')
        scratch = mujoco.MjData(model)
        initial = _relative_pose(model, data, scratch, target, reference)
        planned = round(duration_s/model.opt.timestep)
        recorder = ContactRecorder(model, target, roles, snapshot_step=round(2/model.opt.timestep)) if observed else None
        q, pose_trace, states = [], [], []
        for step in range(planned):
            if recorder:
                relative = _relative_pose(model, data, scratch, target, reference)
                velocity = data.qvel[va:va+3].copy()
                recorder.before_step(data, step)
            runtime.control_hand_step(1)
            if recorder:
                recorder.after_step(data)
                hand_contact = any(target in (int(model.geom_bodyid[c.geom1]), int(model.geom_bodyid[c.geom2]))
                                   and c.efc_address >= 0 for c in data.contact)
                angle = 2*np.arccos(np.clip(abs(relative[3:]@initial[3:]), 0., 1.))
                q.append(bool(step*model.opt.timestep >= .5 and np.linalg.norm(relative[:3]-initial[:3]) <= .03
                              and angle <= .35 and np.linalg.norm(velocity) <= .2 and hand_contact))
                pose_trace.append(relative)
            states.append(np.r_[data.qpos, data.qvel, data.actuator_force])
        if not observed:
            return np.asarray(states)
        arrays = recorder.arrays()
        arrays.update(common_q=np.asarray(q), relative_pose=np.asarray(pose_trace),
                      geometry_gap=np.full(planned, 1e10))
        bounds = object_bounds(model, target)
        metadata = recorder.metadata()
        metadata.update(start_time_s=closure_time, planned_steps=planned, global_common=True, branch_prefix_ok=True,
                        terminal_reason='controller_schedule_completed', reference_body_id=reference,
                        target_qadr=qa, target_vadr=va, length_scale_m=bounds['length_scale_m'],
                        object_bounds=bounds, reference_initial_pose=initial.tolist(),
                        source_input=str(Path(selected).relative_to(ROOT)), input_sha256=sha256(selected),
                        environment_geometry='No environmental collision geoms or explicit pairs in the native FC model; clearance sentinel 1e10',
                        source='DGB static pregrasp/grasp/squeeze example, not a learned acquisition controller',
                        task_contract='Added 18s gravity-on continuation after unchanged .8s gravity-off staged closure; '
                                      'fixed squeeze commands/mocap, 15 contiguous seconds with hand contact, relative displacement <=.03m, '
                                      'rotation <=.35rad, world speed <=.2m/s after .5s settling',
                        native_result_not_used=True, gravity_disableflag=int(model.opt.disableflags),
                        elapsed_s=time.perf_counter()-started, mujoco_version=mujoco.__version__)
        return arrays, metadata, np.asarray(states), model_factory(model)


def smoke():
    selected = sorted((ROOT/'output/example_shadow/graspdata').rglob('*.npy'))[0]
    arrays, metadata, trace, factory = added_retention(selected)
    plain = added_retention(selected, observed=False)
    equivalent = bool(np.array_equal(trace, plain))
    if not equivalent:
        raise RuntimeError('Added task observer changed trajectory')
    result = evaluate(arrays['steps'], metadata['step_columns'], arrays['common_q'], metadata,
                      geometry_gap=arrays['geometry_gap'])
    cf = branch_model(arrays, metadata, factory)
    destination = OUT/'external/dexgraspbench/smoke/added_gravity_retention'
    with output_path(destination.with_suffix('.npz')).open('xb') as handle:
        np.savez_compressed(handle, **arrays)
    record = dict(role='ENGINEERING_SMOKE_ONLY', metadata=metadata, B5=result, counterfactual=cf,
                  observer_bit_equal=equivalent, native_and_added_not_pooled=True)
    write_json(destination.with_suffix('.json'), record, exclusive=True)
    print(dict(observer_bit_equal=equivalent, verdict=result['no_external_load_verdict'],
               cf=cf.get('cell', cf['status']), elapsed_s=metadata['elapsed_s'], bounds=metadata['object_bounds']))


if __name__ == '__main__':
    smoke()
