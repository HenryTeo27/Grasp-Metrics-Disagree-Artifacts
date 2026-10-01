"""Bounded native-example smoke. No retuning and no formal external outcomes."""
from contextlib import contextmanager
import importlib.metadata
import os
from pathlib import Path
import sys
import time

import mujoco
import numpy as np
from omegaconf import OmegaConf

from .common import OUT, sha256, write_json
from .contact_observer import ContactRecorder


@contextmanager
def in_directory(path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def native_smoke():
    root = OUT / 'external/dexgraspbench/dependency_source'
    sys.path.insert(0, str(root / 'src'))
    from task.eval_func.fc_mocap import fcMocapEval
    inputs = sorted((root / 'output/example_shadow/graspdata').rglob('*.npy'))
    selected = inputs[0]
    records, outcomes, samples = [], [], []
    started = time.perf_counter()
    with in_directory(root):
        config = OmegaConf.create(dict(setting='fc', hand=OmegaConf.load('config/hand/shadow.yaml'),
                                       task=OmegaConf.load('config/task/eval.yaml')))
        for observed in (False, True):
            task = fcMocapEval(str(selected), config)
            runtime = task.mj_ho
            trace, observer_list = [], []
            counter = [0]
            original_reset = runtime.reset_pose_qpos
            original_step = runtime.control_hand_step
            active = [None]
            roles = np.ones(runtime.model.nbody, dtype=int)*2
            roles[0] = 0
            for b in range(runtime.model.nbody):
                if 'rh_th' in (mujoco.mj_id2name(runtime.model, mujoco.mjtObj.mjOBJ_BODY, b) or ''):
                    roles[b] = 1

            def reset(*args, **kwargs):
                original_reset(*args, **kwargs)
                counter[0] = 0
                if observed:
                    active[0] = ContactRecorder(runtime.model, runtime.model.body('object').id, roles)
                    observer_list.append(active[0])

            def step(step_inner):
                # Delegate one physical step to the unchanged upstream routine.
                for _ in range(step_inner):
                    if observed:
                        active[0].before_step(runtime.data, counter[0])
                    original_step(1)
                    if observed:
                        active[0].after_step(runtime.data)
                    trace.append(np.r_[runtime.data.time, runtime.data.qpos.copy(), runtime.data.qvel.copy()])
                    counter[0] += 1

            runtime.reset_pose_qpos = reset
            runtime.control_hand_step = step
            outcome = task._eval_simulate_under_extforce()
            outcomes.append([bool(outcome[0]), float(outcome[1]), float(outcome[2])])
            samples.append(np.asarray(trace))
            records.extend(observer.metadata() for observer in observer_list if observer.steps)
    equivalent = np.array_equal(samples[0], samples[1]) and outcomes[0] == outcomes[1]
    result = dict(role='engineering_smoke_only', input=str(selected.relative_to(root)),
                  input_sha256=sha256(selected), candidate_choice='lexicographically first before outcomes',
                  source='Public static pregrasp/grasp/squeeze trajectory, not learned acquisition policy',
                  native_task='Upstream six signed external-force tests, gravity disabled; original early stop and reset semantics',
                  native_outcomes=outcomes, observer_bit_equal=bool(equivalent),
                  physics_steps=len(samples[0]), recorded_segments=len(records),
                  geometry_clock_max_error=max((r['geometry_clock_max_error'] for r in records), default=None),
                  elapsed_s=time.perf_counter()-started,
                  versions={p: importlib.metadata.version(p) for p in ('mujoco', 'numpy', 'torch', 'scipy', 'trimesh')},
                  independence='Upstream native implementation executed twice; not reproduction of a published aggregate score')
    write_json(OUT / 'external/dexgraspbench/smoke/native_example.json', result, exclusive=True)
    print(result)
    if not equivalent or not len(samples[0]):
        raise RuntimeError('Native smoke failed observer qualification')


if __name__ == '__main__':
    native_smoke()
